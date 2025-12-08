"""
Network query command.
"""

from typing import Dict, Any, List
from .base import BaseCommand
from ..audit import get_audit_for_object, format_audit_summary


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

    RANGE_RETURN_FIELDS = [
        "start_addr", "end_addr", "server_association_type",
        "member", "failover_association", "options", "comment",
        "disable", "name", "bootfile", "bootserver",
        "deny_all_clients", "deny_bootp", "ignore_client_requested_options",
        "pxe_lease_time", "option"
    ]

    MEMBER_DHCP_FIELDS = [
        "host_name", "ipv4addr", "enable_dhcp",
        "options", "option"
    ]

    def execute(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Query network by CIDR.

        Args:
            query: Network CIDR (e.g., "10.20.30.0/24")
            network_view: Network view (default: "default")
            all_views: If True, search across all network views
            include_audit: Include audit trail (default: True)

        Returns:
            Network details including DHCP ranges, leases, and audit info
        """
        network_view = kwargs.get("network_view", "default")
        all_views = kwargs.get("all_views", False)
        include_audit = kwargs.get("include_audit", True)

        # Build query params
        params = {"network": query}
        if not all_views and network_view:
            params["network_view"] = network_view

        # Get network object
        networks = self.client.get(
            "network",
            params=params,
            return_fields=self.RETURN_FIELDS
        )

        if not networks:
            return {
                "error": f"Network {query} not found",
                "query": query,
                "network_view": network_view
            }

        network = networks[0]
        object_ref = network.get("_ref", "")
        actual_view = network.get("network_view", network_view)

        # Build params for related queries (use actual view from found network)
        related_params = {"network": query}
        if actual_view:
            related_params["network_view"] = actual_view

        # Get DHCP ranges for this network with full options
        ranges = self.client.get(
            "range",
            params=related_params,
            return_fields=self.RANGE_RETURN_FIELDS
        )

        # If ranges exist, get DHCP server info and effective options
        dhcp_servers = []
        effective_options = []
        if ranges:
            # Collect unique DHCP members from ranges
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

            # Get DHCP member/server details
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

            # Get effective DHCP options (network-level options merged with range options)
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

        # Get active leases
        leases = self.client.get(
            "lease",
            params=related_params,
            return_fields=[
                "address", "hardware", "client_hostname",
                "starts", "ends", "binding_state", "served_by"
            ]
        )

        # Get audit information
        audit_info = {}
        audit_summary = {}
        if include_audit:
            audit_info = get_audit_for_object(
                object_ref=object_ref,
                object_type="NETWORK",
                object_name=query,
                max_results=10
            )
            audit_summary = format_audit_summary(audit_info)

        # Build response
        result = {
            "network": network.get("network"),
            "network_view": network.get("network_view"),
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
                "Utilization": f"{network.get('utilization', 'N/A')}%",
                "Total Hosts": network.get("total_hosts", "N/A"),
                "DHCP Ranges": len(ranges),
                "DHCP Servers": len(dhcp_servers),
                "Active Leases": len(leases),
                **audit_summary
            }
        }

        return result


# Register command
command = NetworkCommand
