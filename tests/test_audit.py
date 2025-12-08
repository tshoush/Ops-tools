"""
Tests for audit module.
"""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, Mock, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.audit import AuditClient, get_audit_for_object, format_audit_summary


class TestAuditClient:
    """Tests for AuditClient class."""

    @pytest.fixture
    def mock_config_splunk_disabled(self):
        """Config with Splunk disabled."""
        return {
            "splunk": {
                "enabled": False,
                "host": "",
                "token": "",
                "index": "infoblox_audit"
            }
        }

    @pytest.fixture
    def mock_config_splunk_enabled(self):
        """Config with Splunk enabled."""
        return {
            "splunk": {
                "enabled": True,
                "host": "splunk.example.com:8089",
                "token": "test-token",
                "index": "infoblox_audit",
                "sourcetype": ""
            }
        }

    def test_get_object_audit_splunk_disabled(self, mock_config_splunk_disabled):
        """Test audit when Splunk is disabled."""
        with patch('lib.audit.load_config', return_value=mock_config_splunk_disabled):
            client = AuditClient()
            result = client.get_object_audit(
                object_ref="network/test:10.20.30.0/24/default",
                object_type="NETWORK",
                object_name="10.20.30.0/24"
            )

            assert result["source"] == "none"
            assert "message" in result
            assert "Splunk" in result["message"]

    def test_get_object_audit_splunk_enabled(self, mock_config_splunk_enabled):
        """Test audit when Splunk is enabled."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"result": {"_time": "2024-01-15T10:30:00", "admin": "jsmith", "action": "INSERT"}}'

        with patch('lib.audit.load_config', return_value=mock_config_splunk_enabled):
            with patch('lib.audit.requests.post', return_value=mock_response):
                client = AuditClient()
                result = client.get_object_audit(
                    object_ref="network/test:10.20.30.0/24/default",
                    object_type="NETWORK",
                    object_name="10.20.30.0/24"
                )

                assert result["source"] == "splunk"
                assert "splunk_audit" in result

    def test_extract_search_term_network(self):
        """Test extracting search term from network ref."""
        with patch('lib.audit.load_config', return_value={"splunk": {"enabled": False}}):
            client = AuditClient()

            # Test network CIDR extraction
            term = client._extract_search_term("network/ZG5zLm5ldH:10.20.30.0/24/default")
            assert term == "10.20.30.0/24"

    def test_extract_search_term_simple(self):
        """Test extracting search term from simple ref."""
        with patch('lib.audit.load_config', return_value={"splunk": {"enabled": False}}):
            client = AuditClient()

            # Test simple extraction
            term = client._extract_search_term("zone/ZG5z:example.com")
            assert term == "example.com"

    def test_extract_search_term_none(self):
        """Test extracting search term from None."""
        with patch('lib.audit.load_config', return_value={"splunk": {"enabled": False}}):
            client = AuditClient()
            term = client._extract_search_term(None)
            assert term is None

    def test_extract_audit_metadata(self, mock_config_splunk_enabled):
        """Test extracting metadata from Splunk results."""
        with patch('lib.audit.load_config', return_value=mock_config_splunk_enabled):
            client = AuditClient()
            audit_info = {"timestamps": {}, "created_by": None, "last_modified_by": None}

            splunk_results = [
                {"_time": "2024-01-10T08:00:00", "admin": "creator", "action": "INSERT"},
                {"_time": "2024-01-15T10:30:00", "admin": "modifier", "action": "UPDATE"}
            ]

            client._extract_audit_metadata(audit_info, splunk_results)

            assert audit_info["created_by"] == "creator"
            assert audit_info["last_modified_by"] == "modifier"
            assert "2024-01-10" in audit_info["timestamps"]["created"]
            assert "2024-01-15" in audit_info["timestamps"]["last_modified"]

    def test_normalize_splunk_result(self, mock_config_splunk_enabled):
        """Test normalizing Splunk result."""
        with patch('lib.audit.load_config', return_value=mock_config_splunk_enabled):
            client = AuditClient()

            raw_result = {
                "_time": "2024-01-15T10:30:00",
                "admin": "testuser",
                "action": "UPDATE",
                "object_type": "NETWORK",
                "_raw": "Some raw log message"
            }

            normalized = client._normalize_splunk_result(raw_result)

            assert normalized["admin"] == "testuser"
            assert normalized["action"] == "UPDATE"
            assert normalized["object_type"] == "NETWORK"
            assert "timestamp" in normalized

    def test_splunk_connection_error(self, mock_config_splunk_enabled):
        """Test handling Splunk connection error."""
        import requests

        with patch('lib.audit.load_config', return_value=mock_config_splunk_enabled):
            with patch('lib.audit.requests.post', side_effect=requests.exceptions.ConnectionError()):
                client = AuditClient()
                results = client._get_splunk_audit("10.20.30.0/24", "NETWORK")

                assert len(results) == 1
                assert "error" in results[0]
                assert "connect" in results[0]["error"].lower()

    def test_splunk_auth_failure(self, mock_config_splunk_enabled):
        """Test handling Splunk authentication failure."""
        mock_response = Mock()
        mock_response.status_code = 401

        with patch('lib.audit.load_config', return_value=mock_config_splunk_enabled):
            with patch('lib.audit.requests.post', return_value=mock_response):
                client = AuditClient()
                results = client._get_splunk_audit("10.20.30.0/24", "NETWORK")

                assert len(results) == 1
                assert "error" in results[0]
                assert "authentication" in results[0]["error"].lower()


class TestFormatAuditSummary:
    """Tests for format_audit_summary function."""

    def test_format_complete_audit(self):
        """Test formatting complete audit info."""
        audit_info = {
            "timestamps": {
                "created": "2024-01-10T08:00:00",
                "last_modified": "2024-01-15T10:30:00"
            },
            "created_by": "admin",
            "last_modified_by": "jsmith"
        }

        summary = format_audit_summary(audit_info)

        assert summary["Created By"] == "admin"
        assert summary["Modified By"] == "jsmith"

    def test_format_empty_audit(self):
        """Test formatting empty audit info."""
        audit_info = {"timestamps": {}}

        summary = format_audit_summary(audit_info)

        assert summary["Created"] == "N/A"
        assert summary["Created By"] == "N/A"
        assert summary["Last Modified"] == "N/A"
        assert summary["Modified By"] == "N/A"

    def test_format_partial_audit(self):
        """Test formatting partial audit info."""
        audit_info = {
            "timestamps": {
                "last_modified": "2024-01-15T10:30:00"
            },
            "last_modified_by": "jsmith"
        }

        summary = format_audit_summary(audit_info)

        assert summary["Created"] == "N/A"
        assert summary["Modified By"] == "jsmith"


class TestGetAuditForObject:
    """Tests for get_audit_for_object convenience function."""

    def test_get_audit_for_object(self):
        """Test convenience function."""
        mock_config = {
            "splunk": {
                "enabled": False
            }
        }

        with patch('lib.audit.load_config', return_value=mock_config):
            result = get_audit_for_object(
                object_ref="network/test:10.20.30.0/24/default",
                object_type="NETWORK",
                object_name="10.20.30.0/24"
            )

            assert "source" in result
            assert "timestamps" in result
