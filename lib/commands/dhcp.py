"""
DHCP query command.
"""

from typing import Dict, Any, List
from .base import BaseCommand
from ..audit import get_audit_for_object, format_audit_summary


class DHCPCommand(BaseCommand):
    """Query DHCP ranges, leases, and failover status."""

    name = "dhcp"
    description = "Query DHCP pools, leases, failover, with audit info"
    aliases = ["lease", "pool"]

    def execute(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Query DHCP information.

        Args:
            query: Query type - 'ranges', 'leases', or 'failover'
            network: Optional network filter (CIDR)
            network_view: Network view (default: "default")
            all_views: If True, search across all network views
            include_audit: Include audit trail (default: True)

        Returns:
            DHCP information based on query type with audit info
        """
        network = kwargs.get("network")
        network_view = kwargs.get("network_view", "default")
        all_views = kwargs.get("all_views", False)
        include_audit = kwargs.get("include_audit", True)

        if query == "ranges":
            return self._query_ranges(network, network_view, all_views, include_audit)
        elif query == "leases":
            return self._query_leases(network, network_view, all_views, include_audit)
        elif query == "failover":
            return self._query_failover(include_audit)
        else:
            return {
                "error": f"Unknown query type: {query}",
                "valid_types": ["ranges", "leases", "failover"]
            }

    def _query_ranges(
        self,
        network: str,
        network_view: str,
        all_views: bool,
        include_audit: bool
    ) -> Dict[str, Any]:
        """Query DHCP ranges/pools with audit info."""
        params = {}
        if not all_views and network_view:
            params["network_view"] = network_view
        if network:
            params["network"] = network

        ranges = self.client.get(
            "range",
            params=params,
            return_fields=[
                "start_addr", "end_addr", "network", "network_view",
                "server_association_type", "member", "failover_association",
                "options", "comment", "disable", "extattrs"
            ]
        )

        # Calculate statistics
        total_ranges = len(ranges)
        disabled_ranges = sum(1 for r in ranges if r.get("disable"))
        active_ranges = total_ranges - disabled_ranges

        # Get audit info for each range (limited to first 5 for performance)
        if include_audit and ranges:
            for i, rng in enumerate(ranges[:5]):
                rng_ref = rng.get("_ref", "")
                rng_name = f"{rng.get('start_addr', '')}-{rng.get('end_addr', '')}"
                audit_info = get_audit_for_object(
                    object_ref=rng_ref,
                    object_type="RANGE",
                    object_name=rng_name,
                    max_results=3
                )
                ranges[i]["audit"] = {
                    "created": audit_info.get("timestamps", {}).get("created"),
                    "created_by": audit_info.get("created_by"),
                    "last_modified": audit_info.get("timestamps", {}).get("last_modified"),
                    "last_modified_by": audit_info.get("last_modified_by")
                }

        result = {
            "query_type": "ranges",
            "network_filter": network,
            "network_view": network_view,
            "ranges": ranges,
            "statistics": {
                "total_ranges": total_ranges,
                "active_ranges": active_ranges,
                "disabled_ranges": disabled_ranges
            },
            "_summary": {
                "Query": "DHCP Ranges",
                "Network Filter": network or "All",
                "Total Ranges": total_ranges,
                "Active": active_ranges,
                "Disabled": disabled_ranges
            }
        }

        return result

    def _query_leases(
        self,
        network: str,
        network_view: str,
        all_views: bool,
        include_audit: bool
    ) -> Dict[str, Any]:
        """Query active DHCP leases with paging for large datasets."""
        params = {}
        if not all_views and network_view:
            params["network_view"] = network_view
        if network:
            params["network"] = network

        # Use paging for potentially large lease datasets
        leases = self.client.get(
            "lease",
            params=params,
            return_fields=[
                "address", "network", "network_view", "hardware",
                "client_hostname", "fingerprint", "starts", "ends",
                "binding_state", "served_by", "tstp", "cltt"
            ],
            paging=True,
            page_size=1000
        )

        # Categorize by binding state
        state_counts = {}
        for lease in leases:
            state = lease.get("binding_state", "unknown")
            state_counts[state] = state_counts.get(state, 0) + 1

        # Format lease timestamps for readability
        from datetime import datetime
        for lease in leases:
            for field in ["starts", "ends", "tstp", "cltt"]:
                if lease.get(field):
                    try:
                        ts = datetime.fromtimestamp(int(lease[field]))
                        lease[f"{field}_formatted"] = ts.strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, TypeError):
                        pass

        result = {
            "query_type": "leases",
            "network_filter": network,
            "network_view": network_view,
            "leases": leases,
            "statistics": {
                "total_leases": len(leases),
                "by_state": state_counts
            },
            "_summary": {
                "Query": "DHCP Leases",
                "Network Filter": network or "All",
                "Total Leases": len(leases),
                "Active": state_counts.get("active", 0),
                "Free": state_counts.get("free", 0)
            }
        }

        return result

    def _query_failover(self, include_audit: bool) -> Dict[str, Any]:
        """Query DHCP failover associations with audit info."""
        failovers = self.client.get(
            "dhcpfailover",
            return_fields=[
                "name", "primary", "secondary", "primary_state",
                "secondary_state", "primary_server_type", "secondary_server_type",
                "max_response_delay", "max_load_balance_delay",
                "max_unacked_updates", "max_client_lead_time",
                "load_balance_split", "extattrs"
            ]
        )

        # Count by state
        healthy = 0
        degraded = 0
        for fo in failovers:
            p_state = fo.get("primary_state", "").lower()
            s_state = fo.get("secondary_state", "").lower()

            if p_state == "normal" and s_state == "normal":
                healthy += 1
            else:
                degraded += 1

        # Get audit info for each failover association
        if include_audit and failovers:
            for i, fo in enumerate(failovers):
                fo_ref = fo.get("_ref", "")
                fo_name = fo.get("name", "")
                audit_info = get_audit_for_object(
                    object_ref=fo_ref,
                    object_type="DHCPFAILOVER",
                    object_name=fo_name,
                    max_results=5
                )
                failovers[i]["audit"] = {
                    "created": audit_info.get("timestamps", {}).get("created"),
                    "created_by": audit_info.get("created_by"),
                    "last_modified": audit_info.get("timestamps", {}).get("last_modified"),
                    "last_modified_by": audit_info.get("last_modified_by"),
                    "recent_changes": audit_info.get("wapi_audit", [])[:3]
                }

        result = {
            "query_type": "failover",
            "failover_associations": failovers,
            "statistics": {
                "total": len(failovers),
                "healthy": healthy,
                "degraded": degraded
            },
            "_summary": {
                "Query": "DHCP Failover",
                "Total Associations": len(failovers),
                "Healthy": healthy,
                "Degraded": degraded
            }
        }

        return result


# Register command
command = DHCPCommand
