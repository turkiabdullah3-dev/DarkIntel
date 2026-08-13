"""Passive onion-service HTTP verification through Tor."""

from __future__ import annotations

import hashlib
import logging
import re
from time import perf_counter
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup
import requests

from .models import OnionResult, utc_now
from .tor import check_tor

LOGGER = logging.getLogger(__name__)
V3_ONION_RE = re.compile(r"^[a-z2-7]{56}\.onion$")


class OnionValidationError(ValueError):
    """Raised when an input is not a supported Tor v3 onion URL."""


def normalize_onion_url(value: str) -> str:
    """Normalize and strictly validate an HTTP(S) Tor v3 onion URL."""
    if not isinstance(value, str) or not value.strip():
        raise OnionValidationError("onion URL cannot be empty")
    candidate = value.strip()
    if "://" not in candidate:
        candidate = f"http://{candidate}"
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except (ValueError, UnicodeError) as exc:
        raise OnionValidationError(f"malformed onion URL: {exc}") from exc
    if parsed.scheme.lower() not in {"http", "https"}:
        raise OnionValidationError("only http and https schemes are supported")
    if parsed.username is not None or parsed.password is not None:
        raise OnionValidationError("embedded credentials are not allowed")
    if not parsed.hostname:
        raise OnionValidationError("URL must include a hostname")
    hostname = parsed.hostname.lower()
    if not V3_ONION_RE.fullmatch(hostname):
        raise OnionValidationError("hostname must be a valid 56-character Tor v3 .onion address")
    netloc = hostname if port is None else f"{hostname}:{port}"
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme.lower(), netloc, path, parsed.query, ""))


def _extract_title(body: bytes, encoding: str | None) -> str | None:
    try:
        soup = BeautifulSoup(body, "html.parser", from_encoding=encoding)
        if soup.title:
            title = soup.title.get_text(" ", strip=True)
            return title or None
    except (TypeError, ValueError, UnicodeError):
        LOGGER.debug("Could not parse page title", exc_info=True)
    return None


class OnionVerifier:
    """Reusable verifier configured for a single Tor SOCKS endpoint."""

    def __init__(self, tor_host: str = "127.0.0.1", tor_port: int = 9050,
                 timeout: float = 15.0, session: requests.Session | None = None) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        self.tor_host = tor_host
        self.tor_port = tor_port
        self.timeout = timeout
        self.session = session or requests.Session()
        proxy = f"socks5h://{tor_host}:{tor_port}"
        self.session.proxies.update({"http": proxy, "https": proxy})

    def verify(self, value: str, *, require_tor_check: bool = True) -> OnionResult:
        observed_at = utc_now()
        try:
            url = normalize_onion_url(value)
        except OnionValidationError as exc:
            LOGGER.warning("validation failed: %s", exc)
            return OnionResult(url=str(value), is_live=False, error=f"Validation error: {exc}", observed_at=observed_at)

        LOGGER.info("verification started: %s", url)
        if require_tor_check:
            status = check_tor(self.tor_host, self.tor_port, min(self.timeout, 2.0))
            if not status.available:
                LOGGER.warning("target unreachable: Tor unavailable")
                return OnionResult(url=url, is_live=False, error=status.error, observed_at=observed_at)

        started = perf_counter()
        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            elapsed_ms = round((perf_counter() - started) * 1000, 3)
            body = response.content or b""
            content_type = response.headers.get("Content-Type")
            media_type = content_type.split(";", 1)[0].strip().lower() if content_type else ""
            title = _extract_title(body, response.encoding) if media_type in {"text/html", "application/xhtml+xml"} else None
            result = OnionResult(
                url=url,
                is_live=True,
                status_code=response.status_code,
                title=title,
                response_time_ms=elapsed_ms,
                content_type=content_type,
                final_url=response.url,
                sha256=hashlib.sha256(body).hexdigest(),
                error=None if response.ok else f"HTTP {response.status_code}",
                observed_at=observed_at,
            )
            LOGGER.info("target reachable: %s status=%s", url, response.status_code)
            return result
        except requests.RequestException as exc:
            elapsed_ms = round((perf_counter() - started) * 1000, 3)
            LOGGER.warning("target unreachable: %s", url)
            return OnionResult(url=url, is_live=False, response_time_ms=elapsed_ms,
                               error=f"{type(exc).__name__}: {exc}", observed_at=observed_at)


def verify_onion(value: str, **kwargs: object) -> OnionResult:
    """Convenience wrapper for one verification."""
    return OnionVerifier(**kwargs).verify(value)
