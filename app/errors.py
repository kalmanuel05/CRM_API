from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError


def raise_api_error(status_code: int, code: str, message: str) -> None:
    """Raise HTTPException with structured detail (request_id is added by exception handlers)."""
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _error_body(code: str, message: str, request_id: str | None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


def register_exception_handlers(app) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        rid = _request_id(request)
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            body = _error_body(str(detail["code"]), str(detail["message"]), rid)
        else:
            msg = detail if isinstance(detail, str) else str(detail)
            code = _status_to_code(int(exc.status_code))
            body = _error_body(code, msg, rid)
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        rid = _request_id(request)
        # Concise first error for humans; full issues remain in OpenAPI client behavior
        errs = exc.errors()
        first = errs[0] if errs else {}
        loc = ".".join(str(x) for x in first.get("loc", ()) if x != "body")
        msg = first.get("msg", "Invalid request.")
        human = f"{loc}: {msg}" if loc else msg
        body = _error_body("VALIDATION_ERROR", human, rid)
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=body)

    @app.exception_handler(ValidationError)
    async def pydantic_validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
        rid = _request_id(request)
        errs = exc.errors()
        first = errs[0] if errs else {}
        loc = ".".join(str(x) for x in first.get("loc", ()))
        msg = first.get("msg", "Validation failed.")
        human = f"{loc}: {msg}" if loc else msg
        body = _error_body("VALIDATION_ERROR", human, rid)
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=body)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        rid = _request_id(request)
        # Import here to avoid circular imports at module load
        from app.error_monitor import log_unhandled_exception

        log_unhandled_exception(request_id=rid or "", path=request.url.path, exc=exc)
        body = _error_body(
            "INTERNAL_ERROR",
            "An unexpected error occurred. Try again later or contact support with your request id.",
            rid,
        )
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=body)


def _status_to_code(status_code: int) -> str:
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        413: "PAYLOAD_TOO_LARGE",
        422: "UNPROCESSABLE_ENTITY",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
    }.get(status_code, "HTTP_ERROR")
