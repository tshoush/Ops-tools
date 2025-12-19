"""
IP address query command.
"""

from typing import Dict, Any
from .base import BaseCommand
from ..audit import get_audit_for_object, format_audit_summary


class IPCommand(BaseCommand):
    """Query IP address status, bindings, and history."""

    name = "ip"
    description = "Query IP address details, bindings, conflicts, audit info"
    aliases = ["ipv4", "address", "addr"]

    # Core fields supported across WAPI versions
    RETURN_FIELDS = [
        "ip_address", "status", "types", "names", "mac_address",
        "network", "network_view", "usage", "extattrs",
        "lease_state", "is_conflict"
    ]

    def execute(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Query IP address.

        Args:
            query: IP address (e.g., "10.20.30.50")
            network_view: Network view (default: "default")
            all_views: If True, search across all network views
            include_audit: Include audit trail (default: True)

        Returns:
            IP address details including bindings, conflicts, and audit info
        """
        network_view = kwargs.get("network_view", "default")
        all_views = kwargs.get("all_views", False)
        include_audit = kwargs.get("include_audit", True)

        # Build query params
        params = {"ip_address": query}
        if not all_views and network_view:
            params["network_view"] = network_view

        # Get IP address object
        addresses = self.client.get(
            "ipv4address",
            params=params,
            return_fields=self.RETURN_FIELDS
        )

        if not addresses:
            # Check if IP exists in other views
            other_views = []
            if not all_views:
                all_addresses = self.client.get(
                    "ipv4address",
                    params={"ip_address": query},
                    return_fields=["ip_address", "network_view"]
                )
                other_views = [a.get("network_view") for a in all_addresses if a.get("network_view")]

            if other_views:
                return {
                    "error": f"IP {query} not found in view '{network_view}'",
                    "found_in_views": other_views,
                    "query": query,
                    "network_view": network_view,
                    "hint": f"IP exists in: {', '.join(other_views)}"
                }
            else:
                return {
                    "error": f"IP {query} not found or not in managed range",
                    "query": query,
                    "network_view": network_view
                }

        addr = addresses[0]
        object_ref = addr.get("_ref", "")
        actual_view = addr.get("network_view", network_view)

        # Build params for related queries using actual view
        related_params_view = {"network_view": actual_view} if actual_view else {}

        # Check for fixed address binding
        fixed = self.client.get(
            "fixedaddress",
            params={"ipv4addr": query, **related_params_view},
            return_fields=[
                "mac", "name", "comment", "match_client",
                "extattrs", "disable", "options"
            ]
        )
        fixed_ref = fixed[0].get("_ref") if fixed else None

        # Check for lease
        lease = self.client.get(
            "lease",
            params={"address": query, **related_params_view},
            return_fields=[
                "hardware", "client_hostname", "starts", "ends",
                "binding_state", "served_by", "tstp", "cltt"
            ]
        )

        # Check for host record
        hosts = self.client.get(
            "record:host",
            params={"ipv4addr": query},
            return_fields=["name", "view", "comment", "extattrs", "ttl"]
        )
        host_ref = hosts[0].get("_ref") if hosts else None

        # Check for A records
        a_records = self.client.get(
            "record:a",
            params={"ipv4addr": query},
            return_fields=["name", "view", "comment", "ttl"]
        )

        # Check for PTR records
        ptr_records = self.client.get(
            "record:ptr",
            params={"ipv4addr": query},
            return_fields=["ptrdname", "view", "comment", "ttl"]
        )

        # Get audit information
        # We query audit for multiple related objects
        audit_info = {}
        audit_summary = {}
        if include_audit:
            # Try to get audit for the most relevant object
            # Priority: fixed address > host record > IP address
            audit_ref = fixed_ref or host_ref or object_ref
            audit_type = "FIXEDADDRESS" if fixed_ref else ("HOST" if host_ref else "IPV4ADDRESS")

            audit_info = get_audit_for_object(
                object_ref=audit_ref,
                object_type=audit_type,
                object_name=query,
                max_results=10
            )
            audit_summary = format_audit_summary(audit_info)

        result = {
            "ip_address": addr.get("ip_address"),
            "status": addr.get("status"),
            "types": addr.get("types", []),
            "names": addr.get("names", []),
            "mac_address": addr.get("mac_address", ""),
            "network": addr.get("network"),
            "network_view": addr.get("network_view"),
            "conflict": addr.get("is_conflict", False),
            "usage": addr.get("usage", []),
            "lease_state": addr.get("lease_state"),
            "bindings": {
                "fixed_address": fixed[0] if fixed else None,
                "lease": lease[0] if lease else None,
            },
            "dns_records": {
                "host_records": hosts,
                "a_records": a_records,
                "ptr_records": ptr_records
            },
            "discovered_data": addr.get("discovered_data"),
            "extattrs": addr.get("extattrs", {}),
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
                "IP Address": query,
                "Status": addr.get("status", "N/A"),
                "Types": ", ".join(addr.get("types", [])) or "N/A",
                "MAC": addr.get("mac_address") or "N/A",
                "Conflict": "Yes" if addr.get("is_conflict") else "No",
                "DNS Names": len(addr.get("names", [])),
                **audit_summary
            }
        }

        return result


# Register command
command = IPCommand
