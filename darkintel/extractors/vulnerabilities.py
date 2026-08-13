"""CVE identifier extraction without exploitation-state inference."""

from __future__ import annotations

import re

from .base import Candidate
from ..models import IOCType

CVE_RE = re.compile(r"(?i)(?<![a-z0-9-])CVE-(1999|2\d{3})-(\d{4,})(?![a-z0-9-])")


class VulnerabilityExtractor:
    name = "vulnerabilities"

    def extract(self, content: str) -> list[Candidate]:
        return [Candidate(IOCType.CVE, match.group(), match.group().upper(), match.start(), match.end(), 1.0)
                for match in CVE_RE.finditer(content)]
