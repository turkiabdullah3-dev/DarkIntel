"""Provider contracts and bounded HTTPS request support."""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
import ipaddress
import time
from typing import Any, Callable
from urllib.parse import urljoin, urlsplit

import requests

from ..models import EnrichmentRecord, IOC

MAX_PROVIDER_RESPONSE_BYTES = 1_000_000
MAX_SUMMARY_STRING_CHARS = 500


def bound_summary(value: Any, depth: int = 0) -> object:
    """Bound provider-selected data before it enters analyst records."""
    if depth >= 3:
        return "[bounded]"
    if isinstance(value, str):
        return value[:MAX_SUMMARY_STRING_CHARS]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [bound_summary(item, depth + 1) for item in value[:20]]
    if isinstance(value, dict):
        return {str(key)[:100]: bound_summary(item, depth + 1)
                for key, item in list(value.items())[:20]}
    return str(value)[:MAX_SUMMARY_STRING_CHARS]


class ProviderRequestError(Exception):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category
        self.safe_message = message


class EnrichmentProvider(ABC):
    name: str
    supported_types: frozenset[str]
    requires_network: bool = False

    def supports(self, indicator: IOC) -> bool:
        return indicator.type.value in self.supported_types

    @abstractmethod
    def enrich(self, indicator: IOC) -> EnrichmentRecord:
        """Return one bounded provider record."""


class HTTPSProvider(EnrichmentProvider):
    """HTTPS-only base with throttling, bounded responses, and one bounded retry."""

    requires_network = True
    allowed_hosts: frozenset[str]
    allow_external_https_redirects: bool = False

    def __init__(self, *, session: requests.Session | None = None, timeout: float = 10.0,
                 minimum_request_interval: float = 0.25, max_retries: int = 1,
                 sleeper: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if timeout <= 0 or minimum_request_interval < 0 or max_retries not in {0, 1}:
            raise ValueError("invalid provider request settings")
        self.session = session or requests.Session()
        self.timeout = timeout
        self.minimum_request_interval = minimum_request_interval
        self.max_retries = max_retries
        self._sleep = sleeper
        self._clock = clock
        self._last_request_at: float | None = None
        self.requests_made = 0
        self.max_requests_for_run: int | None = None

    def reset_run(self) -> None:
        self.requests_made = 0
        self._last_request_at = None

    def _get_json(self, url: str, *, headers: dict[str, str] | None = None,
                  params: dict[str, object] | None = None, _redirects: int = 0) -> dict[str, Any]:
        parsed = urlsplit(url)
        approved_redirect = _redirects > 0 and self.allow_external_https_redirects and self._safe_redirect_host(parsed.hostname)
        if parsed.scheme != "https" or (parsed.hostname not in self.allowed_hosts and not approved_redirect):
            raise ProviderRequestError("configuration_error", "Provider endpoint is not an approved HTTPS host")
        for attempt in range(self.max_retries + 1):
            if self.max_requests_for_run is not None and self.requests_made >= self.max_requests_for_run:
                raise ProviderRequestError("rate_limited", "Per-run provider request limit reached")
            self._throttle()
            try:
                response = self.session.get(url, headers=headers, params=params, timeout=self.timeout,
                                            allow_redirects=False, verify=True)
                self.requests_made += 1
            except requests.Timeout as exc:
                raise ProviderRequestError("timeout", "Provider request timed out") from exc
            except requests.RequestException as exc:
                raise ProviderRequestError("network_error", "Provider network request failed") from exc
            if 300 <= response.status_code < 400 and self.allow_external_https_redirects:
                if _redirects >= 2:
                    raise ProviderRequestError("provider_error", "Provider redirect limit reached")
                location = response.headers.get("Location")
                redirected = urlsplit(urljoin(url, location or ""))
                if (redirected.scheme != "https" or redirected.username is not None or redirected.password is not None
                        or not self._safe_redirect_host(redirected.hostname)):
                    raise ProviderRequestError("provider_error", "Provider redirect was refused")
                return self._get_json(redirected.geturl(), headers=headers, params=None, _redirects=_redirects + 1)
            if response.status_code == 429 and attempt < self.max_retries:
                retry_after = response.headers.get("Retry-After", "0")
                try:
                    delay = min(max(float(retry_after), 0.0), 5.0)
                except ValueError:
                    delay = 0.0
                if delay:
                    self._sleep(delay)
                continue
            self._raise_for_status(response.status_code)
            raw = response.content
            declared = response.headers.get("Content-Length")
            if declared and declared.isdigit() and int(declared) > MAX_PROVIDER_RESPONSE_BYTES:
                raise ProviderRequestError("parse_error", "Provider response exceeded size limit")
            if len(raw) > MAX_PROVIDER_RESPONSE_BYTES:
                raise ProviderRequestError("parse_error", "Provider response exceeded size limit")
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise ProviderRequestError("parse_error", "Provider returned malformed JSON") from exc
            if not isinstance(payload, dict):
                raise ProviderRequestError("parse_error", "Provider returned an unexpected JSON shape")
            return payload
        raise ProviderRequestError("rate_limited", "Provider rate limit reached")

    @staticmethod
    def _safe_redirect_host(hostname: str | None) -> bool:
        if not hostname or hostname.lower() == "localhost":
            return False
        try:
            address = ipaddress.ip_address(hostname)
            return address.is_global
        except ValueError:
            return "." in hostname and not hostname.endswith(".local")

    def _throttle(self) -> None:
        now = self._clock()
        if self._last_request_at is not None:
            remaining = self.minimum_request_interval - (now - self._last_request_at)
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_at = self._clock()

    @staticmethod
    def _raise_for_status(status: int) -> None:
        if 200 <= status < 300:
            return
        if status in {401, 403}:
            raise ProviderRequestError("authentication_error", "Provider authentication failed")
        if status == 404:
            raise ProviderRequestError("not_found", "Indicator was not found by provider")
        if status == 429:
            raise ProviderRequestError("rate_limited", "Provider rate limit reached")
        if 300 <= status < 400:
            raise ProviderRequestError("provider_error", "Provider redirect was refused")
        raise ProviderRequestError("provider_error", f"Provider returned HTTP {status}")

    def _error_record(self, indicator: IOC, error: ProviderRequestError) -> EnrichmentRecord:
        return EnrichmentRecord(provider=self.name, indicator_type=indicator.type.value,
                                indicator_value=indicator.value, normalized_value=indicator.normalized_value,
                                success=False, error=error.safe_message, error_category=error.category)
