"""Cryptographic hash indicator extraction."""

from __future__ import annotations

import re

from .base import Candidate
from ..models import IOCType

HASH_TYPES = ((IOCType.SHA512, 128), (IOCType.SHA256, 64), (IOCType.SHA1, 40), (IOCType.MD5, 32))


class HashExtractor:
    name = "hashes"

    def extract(self, content: str) -> list[Candidate]:
        found = []
        for indicator_type, length in HASH_TYPES:
            pattern = re.compile(rf"(?i)(?<![0-9a-f])[0-9a-f]{{{length}}}(?![0-9a-f])")
            for match in pattern.finditer(content):
                raw = match.group()
                found.append(Candidate(indicator_type, raw, raw.lower(), match.start(), match.end(), 1.0))
        return found
