from __future__ import annotations

from app.merge_recommendations import build_merge_recommendations
from app.models import CleanedRecord


def test_merge_recommendation_keeps_most_complete_row() -> None:
    sparse = CleanedRecord(
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        phone_e164=None,
        company="Acme",
    )
    rich = CleanedRecord(
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        phone_e164="+12025550100",
        company="Acme",
        title="VP",
        city="Austin",
    )
    cleaned = [sparse, rich]
    duplicate_groups = [[0, 1]]
    recs = build_merge_recommendations(cleaned, duplicate_groups)
    assert len(recs) == 1
    mr = recs[0]
    assert mr.keep_index == 1
    assert 0 in mr.merge_indices
    assert mr.duplicate_group_index == 0
    assert "most populated" in mr.rationale.lower()
