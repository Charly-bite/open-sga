import pytest
from unittest.mock import patch, MagicMock
from database_client import DatabaseClient

hdbcli = pytest.importorskip("hdbcli", reason="hdbcli not installed (SAP HANA driver)")
from sga_web.core.sap_connector import SAPHanaConnector  # noqa: E402


def test_database_client_ping_server():
    client = DatabaseClient()

    # Mock socket connection to simulate server unreachable
    with patch("socket.socket") as mock_socket:
        mock_sock_instance = MagicMock()
        mock_sock_instance.connect_ex.return_value = 1  # 1 means error/unreachable
        mock_socket.return_value = mock_sock_instance

        is_reachable = client._ping_server("192.168.1.99", timeout=1)
        assert is_reachable is False

    # Mock socket connection to simulate server reachable
    with patch("socket.socket") as mock_socket:
        mock_sock_instance = MagicMock()
        mock_sock_instance.connect_ex.return_value = 0  # 0 means success
        mock_socket.return_value = mock_sock_instance

        is_reachable = client._ping_server("192.168.1.99", timeout=1)
        assert is_reachable is True


def test_database_client_fallback_mode():
    client = DatabaseClient()
    # Force client to use local mode by mocking config
    client.config = {
        "deployment_type": "local",
        "fallback": {"enabled": True, "local_database_path": "unified_db"},
    }

    with patch.object(client, "_verify_database", return_value=True), patch(
        "os.path.exists", return_value=True
    ):

        # Test connection in fallback mode
        result = client.connect()
        assert result is True
        assert client.connection_mode == "local"


def test_sap_connection_failure_handled_gracefully():
    sap = SAPHanaConnector()

    # Mock the internal connection to throw an error (e.g. server offline)
    with patch(
        "sga_web.core.sap_connector.dbapi.connect", side_effect=Exception("SAP Timeout")
    ):
        result = sap.connect()
        assert result is False
        assert sap.connection is None


@pytest.mark.integration
def test_sap_connection_integration():
    """
    Live integration test for SAP. Only runs when explicitly requested
    via `pytest -m integration`
    """
    sap = SAPHanaConnector()
    assert sap.connect() is True
    sap.disconnect()
