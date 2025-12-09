"""
Tests for audit module.

Tests both Splunk and WAPI fileop audit sources.
"""

import pytest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, MagicMock
import tarfile
import io

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.audit import AuditClient, get_audit_for_object, format_audit_summary, download_full_audit_log, _parse_timestamp


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
        """Config with Splunk enabled (token auth)."""
        return {
            "splunk": {
                "enabled": True,
                "host": "splunk.example.com:8089",
                "token": "test-token",
                "username": "",
                "password": "",
                "index": "infoblox_audit",
                "sourcetype": ""
            }
        }

    @pytest.fixture
    def mock_config_splunk_userpass(self):
        """Config with Splunk enabled (username/password auth)."""
        import base64
        return {
            "splunk": {
                "enabled": True,
                "host": "splunk.example.com:8089",
                "token": "",
                "username": "splunkuser",
                "password": base64.b64encode(b"splunkpass").decode(),
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

    def test_splunk_userpass_auth(self, mock_config_splunk_userpass):
        """Test Splunk with username/password authentication."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"result": {"_time": "2024-01-15T10:30:00", "admin": "jsmith", "action": "INSERT"}}'

        with patch('lib.audit.load_config', return_value=mock_config_splunk_userpass):
            with patch('lib.audit.requests.post', return_value=mock_response) as mock_post:
                client = AuditClient()
                results = client._get_splunk_audit("10.20.30.0/24", "NETWORK")

                # Verify basic auth was used (not token)
                call_args = mock_post.call_args
                assert call_args.kwargs.get('auth') == ('splunkuser', 'splunkpass')
                assert 'Authorization' not in call_args.kwargs.get('headers', {})


class TestParseTimestamp:
    """Tests for _parse_timestamp function."""

    def test_parse_iso_format(self):
        """Test parsing ISO format timestamp."""
        result = _parse_timestamp("2024-01-15T10:30:00")
        assert result == "2024-01-15 10:30:00"

    def test_parse_iso_format_with_z(self):
        """Test parsing ISO format with Z suffix."""
        result = _parse_timestamp("2024-01-15T10:30:00Z")
        assert "2024-01-15" in result
        assert "10:30:00" in result

    def test_parse_unix_timestamp(self):
        """Test parsing Unix timestamp."""
        # 1705315800 = 2024-01-15 10:30:00 UTC
        result = _parse_timestamp("1705315800")
        assert "2024-01-15" in result

    def test_parse_unix_timestamp_float(self):
        """Test parsing Unix timestamp with decimal."""
        result = _parse_timestamp("1705315800.123")
        assert "2024-01-15" in result

    def test_parse_empty_value(self):
        """Test parsing empty value."""
        assert _parse_timestamp("") == "N/A"
        assert _parse_timestamp(None) == "N/A"

    def test_parse_already_formatted(self):
        """Test parsing already formatted string."""
        result = _parse_timestamp("Jan 15 10:30:00")
        assert result == "Jan 15 10:30:00"


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
            with patch.object(AuditClient, '_get_fileop_audit', return_value=[]):
                result = get_audit_for_object(
                    object_ref="network/test:10.20.30.0/24/default",
                    object_type="NETWORK",
                    object_name="10.20.30.0/24"
                )

                assert "source" in result
                assert "timestamps" in result


class TestFileopAudit:
    """Tests for WAPI fileop audit functionality."""

    @pytest.fixture
    def mock_config_splunk_disabled(self):
        """Config with Splunk disabled."""
        return {
            "splunk": {
                "enabled": False
            }
        }

    @pytest.fixture
    def mock_infoblox_creds(self):
        """Mock InfoBlox credentials."""
        return ("192.168.1.224", "admin", "infoblox", "2.13.1", False, 30)

    def _create_mock_audit_archive(self, log_content: str) -> bytes:
        """Create a mock tar.gz archive with audit log content."""
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
            # Add audit log file
            log_bytes = log_content.encode('utf-8')
            info = tarfile.TarInfo(name='var/log/audit.log')
            info.size = len(log_bytes)
            tar.addfile(info, io.BytesIO(log_bytes))
        buffer.seek(0)
        return buffer.read()

    def test_parse_audit_line_with_timestamp(self, mock_config_splunk_disabled):
        """Test parsing audit line with ISO timestamp."""
        with patch('lib.audit.load_config', return_value=mock_config_splunk_disabled):
            client = AuditClient()

            line = "2024-01-15 10:30:00 admin=jsmith INSERT NETWORK 10.99.1.0/24"
            entry = client._parse_audit_line(line)

            assert entry is not None
            assert entry["timestamp"] == "2024-01-15 10:30:00"
            assert entry["admin"] == "jsmith"
            assert entry["action"] == "INSERT"
            assert entry["object_type"] == "NETWORK"

    def test_parse_audit_line_syslog_format(self, mock_config_splunk_disabled):
        """Test parsing audit line with syslog timestamp."""
        with patch('lib.audit.load_config', return_value=mock_config_splunk_disabled):
            client = AuditClient()

            line = "Jan 15 10:30:00 infoblox audit: user=admin DELETE ZONE example.com"
            entry = client._parse_audit_line(line)

            assert entry is not None
            assert "Jan 15" in entry["timestamp"]
            assert entry["admin"] == "admin"
            assert entry["action"] == "DELETE"
            assert entry["object_type"] == "ZONE"

    def test_parse_audit_archive(self, mock_config_splunk_disabled):
        """Test parsing audit log from tar.gz archive."""
        with patch('lib.audit.load_config', return_value=mock_config_splunk_disabled):
            client = AuditClient()

            log_content = """2024-01-15 10:30:00 admin=jsmith INSERT NETWORK 10.99.1.0/24
2024-01-15 11:00:00 admin=admin UPDATE ZONE example.com
"""
            archive = self._create_mock_audit_archive(log_content)
            entries = client._parse_audit_archive(archive)

            assert len(entries) == 2
            assert entries[0]["admin"] == "jsmith"
            assert entries[1]["admin"] == "admin"

    def test_get_fileop_audit_filters_by_name(self, mock_config_splunk_disabled):
        """Test fileop audit filters by object name."""
        with patch('lib.audit.load_config', return_value=mock_config_splunk_disabled):
            client = AuditClient()

            # Pre-populate cache with test entries
            client._audit_log_cache = [
                {"message": "INSERT NETWORK 10.99.1.0/24", "object_name": "10.99.1.0/24", "raw": "", "timestamp": "2024-01-15", "admin": "jsmith"},
                {"message": "INSERT NETWORK 10.99.2.0/24", "object_name": "10.99.2.0/24", "raw": "", "timestamp": "2024-01-16", "admin": "admin"},
                {"message": "INSERT ZONE example.com", "object_name": "example.com", "raw": "", "timestamp": "2024-01-17", "admin": "jsmith"}
            ]
            client._audit_log_cache_time = datetime.now()

            results = client._get_fileop_audit("10.99.1.0/24")

            assert len(results) == 1
            assert "10.99.1.0/24" in results[0]["message"]

    def test_get_fileop_audit_filters_by_type(self, mock_config_splunk_disabled):
        """Test fileop audit filters by object type."""
        with patch('lib.audit.load_config', return_value=mock_config_splunk_disabled):
            client = AuditClient()

            # Pre-populate cache
            client._audit_log_cache = [
                {"message": "INSERT NETWORK 10.99.0.0/16", "object_type": "NETWORK", "raw": "", "timestamp": "2024-01-15", "admin": "jsmith"},
                {"message": "INSERT ZONE 10.99.local", "object_type": "ZONE", "raw": "", "timestamp": "2024-01-16", "admin": "admin"}
            ]
            client._audit_log_cache_time = datetime.now()

            # Both entries match "10.99" but only one is NETWORK type
            results = client._get_fileop_audit("10.99", object_type="NETWORK")

            assert len(results) == 1
            assert results[0]["object_type"] == "NETWORK"

    def test_audit_cache_expiration(self, mock_config_splunk_disabled):
        """Test that audit cache expires after TTL."""
        with patch('lib.audit.load_config', return_value=mock_config_splunk_disabled):
            client = AuditClient()
            client._cache_ttl = 300  # 5 minutes

            # Set old cache time (expired)
            client._audit_log_cache = [{"message": "old entry"}]
            client._audit_log_cache_time = datetime.now() - timedelta(seconds=600)

            # Mock the download to return new data
            with patch.object(client, '_download_audit_log', return_value=[{"message": "new entry"}]):
                entries = client._get_cached_audit_log()

                assert len(entries) == 1
                assert entries[0]["message"] == "new entry"

    def test_audit_cache_valid(self, mock_config_splunk_disabled):
        """Test that valid cache is used."""
        with patch('lib.audit.load_config', return_value=mock_config_splunk_disabled):
            client = AuditClient()

            # Set recent cache (valid)
            client._audit_log_cache = [{"message": "cached entry"}]
            client._audit_log_cache_time = datetime.now()

            # Should NOT call download
            with patch.object(client, '_download_audit_log') as mock_download:
                entries = client._get_cached_audit_log()

                mock_download.assert_not_called()
                assert entries[0]["message"] == "cached entry"

    def test_splunk_fallback_to_fileop(self):
        """Test fallback from Splunk to fileop when Splunk fails."""
        mock_config = {
            "splunk": {
                "enabled": True,
                "host": "splunk.example.com:8089",
                "token": "test-token",
                "index": "infoblox_audit"
            }
        }

        with patch('lib.audit.load_config', return_value=mock_config):
            client = AuditClient()

            # Mock Splunk to fail
            with patch.object(client, '_get_splunk_audit', return_value=[{"error": "Connection failed"}]):
                # Mock fileop to succeed
                with patch.object(client, '_get_fileop_audit', return_value=[
                    {"message": "INSERT NETWORK", "timestamp": "2024-01-15", "admin": "jsmith"}
                ]):
                    result = client.get_object_audit(
                        object_ref="network/test:10.99.1.0/24/default",
                        object_name="10.99.1.0/24"
                    )

                    assert result["source"] == "fileop"
                    assert "splunk_error" in result
                    assert len(result["fileop_audit"]) == 1

    def test_download_audit_log_success(self, mock_config_splunk_disabled, mock_infoblox_creds):
        """Test successful audit log download."""
        with patch('lib.audit.load_config', return_value=mock_config_splunk_disabled):
            with patch('lib.audit.get_infoblox_creds', return_value=mock_infoblox_creds):
                client = AuditClient()

                # Mock fileop response
                fileop_resp = Mock()
                fileop_resp.status_code = 200
                fileop_resp.json.return_value = {
                    "url": "https://192.168.1.224/wapi/v2.13.1/fileop/download",
                    "token": "test-token"
                }

                # Mock download response
                log_content = "2024-01-15 10:30:00 admin=jsmith INSERT NETWORK 10.99.1.0/24"
                archive = self._create_mock_audit_archive(log_content)
                download_resp = Mock()
                download_resp.status_code = 200
                download_resp.content = archive

                with patch('lib.audit.requests.post', side_effect=[fileop_resp, download_resp]):
                    entries = client._download_audit_log()

                    assert len(entries) >= 1


class TestDownloadFullAuditLog:
    """Tests for download_full_audit_log convenience function."""

    def test_download_full_audit_log_no_path(self):
        """Test downloading audit log without saving to file."""
        mock_creds = ("192.168.1.224", "admin", "infoblox", "2.13.1", False, 30)

        fileop_resp = Mock()
        fileop_resp.status_code = 200
        fileop_resp.json.return_value = {
            "url": "https://192.168.1.224/download",
            "token": "test-token"
        }

        download_resp = Mock()
        download_resp.status_code = 200
        download_resp.content = b"test archive content"

        with patch('lib.audit.get_infoblox_creds', return_value=mock_creds):
            with patch('lib.audit.requests.post', side_effect=[fileop_resp, download_resp]):
                success, message = download_full_audit_log()

                assert success is True
                assert "20 bytes" in message

    def test_download_full_audit_log_failure(self):
        """Test handling download failure."""
        mock_creds = ("192.168.1.224", "admin", "infoblox", "2.13.1", False, 30)

        fileop_resp = Mock()
        fileop_resp.status_code = 500

        with patch('lib.audit.get_infoblox_creds', return_value=mock_creds):
            with patch('lib.audit.requests.post', return_value=fileop_resp):
                success, message = download_full_audit_log()

                assert success is False
                assert "500" in message
