from datetime import datetime, timezone

import pytest

from darkintel.models import InvestigationCase, OnionResult


def test_onion_result_serializes_utc_timestamp():
    result = OnionResult("http://example.onion/", False)
    assert result.observed_at.tzinfo is timezone.utc
    assert result.to_dict()["observed_at"].endswith("Z")


def test_result_rejects_naive_observation_time():
    with pytest.raises(ValueError, match="timezone-aware"):
        OnionResult("http://example.onion/", False, observed_at=datetime.now())


def test_case_round_trip():
    case = InvestigationCase("CASE-2026-0001", "Test", tags=["cti"])
    assert InvestigationCase.from_dict(case.to_dict()) == case


def test_case_rejects_unknown_status():
    with pytest.raises(ValueError, match="status"):
        InvestigationCase("CASE-2026-0001", "Test", status="unknown")
