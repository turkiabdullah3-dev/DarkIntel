"""JSON-backed investigation case management."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any

from filelock import FileLock

from .models import CASE_STATUSES, InvestigationCase, utc_now
from .utils import read_json, validate_case_id, write_json

LOGGER = logging.getLogger(__name__)
CASE_DIRECTORIES = ("results", "evidence", "screenshots", "extracted_iocs", "enrichment", "timeline",
                    "graph", "logs", "reports")


class CaseStore:
    def __init__(self, root: str | Path = "cases") -> None:
        self.root = Path(root)

    def _path(self, case_id: str) -> Path:
        validate_case_id(case_id)
        return self.root / case_id

    def _next_id(self) -> str:
        year = datetime.now(timezone.utc).year
        prefix = f"CASE-{year}-"
        numbers = []
        if self.root.exists():
            for entry in self.root.iterdir():
                if entry.is_dir() and entry.name.startswith(prefix):
                    try:
                        validate_case_id(entry.name)
                        numbers.append(int(entry.name.rsplit("-", 1)[1]))
                    except ValueError:
                        continue
        return f"{prefix}{max(numbers, default=0) + 1:04d}"

    def create_case(self, name: str, description: str = "", tags: list[str] | None = None) -> InvestigationCase:
        if not name or not name.strip():
            raise ValueError("case name cannot be empty")
        self.root.mkdir(parents=True, exist_ok=True)
        with FileLock(str(self.root / ".case-id.lock"), timeout=10):
            case = InvestigationCase(self._next_id(), name.strip(), description.strip(), tags=list(tags or []))
            case_path = self._path(case.case_id)
            case_path.mkdir()
            for directory in CASE_DIRECTORIES:
                (case_path / directory).mkdir()
            write_json(case_path / "case.json", case.to_dict())
        LOGGER.info("case created: %s", case.case_id)
        return case

    def load_case(self, case_id: str) -> InvestigationCase:
        path = self._path(case_id) / "case.json"
        if not path.is_file():
            raise FileNotFoundError(f"case not found: {case_id}")
        return InvestigationCase.from_dict(read_json(path))

    def list_cases(self) -> list[InvestigationCase]:
        if not self.root.exists():
            return []
        cases = []
        for path in sorted(self.root.glob("CASE-????-????/case.json")):
            try:
                cases.append(self.load_case(path.parent.name))
            except (ValueError, KeyError, TypeError):
                LOGGER.warning("skipping invalid case metadata: %s", path)
        return cases

    def update_case(self, case_id: str, *, name: str | None = None, description: str | None = None,
                    status: str | None = None, tags: list[str] | None = None) -> InvestigationCase:
        case = self.load_case(case_id)
        if name is not None:
            if not name.strip():
                raise ValueError("case name cannot be empty")
            case.name = name.strip()
        if description is not None:
            case.description = description.strip()
        if status is not None:
            if status not in CASE_STATUSES:
                raise ValueError(f"status must be one of: {', '.join(sorted(CASE_STATUSES))}")
            case.status = status
        if tags is not None:
            case.tags = list(tags)
        case.updated_at = utc_now()
        write_json(self._path(case_id) / "case.json", case.to_dict())
        return case

    def close_case(self, case_id: str) -> InvestigationCase:
        return self.update_case(case_id, status="closed")


def create_case(name: str, description: str = "", tags: list[str] | None = None, root: str | Path = "cases") -> InvestigationCase:
    return CaseStore(root).create_case(name, description, tags)


def load_case(case_id: str, root: str | Path = "cases") -> InvestigationCase:
    return CaseStore(root).load_case(case_id)


def list_cases(root: str | Path = "cases") -> list[InvestigationCase]:
    return CaseStore(root).list_cases()


def update_case(case_id: str, root: str | Path = "cases", **changes: Any) -> InvestigationCase:
    return CaseStore(root).update_case(case_id, **changes)


def close_case(case_id: str, root: str | Path = "cases") -> InvestigationCase:
    return CaseStore(root).close_case(case_id)
