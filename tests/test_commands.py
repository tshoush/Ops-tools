"""
Tests for command modules.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock, PropertyMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from ddi_toolkit.commands import get_command, list_commands, get_command_names
from ddi_toolkit.commands.base import BaseCommand


class TestCommandRegistry:
    """Tests for command registry."""

    def test_get_command_by_name(self):
        """Test getting command by name."""
        cmd = get_command("network")
        assert cmd is not None
        assert cmd.name == "network"

    def test_get_command_by_alias(self):
        """Test getting command by alias."""
        cmd = get_command("net")  # alias for network
        assert cmd is not None
        assert cmd.name == "network"

    def test_get_command_invalid(self):
        """Test getting invalid command returns None."""
        cmd = get_command("invalid_command")
        assert cmd is None

    def test_list_commands(self):
        """Test listing all commands."""
        commands = list_commands()

        assert "network" in commands
        assert "ip" in commands
        assert "zone" in commands
        assert "container" in commands
        assert "dhcp" in commands
        assert "search" in commands

    def test_get_command_names(self):
        """Test getting command names."""
        names = get_command_names()

        assert isinstance(names, list)
        assert "network" in names
        assert "ip" in names


class TestNetworkCommand:
    """Tests for network command."""

    @pytest.fixture
    def network_command(self):
        """Get network command class."""
        return get_command("network")

    def test_network_command_properties(self, network_command):
        """Test network command properties."""
        assert network_command.name == "network"
        assert "net" in network_command.aliases
        assert "subnet" in network_command.aliases

    def test_network_execute_success(self, network_command, mock_network_response,
                                     mock_range_response, mock_lease_response):
        """Test successful network query."""
        mock_client = Mock()

        def mock_get(obj, **kwargs):
            if obj == "network":
                return mock_network_response
            elif obj == "range":
                return mock_range_response
            elif obj == "lease":
                return mock_lease_response
            elif obj == "auditlog":
                return []
            return []

        mock_client.get = Mock(side_effect=mock_get)

        with patch('ddi_toolkit.wapi._client', mock_client):
            with patch('ddi_toolkit.wapi.get_client', return_value=mock_client):
                cmd = network_command()
                cmd._client = mock_client  # Inject mock directly
                result = cmd.execute("10.20.30.0/24")

                assert result["network"] == "10.20.30.0/24"
                assert "utilization" in result
                assert "dhcp" in result
                assert "ranges" in result["dhcp"]
                assert "servers" in result["dhcp"]
                assert "effective_options" in result["dhcp"]
                assert "active_leases" in result
                assert "audit" in result

    def test_network_execute_not_found(self, network_command):
        """Test network query when not found."""
        mock_client = Mock()
        mock_client.get = Mock(return_value=[])

        with patch('ddi_toolkit.wapi._client', mock_client):
            with patch('ddi_toolkit.wapi.get_client', return_value=mock_client):
                cmd = network_command()
                cmd._client = mock_client
                result = cmd.execute("192.168.1.0/24")

                assert "error" in result
                assert "not found" in result["error"].lower()


class TestIPCommand:
    """Tests for IP command."""

    @pytest.fixture
    def ip_command(self):
        """Get IP command class."""
        return get_command("ip")

    def test_ip_command_properties(self, ip_command):
        """Test IP command properties."""
        assert ip_command.name == "ip"
        assert "ipv4" in ip_command.aliases
        assert "address" in ip_command.aliases

    def test_ip_execute_success(self, ip_command, mock_ip_response):
        """Test successful IP query."""
        mock_client = Mock()
        mock_client.get = Mock(side_effect=lambda obj, **kwargs:
            mock_ip_response if obj == "ipv4address" else [])

        with patch('ddi_toolkit.wapi._client', mock_client):
            with patch('ddi_toolkit.wapi.get_client', return_value=mock_client):
                cmd = ip_command()
                cmd._client = mock_client
                result = cmd.execute("10.20.30.50")

                assert result["ip_address"] == "10.20.30.50"
                assert result["status"] == "USED"
                assert "bindings" in result
                assert "dns_records" in result
                assert "audit" in result

    def test_ip_execute_not_found(self, ip_command):
        """Test IP query when not found."""
        mock_client = Mock()
        mock_client.get = Mock(return_value=[])

        with patch('ddi_toolkit.wapi._client', mock_client):
            with patch('ddi_toolkit.wapi.get_client', return_value=mock_client):
                cmd = ip_command()
                cmd._client = mock_client
                result = cmd.execute("192.168.1.50")

                assert "error" in result
                assert "not found" in result["error"].lower()


class TestZoneCommand:
    """Tests for zone command."""

    @pytest.fixture
    def zone_command(self):
        """Get zone command class."""
        return get_command("zone")

    def test_zone_command_properties(self, zone_command):
        """Test zone command properties."""
        assert zone_command.name == "zone"
        assert "dns" in zone_command.aliases
        assert "domain" in zone_command.aliases

    def test_zone_execute_success(self, zone_command, mock_zone_response):
        """Test successful zone query."""
        mock_client = Mock()

        def mock_get(obj, **kwargs):
            if obj == "zone_auth":
                return mock_zone_response
            elif obj.startswith("record:"):
                return [{"name": "test"}] * 5
            elif obj == "auditlog":
                return []
            return []

        mock_client.get = Mock(side_effect=mock_get)

        with patch('ddi_toolkit.wapi._client', mock_client):
            with patch('ddi_toolkit.wapi.get_client', return_value=mock_client):
                cmd = zone_command()
                cmd._client = mock_client
                result = cmd.execute("example.com")

                assert result["fqdn"] == "example.com"
                assert result["zone_type"] == "authoritative"
                assert "record_counts" in result
                assert "audit" in result


class TestContainerCommand:
    """Tests for container command."""

    @pytest.fixture
    def container_command(self):
        """Get container command class."""
        return get_command("container")

    def test_container_command_properties(self, container_command):
        """Test container command properties."""
        assert container_command.name == "container"
        assert "netcontainer" in container_command.aliases

    def test_container_execute_success(self, container_command, mock_container_response):
        """Test successful container query."""
        mock_client = Mock()

        def mock_get(obj, **kwargs):
            params = kwargs.get("params", {})
            if obj == "networkcontainer" and params.get("network"):
                return mock_container_response
            elif obj == "auditlog":
                return []
            return []

        mock_client.get = Mock(side_effect=mock_get)

        with patch('ddi_toolkit.wapi._client', mock_client):
            with patch('ddi_toolkit.wapi.get_client', return_value=mock_client):
                cmd = container_command()
                cmd._client = mock_client
                result = cmd.execute("10.0.0.0/8")

                assert result["network"] == "10.0.0.0/8"
                assert "hierarchy" in result
                assert "statistics" in result
                assert "audit" in result


class TestDHCPCommand:
    """Tests for DHCP command."""

    @pytest.fixture
    def dhcp_command(self):
        """Get DHCP command class."""
        return get_command("dhcp")

    def test_dhcp_command_properties(self, dhcp_command):
        """Test DHCP command properties."""
        assert dhcp_command.name == "dhcp"
        assert "lease" in dhcp_command.aliases
        assert "pool" in dhcp_command.aliases

    def test_dhcp_ranges_query(self, dhcp_command, mock_range_response):
        """Test DHCP ranges query."""
        mock_client = Mock()
        mock_client.get = Mock(return_value=mock_range_response)

        with patch('ddi_toolkit.wapi._client', mock_client):
            with patch('ddi_toolkit.wapi.get_client', return_value=mock_client):
                cmd = dhcp_command()
                cmd._client = mock_client
                result = cmd.execute("ranges")

                assert result["query_type"] == "ranges"
                assert "ranges" in result
                assert "statistics" in result

    def test_dhcp_leases_query(self, dhcp_command, mock_lease_response):
        """Test DHCP leases query."""
        mock_client = Mock()
        mock_client.get = Mock(return_value=mock_lease_response)

        with patch('ddi_toolkit.wapi._client', mock_client):
            with patch('ddi_toolkit.wapi.get_client', return_value=mock_client):
                cmd = dhcp_command()
                cmd._client = mock_client
                result = cmd.execute("leases")

                assert result["query_type"] == "leases"
                assert "leases" in result
                assert "statistics" in result

    def test_dhcp_invalid_query_type(self, dhcp_command):
        """Test DHCP with invalid query type."""
        mock_client = Mock()

        with patch('ddi_toolkit.wapi._client', mock_client):
            with patch('ddi_toolkit.wapi.get_client', return_value=mock_client):
                cmd = dhcp_command()
                cmd._client = mock_client
                result = cmd.execute("invalid")

                assert "error" in result
                assert "Unknown query type" in result["error"]


class TestSearchCommand:
    """Tests for search command."""

    @pytest.fixture
    def search_command(self):
        """Get search command class."""
        return get_command("search")

    def test_search_command_properties(self, search_command):
        """Test search command properties."""
        assert search_command.name == "search"
        assert "find" in search_command.aliases
        assert "lookup" in search_command.aliases

    def test_search_execute(self, search_command):
        """Test search execution."""
        mock_client = Mock()
        mock_client.get = Mock(return_value=[])

        with patch('ddi_toolkit.wapi._client', mock_client):
            with patch('ddi_toolkit.wapi.get_client', return_value=mock_client):
                cmd = search_command()
                cmd._client = mock_client
                result = cmd.execute("test-server")

                assert result["query"] == "test-server"
                assert "results" in result
                assert "statistics" in result


class TestSearchInputDetection:
    """Tests for intelligent search input detection."""

    @pytest.fixture
    def search_cmd(self):
        """Get search command instance."""
        cmd_class = get_command("search")
        return cmd_class()

    def test_detect_ip_address(self, search_cmd):
        """Test IP address detection."""
        detected_type, search_types = search_cmd._detect_input_type("10.20.30.40")
        assert detected_type == "ip_address"
        assert "ipv4address" in search_types
        assert "record:host" in search_types
        assert "record:ptr" in search_types

    def test_detect_cidr(self, search_cmd):
        """Test CIDR detection."""
        detected_type, search_types = search_cmd._detect_input_type("10.20.30.0/24")
        assert detected_type == "cidr"
        assert "network" in search_types
        assert "networkcontainer" in search_types

    def test_detect_mac_address(self, search_cmd):
        """Test MAC address detection."""
        detected_type, search_types = search_cmd._detect_input_type("00:50:56:aa:bb:cc")
        assert detected_type == "mac_address"
        assert "fixedaddress" in search_types
        assert "lease" in search_types

    def test_detect_mac_address_with_dashes(self, search_cmd):
        """Test MAC address detection with dash separators."""
        detected_type, search_types = search_cmd._detect_input_type("00-50-56-aa-bb-cc")
        assert detected_type == "mac_address"

    def test_detect_fqdn(self, search_cmd):
        """Test FQDN/hostname detection."""
        detected_type, search_types = search_cmd._detect_input_type("server.example.com")
        assert detected_type == "fqdn"
        assert "record:host" in search_types
        assert "record:a" in search_types
        assert "record:cname" in search_types

    def test_detect_zone(self, search_cmd):
        """Test zone/domain detection (2-part domain)."""
        detected_type, search_types = search_cmd._detect_input_type("example.com")
        assert detected_type == "zone"
        assert "zone_auth" in search_types
        assert "record:host" in search_types

    def test_detect_generic_text(self, search_cmd):
        """Test generic text detection."""
        detected_type, search_types = search_cmd._detect_input_type("webserver")
        assert detected_type == "text"
        assert "record:host" in search_types
        assert "network" in search_types


class TestSearchTypePrefixes:
    """Tests for type prefix parsing."""

    @pytest.fixture
    def search_cmd(self):
        """Get search command instance."""
        cmd_class = get_command("search")
        return cmd_class()

    def test_parse_host_prefix(self, search_cmd):
        """Test host: prefix parsing."""
        forced_type, clean_query = search_cmd._parse_type_prefix("host:myserver.com")
        assert forced_type == "host"
        assert clean_query == "myserver.com"

    def test_parse_ptr_prefix(self, search_cmd):
        """Test ptr: prefix parsing."""
        forced_type, clean_query = search_cmd._parse_type_prefix("ptr:10.20.30.40")
        assert forced_type == "ptr"
        assert clean_query == "10.20.30.40"

    def test_parse_zone_prefix(self, search_cmd):
        """Test zone: prefix parsing."""
        forced_type, clean_query = search_cmd._parse_type_prefix("zone:marriott.com")
        assert forced_type == "zone"
        assert clean_query == "marriott.com"

    def test_parse_ip_prefix(self, search_cmd):
        """Test ip: prefix parsing."""
        forced_type, clean_query = search_cmd._parse_type_prefix("ip:10.20.30.40")
        assert forced_type == "ip"
        assert clean_query == "10.20.30.40"

    def test_parse_mac_prefix(self, search_cmd):
        """Test mac: prefix parsing."""
        forced_type, clean_query = search_cmd._parse_type_prefix("mac:00:50:56:aa:bb:cc")
        assert forced_type == "mac"
        assert clean_query == "00:50:56:aa:bb:cc"

    def test_parse_all_prefix(self, search_cmd):
        """Test all: prefix parsing."""
        forced_type, clean_query = search_cmd._parse_type_prefix("all:webserver")
        assert forced_type == "all"
        assert clean_query == "webserver"

    def test_parse_a_record_prefix(self, search_cmd):
        """Test a: prefix parsing."""
        forced_type, clean_query = search_cmd._parse_type_prefix("a:myhost.com")
        assert forced_type == "a_record"
        assert clean_query == "myhost.com"

    def test_parse_cname_prefix(self, search_cmd):
        """Test cname: prefix parsing."""
        forced_type, clean_query = search_cmd._parse_type_prefix("cname:www.example.com")
        assert forced_type == "cname"
        assert clean_query == "www.example.com"

    def test_parse_no_prefix(self, search_cmd):
        """Test query without prefix."""
        forced_type, clean_query = search_cmd._parse_type_prefix("webserver.example.com")
        assert forced_type is None
        assert clean_query == "webserver.example.com"

    def test_parse_unknown_prefix(self, search_cmd):
        """Test query with unknown prefix (treated as no prefix)."""
        forced_type, clean_query = search_cmd._parse_type_prefix("unknown:value")
        assert forced_type is None
        assert clean_query == "unknown:value"


class TestSearchForcedTypes:
    """Tests for forced type search mapping."""

    @pytest.fixture
    def search_cmd(self):
        """Get search command instance."""
        cmd_class = get_command("search")
        return cmd_class()

    def test_forced_type_host(self, search_cmd):
        """Test host forced type."""
        types = search_cmd._get_search_types_for_forced_type("host")
        assert types == ["record:host"]

    def test_forced_type_ptr(self, search_cmd):
        """Test ptr forced type."""
        types = search_cmd._get_search_types_for_forced_type("ptr")
        assert types == ["record:ptr"]

    def test_forced_type_zone(self, search_cmd):
        """Test zone forced type."""
        types = search_cmd._get_search_types_for_forced_type("zone")
        assert types == ["zone_auth"]

    def test_forced_type_mac(self, search_cmd):
        """Test mac forced type."""
        types = search_cmd._get_search_types_for_forced_type("mac")
        assert "fixedaddress" in types
        assert "lease" in types

    def test_forced_type_network(self, search_cmd):
        """Test network forced type."""
        types = search_cmd._get_search_types_for_forced_type("network")
        assert "network" in types
        assert "networkcontainer" in types

    def test_forced_type_all(self, search_cmd):
        """Test all forced type returns None (triggers full search)."""
        types = search_cmd._get_search_types_for_forced_type("all")
        assert types is None


class TestSearchExecution:
    """Tests for search execution with different input types."""

    @pytest.fixture
    def search_cmd(self):
        """Get search command instance."""
        cmd_class = get_command("search")
        return cmd_class()

    def test_execute_with_fqdn(self, search_cmd):
        """Test search execution with FQDN."""
        mock_client = Mock()
        mock_client.get = Mock(return_value=[
            {"_ref": "record:host/xyz", "name": "server.example.com", "view": "default"}
        ])

        with patch('ddi_toolkit.wapi._client', mock_client):
            with patch('ddi_toolkit.wapi.get_client', return_value=mock_client):
                search_cmd._client = mock_client
                result = search_cmd.execute("server.example.com")

                assert result["detected_type"] == "fqdn"
                assert result["zone_hint"] == "example.com"
                assert "host_records" in result["results"]

    def test_execute_with_prefix(self, search_cmd):
        """Test search execution with type prefix."""
        mock_client = Mock()
        mock_client.get = Mock(return_value=[])

        with patch('ddi_toolkit.wapi._client', mock_client):
            with patch('ddi_toolkit.wapi.get_client', return_value=mock_client):
                search_cmd._client = mock_client
                result = search_cmd.execute("ptr:10.20.30.40")

                assert result["detected_type"] == "explicit:ptr"
                assert result["clean_query"] == "10.20.30.40"

    def test_execute_provides_suggestions(self, search_cmd):
        """Test that no results provides suggestions."""
        mock_client = Mock()
        mock_client.get = Mock(return_value=[])

        with patch('ddi_toolkit.wapi._client', mock_client):
            with patch('ddi_toolkit.wapi.get_client', return_value=mock_client):
                search_cmd._client = mock_client
                result = search_cmd.execute("nonexistent.example.com")

                assert result["statistics"]["total_results"] == 0
                assert len(result["suggestions"]) > 0

    def test_execute_with_ip_includes_ptr(self, search_cmd):
        """Test IP search includes PTR record types."""
        mock_client = Mock()
        mock_client.get = Mock(return_value=[])

        with patch('ddi_toolkit.wapi._client', mock_client):
            with patch('ddi_toolkit.wapi.get_client', return_value=mock_client):
                search_cmd._client = mock_client
                result = search_cmd.execute("10.20.30.40")

                assert result["detected_type"] == "ip_address"
                assert "record:ptr" in result["searched_types"]

    def test_execute_with_all_prefix(self, search_cmd):
        """Test all: prefix triggers full search."""
        mock_client = Mock()
        mock_client.get = Mock(return_value=[])

        with patch('ddi_toolkit.wapi._client', mock_client):
            with patch('ddi_toolkit.wapi.get_client', return_value=mock_client):
                search_cmd._client = mock_client
                result = search_cmd.execute("all:webserver")

                assert result["detected_type"] == "all"
                assert result["searched_types"] == ["all"]
