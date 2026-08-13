from darkintel.extractors.vulnerabilities import VulnerabilityExtractor


def test_cve_extraction_and_normalization():
    found = VulnerabilityExtractor().extract("cve-2024-12345 and CVE-1999-0001")
    assert [item.normalized_value for item in found] == ["CVE-2024-12345", "CVE-1999-0001"]


def test_malformed_cves_rejected():
    assert VulnerabilityExtractor().extract("CVE-24-1234 CVE-2024-123 CVE-2024-12x4") == []
