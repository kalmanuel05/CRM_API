from __future__ import annotations

import os
import time
from pathlib import Path


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")


_load_dotenv()
from typing import Annotated

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.api_description import API_DESCRIPTION
from app.auth_deps import AuthContext, enforce_rate_limit, max_batch_for_tier
from app.cleaning import process_batch
from app.config import env_flag, get_diagnostics_secret, get_http_limits, get_settings
from app.crm_formats import format_rows
from app.csv_utils import csv_bytes_from_dicts, dicts_from_csv
from app.error_monitor import recent_errors_snapshot
from app.errors import raise_api_error, register_exception_handlers
from app.merge_recommendations import build_merge_recommendations
from app.models import CleanBatchRequest, CleanBatchResponse, ExportFormat, HealthResponse, UsageInfo
from app.rate_limit import state as rate_limit_state
from app.summary import build_summary_stats
from app.tiers import TIER_LIMITS
from app.usage_log import log_usage, new_request_id

app = FastAPI(
    title="CRM Data Cleaner API",
    description=API_DESCRIPTION,
    version="2.0.0",
    openapi_tags=[
        {"name": "health", "description": "Public liveness check."},
        {"name": "clean", "description": "Normalize, dedupe hints, and CRM export."},
        {"name": "diagnostics", "description": "Optional operational helpers (secret-gated)."},
    ],
)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_and_body_limits(request: Request, call_next):
    """Assign request id (for logs and error bodies) and reject oversized bodies before read."""
    rid = new_request_id()
    request.state.request_id = rid

    limits = get_http_limits()
    path = request.url.path
    cl = request.headers.get("content-length")
    if cl and cl.isdigit():
        n = int(cl)
        if path == "/v1/clean" and n > limits.max_json_body_bytes:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={
                    "error": {
                        "code": "PAYLOAD_TOO_LARGE",
                        "message": (
                            f"JSON body exceeds maximum of {limits.max_json_body_bytes} bytes "
                            f"(Content-Length: {n})."
                        ),
                        "request_id": rid,
                    }
                },
                headers={"X-Request-Id": rid},
            )
        if path == "/v1/clean/csv" and n > limits.max_csv_upload_bytes:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={
                    "error": {
                        "code": "CSV_TOO_LARGE",
                        "message": (
                            f"CSV upload exceeds maximum of {limits.max_csv_upload_bytes} bytes "
                            f"(Content-Length: {n})."
                        ),
                        "request_id": rid,
                    }
                },
                headers={"X-Request-Id": rid},
            )

    response = await call_next(request)
    response.headers["X-Request-Id"] = rid
    return response


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or new_request_id()


def _parse_export_format(raw: str) -> ExportFormat:
    v = (raw or "generic").strip().lower()
    if v in ("generic", "hubspot", "salesforce", "zoho"):
        return v  # type: ignore[return-value]
    raise_api_error(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "INVALID_EXPORT_FORMAT",
        "export_format must be one of: generic, hubspot, salesforce, zoho.",
    )


def _validate_batch_size(n: int, auth: AuthContext) -> None:
    cap = max_batch_for_tier(auth.tier)
    if n > cap:
        raise_api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "BATCH_TOO_LARGE",
            f"Batch has {n} records; tier {auth.tier.value} allows at most {cap} per request.",
        )


def _detail_message(detail: str | dict | list) -> str:
    if isinstance(detail, dict) and "message" in detail:
        return str(detail["message"])
    if isinstance(detail, str):
        return detail
    return str(detail)


def _build_response(
    *,
    cleaned,
    warnings,
    duplicate_groups,
    export_format: ExportFormat,
    auth: AuthContext,
    request_id: str,
) -> CleanBatchResponse:
    crm_rows, _ = format_rows(cleaned, export_format)
    merge_recs = build_merge_recommendations(cleaned, duplicate_groups)
    summary = build_summary_stats(cleaned, warnings, duplicate_groups)
    limits = TIER_LIMITS[auth.tier]
    used = rate_limit_state.monthly_used(auth.api_key)
    usage = UsageInfo(
        request_id=request_id,
        tier=auth.tier.value,
        monthly_quota=limits.requests_per_month,
        monthly_used=used,
        rate_limit_per_minute=limits.requests_per_minute,
        max_batch_records=limits.max_batch_records,
    )
    return CleanBatchResponse(
        cleaned_records=cleaned,
        warnings=warnings,
        duplicate_groups=duplicate_groups,
        merge_recommendations=merge_recs,
        summary=summary,
        crm_import_rows=crm_rows,
        usage=usage,
    )


