"""Strongly typed timeline events and timestamp helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import json
import uuid
from typing import Any

from ..utils import validate_case_id

MAX_DESCRIPTION_CHARS = 4_000
MAX_NOTE_DESCRIPTION_CHARS = 10_000
MAX_METADATA_BYTES = 16_384
MAX_METADATA_ITEMS = 50


class TimelineEventType(StrEnum):
    CASE_CREATED = "case_created"
    CASE_UPDATED = "case_updated"
    CASE_CLOSED = "case_closed"
    TARGET_DISCOVERED = "target_discovered"
    TARGET_VERIFIED = "target_verified"
    TARGET_UNREACHABLE = "target_unreachable"
    EVIDENCE_COLLECTED = "evidence_collected"
    EVIDENCE_HASHED = "evidence_hashed"
    IOC_EXTRACTED = "ioc_extracted"
    IOC_OBSERVED = "ioc_observed"
    ENRICHMENT_REQUESTED = "enrichment_requested"
    ENRICHMENT_COMPLETED = "enrichment_completed"
    ENRICHMENT_FAILED = "enrichment_failed"
    ENRICHMENT_CACHE_HIT = "enrichment_cache_hit"
    ANALYST_NOTE = "analyst_note"


def parse_timestamp(value: str | datetime) -> tuple[datetime, str | None]:
    """Parse an aware timestamp and normalize it to UTC, retaining supplied offset text."""
    original = value.isoformat() if isinstance(value, datetime) else value.strip()
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"invalid timestamp: {value}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    normalized = parsed.astimezone(timezone.utc)
    supplied_zone = original if not original.endswith(("Z", "+00:00")) else None
    return normalized, supplied_zone


def _bound_value(value: object, depth: int = 0) -> object:
    if depth >= 3:
        return "[bounded]"
    if isinstance(value, str):
        return value[:2_000]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_bound_value(item, depth + 1) for item in value[:MAX_METADATA_ITEMS]]
    if isinstance(value, dict):
        return {str(key)[:200]: _bound_value(item, depth + 1)
                for key, item in list(value.items())[:MAX_METADATA_ITEMS]}
    return str(value)[:2_000]


def bound_metadata(metadata: dict[str, object]) -> tuple[dict[str, object], bool]:
    bounded = _bound_value(metadata)
    if not isinstance(bounded, dict):
        raise TypeError("bounded metadata must remain an object")
    encoded = json.dumps(bounded, sort_keys=True, ensure_ascii=False).encode("utf-8")
    if len(encoded) <= MAX_METADATA_BYTES:
        return bounded, bounded != metadata
    compact: dict[str, object] = {"metadata_truncated": True,
                                 "original_sha256": hashlib.sha256(encoded).hexdigest()}
    for key, value in bounded.items():
        candidate = dict(compact)
        candidate[key] = value
        if len(json.dumps(candidate, sort_keys=True, ensure_ascii=False).encode()) > MAX_METADATA_BYTES:
            break
        compact = candidate
    return compact, True


def stable_event_id(case_id: str, event_type: str, timestamp: datetime, object_type: str | None,
                    object_value: str | None, source: str | None) -> str:
    material = "\0".join((case_id, event_type, timestamp.isoformat(), object_type or "",
                           object_value or "", source or ""))
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"darkintel:timeline:{material}"))


@dataclass(slots=True)
class TimelineEvent:
    event_id: str
    case_id: str
    event_type: TimelineEventType
    timestamp: datetime
    title: str
    description: str | None = None
    source: str | None = None
    object_type: str | None = None
    object_value: str | None = None
    related_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_case_id(self.case_id)
        if not isinstance(self.event_type, TimelineEventType):
            self.event_type = TimelineEventType(self.event_type)
        try:
            uuid.UUID(self.event_id)
        except ValueError as exc:
            raise ValueError("event_id must be a UUID") from exc
        self.timestamp, _ = parse_timestamp(self.timestamp)
        if not self.title.strip():
            raise ValueError("timeline title cannot be empty")
        self.title = self.title.strip()[:500]
        limit = MAX_NOTE_DESCRIPTION_CHARS if self.event_type == TimelineEventType.ANALYST_NOTE else MAX_DESCRIPTION_CHARS
        if self.description is not None:
            self.description = self.description[:limit]
        self.related_ids = sorted(set(self.related_ids))[:1_000]
        self.tags = sorted(set(self.tags))[:100]
        self.metadata, truncated = bound_metadata(self.metadata)
        if truncated:
            self.metadata["bounded"] = True

    @classmethod
    def generated(cls, *, case_id: str, event_type: TimelineEventType, timestamp: str | datetime,
                  title: str, description: str | None = None, source: str | None = None,
                  object_type: str | None = None, object_value: str | None = None,
                  tags: list[str] | None = None, metadata: dict[str, object] | None = None) -> "TimelineEvent":
        normalized, original_zone = parse_timestamp(timestamp)
        details = dict(metadata or {})
        if original_zone:
            details["original_timestamp"] = original_zone
        event_id = stable_event_id(case_id, event_type.value, normalized, object_type, object_value, source)
        return cls(event_id, case_id, event_type, normalized, title, description, source,
                   object_type, object_value, tags=list(tags or []), metadata=details)

    @classmethod
    def analyst_note(cls, *, case_id: str, timestamp: str | datetime, title: str,
                     description: str | None = None, tags: list[str] | None = None) -> "TimelineEvent":
        normalized, original_zone = parse_timestamp(timestamp)
        metadata: dict[str, object] = {"manual": True}
        if original_zone:
            metadata["original_timestamp"] = original_zone
        return cls(str(uuid.uuid4()), case_id, TimelineEventType.ANALYST_NOTE, normalized, title,
                   description, "analyst", "case", case_id, tags=list(tags or []), metadata=metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id, "case_id": self.case_id, "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat().replace("+00:00", "Z"), "title": self.title,
            "description": self.description, "source": self.source, "object_type": self.object_type,
            "object_value": self.object_value, "related_ids": list(self.related_ids),
            "tags": list(self.tags), "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimelineEvent":
        return cls(**dict(data))


def sort_events(events: list[TimelineEvent]) -> list[TimelineEvent]:
    return sorted(events, key=lambda event: (event.timestamp, event.event_type.value, event.event_id))
