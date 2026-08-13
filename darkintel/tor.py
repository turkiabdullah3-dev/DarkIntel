"""Safe, unprivileged Tor SOCKS endpoint detection."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import socket
from typing import Any


@dataclass(frozen=True, slots=True)
class TorStatus:
    available: bool
    host: str
    port: int
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_tor(host: str = "127.0.0.1", port: int = 9050, timeout: float = 1.0) -> TorStatus:
    """Check whether a local SOCKS listener is reachable without changing the system."""
    if not host:
        return TorStatus(False, host, port, "Tor host cannot be empty")
    if not 1 <= port <= 65535:
        return TorStatus(False, host, port, "Tor port must be between 1 and 65535")
    if timeout <= 0:
        return TorStatus(False, host, port, "timeout must be greater than zero")
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return TorStatus(True, host, port)
    except OSError as exc:
        return TorStatus(False, host, port, f"Tor SOCKS endpoint unavailable: {exc}")


def is_tor_available(host: str = "127.0.0.1", port: int = 9050, timeout: float = 1.0) -> bool:
    """Return whether the configured Tor SOCKS port accepts connections."""
    return check_tor(host, port, timeout).available
