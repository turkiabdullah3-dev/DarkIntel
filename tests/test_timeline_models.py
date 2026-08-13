from datetime import datetime, timezone
import uuid

import pytest

from darkintel.timeline.models import (MAX_DESCRIPTION_CHARS, TimelineEvent, TimelineEventType,
                                       parse_timestamp)

CASE = "CASE-2026-0001"


def test_serialization_utc_and_stable_generated_id():
    first = TimelineEvent.generated(case_id=CASE, event_type=TimelineEventType.CASE_CREATED,
                                    timestamp="2026-08-13T10:30:00+03:00", title="Created",
                                    object_type="case", object_value=CASE, source="case.json")
    second = TimelineEvent.generated(case_id=CASE, event_type=TimelineEventType.CASE_CREATED,
                                     timestamp="2026-08-13T07:30:00Z", title="Different title",
                                     object_type="case", object_value=CASE, source="case.json")
    assert first.timestamp == datetime(2026, 8, 13, 7, 30, tzinfo=timezone.utc)
    assert first.event_id == second.event_id
    assert first.to_dict()["timestamp"] == "2026-08-13T07:30:00Z"
    assert first.metadata["original_timestamp"] == "2026-08-13T10:30:00+03:00"
    assert TimelineEvent.from_dict(first.to_dict()).event_id == first.event_id


@pytest.mark.parametrize("value", ["not-a-time", "2026-08-13T10:00:00"])
def test_invalid_or_naive_timestamp(value):
    with pytest.raises(ValueError):
        parse_timestamp(value)


def test_event_type_and_uuid_validation():
    with pytest.raises(ValueError):
        TimelineEvent("bad", CASE, "arbitrary", datetime.now(timezone.utc), "Title")


def test_analyst_note_unique_and_bounded():
    one = TimelineEvent.analyst_note(case_id=CASE, timestamp="2026-01-01T00:00:00Z", title="Note",
                                     description="x" * 20_000)
    two = TimelineEvent.analyst_note(case_id=CASE, timestamp="2026-01-01T00:00:00Z", title="Note")
    assert uuid.UUID(one.event_id) and one.event_id != two.event_id
    assert len(one.description) == 10_000


def test_metadata_and_machine_description_are_bounded():
    event = TimelineEvent.generated(case_id=CASE, event_type=TimelineEventType.EVIDENCE_COLLECTED,
                                    timestamp="2026-01-01T00:00:00Z", title="Evidence",
                                    description="x" * 10_000, metadata={"large": "y" * 100_000})
    assert len(event.description) == MAX_DESCRIPTION_CHARS
    assert event.metadata["bounded"] is True