def _finalize_log(
    *,
    request: Request,
    auth: AuthContext,
    endpoint: str,
    status_code: int,
    record_count: int | None,
    t0: float,
    error: str | None,
) -> None:
    _, _, log_path = get_settings()
    log_usage(
        log_path=log_path,
        request_id=_request_id(request),
        api_key_fingerprint=auth.fingerprint,
        tier=auth.tier,
        endpoint=endpoint,
        method=request.method,
        status_code=status_code,
        record_count=record_count,
        duration_ms=(time.perf_counter() - t0) * 1000.0,
        error=error,
    )


_diag_secret = get_diagnostics_secret()
if _diag_secret:

    @app.get(
        "/v1/diagnostics/recent-errors",
        tags=["diagnostics"],
        include_in_schema=env_flag("CRM_DIAGNOSTICS_OPENAPI", default=False),
    )
    def diagnostics_recent_errors(
        x_diagnostics_secret: Annotated[str | None, Header(alias="X-Diagnostics-Secret")] = None,
    ) -> dict:
        """
        Returns the last ~100 unhandled errors held in memory (ring buffer), newest first.
        Set `CRM_DIAGNOSTICS_SECRET` on the server and send the same value in `X-Diagnostics-Secret`.
        """
        if x_diagnostics_secret != _diag_secret:
            raise_api_error(
                status.HTTP_401_UNAUTHORIZED,
                "DIAGNOSTICS_UNAUTHORIZED",
                "Invalid or missing diagnostics secret.",
            )
        return {"errors": recent_errors_snapshot(50)}


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/v1/clean", response_model=CleanBatchResponse, tags=["clean"])
async def clean_batch(
    request: Request,
    body: CleanBatchRequest,
    auth: Annotated[AuthContext, Depends(enforce_rate_limit)],
) -> CleanBatchResponse:
    t0 = time.perf_counter()
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    err: str | None = None
    nrec: int | None = None
    try:
        _validate_batch_size(len(body.records), auth)
        cleaned, warnings, dups = process_batch(body.records, body.default_phone_region)
        nrec = len(body.records)
        status_code = status.HTTP_200_OK
        return _build_response(
            cleaned=cleaned,
            warnings=warnings,
            duplicate_groups=dups,
            export_format=body.export_format,
            auth=auth,
            request_id=_request_id(request),
        )
    except HTTPException as e:
        status_code = int(e.status_code)
        err = _detail_message(e.detail)  # type: ignore[arg-type]
        raise
    finally:
        _finalize_log(
            request=request,
            auth=auth,
            endpoint="/v1/clean",
            status_code=status_code,
            record_count=nrec,
            t0=t0,
            error=err,
        )


@app.post("/v1/clean/csv", tags=["clean"])
async def clean_batch_csv(
    request: Request,
    auth: Annotated[AuthContext, Depends(enforce_rate_limit)],
    file: UploadFile = File(..., description="UTF-8 CSV with a header row."),
    default_phone_region: str = Form("US"),
    export_format: str = Form("generic"),
    download: bool = Query(False, description="If true, response is a CSV file attachment."),
):
    t0 = time.perf_counter()
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    err: str | None = None
    nrec: int | None = None
    limits = get_http_limits()
    try:
        raw = await file.read()
        if not raw:
            raise_api_error(status.HTTP_400_BAD_REQUEST, "EMPTY_CSV", "Empty CSV file.")
        if len(raw) > limits.max_csv_upload_bytes:
            raise_api_error(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                "CSV_TOO_LARGE",
                f"CSV upload exceeds maximum of {limits.max_csv_upload_bytes} bytes after read.",
            )
        rows = dicts_from_csv(raw)
        _validate_batch_size(len(rows), auth)
        fmt = _parse_export_format(export_format)
        cleaned, warnings, dups = process_batch(rows, default_phone_region)
        nrec = len(rows)
        status_code = status.HTTP_200_OK
        resp_model = _build_response(
            cleaned=cleaned,
            warnings=warnings,
            duplicate_groups=dups,
            export_format=fmt,
            auth=auth,
            request_id=_request_id(request),
        )
        if download:
            crm_rows, fieldnames = format_rows(cleaned, fmt)
            payload = csv_bytes_from_dicts(crm_rows, fieldnames)
            return Response(
                content=payload,
                media_type="text/csv; charset=utf-8",
                headers={
                    "Content-Disposition": 'attachment; filename="cleaned_export.csv"',
                    "X-Request-Id": _request_id(request),
                },
            )
        return resp_model
    except HTTPException as e:
        status_code = int(e.status_code)
        err = _detail_message(e.detail)  # type: ignore[arg-type]
        raise
    finally:
        _finalize_log(
            request=request,
            auth=auth,
            endpoint="/v1/clean/csv",
            status_code=status_code,
            record_count=nrec,
            t0=t0,
            error=err,
        )
