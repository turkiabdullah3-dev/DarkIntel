from darkintel.extractors.crypto import CryptoExtractor
from darkintel.models import IOCType


def test_bitcoin_base58check_validation():
    valid = "1BoatSLRHtKNngkdXEeobR76b53LETtpyT"
    invalid = "1BoatSLRHtKNngkdXEeobR76b53LETtpyU"
    found = CryptoExtractor().extract(f"pay {valid} not {invalid}")
    assert [(item.type, item.value) for item in found] == [(IOCType.BITCOIN, valid)]


def test_bitcoin_bech32_validation_and_normalization():
    address = "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"
    found = CryptoExtractor().extract(address.upper())
    assert found[0].type == IOCType.BITCOIN
    assert found[0].normalized_value == address


def test_monero_standard_shape_detection():
    address = "4" + "A" * 94
    found = CryptoExtractor().extract(f"Monero: {address}")
    assert found[0].type == IOCType.MONERO
    assert found[0].confidence == 0.8


def test_monero_invalid_length_rejected():
    assert CryptoExtractor().extract("4" + "A" * 93) == []
