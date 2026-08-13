"""Passive persistence of HTTP observations and supplied response bodies."""

from __future__ import annotations

import hashlib
import csv
import io
import logging
from pathlib import Path
import re

from .models import ExtractionResult, IOC, OnionResult
from .utils import atomic_write_text, read_json, validate_case_id, write_json

LOGGER = logging.getLogger(__name__)


class EvidenceStore:
    def __init__(self, root: str | Path = "cases") -> None:
        self.root = Path(root)

    def _case_path(self, case_id: str) -> Path:
        validate_case_id(case_id)
        path = self.root / case_id
        if not (path / "case.json").is_file():
            raise FileNotFoundError(f"case not found: {case_id}")
        return path

    def save_result(self, case_id: str, result: OnionResult, body: bytes | None = None) -> Path:
        case_path = self._case_path(case_id)
        timestamp = result.observed_at.strftime("%Y%m%dT%H%M%S%fZ")
        host = re.sub(r"[^a-zA-Z0-9.-]", "_", result.url.split("/", 3)[2] if "://" in result.url else "invalid")
        stem = f"{timestamp}_{host}"
        result_path = case_path / "results" / f"{stem}.json"
        metadata = result.to_dict()
        if body is not None:
            digest = hashlib.sha256(body).hexdigest()
            if result.sha256 and digest != result.sha256:
                raise ValueError("response body does not match result SHA-256")
            body_path = case_path / "evidence" / f"{stem}.bin"
            body_path.write_bytes(body)
            metadata["evidence_file"] = str(body_path.relative_to(case_path))
            metadata["sha256"] = digest
        write_json(result_path, metadata)
        LOGGER.info("evidence written: %s", result_path)
        return result_path


class IOCStore:
    """Maintain canonical case-level IOC JSON and analyst-friendly CSV."""

    CSV_FIELDS = ("type", "value", "normalized_value", "confidence", "source", "first_seen",
                  "context", "tags", "observation_count", "sources")

    def __init__(self, root: str | Path = "cases") -> None:
        self.root = Path(root)

    def _directory(self, case_id: str) -> Path:
        validate_case_id(case_id)
        case_path = self.root / case_id
        if not (case_path / "case.json").is_file():
            raise FileNotFoundError(f"case not found: {case_id}")
        directory = case_path / "extracted_iocs"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def merge(self, case_id: str, result: ExtractionResult) -> list[IOC]:
        directory = self._directory(case_id)
        json_path = directory / "indicators.json"
        existing: list[IOC] = []
        if json_path.is_file():
            payload = read_json(json_path)
            existing = [IOC.from_dict(item) for item in payload.get("indicators", [])]
        merged = {(item.type.value, item.normalized_value): item for item in existing}
        for incoming in result.indicators:
            key = (incoming.type.value, incoming.normalized_value)
            current = merged.get(key)
            if current is None:
                merged[key] = incoming
                continue
            current.observation_count += incoming.observation_count
            current.sources = list(dict.fromkeys(current.sources + incoming.sources))
            current.confidence = max(current.confidence, incoming.confidence)
            current.tags = list(dict.fromkeys(current.tags + incoming.tags))
            if incoming.first_seen < current.first_seen:
                current.first_seen = incoming.first_seen
            if not current.context and incoming.context:
                current.context = incoming.context
        indicators = sorted(merged.values(), key=lambda item: (item.type.value, item.normalized_value))
        write_json(json_path, {"case_id": case_id, "indicators": [item.to_dict() for item in indicators],
                               "total_unique": len(indicators)})
        self._write_csv(directory / "indicators.csv", indicators)
        LOGGER.info("case IOC exports written: %s count=%d", case_id, len(indicators))
        return indicators

    def _write_csv(self, path: Path, indicators: list[IOC]) -> None:
        handle = io.StringIO(newline="")
        writer = csv.DictWriter(handle, fieldnames=self.CSV_FIELDS)
        writer.writeheader()
        for indicator in indicators:
            data = indicator.to_dict()
            writer.writerow({
                "type": data["type"], "value": data["value"],
                "normalized_value": data["normalized_value"], "confidence": data["confidence"],
                "source": data["source"] or "", "first_seen": data["first_seen"],
                "context": data["context"] or "", "tags": ";".join(data["tags"]),
                "observation_count": data["observation_count"], "sources": ";".join(data["sources"]),
            })
        atomic_write_text(path, handle.getvalue())
