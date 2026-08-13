"""Read-only HTTPS RDAP enrichment."""

from __future__ import annotations

from urllib.parse import quote

from ..base import HTTPSProvider, ProviderRequestError, bound_summary
from ...models import EnrichmentRecord, IOC


class RDAPProvider(HTTPSProvider):
    name = "rdap"
    supported_types = frozenset({"ipv4", "ipv6", "domain"})
    allowed_hosts = frozenset({"rdap.org"})
    allow_external_https_redirects = True

    def enrich(self, indicator: IOC) -> EnrichmentRecord:
        if not self.supports(indicator):
            return self._error_record(indicator, ProviderRequestError("unsupported_indicator", "Indicator type is unsupported"))
        category = "domain" if indicator.type.value == "domain" else "ip"
        url = f"https://rdap.org/{category}/{quote(indicator.normalized_value, safe='')}"
        try:
            payload = self._get_json(url)
            summary = self._summarize(payload)
            return EnrichmentRecord(provider=self.name, indicator_type=indicator.type.value,
                                    indicator_value=indicator.value, normalized_value=indicator.normalized_value,
                                    success=True, summary=bound_summary(summary))
        except ProviderRequestError as exc:
            return self._error_record(indicator, exc)

    @staticmethod
    def _summarize(payload: dict[str, object]) -> dict[str, object]:
        summary: dict[str, object] = {}
        direct = {"country": "country", "name": "network_name", "cidr0_cidrs": "cidr",
                  "port43": "registrar", "handle": "handle", "status": "status"}
        for source, target in direct.items():
            value = payload.get(source)
            if value not in (None, "", []):
                summary[target] = value if not isinstance(value, list) else value[:20]
        events = payload.get("events")
        if isinstance(events, list):
            event_names = {"registration": "registration_date", "expiration": "expiration_date",
                           "last changed": "last_changed"}
            for event in events[:30]:
                if isinstance(event, dict) and event.get("eventAction") in event_names:
                    summary[event_names[str(event["eventAction"])]] = event.get("eventDate")
        entities = payload.get("entities")
        if isinstance(entities, list):
            for entity in entities[:20]:
                if isinstance(entity, dict) and "registrar" in entity.get("roles", []):
                    summary["registrar"] = entity.get("handle")
                    break
        if not summary:
            raise ProviderRequestError("parse_error", "RDAP response contained no supported fields")
        return summary
