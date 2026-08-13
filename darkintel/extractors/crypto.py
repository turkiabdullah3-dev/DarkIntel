"""Offline cryptocurrency address detection; no wallet or chain interaction."""

from __future__ import annotations

import hashlib
import re

from .base import Candidate
from ..models import IOCType

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BTC_BASE58_RE = re.compile(r"(?<![A-Za-z0-9])[13][1-9A-HJ-NP-Za-km-z]{25,34}(?![A-Za-z0-9])")
BTC_BECH32_RE = re.compile(r"(?i)(?<![a-z0-9])bc1[ac-hj-np-z02-9]{11,71}(?![a-z0-9])")
MONERO_RE = re.compile(r"(?<![1-9A-HJ-NP-Za-km-z])[48][1-9A-HJ-NP-Za-km-z]{94}(?![1-9A-HJ-NP-Za-km-z])")


def _base58check_valid(value: str) -> bool:
    number = 0
    try:
        for char in value:
            number = number * 58 + BASE58_ALPHABET.index(char)
    except ValueError:
        return False
    decoded = number.to_bytes((number.bit_length() + 7) // 8, "big")
    decoded = b"\x00" * (len(value) - len(value.lstrip("1"))) + decoded
    if len(decoded) != 25:
        return False
    checksum = hashlib.sha256(hashlib.sha256(decoded[:-4]).digest()).digest()[:4]
    return decoded[-4:] == checksum and decoded[0] in {0, 5}


def _bech32_polymod(values: list[int]) -> int:
    generators = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
    checksum = 1
    for value in values:
        top = checksum >> 25
        checksum = ((checksum & 0x1FFFFFF) << 5) ^ value
        for index, generator in enumerate(generators):
            if (top >> index) & 1:
                checksum ^= generator
    return checksum


def _bech32_valid(value: str) -> bool:
    if value.lower() != value and value.upper() != value:
        return False
    value = value.lower()
    separator = value.rfind("1")
    charset = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
    if separator < 1 or separator + 7 > len(value) or len(value) > 90:
        return False
    try:
        data = [charset.index(char) for char in value[separator + 1:]]
    except ValueError:
        return False
    hrp = value[:separator]
    expanded = [ord(char) >> 5 for char in hrp] + [0] + [ord(char) & 31 for char in hrp]
    return _bech32_polymod(expanded + data) in {1, 0x2BC830A3}


class CryptoExtractor:
    name = "crypto"

    def extract(self, content: str) -> list[Candidate]:
        found = []
        for match in BTC_BASE58_RE.finditer(content):
            if _base58check_valid(match.group()):
                found.append(Candidate(IOCType.BITCOIN, match.group(), match.group(), match.start(), match.end(), 1.0,
                                       ("base58check",)))
        for match in BTC_BECH32_RE.finditer(content):
            if _bech32_valid(match.group()):
                found.append(Candidate(IOCType.BITCOIN, match.group(), match.group().lower(), match.start(), match.end(),
                                       1.0, ("bech32",)))
        for match in MONERO_RE.finditer(content):
            found.append(Candidate(IOCType.MONERO, match.group(), match.group(), match.start(), match.end(), 0.8,
                                   ("standard-address-shape",)))
        return found
