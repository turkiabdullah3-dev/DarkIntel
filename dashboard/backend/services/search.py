from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import case_path, payload


def search_case(root: Path, case_id: str, query: str, limit: int) -> dict[str, Any]:
    """Search bounded, display-safe fields from existing local case artifacts."""
    path = case_path(root, case_id)
    needle = query.casefold().strip()
    results: list[dict[str, Any]] = []

    def add(kind: str, identifier: str, title: str, detail: str = "") -> None:
        if len(results) >= limit:
            return
        haystack = f"{identifier} {title} {detail}".casefold()
        if needle in haystack:
            results.append({"kind": kind, "id": identifier[:500], "title": title[:500],
                            "detail": detail[:1000]})

    for item in payload(path / "extracted_iocs" / "indicators.json", {}).get("indicators", []):
        add("indicator", str(item.get("normalized_value", "")), str(item.get("normalized_value", "")),
            str(item.get("type", "")))
    for record_path in sorted((path / "results").glob("*.json")):
        record = payload(record_path, {})
        add("evidence", record_path.stem, str(record.get("url", record_path.stem)),
            str(record.get("content_type", "")))
    for event in payload(path / "timeline" / "events.json", {}).get("events", []):
        add("timeline", str(event.get("event_id", "")), str(event.get("title", "")),
            str(event.get("object_value", "")))
    for group in payload(path / "enrichment" / "records.json", {}).get("results", []):
        for record in group.get("records", []):
            add("provider", str(record.get("provider", "")), str(record.get("provider", "")),
                str(record.get("normalized_value", "")))
    for node in payload(path / "graph" / "graph.json", {}).get("nodes", []):
        add("graph_node", str(node.get("node_id", "")), str(node.get("label", "")),
            f'{node.get("node_type", "")} {node.get("value", "")}')
    return {"items": results, "total": len(results), "limit": limit}
