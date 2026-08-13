import json
from unittest.mock import Mock

import pytest

from darkintel.enrichment.base import MAX_PROVIDER_RESPONSE_BYTES, bound_summary
from darkintel.enrichment.providers.rdap import RDAPProvider
from darkintel.models import EnrichmentRecord, IOC, IOCType


def response(status, payload, headers=None):
    result = Mock()
    result.status_code = status
    result.content = json.dumps(payload).encode() if not isinstance(payload, bytes) else payload
    result.headers = headers or {}
    return result


def test_provider_declares_type_support():
    provider = RDAPProvider(minimum_request_interval=0)
    assert provider.supports(IOC(IOCType.DOMAIN, "example.com", "example.com"))
    assert not provider.supports(IOC(IOCType.EMAIL, "a@example.com", "a@example.com"))


def test_enrichment_record_serialization_and_validation():
    record = EnrichmentRecord("local", "domain", "Example.COM", "example.com", success=True)
    payload = record.to_dict()
    assert payload["queried_at"].endswith("Z")
    assert EnrichmentRecord.from_dict(payload).provider == "local"
    with pytest.raises(ValueError, match="confidence"):
        EnrichmentRecord("local", "domain", "x", "x", confidence=2)


def test_raw_response_size_limit():
    session = Mock()
    session.get.return_value = response(200, b"x" * (MAX_PROVIDER_RESPONSE_BYTES + 1))
    provider = RDAPProvider(session=session, minimum_request_interval=0, max_retries=0)
    record = provider.enrich(IOC(IOCType.DOMAIN, "example.com", "example.com"))
    assert record.error_category == "parse_error"
    assert "size limit" in record.error


def test_https_request_has_timeout_tls_and_no_redirects():
    session = Mock()
    session.get.return_value = response(200, {"name": "EXAMPLE"})
    RDAPProvider(session=session, timeout=4, minimum_request_interval=0).enrich(
        IOC(IOCType.DOMAIN, "example.com", "example.com"))
    assert session.get.call_args.kwargs["timeout"] == 4
    assert session.get.call_args.kwargs["verify"] is True
    assert session.get.call_args.kwargs["allow_redirects"] is False


def test_nested_summary_values_are_bounded():
    bounded = bound_summary({"claim": "x" * 1000, "items": list(range(100))})
    assert len(bounded["claim"]) == 500
    assert len(bounded["items"]) == 20
