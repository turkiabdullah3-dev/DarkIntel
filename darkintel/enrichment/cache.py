"""Case-scoped JSON cache for provider records."""

from __future__ import annotations

from datetime import timedelta
import hashlib
from pathlib import Path

from ..models import EnrichmentRecord, utc_now
from ..utils import read_json, validate_case_id, write_json


class EnrichmentCache:
    def __init__(self, root: str | Path, case_id: str, *, max_entries: int = 5000) -> None:
        validate_case_id(case_id)
        case_path = Path(root) / case_id
        if not (case_path / "case.json").is_file():
            raise FileNotFoundError(f"case not found: {case_id}")
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        self.directory = case_path / "enrichment" / "cache"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_entries = max_entries

    @staticmethod
    def key(provider: str, indicator_type: str, normalized_value: str) -> str:
        material = f"{provider}\0{indicator_type}\0{normalized_value}".encode("utf-8")
        return hashlib.sha256(material).hexdigest()

    def get(self, provider: str, indicator_type: str, normalized_value: str) -> EnrichmentRecord | None:
        path = self.directory / f"{self.key(provider, indicator_type, normalized_value)}.json"
        if not path.is_file():
            return None
        try:
            record = EnrichmentRecord.from_dict(read_json(path))
        except (ValueError, TypeError, KeyError):
            return None
        if record.expires_at is None or record.expires_at <= utc_now():
            return None
        record.cached = True
        return record

    def put(self, record: EnrichmentRecord, ttl_hours: int) -> None:
        effective_ttl = ttl_hours if record.success else min(ttl_hours, 1)
        record.expires_at = utc_now() + timedelta(hours=effective_ttl)
        record.cached = False
        path = self.directory / f"{self.key(record.provider, record.indicator_type, record.normalized_value)}.json"
        write_json(path, record.to_dict())
        self._prune()

    def _prune(self) -> None:
        paths = sorted(self.directory.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        for path in paths[self.max_entries:]:
            path.unlink(missing_ok=True)
