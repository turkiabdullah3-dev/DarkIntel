"""Bounded read-only VirusTotal API v3 enrichment."""

from __future__ import annotations

import base64
import os
from urllib.parse import quote

from ..base import HTTPSProvider, ProviderRequestError, bound_summary
from ...models import EnrichmentRecord, IOC


class VirusTotalProvider(HTTPSProvider):
    name = "virustotal"
    supported_types = frozenset({"ipv4", "domain", "url", "md5", "sha1", "sha256"})
    allowed_hosts = frozenset({"www.virustotal.com"})

    def enrich(self, indicator: IOC) -> EnrichmentRecord:
        if not self.supports(indicator):
            return self._error_record(indicator, ProviderRequestError("unsupported_indicator", "Indicator type is unsupported"))
        api_key = os.environ.get("DARKINTEL_VT_API_KEY")
        if not api_key:
            return self._error_record(indicator, ProviderRequestError("configuration_error", "VirusTotal API key is not configured"))
        kind = indicator.type.value
        if kind == "ipv4":
            endpoint, identifier = "ip_addresses", indicator.normalized_value
        elif kind == "domain":
            endpoint, identifier = "domains", indicator.normalized_value
        elif kind == "url":
            endpoint = "urls"
            identifier = base64.urlsafe_b64encode(indicator.normalized_value.encode()).decode().rstrip("=")
        else:
            endpoint, identifier = "files", indicator.normalized_value
        url = f"https://www.virustotal.com/api/v3/{endpoint}/{quote(identifier, safe='')}"
        try:
            payload = self._get_json(url, headers={"x-apikey": api_key})
            data = payload.get("data")
            if not isinstance(data, dict) or not isinstance(data.get("attributes"), dict):
                raise ProviderRequestError("parse_error", "VirusTotal returned an unexpected response")
            attributes = data["attributes"]
            summary: dict[str, object] = {}
            stats = attributes.get("last_analysis_stats")
            if isinstance(stats, dict):
                for key in ("malicious", "suspicious", "harmless", "undetected"):
                    if isinstance(stats.get(key), int):
                        summary[key] = stats[key]
            for key in ("reputation", "last_analysis_date", "popular_threat_classification"):
                if key in attributes:
                    summary[key] = attributes[key]
            categories = attributes.get("categories")
            if isinstance(categories, dict):
                summary["categories"] = sorted(set(str(value) for value in categories.values()))[:20]
            return EnrichmentRecord(provider=self.name, indicator_type=kind, indicator_value=indicator.value,
                                    normalized_value=indicator.normalized_value, success=True,
                                    summary=bound_summary(summary))
        except ProviderRequestError as exc:
            return self._error_record(indicator, exc)
