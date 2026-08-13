import json

import pytest

from darkintel.cases import CaseStore
from darkintel.timeline.models import TimelineEvent, TimelineEventType
from darkintel.timeline.store import TimelineStore


def setup(tmp_path):
    case = CaseStore(tmp_path).create_case("Timeline")
    return case, TimelineStore(tmp_path)


def generated(case_id, kind=TimelineEventType.CASE_CREATED, timestamp="2026-01-01T00:00:00Z", value="x"):
    return TimelineEvent.generated(case_id=case_id, event_type=kind, timestamp=timestamp, title=kind.value,
                                   object_type="domain", object_value=value, source="source.json")


def test_save_summary_stable_order_and_deduplication(tmp_path):
    case, store = setup(tmp_path)
    late = generated(case.case_id, timestamp="2026-01-02T00:00:00Z")
    early = generated(case.case_id, timestamp="2026-01-01T00:00:00Z")
    saved = store.save(case.case_id, [late, early, early])
    assert saved == [early, late]
    summary = json.loads((tmp_path / case.case_id / "timeline" / "summary.json").read_text())
    assert summary["total_events"] == 2 and summary["unique_objects"] == 1


def test_note_manual_offset_and_rebuild_preservation(tmp_path):
    case, store = setup(tmp_path)
    store.save(case.case_id, [generated(case.case_id)])
    note = store.add_note(case.case_id, "Confirmed", "Public disclosure", "2026-08-13T10:30:00+03:00")
    assert note.timestamp.hour == 7
    store.save(case.case_id, [generated(case.case_id)])
    assert any(item.event_id == note.event_id for item in store.load(case.case_id))


def test_filters_are_inclusive(tmp_path):
    case, store = setup(tmp_path)
    one = generated(case.case_id, TimelineEventType.IOC_EXTRACTED, "2026-01-01T00:00:00Z", "example.com")
    two = generated(case.case_id, TimelineEventType.ENRICHMENT_COMPLETED, "2026-01-02T00:00:00Z", "example.com")
    store.save(case.case_id, [two, one])
    assert store.filter(case.case_id, event_type="ioc_extracted") == [one]
    assert len(store.filter(case.case_id, object_value="example.com", object_type="domain")) == 2
    assert store.filter(case.case_id, from_time="2026-01-02T00:00:00Z", to_time="2026-01-02T00:00:00Z") == [two]
    with pytest.raises(ValueError):
        store.filter(case.case_id, from_time="bad")


def test_path_traversal_and_exports(tmp_path):
    _, store = setup(tmp_path)
    with pytest.raises(ValueError):
        store.load("../escape")
    case = CaseStore(tmp_path).list_cases()[0]
    store.save(case.case_id, [generated(case.case_id)])
    assert store.export(case.case_id, "json").is_file()
    assert store.export(case.case_id, "csv").is_file()
    assert store.export(case.case_id, "markdown").is_file()
