from __future__ import annotations

from pathlib import Path

from .common import case_path, paginate, payload


def _enriched_keys(path: Path) -> set[tuple[str, str]]:
    keys = set()
    for result in payload(path / "enrichment" / "records.json", {}).get("results", []):
        indicator = result.get("indicator", {})
        keys.add((indicator.get("type"), indicator.get("normalized_value")))
    return keys


def list_indicators(root: Path, case_id: str, ioc_type: str | None, search: str | None,
                    min_confidence: float, enriched: bool | None, offset: int, limit: int) -> dict[str, object]:
    path = case_path(root, case_id)
    enriched_keys = _enriched_keys(path)
    items = []
    for item in payload(path / "extracted_iocs" / "indicators.json", {}).get("indicators", []):
        is_enriched = (item.get("type"), item.get("normalized_value")) in enriched_keys
        if ioc_type and item.get("type") != ioc_type:
            continue
        if search and search.lower() not in str(item.get("normalized_value", "")).lower():
            continue
        if float(item.get("confidence", 0)) < min_confidence or enriched is not None and is_enriched != enriched:
            continue
        clean = dict(item)
        clean["enriched"] = is_enriched
        items.append(clean)
    items.sort(key=lambda item: (item.get("type", ""), item.get("normalized_value", "")))
    return paginate(items, offset, limit)


def indicator_detail(root: Path, case_id: str, ioc_type: str, value: str) -> dict[str, object]:
    path = case_path(root, case_id)
    indicator = next((item for item in payload(path / "extracted_iocs" / "indicators.json", {}).get("indicators", [])
                      if item.get("type") == ioc_type and item.get("normalized_value") == value), None)
    if indicator is None:
        raise LookupError("Indicator does not exist.")
    records = []
    for result in payload(path / "enrichment" / "records.json", {}).get("results", []):
        obj = result.get("indicator", {})
        if obj.get("type") == ioc_type and obj.get("normalized_value") == value:
            records.extend(result.get("records", []))
    return {"indicator": indicator, "enrichment": records}
