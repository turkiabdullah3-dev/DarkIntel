from __future__ import annotations

from pathlib import Path

from .common import case_path, paginate, payload


def list_evidence(root: Path, case_id: str, search: str | None, content_type: str | None,
                  source: str | None, offset: int, limit: int) -> dict[str, object]:
    path = case_path(root, case_id)
    items = []
    for record_path in sorted((path / "results").glob("*.json")):
        record = payload(record_path, {})
        record = {key: record.get(key) for key in ("url", "observed_at", "content_type", "status_code", "sha256",
                                                     "response_time_ms", "evidence_file", "is_live", "error")}
        record["evidence_id"] = record_path.stem
        record["source"] = f"results/{record_path.name}"
        text = " ".join(str(value) for value in record.values()).lower()
        if search and search.lower() not in text:
            continue
        if content_type and record.get("content_type") != content_type:
            continue
        if source and record.get("source") != source:
            continue
        items.append(record)
    return paginate(items, offset, limit)
