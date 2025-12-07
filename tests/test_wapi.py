"""
Tests for WAPI client.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
import requests

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.wapi import WAPIClient, WAPIError, get_client, reset_client


class TestWAPIClient:
    """Tests for WAPIClient class."""

    @pytest.fixture
    def mock_credentials(self):
        """Mock credentials tuple."""
        return (
            "192.168.1.100",  # grid_master
            "admin",          # username
            "password",       # password
            "2.13.1",         # wapi_version
            False,            # verify_ssl
            30                # timeout
        )

    def test_init_success(self, mock_credentials):
        """Test successful client initialization."""
        with patch('lib.wapi.get_infoblox_creds', return_value=mock_credentials):
            client = WAPIClient()

            assert client.base_url == "https://192.168.1.100/wapi/v2.13.1"
            assert client.auth == ("admin", "password")
            assert client.verify is False
            assert client.timeout == 30

    def test_init_missing_credentials(self):
        """Test initialization fails with missing credentials."""
        missing_creds = ("", "", "", "2.13.1", False, 30)

        with patch('lib.wapi.get_infoblox_creds', return_value=missing_creds):
            with pytest.raises(WAPIError) as exc_info:
                WAPIClient()

            assert "not configured" in str(exc_info.value).lower()

    def test_get_success(self, mock_credentials, mock_network_response):
        """Test successful GET request."""
        with patch('lib.wapi.get_infoblox_creds', return_value=mock_credentials):
            client = WAPIClient()

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = json.dumps({"result": mock_network_response})
            mock_response.json.return_value = {"result": mock_network_response}

            with patch.object(client.session, 'request', return_value=mock_response):
                result = client.get("network", params={"network": "10.20.30.0/24"})

                assert len(result) == 1
                assert result[0]["network"] == "10.20.30.0/24"

    def test_get_auth_failure(self, mock_credentials):
        """Test GET request with authentication failure."""
        with patch('lib.wapi.get_infoblox_creds', return_value=mock_credentials):
            client = WAPIClient()

            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"

            with patch.object(client.session, 'request', return_value=mock_response):
                with pytest.raises(WAPIError) as exc_info:
                    client.get("network")

                assert exc_info.value.status_code == 401
                assert "Authentication failed" in exc_info.value.message

    def test_get_not_found(self, mock_credentials):
        """Test GET request returns empty list on 404."""
        with patch('lib.wapi.get_infoblox_creds', return_value=mock_credentials):
            client = WAPIClient()

            mock_response = Mock()
            mock_response.status_code = 404

            with patch.object(client.session, 'request', return_value=mock_response):
                result = client.get("network", params={"network": "invalid"})

                assert result == []

    def test_get_connection_error(self, mock_credentials):
        """Test GET request with connection error."""
        with patch('lib.wapi.get_infoblox_creds', return_value=mock_credentials):
            client = WAPIClient()

            with patch.object(client.session, 'request',
                            side_effect=requests.exceptions.ConnectionError("Connection refused")):
                with pytest.raises(WAPIError) as exc_info:
                    client.get("network")

                assert "Connection failed" in exc_info.value.message

    def test_get_timeout(self, mock_credentials):
        """Test GET request with timeout."""
        with patch('lib.wapi.get_infoblox_creds', return_value=mock_credentials):
            client = WAPIClient()

            with patch.object(client.session, 'request',
                            side_effect=requests.exceptions.Timeout()):
                with pytest.raises(WAPIError) as exc_info:
                    client.get("network")

                assert "timed out" in exc_info.value.message.lower()

    def test_get_with_return_fields(self, mock_credentials):
        """Test GET request with return_fields."""
        with patch('lib.wapi.get_infoblox_creds', return_value=mock_credentials):
            client = WAPIClient()

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = json.dumps({"result": []})
            mock_response.json.return_value = {"result": []}

            with patch.object(client.session, 'request', return_value=mock_response) as mock_req:
                client.get("network", return_fields=["network", "comment"])

                # Verify return_fields was added to params
                call_kwargs = mock_req.call_args[1]
                assert "_return_fields+" in call_kwargs['params']

    def test_test_connection_success(self, mock_credentials):
        """Test successful connection test."""
        with patch('lib.wapi.get_infoblox_creds', return_value=mock_credentials):
            client = WAPIClient()

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = json.dumps({"result": [{"name": "Test Grid"}]})
            mock_response.json.return_value = {"result": [{"name": "Test Grid"}]}

            with patch.object(client.session, 'request', return_value=mock_response):
                result = client.test_connection()

                assert result["name"] == "Test Grid"


class TestClientSingleton:
    """Tests for client singleton pattern."""

    def test_get_client_creates_instance(self, mock_config):
        """Test get_client creates new instance."""
        reset_client()

        mock_creds = ("192.168.1.100", "admin", "password", "2.13.1", False, 30)
        with patch('lib.wapi.get_infoblox_creds', return_value=mock_creds):
            client = get_client()
            assert client is not None

    def test_get_client_returns_same_instance(self):
        """Test get_client returns same instance on subsequent calls."""
        reset_client()

        mock_creds = ("192.168.1.100", "admin", "password", "2.13.1", False, 30)
        with patch('lib.wapi.get_infoblox_creds', return_value=mock_creds):
            client1 = get_client()
            client2 = get_client()
            assert client1 is client2

    def test_reset_client(self):
        """Test reset_client clears singleton."""
        mock_creds = ("192.168.1.100", "admin", "password", "2.13.1", False, 30)
        with patch('lib.wapi.get_infoblox_creds', return_value=mock_creds):
            client1 = get_client()
            reset_client()
            client2 = get_client()

            assert client1 is not client2
