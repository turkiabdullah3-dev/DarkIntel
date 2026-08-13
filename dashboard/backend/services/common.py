from __future__ import annotations

from pathlib import Path
from typing import Any

from darkintel.utils import read_json, validate_case_id


def case_path(root: Path, case_id: str) -> Path:
    validate_case_id(case_id)
    path = root / case_id
    if not (path / "case.json").is_file():
        raise FileNotFoundError("Case does not exist.")
    return path


def payload(path: Path, default: Any) -> Any:
    try:
        return read_json(path) if path.is_file() else default
    except (OSError, ValueError, TypeError):
        return default


def paginate(items: list[Any], offset: int, limit: int) -> dict[str, Any]:
    return {"items": items[offset:offset + limit], "total": len(items), "offset": offset, "limit": limit}
