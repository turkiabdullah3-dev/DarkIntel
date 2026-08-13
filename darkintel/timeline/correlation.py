"""Deterministic, non-speculative timeline correlations."""

from __future__ import annotations

from .models import TimelineEvent, TimelineEventType


def correlate_events(events: list[TimelineEvent]) -> list[TimelineEvent]:
    by_object: dict[tuple[str, str], list[TimelineEvent]] = {}
    by_source: dict[str, list[TimelineEvent]] = {}
    for event in events:
        if event.object_type and event.object_value:
            by_object.setdefault((event.object_type, event.object_value), []).append(event)
        if event.source:
            by_source.setdefault(event.source, []).append(event)

    for event in events:
        related = set(event.related_ids)
        if event.object_type and event.object_value:
            related.update(item.event_id for item in by_object[(event.object_type, event.object_value)]
                           if item.event_id != event.event_id)
        if event.source:
            related.update(item.event_id for item in by_source[event.source] if item.event_id != event.event_id)
        evidence_hash = event.metadata.get("sha256")
        if isinstance(evidence_hash, str):
            related.update(item.event_id for item in events
                           if item.event_type in {TimelineEventType.IOC_EXTRACTED, TimelineEventType.IOC_OBSERVED}
                           and item.object_value == evidence_hash)
        event.related_ids = sorted(related)[:1_000]
    return events
