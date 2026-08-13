"""Read-only AbuseIPDB address check provider."""

from __future__ import annotations

import os

from ..base import HTTPSProvider, ProviderRequestError, bound_summary
from ...models import EnrichmentRecord, IOC


class AbuseIPDBProvider(HTTPSProvider):
    name = "abuseipdb"
    supported_types = frozenset({"ipv4"})
    allowed_hosts = frozenset({"api.abuseipdb.com"})

    def enrich(self, indicator: IOC) -> EnrichmentRecord:
        if not self.supports(indicator):
            return self._error_record(indicator, ProviderRequestError("unsupported_indicator", "Indicator type is unsupported"))
        api_key = os.environ.get("DARKINTEL_ABUSEIPDB_API_KEY")
        if not api_key:
            return self._error_record(indicator, ProviderRequestError("configuration_error", "AbuseIPDB API key is not configured"))
        try:
            payload = self._get_json("https://api.abuseipdb.com/api/v2/check",
                                     headers={"Key": api_key, "Accept": "application/json"},
                                     params={"ipAddress": indicator.normalized_value, "maxAgeInDays": 90})
            data = payload.get("data")
            if not isinstance(data, dict):
                raise ProviderRequestError("parse_error", "AbuseIPDB returned an unexpected response")
            fields = ("abuseConfidenceScore", "countryCode", "usageType", "isp", "domain",
                      "totalReports", "lastReportedAt")
            names = ("abuse_confidence_score", "country_code", "usage_type", "isp", "domain",
                     "total_reports", "last_reported_at")
            summary = {target: data[source] for source, target in zip(fields, names) if source in data}
            confidence = data.get("abuseConfidenceScore")
            provider_confidence = confidence / 100 if isinstance(confidence, (int, float)) else None
            return EnrichmentRecord(provider=self.name, indicator_type=indicator.type.value,
                                    indicator_value=indicator.value, normalized_value=indicator.normalized_value,
                                    success=True, confidence=provider_confidence, summary=bound_summary(summary))
        except ProviderRequestError as exc:
            return self._error_record(indicator, exc)
