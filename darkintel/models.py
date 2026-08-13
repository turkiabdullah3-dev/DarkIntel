"""Core data models for DarkIntel investigations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(slots=True)
class OnionResult:
    """HTTP observation of one onion service."""

    url: str
    is_live: bool
    status_code: int | None = None
    title: str | None = None
    response_time_ms: float | None = None
    content_type: str | None = None
    final_url: str | None = None
    sha256: str | None = None
    error: str | None = None
    observed_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.observed_at = _require_utc(self.observed_at)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["observed_at"] = self.observed_at.isoformat().replace("+00:00", "Z")
        return data


CASE_STATUSES = frozenset({"open", "closed", "archived"})


class IOCType(StrEnum):
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    DOMAIN = "domain"
    URL = "url"
    ONION = "onion"
    EMAIL = "email"
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    SHA512 = "sha512"
    BITCOIN = "bitcoin"
    MONERO = "monero"
    CVE = "cve"
    TELEGRAM = "telegram"


@dataclass(slots=True)
class IOC:
    """A normalized indicator extracted from passive evidence."""

    type: IOCType
    value: str
    normalized_value: str
    source: str | None = None
    first_seen: datetime = field(default_factory=utc_now)
    confidence: float = 0.7
    context: str | None = None
    tags: list[str] = field(default_factory=list)
    observation_count: int = 1
    sources: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.type, IOCType):
            self.type = IOCType(self.type)
        self.first_seen = _require_utc(self.first_seen)
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if self.observation_count < 1:
            raise ValueError("observation_count must be at least 1")
        if self.source and self.source not in self.sources:
            self.sources.append(self.source)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["type"] = self.type.value
        data["first_seen"] = self.first_seen.isoformat().replace("+00:00", "Z")
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IOC":
        values = dict(data)
        raw_seen = values.get("first_seen")
        if isinstance(raw_seen, str):
            values["first_seen"] = datetime.fromisoformat(raw_seen.replace("Z", "+00:00"))
        values["type"] = IOCType(values["type"])
        return cls(**values)


@dataclass(slots=True)
class ExtractionResult:
    source: str
    indicators: list[IOC]
    total_found: int = 0
    extracted_at: datetime = field(default_factory=utc_now)
    errors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.extracted_at = _require_utc(self.extracted_at)
        self.total_found = len(self.indicators)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "indicators": [indicator.to_dict() for indicator in self.indicators],
            "total_found": self.total_found,
            "extracted_at": self.extracted_at.isoformat().replace("+00:00", "Z"),
            "errors": list(self.errors),
        }


ENRICHMENT_ERROR_CATEGORIES = frozenset({
    "configuration_error", "unsupported_indicator", "network_error", "timeout",
    "authentication_error", "rate_limited", "not_found", "provider_error", "parse_error",
})


@dataclass(slots=True)
class EnrichmentRecord:
    """One provider's bounded, attributable claim about an IOC."""

    provider: str
    indicator_type: str
    indicator_value: str
    normalized_value: str
    queried_at: datetime = field(default_factory=utc_now)
    success: bool = False
    confidence: float | None = None
    summary: dict[str, object] = field(default_factory=dict)
    raw_reference: str | None = None
    error: str | None = None
    error_category: str | None = None
    expires_at: datetime | None = None
    cached: bool = False

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider name cannot be empty")
        self.queried_at = _require_utc(self.queried_at)
        if self.expires_at is not None:
            self.expires_at = _require_utc(self.expires_at)
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("provider confidence must be between 0.0 and 1.0")
        if self.error_category is not None and self.error_category not in ENRICHMENT_ERROR_CATEGORIES:
            raise ValueError("unknown enrichment error category")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["queried_at"] = self.queried_at.isoformat().replace("+00:00", "Z")
        data["expires_at"] = (self.expires_at.isoformat().replace("+00:00", "Z")
                              if self.expires_at else None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EnrichmentRecord":
        values = dict(data)
        for key in ("queried_at", "expires_at"):
            raw = values.get(key)
            if isinstance(raw, str):
                values[key] = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return cls(**values)


@dataclass(slots=True)
class EnrichmentResult:
    indicator: IOC
    records: list[EnrichmentRecord]
    enriched_at: datetime = field(default_factory=utc_now)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.enriched_at = _require_utc(self.enriched_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "indicator": self.indicator.to_dict(),
            "records": [record.to_dict() for record in self.records],
            "enriched_at": self.enriched_at.isoformat().replace("+00:00", "Z"),
            "warnings": list(self.warnings),
        }


@dataclass(slots=True)
class InvestigationCase:
    """Persistent metadata for an investigation case."""

    case_id: str
    name: str
    description: str = ""
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    status: str = "open"
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.status not in CASE_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(CASE_STATUSES))}")
        self.created_at = _require_utc(self.created_at)
        self.updated_at = _require_utc(self.updated_at)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("created_at", "updated_at"):
            data[key] = data[key].isoformat().replace("+00:00", "Z")
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InvestigationCase":
        values = dict(data)
        for key in ("created_at", "updated_at"):
            raw = values[key]
            if isinstance(raw, str):
                values[key] = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return cls(**values)
