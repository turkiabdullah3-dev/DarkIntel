from __future__ import annotations

from collections import Counter
from pathlib import Path

from darkintel.cases import CaseStore

from .common import case_path, payload


def counts(path: Path) -> dict[str, object]:
    indicators = payload(path / "extracted_iocs" / "indicators.json", {}).get("indicators", [])
    enrichment = payload(path / "enrichment" / "records.json", {}).get("results", [])
    timeline = payload(path / "timeline" / "events.json", {}).get("events", [])
    graph = payload(path / "graph" / "graph.json", {})
    results = list((path / "results").glob("*.json"))
    types = Counter(item.get("type", "unknown") for item in indicators)
    enrichment_count = sum(len(item.get("records", [])) for item in enrichment)
    onion_targets = sum(1 for result in results if ".onion" in str(payload(result, {}).get("url", "")))
    return {"evidence": len(results), "indicators": len(indicators), "onion_targets": onion_targets,
            "enrichment_records": enrichment_count, "timeline_events": len(timeline),
            "graph_nodes": len(graph.get("nodes", [])), "graph_edges": len(graph.get("edges", [])),
            "ioc_types": dict(sorted(types.items())), "recent_events": timeline[-10:][::-1]}


def list_cases(root: Path) -> list[dict[str, object]]:
    output = []
    for case in CaseStore(root).list_cases():
        metrics = counts(root / case.case_id)
        item = case.to_dict()
        item.update({"indicator_count": metrics["indicators"], "evidence_count": metrics["evidence"],
                     "timeline_event_count": metrics["timeline_events"], "graph_node_count": metrics["graph_nodes"]})
        output.append(item)
    return output


def case_detail(root: Path, case_id: str) -> dict[str, object]:
    path = case_path(root, case_id)
    item = payload(path / "case.json", {})
    item["overview"] = counts(path)
    return item
