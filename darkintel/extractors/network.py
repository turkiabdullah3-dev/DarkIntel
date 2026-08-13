"""Offline extraction and normalization of network indicators."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit

from .base import Candidate
from ..models import IOCType
from ..verifier import OnionValidationError, normalize_onion_url

URL_RE = re.compile(r"(?i)\bhttps?://[^\s<>\"']+")
IPV4_RE = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
IPV6_TOKEN_RE = re.compile(r"(?<![\w:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![\w:])")
DOMAIN_RE = re.compile(r"(?i)(?<![@\w.-])(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}(?![\w.-])")
ONION_RE = re.compile(r"(?i)(?<![a-z2-7])(?:[a-z2-7]{56}\.onion)(?![a-z2-7.-])")
TRAILING_URL_PUNCTUATION = ".,;:!?)]}"


def _ip_tags(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> tuple[str, ...]:
    tags = []
    for label, flag in (("private", address.is_private), ("loopback", address.is_loopback),
                        ("reserved", address.is_reserved), ("multicast", address.is_multicast)):
        if flag:
            tags.append(label)
    if not tags and address.is_global:
        tags.append("public")
    return tuple(tags)


class NetworkExtractor:
    name = "network"

    def extract(self, content: str) -> list[Candidate]:
        found: list[Candidate] = []
        for match in URL_RE.finditer(content):
            raw = match.group().rstrip(TRAILING_URL_PUNCTUATION)
            try:
                parsed = urlsplit(raw)
                port = parsed.port
                if parsed.username is not None or parsed.password is not None or not parsed.hostname:
                    continue
                host = parsed.hostname.lower()
                netloc = host if port is None else f"{host}:{port}"
                normalized = urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "/", parsed.query, ""))
            except (ValueError, UnicodeError):
                continue
            found.append(Candidate(IOCType.URL, raw, normalized, match.start(), match.start() + len(raw), 0.9))

        for match in ONION_RE.finditer(content):
            raw = match.group()
            try:
                normalized = urlsplit(normalize_onion_url(raw)).hostname
            except OnionValidationError:
                continue
            if normalized:
                found.append(Candidate(IOCType.ONION, raw, normalized, match.start(), match.end(), 1.0, ("tor-v3",)))

        for match in IPV4_RE.finditer(content):
            try:
                address = ipaddress.ip_address(match.group())
            except ValueError:
                continue
            if address.version == 4:
                found.append(Candidate(IOCType.IPV4, match.group(), str(address), match.start(), match.end(), 1.0,
                                       _ip_tags(address)))

        for match in IPV6_TOKEN_RE.finditer(content):
            raw = match.group()
            if raw in {"::", ":"}:
                continue
            try:
                address = ipaddress.ip_address(raw)
            except ValueError:
                continue
            if address.version == 6:
                found.append(Candidate(IOCType.IPV6, raw, address.compressed, match.start(), match.end(), 1.0,
                                       _ip_tags(address)))

        for match in DOMAIN_RE.finditer(content):
            raw = match.group()
            normalized = raw.rstrip(".").lower()
            if normalized.endswith(".onion") or _is_ip(normalized) or _looks_like_filename(normalized):
                continue
            found.append(Candidate(IOCType.DOMAIN, raw, normalized, match.start(), match.end(), 0.8))
        return found


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _looks_like_filename(value: str) -> bool:
    suffix = value.rsplit(".", 1)[-1]
    return suffix in {"exe", "dll", "sys", "zip", "pdf", "html", "txt", "json", "csv", "log", "py", "js"}
