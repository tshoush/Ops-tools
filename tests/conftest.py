"""
Pytest configuration and fixtures for DDI Toolkit tests.
"""

import pytest
import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_config():
    """Mock configuration data."""
    return {
        "version": "1.0",
        "infoblox": {
            "grid_master": "192.168.1.100",
            "username": "admin",
            "password": "YWRtaW4=",  # base64 'admin'
            "wapi_version": "2.13.1",
            "verify_ssl": False,
            "timeout": 30
        },
        "splunk": {
            "enabled": False,
            "host": "",
            "token": "",
            "index": "infoblox_audit"
        },
        "output": {
            "default_dir": "./test_output",
            "timestamp_files": False
        },
        "defaults": {
            "network_view": "default",
            "dns_view": "default"
        }
    }


@pytest.fixture
def mock_network_response():
    """Mock WAPI network response."""
    return [{
        "_ref": "network/ZG5zLm5ldHdvcmskMTAuMjAuMzAuMC8yNC8w:10.20.30.0/24/default",
        "network": "10.20.30.0/24",
        "network_view": "default",
        "comment": "Test network",
        "utilization": 45,
        "total_hosts": 254,
        "dynamic_hosts": 100,
        "static_hosts": 14,
        "dhcp_utilization": 40,
        "extattrs": {},
        "options": [],
        "members": []
    }]


@pytest.fixture
def mock_ip_response():
    """Mock WAPI IPv4 address response."""
    return [{
        "_ref": "ipv4address/Li5pcHY0X2FkZHJlc3MkMTAuMjAuMzAuNTAvMA:10.20.30.50",
        "ip_address": "10.20.30.50",
        "status": "USED",
        "types": ["HOST", "A"],
        "names": ["server1.example.com"],
        "mac_address": "00:11:22:33:44:55",
        "network": "10.20.30.0/24",
        "network_view": "default",
        "is_conflict": False,
        "usage": ["DNS", "DHCP"],
        "extattrs": {}
    }]


@pytest.fixture
def mock_zone_response():
    """Mock WAPI zone_auth response."""
    return [{
        "_ref": "zone_auth/ZG5zLnpvbmUkLl9kZWZhdWx0LmNvbS5leGFtcGxl:example.com/default",
        "fqdn": "example.com",
        "view": "default",
        "zone_format": "FORWARD",
        "comment": "Test zone",
        "disable": False,
        "grid_primary": [{"name": "ns1.example.com"}],
        "grid_secondaries": [],
        "soa_default_ttl": 3600,
        "soa_expire": 604800,
        "soa_refresh": 10800,
        "soa_retry": 3600,
        "extattrs": {}
    }]


@pytest.fixture
def mock_container_response():
    """Mock WAPI network container response."""
    return [{
        "_ref": "networkcontainer/ZG5zLm5ldHdvcmtfY29udGFpbmVyJDEwLjAuMC4wLzgvMA:10.0.0.0/8/default",
        "network": "10.0.0.0/8",
        "network_view": "default",
        "comment": "Test container",
        "utilization": 10,
        "extattrs": {},
        "options": []
    }]


@pytest.fixture
def mock_range_response():
    """Mock WAPI DHCP range response."""
    return [{
        "_ref": "range/ZG5zLmRoY3BfcmFuZ2UkMTAuMjAuMzAuMTAwLzEwLjIwLjMwLjIwMC8w:10.20.30.100/10.20.30.200/default",
        "start_addr": "10.20.30.100",
        "end_addr": "10.20.30.200",
        "network": "10.20.30.0/24",
        "network_view": "default",
        "disable": False,
        "comment": "Test range"
    }]


@pytest.fixture
def mock_lease_response():
    """Mock WAPI lease response."""
    return [{
        "_ref": "lease/ZG5zLmxlYXNlJC8vMTAuMjAuMzAuMTUwLzAvMA:10.20.30.150",
        "address": "10.20.30.150",
        "hardware": "00:11:22:33:44:66",
        "client_hostname": "client1",
        "binding_state": "active",
        "starts": 1701388800,
        "ends": 1701475200,
        "network": "10.20.30.0/24",
        "network_view": "default"
    }]


@pytest.fixture
def mock_audit_response():
    """Mock WAPI auditlog response."""
    return [{
        "timestamp": "1701388800",
        "admin": "admin",
        "action": "INSERT",
        "object_type": "NETWORK",
        "object_name": "10.20.30.0/24",
        "message": "Created network"
    }, {
        "timestamp": "1701475200",
        "admin": "jsmith",
        "action": "UPDATE",
        "object_type": "NETWORK",
        "object_name": "10.20.30.0/24",
        "message": "Modified comment"
    }]


@pytest.fixture
def mock_wapi_client(mock_network_response, mock_range_response, mock_lease_response, mock_audit_response):
    """Create a mock WAPI client."""
    client = Mock()

    def mock_get(object_type, params=None, return_fields=None, max_results=None):
        """Mock get method based on object type."""
        if object_type == "network":
            return mock_network_response
        elif object_type == "range":
            return mock_range_response
        elif object_type == "lease":
            return mock_lease_response
        elif object_type == "auditlog":
            return mock_audit_response
        elif object_type == "grid":
            return [{"name": "Test Grid"}]
        return []

    client.get = Mock(side_effect=mock_get)
    client.test_connection = Mock(return_value={"name": "Test Grid"})

    return client


@pytest.fixture
def temp_config_file(tmp_path, mock_config):
    """Create a temporary config file."""
    config_path = tmp_path / "config.json"
    with open(config_path, 'w') as f:
        json.dump(mock_config, f)
    return config_path


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create a temporary output directory."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir
