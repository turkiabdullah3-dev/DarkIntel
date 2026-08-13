"""Conservative enrichment governance policy."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class EnrichmentPolicy:
    enabled_providers: list[str] = field(default_factory=lambda: ["local"])
    max_indicators_per_run: int = 50
    max_requests_per_provider: int = 25
    allow_network: bool = False
    cache_enabled: bool = True
    cache_ttl_hours: int = 24

    def __post_init__(self) -> None:
        self.enabled_providers = list(dict.fromkeys(self.enabled_providers))
        if self.max_indicators_per_run < 1 or self.max_requests_per_provider < 1:
            raise ValueError("enrichment limits must be positive")
        if self.cache_ttl_hours < 1:
            raise ValueError("cache TTL must be positive")
