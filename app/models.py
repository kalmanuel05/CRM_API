from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ExportFormat = Literal["generic", "hubspot", "salesforce", "zoho"]


class CustomerRecordIn(BaseModel):
    """Flexible inbound row: common CRM / spreadsheet column names."""

    first_name: str | None = Field(default=None, alias="firstName")
    last_name: str | None = Field(default=None, alias="lastName")
    full_name: str | None = Field(default=None, alias="fullName")
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    title: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    country: str | None = None
    notes: str | None = None

    model_config = {"populate_by_name": True, "extra": "allow"}

    @classmethod
    def from_loose_dict(cls, data: dict[str, Any]) -> CustomerRecordIn:
        key_map = {
            "firstname": "first_name",
            "first_name": "first_name",
            "last_name": "last_name",
            "lastname": "last_name",
            "fullname": "full_name",
            "full_name": "full_name",
            "name": "name",
            "e_mail": "email",
            "email_address": "email",
            "phone_number": "phone",
            "mobile": "phone",
            "tel": "phone",
            "telephone": "phone",
            "zipcode": "zip",
            "postal": "zip",
            "postal_code": "zip",
            "zip_code": "zip",
        }
        normalized: dict[str, Any] = {}
        for k, v in data.items():
            if k is None:
                continue
            nk = str(k).strip()
            lk = nk.lower().replace("-", "_").replace(" ", "_")
            while "__" in lk:
                lk = lk.replace("__", "_")
            canon = key_map.get(lk, lk)
            normalized[canon] = v
        return cls.model_validate(normalized)


class FieldWarning(BaseModel):
    record_index: int
    field: str
    severity: str
    message: str


class CleanedRecord(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone_e164: str | None = None
    company: str | None = None
    title: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    country: str | None = None
    notes: str | None = None


class MergeRecommendation(BaseModel):
    duplicate_group_index: int
    member_indices: list[int]
    keep_index: int
    merge_indices: list[int]
    rationale: str


class SummaryStats(BaseModel):
    record_count: int
    warning_count: int
    warnings_by_field: dict[str, int]
    warnings_by_severity: dict[str, int]
    duplicate_group_count: int
    records_in_duplicate_groups: int
    avg_non_empty_fields_per_record: float | None = None


class UsageInfo(BaseModel):
    request_id: str
    tier: str
    monthly_quota: int
    monthly_used: int
    rate_limit_per_minute: int
    max_batch_records: int


class CleanBatchRequest(BaseModel):
    records: list[dict[str, Any]]
    default_phone_region: str = "US"
    export_format: ExportFormat = "generic"


class CleanBatchResponse(BaseModel):
    cleaned_records: list[CleanedRecord]
    warnings: list[FieldWarning]
    duplicate_groups: list[list[int]]
    merge_recommendations: list[MergeRecommendation]
    summary: SummaryStats
    crm_import_rows: list[dict[str, str]]
    usage: UsageInfo


class HealthResponse(BaseModel):
    status: str = "ok"
