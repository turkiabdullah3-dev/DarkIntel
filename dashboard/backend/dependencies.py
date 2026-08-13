"""Dashboard dependency configuration."""

from __future__ import annotations

import os
from pathlib import Path


def cases_root() -> Path:
    return Path(os.environ.get("DARKINTEL_CASES_DIR", "cases"))


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
ALLOWED_ORIGINS = ("http://127.0.0.1:5173", "http://localhost:5173")
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 1000
MAX_GRAPH_NODES = 5000
