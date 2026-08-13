"""Zero-network local metadata provider."""

from __future__ import annotations

import ipaddress
import re

from ..base import EnrichmentProvider
from ...models import EnrichmentRecord, IOC
from ...verifier import OnionValidationError, normalize_onion_url


class LocalProvider(EnrichmentProvider):
    name = "local"
    supported_types = frozenset({"ipv4", "ipv6", "domain", "onion", "md5", "sha1", "sha256", "sha512", "cve"})

    def enrich(self, indicator: IOC) -> EnrichmentRecord:
        if not self.supports(indicator):
            return EnrichmentRecord(provider=self.name, indicator_type=indicator.type.value,
                                    indicator_value=indicator.value, normalized_value=indicator.normalized_value,
                                    success=False, error="Indicator type is unsupported",
                                    error_category="unsupported_indicator")
        try:
            summary = self._summary(indicator)
            return EnrichmentRecord(provider=self.name, indicator_type=indicator.type.value,
                                    indicator_value=indicator.value, normalized_value=indicator.normalized_value,
                                    success=True, confidence=1.0, summary=summary)
        except ValueError:
            return EnrichmentRecord(provider=self.name, indicator_type=indicator.type.value,
                                    indicator_value=indicator.value, normalized_value=indicator.normalized_value,
                                    success=False, error="Indicator failed local validation", error_category="parse_error")

    @staticmethod
    def _summary(indicator: IOC) -> dict[str, object]:
        kind = indicator.type.value
        value = indicator.normalized_value
        if kind in {"ipv4", "ipv6"}:
            address = ipaddress.ip_address(value)
            classifications = [name for name, enabled in (
                ("private", address.is_private), ("public", address.is_global),
                ("loopback", address.is_loopback), ("multicast", address.is_multicast),
                ("reserved", address.is_reserved), ("link-local", address.is_link_local),
            ) if enabled]
            return {"version": address.version, "compressed": address.compressed,
                    "classifications": classifications}
        if kind in {"md5", "sha1", "sha256", "sha512"}:
            return {"hash_family": kind, "hex_length": len(value)}
        if kind == "domain":
            labels = value.rstrip(".").split(".")
            if len(labels) < 2 or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label,
                                                       re.IGNORECASE) for label in labels):
                raise ValueError("invalid domain")
            return {"labels": len(labels), "top_level_domain": labels[-1].lower(),
                    "ascii_length": len(value.encode("idna"))}
        if kind == "onion":
            host = normalize_onion_url(value).split("/", 3)[2]
            return {"tor_version": 3, "hostname": host, "valid": True}
        match = re.fullmatch(r"CVE-(1999|2\d{3})-(\d{4,})", value, re.IGNORECASE)
        if not match:
            raise ValueError("invalid CVE")
        return {"year": int(match.group(1)), "identifier": match.group(2), "normalized": value.upper()}
