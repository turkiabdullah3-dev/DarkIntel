import json
from unittest.mock import Mock

from darkintel.enrichment.providers.rdap import RDAPProvider
from darkintel.models import IOC, IOCType


def make_response(status, payload):
    response = Mock(status_code=status, headers={})
    response.content = json.dumps(payload).encode()
    return response


def test_rdap_success():
    session = Mock()
    session.get.return_value = make_response(200, {"name": "NET-EXAMPLE", "country": "US",
                                                   "events": [{"eventAction": "registration",
                                                               "eventDate": "2020-01-01T00:00:00Z"}]})
    record = RDAPProvider(session=session, minimum_request_interval=0).enrich(
        IOC(IOCType.IPV4, "8.8.8.8", "8.8.8.8"))
    assert record.success and record.summary["network_name"] == "NET-EXAMPLE"


def test_rdap_not_found_and_malformed():
    session = Mock()
    provider = RDAPProvider(session=session, minimum_request_interval=0, max_retries=0)
    session.get.return_value = make_response(404, {})
    assert provider.enrich(IOC(IOCType.DOMAIN, "x.test", "x.test")).error_category == "not_found"
    session.get.return_value = make_response(200, [])
    assert provider.enrich(IOC(IOCType.DOMAIN, "x.test", "x.test")).error_category == "parse_error"
