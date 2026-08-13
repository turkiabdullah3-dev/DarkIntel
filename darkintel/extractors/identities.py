"""Passive email and Telegram identity extraction."""

from __future__ import annotations

import re

from .base import Candidate
from ..models import IOCType

EMAIL_RE = re.compile(r"(?i)(?<![\w.+-])[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+(?![\w.-])")
TELEGRAM_URL_RE = re.compile(r"(?i)(?:https?://)?(?:t\.me|telegram\.me)/([a-z][a-z0-9_]{4,31})(?![a-z0-9_])")
TELEGRAM_AT_RE = re.compile(r"(?i)(?<![\w@])@([a-z][a-z0-9_]{4,31})(?![a-z0-9_])")


class IdentityExtractor:
    name = "identities"

    def extract(self, content: str) -> list[Candidate]:
        found = []
        email_spans: list[tuple[int, int]] = []
        for match in EMAIL_RE.finditer(content):
            raw = match.group()
            email_spans.append(match.span())
            local, domain = raw.rsplit("@", 1)
            found.append(Candidate(IOCType.EMAIL, raw, f"{local}@{domain.lower()}", match.start(), match.end(), 0.9))
        for pattern in (TELEGRAM_URL_RE, TELEGRAM_AT_RE):
            for match in pattern.finditer(content):
                if any(start <= match.start() < end for start, end in email_spans):
                    continue
                username = match.group(1).lower()
                found.append(Candidate(IOCType.TELEGRAM, match.group(), f"@{username}", match.start(), match.end(), 0.9))
        return sorted(found, key=lambda item: (item.start, item.type.value))
