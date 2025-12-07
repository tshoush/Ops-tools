"""
Tests for audit module.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, Mock
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.audit import (
    AuditClient,
    get_audit_for_object,
    format_audit_summary
)


class TestAuditClient:
    """Tests for AuditClient class."""

    @pytest.fixture
    def mock_audit_entries(self):
        """Mock audit log entries."""
        return [
            {
                "timestamp": "1701475200",
                "admin": "jsmith",
                "action": "UPDATE",
                "object_type": "NETWORK",
                "object_name": "10.20.30.0/24",
                "message": "Modified comment"
            },
            {
                "timestamp": "1699574400",
                "admin": "admin",
                "action": "INSERT",
                "object_type": "NETWORK",
                "object_name": "10.20.30.0/24",
                "message": "Created network"
            }
        ]

    def test_get_object_audit_success(self, mock_audit_entries):
        """Test successful audit retrieval."""
        mock_client = Mock()
        mock_client.get = Mock(return_value=mock_audit_entries)

        with patch('lib.wapi.get_client', return_value=mock_client):
            client = AuditClient()
            result = client.get_object_audit(
                object_ref="network/test:10.20.30.0/24/default",
                object_type="NETWORK",
                object_name="10.20.30.0/24"
            )

            assert "wapi_audit" in result
            assert "timestamps" in result
            assert result["last_modified_by"] == "jsmith"

    def test_get_object_audit_extracts_creation(self, mock_audit_entries):
        """Test audit extraction finds creation entry."""
        mock_client = Mock()
        mock_client.get = Mock(return_value=mock_audit_entries)

        with patch('lib.wapi.get_client', return_value=mock_client):
            client = AuditClient()
            result = client.get_object_audit(
                object_ref="network/test:10.20.30.0/24/default",
                object_type="NETWORK"
            )

            # Should find INSERT action as creation
            assert result.get("created_by") == "admin"

    def test_get_object_audit_empty(self):
        """Test audit retrieval with no results."""
        mock_client = Mock()
        mock_client.get = Mock(return_value=[])

        with patch('lib.wapi.get_client', return_value=mock_client):
            client = AuditClient()
            result = client.get_object_audit(
                object_ref="network/test:10.20.30.0/24/default",
                object_type="NETWORK"
            )

            assert result["wapi_audit"] == []

    def test_get_wapi_audit_error_handling(self):
        """Test WAPI audit error handling."""
        mock_client = Mock()
        mock_client.get = Mock(side_effect=Exception("API Error"))

        with patch('lib.wapi.get_client', return_value=mock_client):
            client = AuditClient()
            result = client._get_wapi_audit(
                object_ref="network/test",
                object_type="NETWORK"
            )

            # Should return error entry, not raise
            assert len(result) == 1
            assert "error" in result[0]


class TestFormatAuditSummary:
    """Tests for format_audit_summary function."""

    def test_format_complete_audit(self):
        """Test formatting complete audit info."""
        audit_info = {
            "timestamps": {
                "created": 1699574400,
                "last_modified": 1701475200
            },
            "created_by": "admin",
            "last_modified_by": "jsmith"
        }

        result = format_audit_summary(audit_info)

        assert result["Created By"] == "admin"
        assert result["Modified By"] == "jsmith"
        assert result["Created"] != "N/A"
        assert result["Last Modified"] != "N/A"

    def test_format_empty_audit(self):
        """Test formatting empty audit info."""
        audit_info = {}

        result = format_audit_summary(audit_info)

        assert result["Created"] == "N/A"
        assert result["Created By"] == "N/A"
        assert result["Last Modified"] == "N/A"
        assert result["Modified By"] == "N/A"

    def test_format_partial_audit(self):
        """Test formatting partial audit info."""
        audit_info = {
            "timestamps": {
                "created": 1699574400
            },
            "created_by": "admin"
        }

        result = format_audit_summary(audit_info)

        assert result["Created By"] == "admin"
        assert result["Last Modified"] == "N/A"
        assert result["Modified By"] == "N/A"


class TestGetAuditForObject:
    """Tests for get_audit_for_object convenience function."""

    def test_get_audit_for_object(self):
        """Test convenience function."""
        mock_client = Mock()
        mock_client.get = Mock(return_value=[])

        with patch('lib.wapi.get_client', return_value=mock_client):
            result = get_audit_for_object(
                object_ref="network/test",
                object_type="NETWORK",
                object_name="10.0.0.0/24"
            )

            assert "wapi_audit" in result
            assert "timestamps" in result
