"""
Network Container query command.
"""

from typing import Dict, Any, List
from .base import BaseCommand
from ..audit import get_audit_for_object, format_audit_summary


class ContainerCommand(BaseCommand):
    """Query network container information and hierarchy."""

    name = "container"
    description = "Query network container details, hierarchy, audit info"
    aliases = ["netcontainer", "nc"]

    RETURN_FIELDS = [
        "network", "network_view", "comment", "extattrs",
        "options", "utilization"
    ]

    def execute(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Query network container by CIDR.

        Args:
            query: Container CIDR (e.g., "10.0.0.0/8")
            network_view: Network view (default: "default")
            all_views: If True, search across all network views
            include_audit: Include audit trail (default: True)

        Returns:
            Container details including child networks and audit info
        """
        network_view = kwargs.get("network_view", "default")
        all_views = kwargs.get("all_views", False)
        include_audit = kwargs.get("include_audit", True)

        # Build query params
        params = {"network": query}
        if not all_views and network_view:
            params["network_view"] = network_view

        # Get container object
        containers = self.client.get(
            "networkcontainer",
            params=params,
            return_fields=self.RETURN_FIELDS
        )

        if not containers:
            return {
                "error": f"Container {query} not found",
                "query": query,
                "network_view": network_view
            }

        container = containers[0]
        object_ref = container.get("_ref", "")
        actual_view = container.get("network_view", network_view)

        # Build params for child queries using actual view
        child_params = {"network_container": query}
        if actual_view:
            child_params["network_view"] = actual_view

        # Get child containers
        child_containers = self.client.get(
            "networkcontainer",
            params=child_params,
            return_fields=["network", "comment", "utilization"]
        )

        # Get child networks
        child_networks = self.client.get(
            "network",
            params=child_params,
            return_fields=[
                "network", "comment", "utilization",
                "total_hosts", "dhcp_utilization"
            ]
        )

        # Calculate summary stats
        total_child_containers = len(child_containers)
        total_child_networks = len(child_networks)
        total_hosts = sum(n.get("total_hosts", 0) or 0 for n in child_networks)

        # Get audit information
        audit_info = {}
        audit_summary = {}
        if include_audit:
            audit_info = get_audit_for_object(
                object_ref=object_ref,
                object_type="NETWORKCONTAINER",
                object_name=query,
                max_results=10
            )
            audit_summary = format_audit_summary(audit_info)

        result = {
            "network": container.get("network"),
            "network_view": container.get("network_view"),
            "comment": container.get("comment", ""),
            "utilization": container.get("utilization"),
            "hierarchy": {
                "child_containers": child_containers,
                "child_networks": child_networks,
                "child_container_count": total_child_containers,
                "child_network_count": total_child_networks
            },
            "statistics": {
                "total_child_containers": total_child_containers,
                "total_child_networks": total_child_networks,
                "total_hosts_in_children": total_hosts
            },
            "options": container.get("options", []),
            "extattrs": container.get("extattrs", {}),
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
                "Container": query,
                "Utilization": f"{container.get('utilization', 'N/A')}%",
                "Child Containers": total_child_containers,
                "Child Networks": total_child_networks,
                "Total Hosts": total_hosts,
                **audit_summary
            }
        }

        return result


# Register command
command = ContainerCommand
