from pathlib import Path

from .common import case_path, paginate, payload


def list_enrichment(root: Path, case_id: str, provider: str | None, ioc_type: str | None,
                    success: bool | None, cached: bool | None, offset: int, limit: int) -> dict[str, object]:
    path = case_path(root, case_id)
    items = []
    for result in payload(path / "enrichment" / "records.json", {}).get("results", []):
        indicator = result.get("indicator", {})
        for record in result.get("records", []):
            item = {**record, "indicator": {"type": indicator.get("type"),
                                             "normalized_value": indicator.get("normalized_value")}}
            if provider and record.get("provider") != provider or ioc_type and record.get("indicator_type") != ioc_type:
                continue
            if success is not None and bool(record.get("success")) != success:
                continue
            if cached is not None and bool(record.get("cached")) != cached:
                continue
            items.append(item)
    return paginate(items, offset, limit)
