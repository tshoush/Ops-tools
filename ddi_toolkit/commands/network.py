"""
Network query command.
"""

from typing import Dict, Any, List, Tuple
from .base import BaseCommand
from ..audit import get_audit_for_object, format_audit_summary


# Maximum IPs to fetch to prevent memory issues on large networks
MAX_IP_FETCH = 10000


class NetworkCommand(BaseCommand):
    """Query network information including DHCP and utilization."""

    name = "network"
    description = "Query network details, DHCP ranges, utilization, audit info"
    aliases = ["net", "subnet"]

    RETURN_FIELDS = [
        "network", "network_view", "comment", "extattrs",
        "options", "members", "utilization", "total_hosts",
        "dhcp_utilization", "dynamic_hosts", "static_hosts"
    ]

    # Core range fields supported across WAPI versions
    RANGE_RETURN_FIELDS = [
        "start_addr", "end_addr", "server_association_type",
        "member", "failover_association", "options", "comment",
        "disable", "name"
    ]

    MEMBER_DHCP_FIELDS = [
        "host_name", "ipv4addr", "enable_dhcp"
    ]

    IP_RETURN_FIELDS = [
        "ip_address", "status", "types", "names", "mac_address",
        "network", "network_view", "usage", "is_conflict"
    ]

    def execute(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Query network by CIDR.

        Args:
            query: Network CIDR (e.g., "10.20.30.0/24")
            network_view: Network view (default: "default")
            all_views: If True, search across all network views
            include_audit: Include audit trail (default: True)
            include_ips: Include all IP addresses in the network (default: True)

        Returns:
            Network details including DHCP ranges, leases, IPs, and audit info
        """
        network_view = kwargs.get("network_view", "default")
        all_views = kwargs.get("all_views", False)
        include_audit = kwargs.get("include_audit", True)
        include_ips = kwargs.get("include_ips", True)

        # 1. Get Network Object
        network, error_response = self._get_network(query, network_view, all_views)
        if error_response:
            return error_response
        
        object_ref = network.get("_ref", "")
        actual_view = network.get("network_view", network_view)

        # Build params for related queries
        related_params = {"network": query}
        if actual_view:
            related_params["network_view"] = actual_view

        # 2. Get DHCP Ranges
        ranges = self._get_dhcp_ranges(related_params)

        # 3. Get DHCP Servers and Options
        dhcp_servers = self._get_dhcp_servers(ranges)
        effective_options = self._get_effective_options(network, ranges)

        # 4. Get Active Leases
        leases = self._get_active_leases(related_params)

        # 5. Get IP Addresses
        ip_addresses, ip_stats = self._get_ip_addresses(related_params, include_ips)

        # 6. Get Audit Info
        audit_info, audit_summary = self._get_audit_info(
            object_ref, query, include_audit
        )

        # 7. Build Response
        view_note = network.get("_view_note")
        all_views_found = network.get("_all_views", [])

        result = {
            "network": network.get("network"),
            "network_view": network.get("network_view"),
            "view_note": view_note,  # Note if found in different view than requested
            "available_in_views": all_views_found if len(all_views_found) > 1 else None,
            "comment": network.get("comment", ""),
            "utilization": {
                "percentage": network.get("utilization"),
                "total_hosts": network.get("total_hosts"),
                "dynamic_hosts": network.get("dynamic_hosts"),
                "static_hosts": network.get("static_hosts"),
                "dhcp_utilization": network.get("dhcp_utilization")
            },
            "dhcp": {
                "ranges": ranges,
                "range_count": len(ranges),
                "servers": dhcp_servers,
                "server_count": len(dhcp_servers),
                "effective_options": effective_options
            },
            "active_leases": leases,
            "lease_count": len(leases),
            "ip_addresses": ip_addresses,
            "ip_statistics": {
                "total": ip_stats["total"],
                "used": ip_stats["used"],
                "unused": ip_stats["unused"]
            },
            "options": network.get("options", []),
            "members": network.get("members", []),
            "extattrs": network.get("extattrs", {}),
            "audit": {
                "created": audit_info.get("timestamps", {}).get("created"),
                "created_by": audit_info.get("created_by"),
                "last_modified": audit_info.get("timestamps", {}).get("last_modified"),
                "last_modified_by": audit_info.get("last_modified_by"),
                "recent_changes": audit_info.get("wapi_audit", [])[:5],
                "splunk_audit": audit_info.get("splunk_audit", [])
            },
            "_ref": object_ref,
            "_summary": {
                "Network": query,
                "View": network.get("network_view", "N/A"),
                **({"Note": view_note} if view_note else {}),
                "Utilization": f"{network.get('utilization', 'N/A')}%",
                "Total Hosts": network.get("total_hosts", "N/A"),
                "Used IPs": ip_stats["used"],
                "Unused IPs": ip_stats["unused"],
                "DHCP Ranges": len(ranges),
                "DHCP Servers": len(dhcp_servers),
                "Active Leases": len(leases),
                **audit_summary
            }
        }

        return result

    def _get_network(
        self, query: str, network_view: str, all_views: bool
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Fetch the network object, handling view logic.

        If network not found in specified view, automatically searches all views
        and returns the first match with info about which view it was found in.
        """
        # Normalize network_view
        if not network_view or network_view == "None":
            network_view = "default"

        params = {"network": query}
        if not all_views:
            params["network_view"] = network_view

        networks = self.client.get(
            "network",
            params=params,
            return_fields=self.RETURN_FIELDS
        )

        if not networks:
            # Network not found in specified view - search all views automatically
            if not all_views:
                all_networks = self.client.get(
                    "network",
                    params={"network": query},
                    return_fields=self.RETURN_FIELDS
                )

                if all_networks:
                    # Found in other view(s) - use the first one and note where it was found
                    network = all_networks[0]
                    found_view = network.get("network_view", "unknown")
                    other_views = [
                        n.get("network_view") for n in all_networks
                        if n.get("network_view")
                    ]

                    # Add metadata about the view search
                    network["_view_note"] = f"Not found in '{network_view}', found in '{found_view}'"
                    network["_all_views"] = other_views

                    return network, {}

            # Not found anywhere
            return {}, {
                "error": f"Network {query} not found",
                "query": query,
                "network_view": network_view if not all_views else "all"
            }

        return networks[0], {}

    def _get_dhcp_ranges(self, params: Dict[str, str]) -> List[Dict[str, Any]]:
        """Fetch DHCP ranges for the network."""
        return self.client.get(
            "range",
            params=params,
            return_fields=self.RANGE_RETURN_FIELDS
        )

    def _get_dhcp_servers(self, ranges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify unique DHCP servers from ranges."""
        if not ranges:
            return []

        member_set = set()
        for rng in ranges:
            member = rng.get("member")
            if member and isinstance(member, dict):
                # Member could be struct with _struct field
                member_name = member.get("name") or member.get("_struct")
                if member_name:
                    member_set.add(member_name)
            elif member and isinstance(member, str):
                member_set.add(member)

            # Also check failover association for servers
            failover = rng.get("failover_association")
            if failover:
                member_set.add(failover)

        dhcp_servers = []
        for member_name in member_set:
            try:
                member_info = self.client.get(
                    "member:dhcpproperties",
                    params={"host_name": member_name},
                    return_fields=[
                        "host_name", "ipv4addr", "enable_dhcp",
                        "options", "option"
                    ]
                )
                if member_info:
                    dhcp_servers.append(member_info[0])
            except Exception:
                pass
        
        return dhcp_servers

    def _get_effective_options(
        self, network: Dict[str, Any], ranges: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Calculate effective options by merging network and range options."""
        if not ranges:
            return []

        effective_options = []
        network_options = network.get("options", [])
        
        for rng in ranges:
            range_options = rng.get("options", [])
            range_option_detail = rng.get("option", {})

            effective = {
                "range": f"{rng.get('start_addr')}-{rng.get('end_addr')}",
                "network_options": network_options,
                "range_options": range_options,
                "range_option_detail": range_option_detail
            }
            effective_options.append(effective)
            
        return effective_options

    def _get_active_leases(self, params: Dict[str, str]) -> List[Dict[str, Any]]:
        """Fetch active DHCP leases."""
        return self.client.get(
            "lease",
            params=params,
            return_fields=[
                "address", "hardware", "client_hostname",
                "starts", "ends", "binding_state", "served_by"
            ]
        )

    def _get_ip_addresses(
        self, params: Dict[str, str], include_ips: bool
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """Fetch IP addresses and calculate usage stats."""
        ip_addresses = []
        ip_stats = {"total": 0, "used": 0, "unused": 0, "truncated": False}

        if include_ips:
            all_ips = self.client.get(
                "ipv4address",
                params=params,
                return_fields=self.IP_RETURN_FIELDS,
                paging=True,
                page_size=1000,
                max_results=MAX_IP_FETCH
            )

            ip_stats["total"] = len(all_ips)
            if len(all_ips) >= MAX_IP_FETCH:
                ip_stats["truncated"] = True

            for ip in all_ips:
                status = ip.get("status", "").upper()
                if status == "UNUSED":
                    ip_stats["unused"] += 1
                else:
                    ip_stats["used"] += 1
                    ip_addresses.append(ip)

        return ip_addresses, ip_stats

    def _get_audit_info(
        self, object_ref: str, query: str, include_audit: bool
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Fetch audit information."""
        if not include_audit:
            return {}, {}

        audit_info = get_audit_for_object(
            object_ref=object_ref,
            object_type="NETWORK",
            object_name=query,
            max_results=10
        )
        audit_summary = format_audit_summary(audit_info)
        return audit_info, audit_summary


# Register command
command = NetworkCommand
