from __future__ import annotations

import re
import string
from collections import defaultdict
from email_validator import EmailNotValidError, validate_email

import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat

from app.models import CleanedRecord, CustomerRecordIn, FieldWarning

_WS_RE = re.compile(r"\s+")
_NON_NAME_CHARS = re.compile(r"[^\w\s\-'.]")


def _clean_text(value: str | None, *, title_case: bool = True) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = _WS_RE.sub(" ", s)
    if title_case:
        s = string.capwords(s)
    return s or None


def _split_full_name(full: str) -> tuple[str | None, str | None]:
    parts = _WS_RE.split(full.strip())
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])


def clean_name_fields(rec: CustomerRecordIn) -> tuple[str | None, str | None, str | None]:
    fn = _clean_text(rec.first_name)
    ln = _clean_text(rec.last_name)
    raw_full = rec.full_name or rec.name
    full = _clean_text(raw_full) if raw_full else None

    if full and not (fn and ln):
        g_fn, g_ln = _split_full_name(full)
        fn = fn or g_fn
        ln = ln or g_ln
    if fn or ln:
        full = " ".join(p for p in (fn, ln) if p).strip() or None
    elif full:
        g_fn, g_ln = _split_full_name(full)
        fn = fn or g_fn
        ln = ln or g_ln
    return fn, ln, full


def normalize_email(raw: str | None) -> tuple[str | None, bool]:
    if raw is None or not str(raw).strip():
        return None, False

    candidate = str(raw).strip().lower()
    try:
        info = validate_email(candidate, check_deliverability=False)
        normalized = info.normalized

        local, sep, domain = normalized.partition("@")
        if not sep:
            return normalized, True

        if "+" in local:
            local = local.split("+", 1)[0]

        return f"{local}@{domain}", True
    except EmailNotValidError:
        return candidate, False


def normalize_phone(raw: str | None, region: str) -> tuple[str | None, bool]:
    if raw is None or not str(raw).strip():
        return None, False
    text = str(raw).strip()
    try:
        parsed = phonenumbers.parse(text, region)
        if not phonenumbers.is_valid_number(parsed):
            return None, False
        return phonenumbers.format_number(parsed, PhoneNumberFormat.E164), True
    except NumberParseException:
        return None, False


def clean_customer(rec: CustomerRecordIn, region: str) -> CleanedRecord:
    fn, ln, full = clean_name_fields(rec)
    email, _ = normalize_email(rec.email)
    phone_e164, _ = normalize_phone(rec.phone, region)

    return CleanedRecord(
        first_name=fn,
        last_name=ln,
        full_name=full,
        email=email,
        phone_e164=phone_e164,
        company=_clean_text(rec.company),
        title=_clean_text(rec.title),
        address=_clean_text(rec.address, title_case=False),
        city=_clean_text(rec.city),
        state=_clean_text(rec.state, title_case=False),
        zip=_clean_text(rec.zip, title_case=False),
        country=_clean_text(rec.country),
        notes=_clean_text(rec.notes, title_case=False),
    )


def collect_warnings(index: int, rec: CustomerRecordIn, cleaned: CleanedRecord, region: str) -> list[FieldWarning]:
    out: list[FieldWarning] = []

    has_any_name = bool(rec.first_name or rec.last_name or rec.full_name or rec.name)
    if not has_any_name:
        out.append(
            FieldWarning(
                record_index=index,
                field="name",
                severity="missing",
                message="No first name, last name, or full name provided.",
            )
        )

    if rec.email is not None and str(rec.email).strip():
        _, ok = normalize_email(rec.email)
        if not ok:
            out.append(
                FieldWarning(
                    record_index=index,
                    field="email",
                    severity="invalid",
                    message="Email is present but could not be validated.",
                )
            )
    elif not cleaned.email:
        out.append(
            FieldWarning(
                record_index=index,
                field="email",
                severity="missing",
                message="Email is empty.",
            )
        )

    if rec.phone is not None and str(rec.phone).strip():
        _, ok = normalize_phone(rec.phone, region)
        if not ok:
            out.append(
                FieldWarning(
                    record_index=index,
                    field="phone",
                    severity="invalid",
                    message="Phone is present but invalid or not parseable for the given region.",
                )
            )
    elif not cleaned.phone_e164:
        out.append(
            FieldWarning(
                record_index=index,
                field="phone",
                severity="missing",
                message="Phone is empty.",
            )
        )

    return out


def _norm_name_key(c: CleanedRecord) -> str:
    base = (c.full_name or f"{c.first_name or ''} {c.last_name or ''}").strip().lower()
    return _NON_NAME_CHARS.sub("", _WS_RE.sub(" ", base))


def find_duplicate_groups(cleaned: list[CleanedRecord]) -> list[list[int]]:
    by_email: dict[str, list[int]] = defaultdict(list)
    by_phone: dict[str, list[int]] = defaultdict(list)
    by_name_company: dict[tuple[str, str], list[int]] = defaultdict(list)

    for i, c in enumerate(cleaned):
        if c.email:
            by_email[c.email].append(i)
        if c.phone_e164:
            by_phone[c.phone_e164].append(i)
        nk = _norm_name_key(c)
        ck = (c.company or "").strip().lower()
        # Name-only duplicates: require company so "John Smith" rows do not all cluster.
        if nk and len(nk) >= 3 and ck:
            by_name_company[(nk, ck)].append(i)

    uf: dict[int, int] = {}

    def find(x: int) -> int:
        if x not in uf:
            uf[x] = x
        if uf[x] != x:
            uf[x] = find(uf[x])
        return uf[x]

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            uf[ra] = rb

    for group in list(by_email.values()) + list(by_phone.values()) + list(by_name_company.values()):
        if len(group) < 2:
            continue
        first = group[0]
        for j in group[1:]:
            union(first, j)

    clusters: dict[int, list[int]] = defaultdict(list)
    for i in range(len(cleaned)):
        clusters[find(i)].append(i)

    return [sorted(v) for k, v in clusters.items() if len(v) > 1]


def process_batch(
    records: list[dict],
    default_phone_region: str,
) -> tuple[list[CleanedRecord], list[FieldWarning], list[list[int]]]:
    region = (default_phone_region or "US").upper()
    parsed = [CustomerRecordIn.from_loose_dict(r) for r in records]
    cleaned = [clean_customer(p, region) for p in parsed]
    warnings: list[FieldWarning] = []
    for idx, (p, c) in enumerate(zip(parsed, cleaned)):
        warnings.extend(collect_warnings(idx, p, c, region))
    dups = find_duplicate_groups(cleaned)
    return cleaned, warnings, dups
