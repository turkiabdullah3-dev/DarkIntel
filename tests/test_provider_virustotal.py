import json
from unittest.mock import Mock

from darkintel.enrichment.providers.virustotal import VirusTotalProvider
from darkintel.models import IOC, IOCType


def make_response(status, payload, headers=None):
    response = Mock(status_code=status, headers=headers or {})
    response.content = json.dumps(payload).encode()
    return response


def test_vt_missing_key(monkeypatch):
    monkeypatch.delenv("DARKINTEL_VT_API_KEY", raising=False)
    session = Mock()
    record = VirusTotalProvider(session=session).enrich(IOC(IOCType.DOMAIN, "x.test", "x.test"))
    assert record.error_category == "configuration_error"
    session.get.assert_not_called()


def test_vt_success_is_bounded_and_attributed(monkeypatch):
    monkeypatch.setenv("DARKINTEL_VT_API_KEY", "super-secret")
    session = Mock()
    session.get.return_value = make_response(200, {"data": {"attributes": {
        "last_analysis_stats": {"malicious": 3, "harmless": 10, "timeout": 7},
        "reputation": -5, "categories": {"a": "phishing", "b": "phishing"},
        "irrelevant_large_field": "ignored",
    }}})
    record = VirusTotalProvider(session=session, minimum_request_interval=0).enrich(
        IOC(IOCType.DOMAIN, "x.test", "x.test"))
    assert record.success and record.provider == "virustotal"
    assert record.summary == {"malicious": 3, "harmless": 10, "reputation": -5,
                              "categories": ["phishing"]}
    assert "super-secret" not in json.dumps(record.to_dict())


def test_vt_401_and_429_are_normalized_without_secret(monkeypatch):
    monkeypatch.setenv("DARKINTEL_VT_API_KEY", "never-leak")
    session = Mock()
    provider = VirusTotalProvider(session=session, minimum_request_interval=0, max_retries=0)
    session.get.return_value = make_response(401, {})
    auth = provider.enrich(IOC(IOCType.DOMAIN, "x.test", "x.test"))
    assert auth.error_category == "authentication_error" and "never-leak" not in auth.error
    session.get.return_value = make_response(429, {})
    assert provider.enrich(IOC(IOCType.DOMAIN, "x.test", "x.test")).error_category == "rate_limited"
