"""
Global search command.
"""

from typing import Dict, Any, List
from .base import BaseCommand


class SearchCommand(BaseCommand):
    """Global search across all InfoBlox objects."""

    name = "search"
    description = "Search across networks, IPs, zones, records"
    aliases = ["find", "lookup"]

    def execute(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Global search.

        Args:
            query: Search term
            network_view: Network view filter (default: "default")
            all_views: If True, search across all views
            max_results: Maximum results per object type (default: 25)

        Returns:
            Search results grouped by object type
        """
        max_results = kwargs.get("max_results", 25)
        network_view = kwargs.get("network_view", "default")
        all_views = kwargs.get("all_views", False)

        # Build view filter for network objects
        view_filter = {} if all_views else {"network_view": network_view}

        # Search across different object types
        results = {
            "networks": [],
            "containers": [],
            "ipv4addresses": [],
            "zones": [],
            "host_records": [],
            "a_records": [],
            "cname_records": [],
            "fixed_addresses": []
        }

        # Search networks
        try:
            results["networks"] = self.client.get(
                "network",
                params={"comment~": query, **view_filter},
                return_fields=["network", "network_view", "comment"],
                max_results=max_results
            )
        except Exception:
            pass

        # Search by network CIDR pattern
        try:
            net_by_cidr = self.client.get(
                "network",
                params={"network~": query, **view_filter},
                return_fields=["network", "network_view", "comment"],
                max_results=max_results
            )
            results["networks"].extend(net_by_cidr)
        except Exception:
            pass

        # Search containers
        try:
            results["containers"] = self.client.get(
                "networkcontainer",
                params={"comment~": query, **view_filter},
                return_fields=["network", "network_view", "comment"],
                max_results=max_results
            )
        except Exception:
            pass

        # Search zones
        try:
            results["zones"] = self.client.get(
                "zone_auth",
                params={"fqdn~": query},
                return_fields=["fqdn", "view", "comment"],
                max_results=max_results
            )
        except Exception:
            pass

        # Search host records
        try:
            results["host_records"] = self.client.get(
                "record:host",
                params={"name~": query},
                return_fields=["name", "view", "ipv4addrs", "comment"],
                max_results=max_results
            )
        except Exception:
            pass

        # Search A records
        try:
            results["a_records"] = self.client.get(
                "record:a",
                params={"name~": query},
                return_fields=["name", "view", "ipv4addr", "comment"],
                max_results=max_results
            )
        except Exception:
            pass

        # Search CNAME records
        try:
            results["cname_records"] = self.client.get(
                "record:cname",
                params={"name~": query},
                return_fields=["name", "view", "canonical", "comment"],
                max_results=max_results
            )
        except Exception:
            pass

        # Search fixed addresses by MAC or name
        try:
            results["fixed_addresses"] = self.client.get(
                "fixedaddress",
                params={"name~": query, **view_filter},
                return_fields=["ipv4addr", "mac", "name", "network_view", "comment"],
                max_results=max_results
            )
        except Exception:
            pass

        # Try MAC search
        try:
            fixed_by_mac = self.client.get(
                "fixedaddress",
                params={"mac~": query, **view_filter},
                return_fields=["ipv4addr", "mac", "name", "network_view", "comment"],
                max_results=max_results
            )
            results["fixed_addresses"].extend(fixed_by_mac)
        except Exception:
            pass

        # Calculate totals
        total_results = sum(len(v) for v in results.values())

        # Remove empty categories
        results = {k: v for k, v in results.items() if v}

        return {
            "query": query,
            "results": results,
            "statistics": {
                "total_results": total_results,
                "categories": len(results),
                "by_type": {k: len(v) for k, v in results.items()}
            },
            "_summary": {
                "Search Term": query,
                "Total Results": total_results,
                "Categories": len(results)
            }
        }


# Register command
command = SearchCommand
