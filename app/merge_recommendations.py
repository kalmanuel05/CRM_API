from __future__ import annotations

from app.models import CleanedRecord, MergeRecommendation


def _completeness_score(c: CleanedRecord) -> int:
    d = c.model_dump()
    return sum(1 for v in d.values() if v is not None and str(v).strip() != "")


def build_merge_recommendations(
    cleaned: list[CleanedRecord],
    duplicate_groups: list[list[int]],
) -> list[MergeRecommendation]:
    out: list[MergeRecommendation] = []
    for gi, group in enumerate(duplicate_groups):
        if len(group) < 2:
            continue
        scored = [(i, _completeness_score(cleaned[i])) for i in group]
        scored.sort(key=lambda x: (-x[1], x[0]))
        keep = scored[0][0]
        merge_rest = [i for i in group if i != keep]
        out.append(
            MergeRecommendation(
                duplicate_group_index=gi,
                member_indices=sorted(group),
                keep_index=keep,
                merge_indices=sorted(merge_rest),
                rationale=(
                    "Keep the row with the most populated normalized fields; "
                    "merge or discard the others after reviewing source data."
                ),
            )
        )
    return out
