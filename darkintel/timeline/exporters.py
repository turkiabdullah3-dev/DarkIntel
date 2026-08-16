"""Deterministic timeline exports with spreadsheet formula protection."""

from __future__ import annotations

import csv
import io
import json

from ..utils import csv_safe
from .models import TimelineEvent, sort_events

CSV_FIELDS = ("event_id", "timestamp", "event_type", "title", "object_type", "object_value",
              "source", "description", "tags")

def export_json(events: list[TimelineEvent]) -> str:
    return json.dumps({"events": [event.to_dict() for event in sort_events(events)]},
                      indent=2, ensure_ascii=False) + "\n"


def export_csv(events: list[TimelineEvent]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for event in sort_events(events):
        data = event.to_dict()
        writer.writerow({field: csv_safe(";".join(data[field]) if field == "tags" else data.get(field))
                         for field in CSV_FIELDS})
    return output.getvalue()


def export_markdown(events: list[TimelineEvent]) -> str:
    lines = ["# Investigation Timeline", ""]
    for event in sort_events(events):
        timestamp = event.timestamp.isoformat().replace("+00:00", "Z")
        lines.append(f"## {timestamp} — {event.event_type.value.upper()}")
        lines.append(escape_markdown(event.title))
        if event.description:
            lines.append(escape_markdown(event.description))
        if event.object_type and event.object_value:
            lines.append(f"Object: `{escape_code(event.object_type)}:{escape_code(event.object_value)}`")
        if event.source:
            lines.append(f"Source: `{escape_code(event.source)}`")
        lines.append("")
    return "\n".join(lines)


def escape_markdown(value: str) -> str:
    return value.replace("\\", "\\\\").replace("<", "&lt;").replace(">", "&gt;")


def escape_code(value: str) -> str:
    return value.replace("`", "\\`").replace("<", "&lt;").replace(">", "&gt;")
