"""Case-scoped timeline persistence, filtering, notes, and summaries."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import logging

from .exporters import export_csv, export_markdown
from .models import TimelineEvent, TimelineEventType, parse_timestamp, sort_events
from ..models import utc_now
from ..utils import atomic_write_text, read_json, validate_case_id, write_json

LOGGER = logging.getLogger(__name__)
MAX_TIMELINE_EVENTS = 100_000


class TimelineStore:
    def __init__(self, root: str | Path = "cases") -> None:
        self.root = Path(root)

    def directory(self, case_id: str) -> Path:
        validate_case_id(case_id)
        case_path = self.root / case_id
        if not (case_path / "case.json").is_file():
            raise FileNotFoundError(f"case not found: {case_id}")
        directory = case_path / "timeline"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def load(self, case_id: str) -> list[TimelineEvent]:
        path = self.directory(case_id) / "events.json"
        if not path.is_file():
            return []
        payload = read_json(path)
        return sort_events([TimelineEvent.from_dict(item) for item in payload.get("events", [])])

    def save(self, case_id: str, generated: list[TimelineEvent], warnings: list[str] | None = None) -> list[TimelineEvent]:
        directory = self.directory(case_id)
        existing = self.load(case_id)
        notes = [event for event in existing if event.event_type == TimelineEventType.ANALYST_NOTE]
        by_id = {event.event_id: event for event in generated + notes}
        events = sort_events(list(by_id.values()))
        limit_warning = None
        if len(events) > MAX_TIMELINE_EVENTS:
            events = events[:MAX_TIMELINE_EVENTS]
            limit_warning = f"Timeline event limit reached at {MAX_TIMELINE_EVENTS}"
        all_warnings = list(warnings or [])
        if limit_warning:
            all_warnings.append(limit_warning)
        write_json(directory / "events.json", {"case_id": case_id,
                                                "events": [event.to_dict() for event in events],
                                                "warnings": all_warnings})
        atomic_write_text(directory / "events.csv", export_csv(events))
        write_json(directory / "summary.json", self.summary(case_id, events, all_warnings))
        return events

    def add_note(self, case_id: str, title: str, description: str | None = None,
                 timestamp: str | None = None, tags: list[str] | None = None) -> TimelineEvent:
        note = TimelineEvent.analyst_note(case_id=case_id, timestamp=timestamp or utc_now(), title=title,
                                          description=description, tags=tags)
        events = self.load(case_id)
        if len(events) >= MAX_TIMELINE_EVENTS:
            raise ValueError("timeline event limit reached")
        self.save(case_id, events + [note])
        LOGGER.info("analyst note created: case=%s event=%s", case_id, note.event_id)
        return note

    def filter(self, case_id: str, *, event_type: str | None = None, object_value: str | None = None,
               object_type: str | None = None, from_time: str | None = None, to_time: str | None = None,
               source: str | None = None) -> list[TimelineEvent]:
        selected = self.load(case_id)
        kind = TimelineEventType(event_type) if event_type else None
        lower = parse_timestamp(from_time)[0] if from_time else None
        upper = parse_timestamp(to_time)[0] if to_time else None
        if lower and upper and lower > upper:
            raise ValueError("from timestamp must not be after to timestamp")
        return [event for event in selected
                if (kind is None or event.event_type == kind)
                and (object_value is None or event.object_value == object_value)
                and (object_type is None or event.object_type == object_type)
                and (source is None or event.source == source)
                and (lower is None or event.timestamp >= lower)
                and (upper is None or event.timestamp <= upper)]

    def export(self, case_id: str, format_name: str) -> Path:
        events = self.load(case_id)
        exporters = {"csv": ("events.csv", export_csv), "markdown": ("events.md", export_markdown)}
        if format_name == "json":
            path = self.directory(case_id) / "events.json"
            if not path.is_file():
                self.save(case_id, events)
            LOGGER.info("timeline exported: case=%s format=json", case_id)
            return path
        if format_name not in exporters:
            raise ValueError("unsupported timeline export format")
        filename, exporter = exporters[format_name]
        path = self.directory(case_id) / filename
        atomic_write_text(path, exporter(events))
        LOGGER.info("timeline exported: case=%s format=%s", case_id, format_name)
        return path

    @staticmethod
    def summary(case_id: str, events: list[TimelineEvent], warnings: list[str]) -> dict[str, object]:
        types = Counter(event.event_type.value for event in events)
        objects = {(event.object_type, event.object_value) for event in events
                   if event.object_type and event.object_value}
        return {"case_id": case_id, "total_events": len(events),
                "first_event": events[0].timestamp.isoformat().replace("+00:00", "Z") if events else None,
                "last_event": events[-1].timestamp.isoformat().replace("+00:00", "Z") if events else None,
                "event_types": dict(sorted(types.items())), "unique_objects": len(objects),
                "warnings": warnings[:100]}
