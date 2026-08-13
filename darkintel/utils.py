"""Shared serialization and filesystem helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from filelock import FileLock

SAFE_CASE_ID = re.compile(r"^CASE-\d{4}-\d{4}$")


def validate_case_id(case_id: str) -> str:
    if not isinstance(case_id, str) or not SAFE_CASE_ID.fullmatch(case_id):
        raise ValueError("case ID must match CASE-YYYY-NNNN")
    return case_id


def write_json(path: Path, data: Any) -> None:
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def atomic_write_text(path: Path, content: str, *, timeout: float = 10) -> None:
    """Replace a canonical text file atomically under a bounded cross-process lock."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path) + ".lock", timeout=timeout)
    temporary: Path | None = None
    with lock:
        try:
            descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
            temporary = Path(name)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
