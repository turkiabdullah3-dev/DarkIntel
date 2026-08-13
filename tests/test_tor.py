from unittest.mock import patch

from darkintel.tor import check_tor, is_tor_available


def test_tor_available():
    with patch("darkintel.tor.socket.create_connection") as connection:
        connection.return_value.__enter__.return_value = object()
        assert is_tor_available(timeout=0.1) is True


def test_tor_unavailable_is_structured():
    with patch("darkintel.tor.socket.create_connection", side_effect=ConnectionRefusedError("refused")):
        status = check_tor(timeout=0.1)
    assert status.available is False
    assert status.error and "unavailable" in status.error


def test_invalid_tor_port_returns_error():
    status = check_tor(port=70000)
    assert not status.available
    assert "port" in status.error.lower()
