from darkintel.extractors.network import NetworkExtractor
from darkintel.models import IOCType

ONION = "a" * 56 + ".onion"


def values(content, indicator_type):
    return [item.normalized_value for item in NetworkExtractor().extract(content) if item.type == indicator_type]


def test_ipv4_validation_and_classification():
    candidates = NetworkExtractor().extract("public 8.8.8.8 private 192.168.1.5 invalid 999.999.999.999")
    ipv4 = [item for item in candidates if item.type == IOCType.IPV4]
    assert [item.normalized_value for item in ipv4] == ["8.8.8.8", "192.168.1.5"]
    assert "public" in ipv4[0].tags
    assert "private" in ipv4[1].tags


def test_ipv6_is_parser_validated_and_compressed():
    assert values("node 2001:0db8:0000:0000:0000:ff00:0042:8329 bad 2001:::1", IOCType.IPV6) == [
        "2001:db8::ff00:42:8329"
    ]


def test_domain_and_url_normalization():
    content = "Example.COM and HTTPS://Example.COM/Path?q=One plus report.pdf and v1.2.3"
    assert "example.com" in values(content, IOCType.DOMAIN)
    assert "https://example.com/Path?q=One" in values(content, IOCType.URL)
    assert "report.pdf" not in values(content, IOCType.DOMAIN)


def test_onion_reuses_strict_v3_validation():
    assert values(f"valid {ONION} invalid short.onion", IOCType.ONION) == [ONION]


def test_url_does_not_execute_or_accept_credentials():
    assert values("http://user:pass@example.com/x", IOCType.URL) == []  # pragma: allowlist secret
