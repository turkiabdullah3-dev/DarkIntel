import json
from unittest.mock import Mock

from darkintel.enrichment.providers.abuseipdb import AbuseIPDBProvider
from darkintel.models import IOC, IOCType


def make_response(payload):
    response = Mock(status_code=200, headers={})
    response.content = json.dumps(payload).encode()
    return response


def test_abuseipdb_missing_key(monkeypatch):
    monkeypatch.delenv("DARKINTEL_ABUSEIPDB_API_KEY", raising=False)
    session = Mock()
    record = AbuseIPDBProvider(session=session).enrich(IOC(IOCType.IPV4, "8.8.8.8", "8.8.8.8"))
    assert record.error_category == "configuration_error"
    session.get.assert_not_called()


def test_abuseipdb_success(monkeypatch):
    monkeypatch.setenv("DARKINTEL_ABUSEIPDB_API_KEY", "secret")
    session = Mock()
    session.get.return_value = make_response({"data": {"abuseConfidenceScore": 42, "countryCode": "US",
                                                        "totalReports": 7, "ipAddress": "8.8.8.8"}})
    record = AbuseIPDBProvider(session=session, minimum_request_interval=0).enrich(
        IOC(IOCType.IPV4, "8.8.8.8", "8.8.8.8"))
    assert record.success
    assert record.summary["abuse_confidence_score"] == 42
    assert record.confidence == 0.42
