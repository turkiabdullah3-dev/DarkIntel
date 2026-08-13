from darkintel.timeline.correlation import correlate_events
from darkintel.timeline.models import TimelineEvent, TimelineEventType

CASE = "CASE-2026-0001"


def event(kind, object_type, value, source):
    return TimelineEvent.generated(case_id=CASE, event_type=kind, timestamp="2026-01-01T00:00:00Z",
                                   title=kind.value, object_type=object_type, object_value=value, source=source)


def test_exact_object_and_source_correlation_only():
    extracted = event(TimelineEventType.IOC_EXTRACTED, "domain", "example.com", "evidence-1")
    enriched = event(TimelineEventType.ENRICHMENT_COMPLETED, "domain", "example.com", "enrichment.json")
    unrelated = event(TimelineEventType.IOC_EXTRACTED, "domain", "other.com", "evidence-2")
    correlate_events([extracted, enriched, unrelated])
    assert enriched.event_id in extracted.related_ids
    assert unrelated.event_id not in extracted.related_ids


def test_evidence_hash_correlates_to_hash_ioc():
    hashed = TimelineEvent.generated(case_id=CASE, event_type=TimelineEventType.EVIDENCE_HASHED,
                                     timestamp="2026-01-01T00:00:00Z", title="Hash", object_type="sha256",
                                     object_value="a" * 64, source="result.json", metadata={"sha256": "a" * 64})
    ioc = event(TimelineEventType.IOC_EXTRACTED, "sha256", "a" * 64, "notes")
    correlate_events([hashed, ioc])
    assert ioc.event_id in hashed.related_ids
