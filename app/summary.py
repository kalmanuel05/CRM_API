from __future__ import annotations

from collections import Counter

from app.models import CleanedRecord, FieldWarning, SummaryStats


def build_summary_stats(
    cleaned: list[CleanedRecord],
    warnings: list[FieldWarning],
    duplicate_groups: list[list[int]],
) -> SummaryStats:
    wc = len(warnings)
    by_field = Counter(w.field for w in warnings)
    by_sev = Counter(w.severity for w in warnings)
    in_dups = set()
    for g in duplicate_groups:
        in_dups.update(g)
    filled = []
    for c in cleaned:
        d = c.model_dump()
        filled.append(sum(1 for v in d.values() if v is not None and str(v).strip() != ""))
    avg = sum(filled) / len(filled) if filled else None
    return SummaryStats(
        record_count=len(cleaned),
        warning_count=wc,
        warnings_by_field=dict(by_field),
        warnings_by_severity=dict(by_sev),
        duplicate_group_count=len(duplicate_groups),
        records_in_duplicate_groups=len(in_dups),
        avg_non_empty_fields_per_record=round(avg, 3) if avg is not None else None,
    )
