"""
DNS Zone query command.
"""

from typing import Dict, Any
from .base import BaseCommand
from ..audit import get_audit_for_object, format_audit_summary


class ZoneCommand(BaseCommand):
    """Query DNS zone configuration and records."""

    name = "zone"
    description = "Query DNS zone details, servers, record counts, audit info"
    aliases = ["dns", "domain"]

    RETURN_FIELDS = [
        "fqdn", "view", "zone_format", "comment", "extattrs",
        "grid_primary", "grid_secondaries", "ns_group",
        "soa_default_ttl", "soa_expire", "soa_refresh", "soa_retry",
        "soa_mname", "soa_email", "soa_serial_number",
        "allow_transfer", "allow_update", "disable"
    ]

    def execute(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Query DNS zone.

        Args:
            query: Zone name (e.g., "example.com")
            dns_view: DNS view (default: "default")
            all_views: If True, search across all DNS views
            include_audit: Include audit trail (default: True)

        Returns:
            Zone details including servers, record counts, and audit info
        """
        dns_view = kwargs.get("dns_view", "default")
        all_views = kwargs.get("all_views", False)
        include_audit = kwargs.get("include_audit", True)
        zone_type = "authoritative"

        # Build query params
        params = {"fqdn": query}
        if not all_views and dns_view:
            params["view"] = dns_view

        # Get authoritative zone
        zones = self.client.get(
            "zone_auth",
            params=params,
            return_fields=self.RETURN_FIELDS
        )

        if not zones:
            # Try forward zone
            zones = self.client.get(
                "zone_forward",
                params=params,
                return_fields=[
                    "fqdn", "view", "comment", "forward_to",
                    "forwarding_servers", "extattrs", "disable"
                ]
            )
            if zones:
                zone_type = "forward"

        if not zones:
            # Try delegated zone
            zones = self.client.get(
                "zone_delegated",
                params=params,
                return_fields=[
                    "fqdn", "view", "comment", "delegate_to", "extattrs"
                ]
            )
            if zones:
                zone_type = "delegated"

        if not zones:
            return {
                "error": f"Zone {query} not found",
                "query": query,
                "dns_view": dns_view
            }

        zone = zones[0]
        object_ref = zone.get("_ref", "")
        actual_view = zone.get("view", dns_view)

        # Get record counts by type (only for authoritative zones)
        record_counts = {}
        total_records = 0

        if zone_type == "authoritative":
            record_types = ["a", "aaaa", "cname", "mx", "txt", "ptr", "srv", "ns"]

            for rtype in record_types:
                try:
                    records = self.client.get(
                        f"record:{rtype}",
                        params={"zone": query, "view": actual_view}
                    )
                    count = len(records)
                    record_counts[rtype.upper()] = count
                    total_records += count
                except Exception:
                    record_counts[rtype.upper()] = 0

        # Get audit information
        audit_info = {}
        audit_summary = {}
        if include_audit:
            audit_type_map = {
                "authoritative": "ZONE_AUTH",
                "forward": "ZONE_FORWARD",
                "delegated": "ZONE_DELEGATED"
            }
            audit_info = get_audit_for_object(
                object_ref=object_ref,
                object_type=audit_type_map.get(zone_type, "ZONE"),
                object_name=query,
                max_results=10
            )
            audit_summary = format_audit_summary(audit_info)

        result = {
            "fqdn": zone.get("fqdn"),
            "view": zone.get("view"),
            "zone_type": zone_type,
            "zone_format": zone.get("zone_format"),
            "disabled": zone.get("disable", False),
            "comment": zone.get("comment", ""),
            "dns_servers": {
                "primary": zone.get("grid_primary", []),
                "secondaries": zone.get("grid_secondaries", []),
                "ns_group": zone.get("ns_group")
            },
            "soa": {
                "mname": zone.get("soa_mname"),
                "email": zone.get("soa_email"),
                "serial": zone.get("soa_serial_number"),
                "default_ttl": zone.get("soa_default_ttl"),
                "expire": zone.get("soa_expire"),
                "refresh": zone.get("soa_refresh"),
                "retry": zone.get("soa_retry")
            },
            "record_counts": record_counts,
            "total_records": total_records,
            "extattrs": zone.get("extattrs", {}),
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
                "Zone": query,
                "Type": zone_type,
                "View": dns_view,
                "Disabled": "Yes" if zone.get("disable") else "No",
                "Total Records": total_records,
                **audit_summary
            }
        }

        # Add forward-specific fields
        if zone_type == "forward":
            result["forward_to"] = zone.get("forward_to", [])
            result["forwarding_servers"] = zone.get("forwarding_servers", [])

        # Add delegated-specific fields
        if zone_type == "delegated":
            result["delegate_to"] = zone.get("delegate_to", [])

        return result


# Register command
command = ZoneCommand
