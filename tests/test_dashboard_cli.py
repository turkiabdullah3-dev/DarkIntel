import logging

import pytest

from main import build_parser, main, validate_dashboard_bind


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost", "LOCALHOST"])
def test_loopback_dashboard_hosts_are_allowed_without_override(host, caplog):
    validate_dashboard_bind(host)
    assert not caplog.records


@pytest.mark.parametrize("host", [
    "0.0.0.0",
    "::",
    "192.168.1.23",
    "10.10.10.10",
    "172.16.0.20",
    "8.8.8.8",
    "arbitrary-hostname",
])
def test_non_loopback_dashboard_hosts_fail_closed_without_starting_server(host, tmp_path):
    assert main(["--cases-dir", str(tmp_path), "dashboard", "--host", host]) == 2


def test_non_loopback_override_is_explicit_and_warns(caplog):
    args = build_parser().parse_args([
        "dashboard", "--host", "192.168.1.23", "--allow-non-loopback",
    ])
    assert args.allow_non_loopback is True
    with caplog.at_level(logging.WARNING, logger="darkintel"):
        validate_dashboard_bind(args.host, args.allow_non_loopback)
    assert "Authentication is not implemented" in caplog.text
    assert "may be exposed" in caplog.text
