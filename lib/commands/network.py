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

        # Get DHCP ranges for this network
        ranges = self.client.get(
            "range",
            params=related_params,
            return_fields=[
                "start_addr", "end_addr", "server_association_type",
                "member", "options", "comment", "disable"
            ]
        )

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
            "dhcp_ranges": ranges,
            "dhcp_range_count": len(ranges),
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
                "Active Leases": len(leases),
                **audit_summary
            }
        }

        return result


# Register command
command = NetworkCommand
