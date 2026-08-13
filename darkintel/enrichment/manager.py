"""Policy-enforced orchestration and case persistence for enrichment."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from .base import EnrichmentProvider
from .cache import EnrichmentCache
from .policy import EnrichmentPolicy
from ..models import EnrichmentRecord, EnrichmentResult, IOC, utc_now
from ..utils import read_json, validate_case_id, write_json

LOGGER = logging.getLogger(__name__)


class EnrichmentManager:
    def __init__(self, providers: Iterable[EnrichmentProvider], policy: EnrichmentPolicy,
                 *, root: str | Path = "cases", case_id: str | None = None) -> None:
        provider_list = list(providers)
        self.providers = {provider.name: provider for provider in provider_list}
        if len(self.providers) != len(provider_list):
            raise ValueError("provider names must be unique")
        self.policy = policy
        self.root = Path(root)
        self.case_id = case_id
        self.cache = EnrichmentCache(root, case_id) if case_id and policy.cache_enabled else None
        self.request_counts = {name: 0 for name in self.providers}
        self.cache_hits = 0
        for provider in provider_list:
            if provider.requires_network and hasattr(provider, "max_requests_for_run"):
                provider.max_requests_for_run = policy.max_requests_per_provider

    def enrich_indicator(self, indicator: IOC, providers: list[str] | None = None) -> EnrichmentResult:
        selected = providers if providers is not None else self.policy.enabled_providers
        records: list[EnrichmentRecord] = []
        warnings: list[str] = []
        for name in selected:
            provider = self.providers.get(name)
            if provider is None:
                warnings.append(f"Unknown provider skipped: {name}")
                continue
            if name not in self.policy.enabled_providers:
                warnings.append(f"Provider is not enabled by policy: {name}")
                continue
            if not provider.supports(indicator):
                records.append(self._policy_record(provider, indicator, "unsupported_indicator",
                                                   "Indicator type is unsupported"))
                continue
            if provider.requires_network and not self.policy.allow_network:
                records.append(self._policy_record(provider, indicator, "configuration_error",
                                                   "Network enrichment is disabled by policy"))
                warnings.append(f"Network provider blocked by policy: {name}")
                continue
            cached = self.cache.get(name, indicator.type.value, indicator.normalized_value) if self.cache else None
            if cached is not None:
                records.append(cached)
                self.cache_hits += 1
                continue
            if provider.requires_network and self.request_counts[name] >= self.policy.max_requests_per_provider:
                records.append(self._policy_record(provider, indicator, "rate_limited",
                                                   "Per-run provider request limit reached"))
                warnings.append(f"Request limit reached for provider: {name}")
                continue
            try:
                has_request_counter = hasattr(provider, "requests_made")
                before = int(getattr(provider, "requests_made", 0))
                provider_indicator = self._minimal_network_indicator(indicator) if provider.requires_network else indicator
                record = provider.enrich(provider_indicator)
            except Exception as exc:  # provider boundary isolation
                LOGGER.warning("provider failed: %s", name, exc_info=True)
                record = self._policy_record(provider, indicator, "provider_error",
                                             f"Provider failed safely: {type(exc).__name__}")
                warnings.append(f"Provider failure isolated: {name}")
            if provider.requires_network:
                attempts = int(getattr(provider, "requests_made", before)) - before
                self.request_counts[name] += attempts if has_request_counter else 1
            records.append(record)
            if self.cache is not None:
                self.cache.put(record, self.policy.cache_ttl_hours)
        return EnrichmentResult(indicator=indicator, records=records, warnings=warnings)

    def enrich_case(self, case_id: str | None = None, providers: list[str] | None = None,
                    limit: int | None = None) -> tuple[list[EnrichmentResult], dict[str, object]]:
        self.request_counts = {name: 0 for name in self.providers}
        self.cache_hits = 0
        for provider in self.providers.values():
            reset = getattr(provider, "reset_run", None)
            if callable(reset):
                reset()
        selected_case = case_id or self.case_id
        if selected_case is None:
            raise ValueError("case ID is required")
        validate_case_id(selected_case)
        if self.case_id not in {None, selected_case}:
            raise ValueError("manager cache is scoped to a different case")
        case_path = self.root / selected_case
        if not (case_path / "case.json").is_file():
            raise FileNotFoundError(f"case not found: {selected_case}")
        indicator_path = case_path / "extracted_iocs" / "indicators.json"
        if not indicator_path.is_file():
            raise FileNotFoundError("case has no extracted IOC records")
        payload = read_json(indicator_path)
        indicators = [IOC.from_dict(item) for item in payload.get("indicators", [])]
        effective_limit = min(limit or self.policy.max_indicators_per_run, self.policy.max_indicators_per_run)
        indicators = indicators[:effective_limit]
        results = [self.enrich_indicator(indicator, providers) for indicator in indicators]
        summary = self._persist(case_path, results)
        return results, summary

    def _persist(self, case_path: Path, results: list[EnrichmentResult]) -> dict[str, object]:
        directory = case_path / "enrichment"
        directory.mkdir(parents=True, exist_ok=True)
        records_path = directory / "records.json"
        historical = read_json(records_path).get("results", []) if records_path.is_file() else []
        historical.extend(result.to_dict() for result in results)
        write_json(records_path, {"case_id": case_path.name, "results": historical})
        provider_stats: dict[str, dict[str, int]] = {}
        observations: list[str] = []
        warning_count = 0
        for result in results:
            warning_count += len(result.warnings)
            for record in result.records:
                stats = provider_stats.setdefault(record.provider, {"success": 0, "failed": 0, "cached": 0,
                                                                     "unsupported": 0})
                if record.cached:
                    stats["cached"] += 1
                elif record.success:
                    stats["success"] += 1
                elif record.error_category == "unsupported_indicator":
                    stats["unsupported"] += 1
                else:
                    stats["failed"] += 1
                observations.extend(self._observations(record))
        summary: dict[str, object] = {
            "case_id": case_path.name,
            "generated_at": utc_now().isoformat().replace("+00:00", "Z"),
            "indicators_processed": len(results),
            "providers": provider_stats,
            "network_requests": sum(self.request_counts.values()),
            "cache_hits": self.cache_hits,
            "warnings": warning_count,
            "observations": observations[:100],
        }
        write_json(directory / "summary.json", summary)
        return summary

    @staticmethod
    def _policy_record(provider: EnrichmentProvider, indicator: IOC, category: str,
                       message: str) -> EnrichmentRecord:
        return EnrichmentRecord(provider=provider.name, indicator_type=indicator.type.value,
                                indicator_value=indicator.value, normalized_value=indicator.normalized_value,
                                success=False, error=message, error_category=category)

    @staticmethod
    def _minimal_network_indicator(indicator: IOC) -> IOC:
        """Create the explicit third-party boundary: normalized IOC only, no case metadata."""
        return IOC(type=indicator.type, value=indicator.normalized_value,
                   normalized_value=indicator.normalized_value, source=None, context=None,
                   tags=[], sources=[], observation_count=1, confidence=indicator.confidence,
                   first_seen=indicator.first_seen)

    @staticmethod
    def _observations(record: EnrichmentRecord) -> list[str]:
        prefix = f"{record.provider} claim for {record.indicator_type}:{record.normalized_value}"
        observations = []
        malicious = record.summary.get("malicious")
        if isinstance(malicious, int) and malicious > 0:
            observations.append(f"{prefix}: {malicious} malicious detections")
        score = record.summary.get("abuse_confidence_score")
        if isinstance(score, (int, float)) and score > 0:
            observations.append(f"{prefix}: abuse confidence score {score}")
        classifications = record.summary.get("classifications")
        if isinstance(classifications, list) and any(item in classifications for item in ("private", "reserved")):
            observations.append(f"{prefix}: private or reserved address")
        if not record.success:
            observations.append(f"{prefix}: unavailable ({record.error_category})")
        return observations
