import pytest

from darkintel.enrichment.providers.local import LocalProvider
from darkintel.models import IOC, IOCType


@pytest.mark.parametrize("indicator,field", [
    (IOC(IOCType.IPV4, "127.0.0.1", "127.0.0.1"), "classifications"),
    (IOC(IOCType.SHA256, "a" * 64, "a" * 64), "hash_family"),
    (IOC(IOCType.DOMAIN, "Example.COM", "example.com"), "top_level_domain"),
    (IOC(IOCType.ONION, "a" * 56 + ".onion", "a" * 56 + ".onion"), "tor_version"),
    (IOC(IOCType.CVE, "cve-2024-1234", "CVE-2024-1234"), "year"),
])
def test_local_provider(indicator, field):
    provider = LocalProvider()
    record = provider.enrich(indicator)
    assert provider.requires_network is False
    assert record.success
    assert field in record.summary


def test_local_unsupported_type():
    record = LocalProvider().enrich(IOC(IOCType.EMAIL, "a@example.com", "a@example.com"))
    assert record.error_category == "unsupported_indicator"
