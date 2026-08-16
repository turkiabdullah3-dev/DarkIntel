import hashlib
from unittest.mock import Mock

import pytest
import requests

from darkintel.verifier import OnionValidationError, OnionVerifier, normalize_onion_url

HOST = "a" * 56 + ".onion"


@pytest.mark.parametrize("value,expected", [
    (HOST, f"http://{HOST}/"),
    (f"HTTPS://{HOST}/path?q=1#frag", f"https://{HOST}/path?q=1"),
    (f"http://{HOST}:8080", f"http://{HOST}:8080/"),
])
def test_valid_url_normalization(value, expected):
    assert normalize_onion_url(value) == expected


@pytest.mark.parametrize("value,message", [
    ("https://example.com", "valid 56-character"),
    ("http://short.onion", "valid 56-character"),
    (f"ftp://{HOST}", "only http and https"),
    (f"http://user:pass@{HOST}", "credentials"),  # pragma: allowlist secret
    ("http://[broken", "malformed"),
])
def test_invalid_urls(value, message):
    with pytest.raises(OnionValidationError, match=message):
        normalize_onion_url(value)


def make_response(status=200, body=b"<html><title> Test Page </title></html>", content_type="text/html; charset=utf-8"):
    response = Mock()
    response.status_code = status
    response.content = body
    response.headers = {"Content-Type": content_type}
    response.encoding = "utf-8"
    response.url = f"http://{HOST}/final"
    response.ok = status < 400
    return response


def test_successful_result_and_sha256():
    session = Mock(spec=requests.Session)
    session.proxies = {}
    body = b"<html><title>Evidence</title></html>"
    session.get.return_value = make_response(body=body)
    result = OnionVerifier(session=session).verify(HOST, require_tor_check=False)
    assert result.is_live
    assert result.status_code == 200
    assert result.title == "Evidence"
    assert result.sha256 == hashlib.sha256(body).hexdigest()
    session.get.assert_called_once_with(f"http://{HOST}/", timeout=15.0, allow_redirects=True)


def test_http_error_is_recorded_as_reachable():
    session = Mock(spec=requests.Session)
    session.proxies = {}
    session.get.return_value = make_response(status=404)
    result = OnionVerifier(session=session).verify(HOST, require_tor_check=False)
    assert result.is_live
    assert result.status_code == 404
    assert result.error == "HTTP 404"


def test_timeout_is_clean_failure():
    session = Mock(spec=requests.Session)
    session.proxies = {}
    session.get.side_effect = requests.Timeout("slow")
    result = OnionVerifier(session=session).verify(HOST, require_tor_check=False)
    assert not result.is_live
    assert "Timeout" in result.error


def test_validation_failure_does_not_request():
    session = Mock(spec=requests.Session)
    session.proxies = {}
    result = OnionVerifier(session=session).verify("https://example.com", require_tor_check=False)
    assert not result.is_live
    assert result.error.startswith("Validation error:")
    session.get.assert_not_called()


def test_malformed_html_does_not_crash():
    session = Mock(spec=requests.Session)
    session.proxies = {}
    session.get.return_value = make_response(body=b"\xff\xfe<html><title></html>")
    result = OnionVerifier(session=session).verify(HOST, require_tor_check=False)
    assert result.is_live
    assert result.sha256
