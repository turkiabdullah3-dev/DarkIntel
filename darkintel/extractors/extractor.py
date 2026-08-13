"""Central bounded IOC extraction engine."""

from __future__ import annotations

import logging
import re
from typing import Iterable

from .base import Candidate, Extractor
from .crypto import CryptoExtractor
from .hashes import HashExtractor
from .identities import IdentityExtractor
from .network import NetworkExtractor
from .vulnerabilities import VulnerabilityExtractor
from ..models import ExtractionResult, IOC

LOGGER = logging.getLogger(__name__)
DEFAULT_MAX_INPUT_CHARS = 5_000_000
DEFAULT_MAX_IOCS = 10_000
DEFAULT_CONTEXT_CHARS = 80
MAX_CONTEXT_CHARS = 500


class IOCExtractor:
    """Run independent extractors over hostile text without external interaction."""

    def __init__(self, extractors: Iterable[Extractor] | None = None, *,
                 max_input_chars: int = DEFAULT_MAX_INPUT_CHARS,
                 max_iocs: int = DEFAULT_MAX_IOCS,
                 context_chars: int = DEFAULT_CONTEXT_CHARS) -> None:
        if max_input_chars < 1 or max_iocs < 1:
            raise ValueError("input and IOC limits must be positive")
        if not 0 <= context_chars <= MAX_CONTEXT_CHARS:
            raise ValueError(f"context_chars must be between 0 and {MAX_CONTEXT_CHARS}")
        self.extractors = list(extractors) if extractors is not None else [
            NetworkExtractor(), HashExtractor(), CryptoExtractor(), IdentityExtractor(), VulnerabilityExtractor()
        ]
        self.max_input_chars = max_input_chars
        self.max_iocs = max_iocs
        self.context_chars = context_chars

    def extract(self, content: str, source: str | None = None) -> ExtractionResult:
        if not isinstance(content, str):
            raise TypeError("content must be text")
        errors: list[str] = []
        if len(content) > self.max_input_chars:
            content = content[:self.max_input_chars]
            errors.append(f"Input truncated at {self.max_input_chars} characters")
        candidates: list[Candidate] = []
        for extractor in self.extractors:
            try:
                candidates.extend(extractor.extract(content))
            except Exception as exc:  # failure isolation is intentional at the plugin boundary
                name = getattr(extractor, "name", type(extractor).__name__)
                LOGGER.warning("extractor failed: %s", name, exc_info=True)
                errors.append(f"Extractor {name} failed: {type(exc).__name__}: {exc}")

        indicators: list[IOC] = []
        seen: set[tuple[str, str]] = set()
        for candidate in sorted(candidates, key=lambda item: (item.start, item.type.value, item.normalized_value)):
            key = (candidate.type.value, candidate.normalized_value)
            if key in seen:
                continue
            if len(indicators) >= self.max_iocs:
                errors.append(f"IOC limit reached at {self.max_iocs} unique indicators")
                break
            seen.add(key)
            indicators.append(IOC(
                type=candidate.type,
                value=candidate.value,
                normalized_value=candidate.normalized_value,
                source=source,
                confidence=candidate.confidence,
                context=self._context(content, candidate.start, candidate.end),
                tags=list(candidate.tags),
            ))
        return ExtractionResult(source=source or "unknown", indicators=indicators, errors=errors)

    def _context(self, content: str, start: int, end: int) -> str | None:
        if self.context_chars == 0:
            return None
        left = max(0, start - self.context_chars)
        right = min(len(content), end + self.context_chars)
        context = re.sub(r"\s+", " ", content[left:right]).strip()
        return context or None
