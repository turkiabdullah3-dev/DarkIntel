"""Shared contracts for passive IOC extractors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..models import IOCType


@dataclass(frozen=True, slots=True)
class Candidate:
    type: IOCType
    value: str
    normalized_value: str
    start: int
    end: int
    confidence: float
    tags: tuple[str, ...] = field(default_factory=tuple)


class Extractor(Protocol):
    name: str

    def extract(self, content: str) -> list[Candidate]: ...
