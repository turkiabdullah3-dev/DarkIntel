
from darkintel.cases import CaseStore
from darkintel.timeline.builder import TimelineBuilder
from darkintel.timeline.models import TimelineEventType
from darkintel.utils import read_json, write_json


def prepare(tmp_path):
    store = CaseStore(tmp_path)
    case = store.create_case("Builder")
    root = tmp_path / case.case_id
    observed = "2026-08-13T07:37:19Z"
    write_json(root / "results" / "verification.json", {
        "url": "http://" + "a" * 56 + ".onion/", "is_live": True, "status_code": 200,
        "response_time_ms": 821, "sha256": "b" * 64, "evidence_file": "evidence/body.bin",
        "observed_at": observed, "final_url": "http://" + "a" * 56 + ".onion/",
    })
    write_json(root / "extracted_iocs" / "indicators.json", {"indicators": [{
        "type": "domain", "value": "Example.COM", "normalized_value": "example.com",
        "first_seen": "2026-08-13T07:38:03Z", "source": "evidence/body.bin",
        "sources": ["evidence/body.bin"], "observation_count": 1,
    }, {
        "type": "sha256", "value": "b" * 64, "normalized_value": "b" * 64,
        "first_seen": "2026-08-13T07:38:03Z", "source": "evidence/body.bin",
    }]})
    write_json(root / "enrichment" / "records.json", {"results": [{
        "indicator": {"type": "domain", "normalized_value": "example.com"},
        "records": [{"provider": "virustotal", "indicator_type": "domain",
                     "normalized_value": "example.com", "queried_at": "2026-08-13T07:39:52Z",
                     "success": True, "cached": False, "summary": {"malicious": 4}}],
    }]})
    return case, root


def test_builder_maps_all_artifact_families_and_provenance(tmp_path):
    case, _ = prepare(tmp_path)
    events = TimelineBuilder(tmp_path).build_case_timeline(case.case_id)
    types = {event.event_type for event in events}
    assert {TimelineEventType.CASE_CREATED, TimelineEventType.TARGET_DISCOVERED,
            TimelineEventType.TARGET_VERIFIED, TimelineEventType.EVIDENCE_COLLECTED,
            TimelineEventType.EVIDENCE_HASHED, TimelineEventType.IOC_EXTRACTED,
            TimelineEventType.IOC_OBSERVED, TimelineEventType.ENRICHMENT_REQUESTED,
            TimelineEventType.ENRICHMENT_COMPLETED} <= types
    enriched = next(event for event in events if event.event_type == TimelineEventType.ENRICHMENT_COMPLETED)
    assert enriched.metadata["provider"] == "virustotal"
    assert "provider claim" in enriched.description
    assert enriched.source == "enrichment/records.json"


def test_builder_correlates_hash_and_indicator(tmp_path):
    case, _ = prepare(tmp_path)
    events = TimelineBuilder(tmp_path).build_case_timeline(case.case_id)
    hashed = next(event for event in events if event.event_type == TimelineEventType.EVIDENCE_HASHED)
    hash_ioc = next(event for event in events if event.event_type == TimelineEventType.IOC_EXTRACTED
                    and event.object_type == "sha256")
    assert hash_ioc.event_id in hashed.related_ids


def test_rebuild_is_idempotent(tmp_path):
    case, _ = prepare(tmp_path)
    builder = TimelineBuilder(tmp_path)
    first = builder.build_case_timeline(case.case_id)
    second = builder.build_case_timeline(case.case_id)
    assert [event.event_id for event in first] == [event.event_id for event in second]


def test_unreachable_and_missing_timestamp(tmp_path):
    case, root = prepare(tmp_path)
    write_json(root / "results" / "unreachable.json", {"url": "http://x.onion", "is_live": False,
                                                        "observed_at": "2026-08-13T08:00:00Z",
                                                        "error": "timeout"})
    write_json(root / "results" / "missing.json", {"url": "http://missing.onion", "is_live": False})
    builder = TimelineBuilder(tmp_path)
    events = builder.build_case_timeline(case.case_id)
    assert any(event.event_type == TimelineEventType.TARGET_UNREACHABLE for event in events)
    assert any("Missing timestamp" in warning for warning in builder.warnings)


def test_malformed_record_isolated_and_event_limit_warns(tmp_path):
    case, root = prepare(tmp_path)
    (root / "results" / "broken.json").write_text("{bad", encoding="utf-8")
    builder = TimelineBuilder(tmp_path, max_events=2)
    events = builder.build_case_timeline(case.case_id)
    assert len(events) == 2
    assert any("Malformed record" in warning for warning in builder.warnings)
    assert any("event limit" in warning for warning in builder.warnings)


def test_case_updated_and_closed_event(tmp_path):
    case, root = prepare(tmp_path)
    payload = read_json(root / "case.json")
    payload["updated_at"] = "2026-08-14T00:00:00Z"
    payload["status"] = "closed"
    write_json(root / "case.json", payload)
    events = TimelineBuilder(tmp_path).build_case_timeline(case.case_id)
    assert any(event.event_type == TimelineEventType.CASE_CLOSED for event in events)
