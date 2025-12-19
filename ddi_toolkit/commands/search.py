"""
Intelligent search command with auto-detection and type prefixes.
"""

import re
import logging
from typing import Dict, Any, List, Tuple, Optional
from .base import BaseCommand
from ..wapi import WAPIError

logger = logging.getLogger(__name__)


class SearchCommand(BaseCommand):
    """Intelligent search across InfoBlox objects with auto-detection."""

    name = "search"
    description = "Intelligent search with auto-detection"
    aliases = ["find", "lookup"]

    # Type prefix mapping - user can force specific search type
    TYPE_PREFIXES = {
        "host": "host",
        "ptr": "ptr",
        "a": "a_record",
        "cname": "cname",
        "mx": "mx",
        "txt": "txt",
        "srv": "srv",
        "ns": "ns",
        "zone": "zone",
        "ip": "ip",
        "mac": "mac",
        "net": "network",
        "all": "all",
    }

    # Return fields for each record type
    RETURN_FIELDS = {
        "record:host": ["name", "view", "ipv4addrs", "comment", "ttl", "extattrs", "zone"],
        "record:a": ["name", "view", "ipv4addr", "comment", "ttl", "extattrs"],
        "record:ptr": ["ptrdname", "view", "ipv4addr", "comment", "ttl", "extattrs"],
        "record:cname": ["name", "view", "canonical", "comment", "ttl", "extattrs"],
        "record:mx": ["name", "view", "mail_exchanger", "preference", "comment", "ttl"],
        "record:txt": ["name", "view", "text", "comment", "ttl"],
        "record:srv": ["name", "view", "target", "port", "priority", "weight", "comment"],
        "record:ns": ["name", "view", "nameserver", "comment"],
        "zone_auth": ["fqdn", "view", "comment", "zone_format"],
        "ipv4address": ["ip_address", "status", "types", "names", "network", "network_view", "mac_address"],
        "network": ["network", "network_view", "comment"],
        "networkcontainer": ["network", "network_view", "comment"],
        "fixedaddress": ["ipv4addr", "mac", "name", "network_view", "comment"],
        "lease": ["address", "network", "network_view", "hardware", "client_hostname"],
    }

    # Regex patterns for detection
    IP_PATTERN = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
    CIDR_PATTERN = re.compile(r'^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$')
    MAC_PATTERN = re.compile(r'^([0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}$')
    FQDN_PATTERN = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)+$')

    def _parse_type_prefix(self, query: str) -> Tuple[Optional[str], str]:
        """
        Parse type prefix from query if present.

        Args:
            query: Search query, possibly with prefix like "host:hostname"

        Returns:
            Tuple of (search_type, clean_query)
            search_type is None if no prefix found
        """
        if ':' in query:
            parts = query.split(':', 1)
            prefix = parts[0].lower()
            if prefix in self.TYPE_PREFIXES:
                return self.TYPE_PREFIXES[prefix], parts[1]
        return None, query

    def _convert_wildcards(self, query: str) -> str:
        """
        Convert user-friendly wildcards to regex patterns.

        Args:
            query: Search query with possible * wildcards

        Returns:
            Query with wildcards converted for WAPI regex search
        """
        # If already contains regex chars or no wildcards, return as-is
        if '*' not in query:
            return query

        # Convert * to .* for regex (WAPI uses ~ for regex search)
        # But WAPI actually uses * directly in some cases, so be careful
        # For name~ searches, * works directly
        return query

    def _detect_input_type(self, query: str) -> Tuple[str, List[str]]:
        """
        Detect the type of input and return appropriate search types.

        Args:
            query: Clean search query (no prefix)

        Returns:
            Tuple of (detected_type_name, list_of_object_types_to_search)
        """
        # Check for IP address
        if self.IP_PATTERN.match(query):
            return "ip_address", ["ipv4address", "record:host", "record:a", "record:ptr", "fixedaddress"]

        # Check for CIDR
        if self.CIDR_PATTERN.match(query):
            return "cidr", ["network", "networkcontainer"]

        # Check for MAC address
        if self.MAC_PATTERN.match(query):
            return "mac_address", ["fixedaddress", "lease"]

        # Check for FQDN (hostname.domain.tld)
        if self.FQDN_PATTERN.match(query):
            parts = query.split('.')
            if len(parts) >= 3:
                # Looks like a hostname (e.g., server.example.com)
                return "fqdn", ["record:host", "record:a", "record:cname", "record:ptr"]
            elif len(parts) == 2:
                # Looks like a zone (e.g., example.com)
                return "zone", ["zone_auth", "record:host", "record:a"]

        # Default to generic text search
        return "text", ["record:host", "record:a", "record:cname", "zone_auth",
                        "network", "networkcontainer", "fixedaddress"]

    def _get_search_types_for_forced_type(self, forced_type: str) -> List[str]:
        """Get object types to search for a forced type prefix."""
        type_mapping = {
            "host": ["record:host"],
            "ptr": ["record:ptr"],
            "a_record": ["record:a"],
            "cname": ["record:cname"],
            "mx": ["record:mx"],
            "txt": ["record:txt"],
            "srv": ["record:srv"],
            "ns": ["record:ns"],
            "zone": ["zone_auth"],
            "ip": ["ipv4address"],
            "mac": ["fixedaddress", "lease"],
            "network": ["network", "networkcontainer"],
            "all": None,  # Will trigger full search
        }
        return type_mapping.get(forced_type, [])

    def _search_object_type(
        self,
        obj_type: str,
        query: str,
        view_filter: Dict,
        max_results: int
    ) -> List[Dict]:
        """
        Search a specific object type.

        Args:
            obj_type: WAPI object type (e.g., "record:host")
            query: Search query
            view_filter: View filter dict
            max_results: Max results to return

        Returns:
            List of matching objects
        """
        results = []
        return_fields = self.RETURN_FIELDS.get(obj_type, [])

        try:
            if obj_type == "record:host":
                # Search by name
                results = self.client.get(
                    obj_type,
                    params={"name~": query},
                    return_fields=return_fields,
                    max_results=max_results
                )
                # Also search by IP if query looks like IP
                if self.IP_PATTERN.match(query):
                    by_ip = self.client.get(
                        obj_type,
                        params={"ipv4addr": query},
                        return_fields=return_fields,
                        max_results=max_results
                    )
                    results.extend(by_ip)

            elif obj_type == "record:a":
                results = self.client.get(
                    obj_type,
                    params={"name~": query},
                    return_fields=return_fields,
                    max_results=max_results
                )
                if self.IP_PATTERN.match(query):
                    by_ip = self.client.get(
                        obj_type,
                        params={"ipv4addr": query},
                        return_fields=return_fields,
                        max_results=max_results
                    )
                    results.extend(by_ip)

            elif obj_type == "record:ptr":
                if self.IP_PATTERN.match(query):
                    # Search PTR by IP
                    results = self.client.get(
                        obj_type,
                        params={"ipv4addr": query},
                        return_fields=return_fields,
                        max_results=max_results
                    )
                else:
                    # Search PTR by ptrdname
                    results = self.client.get(
                        obj_type,
                        params={"ptrdname~": query},
                        return_fields=return_fields,
                        max_results=max_results
                    )

            elif obj_type == "record:cname":
                results = self.client.get(
                    obj_type,
                    params={"name~": query},
                    return_fields=return_fields,
                    max_results=max_results
                )
                # Also search by canonical name
                by_canonical = self.client.get(
                    obj_type,
                    params={"canonical~": query},
                    return_fields=return_fields,
                    max_results=max_results
                )
                results.extend(by_canonical)

            elif obj_type in ["record:mx", "record:txt", "record:srv", "record:ns"]:
                results = self.client.get(
                    obj_type,
                    params={"name~": query},
                    return_fields=return_fields,
                    max_results=max_results
                )

            elif obj_type == "zone_auth":
                results = self.client.get(
                    obj_type,
                    params={"fqdn~": query},
                    return_fields=return_fields,
                    max_results=max_results
                )

            elif obj_type == "ipv4address":
                if self.IP_PATTERN.match(query):
                    results = self.client.get(
                        obj_type,
                        params={"ip_address": query},
                        return_fields=return_fields,
                        max_results=max_results
                    )

            elif obj_type == "network":
                # Search by comment and CIDR
                by_comment = self.client.get(
                    obj_type,
                    params={"comment~": query, **view_filter},
                    return_fields=return_fields,
                    max_results=max_results
                )
                by_cidr = self.client.get(
                    obj_type,
                    params={"network~": query, **view_filter},
                    return_fields=return_fields,
                    max_results=max_results
                )
                results = by_comment + by_cidr

            elif obj_type == "networkcontainer":
                by_comment = self.client.get(
                    obj_type,
                    params={"comment~": query, **view_filter},
                    return_fields=return_fields,
                    max_results=max_results
                )
                by_cidr = self.client.get(
                    obj_type,
                    params={"network~": query, **view_filter},
                    return_fields=return_fields,
                    max_results=max_results
                )
                results = by_comment + by_cidr

            elif obj_type == "fixedaddress":
                # Search by name
                by_name = self.client.get(
                    obj_type,
                    params={"name~": query, **view_filter},
                    return_fields=return_fields,
                    max_results=max_results
                )
                results = by_name
                # Search by MAC if query looks like MAC
                if self.MAC_PATTERN.match(query):
                    by_mac = self.client.get(
                        obj_type,
                        params={"mac": query, **view_filter},
                        return_fields=return_fields,
                        max_results=max_results
                    )
                    results.extend(by_mac)
                # Search by IP if query looks like IP
                if self.IP_PATTERN.match(query):
                    by_ip = self.client.get(
                        obj_type,
                        params={"ipv4addr": query, **view_filter},
                        return_fields=return_fields,
                        max_results=max_results
                    )
                    results.extend(by_ip)

            elif obj_type == "lease":
                if self.MAC_PATTERN.match(query):
                    results = self.client.get(
                        obj_type,
                        params={"hardware": query, **view_filter},
                        return_fields=return_fields,
                        max_results=max_results
                    )
                elif self.IP_PATTERN.match(query):
                    results = self.client.get(
                        obj_type,
                        params={"address": query, **view_filter},
                        return_fields=return_fields,
                        max_results=max_results
                    )

        except WAPIError as e:
            logger.debug(f"Search failed for {obj_type}: {e.message}")
        except Exception as e:
            logger.warning(f"Unexpected error searching {obj_type}: {e}")

        # Deduplicate by _ref
        seen = set()
        unique_results = []
        for r in results:
            ref = r.get('_ref', '')
            if ref and ref not in seen:
                seen.add(ref)
                unique_results.append(r)
            elif not ref:
                unique_results.append(r)

        return unique_results

    def _full_search(
        self,
        query: str,
        view_filter: Dict,
        max_results: int
    ) -> Dict[str, List]:
        """
        Perform full search across all object types (original behavior).
        """
        all_types = [
            "record:host", "record:a", "record:cname", "record:ptr",
            "record:mx", "record:txt", "record:srv", "record:ns",
            "zone_auth", "network", "networkcontainer", "fixedaddress"
        ]

        results = {}
        for obj_type in all_types:
            type_results = self._search_object_type(obj_type, query, view_filter, max_results)
            if type_results:
                # Convert obj_type to friendly name
                friendly_name = obj_type.replace("record:", "") + "_records" if obj_type.startswith("record:") else obj_type
                if obj_type == "zone_auth":
                    friendly_name = "zones"
                elif obj_type == "networkcontainer":
                    friendly_name = "containers"
                elif obj_type == "fixedaddress":
                    friendly_name = "fixed_addresses"
                elif obj_type == "network":
                    friendly_name = "networks"
                results[friendly_name] = type_results

        return results

    def execute(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Execute intelligent search.

        Args:
            query: Search term (with optional type prefix like "host:hostname")
            network_view: Network view filter (default: "default")
            all_views: If True, search across all views
            max_results: Maximum results per object type (default: 25)

        Returns:
            Search results with detection metadata
        """
        max_results = kwargs.get("max_results", 25)
        network_view = kwargs.get("network_view", "default")
        all_views = kwargs.get("all_views", False)

        # Build view filter for network objects
        view_filter = {} if all_views else {"network_view": network_view}

        # Parse type prefix if present
        forced_type, clean_query = self._parse_type_prefix(query)

        # Convert wildcards
        clean_query = self._convert_wildcards(clean_query)

        # Determine search strategy
        if forced_type:
            if forced_type == "all":
                detected_type = "all"
                search_types = None  # Full search
            else:
                detected_type = f"explicit:{forced_type}"
                search_types = self._get_search_types_for_forced_type(forced_type)
        else:
            detected_type, search_types = self._detect_input_type(clean_query)

        # Execute search
        results = {}
        searched_types = []

        if search_types is None:
            # Full search
            results = self._full_search(clean_query, view_filter, max_results)
            searched_types = ["all"]
        else:
            for obj_type in search_types:
                type_results = self._search_object_type(obj_type, clean_query, view_filter, max_results)
                if type_results:
                    # Convert obj_type to friendly name
                    if obj_type.startswith("record:"):
                        friendly_name = obj_type.replace("record:", "") + "_records"
                    elif obj_type == "zone_auth":
                        friendly_name = "zones"
                    elif obj_type == "networkcontainer":
                        friendly_name = "containers"
                    elif obj_type == "fixedaddress":
                        friendly_name = "fixed_addresses"
                    elif obj_type == "ipv4address":
                        friendly_name = "ip_details"
                    else:
                        friendly_name = obj_type + "s" if not obj_type.endswith("s") else obj_type
                    results[friendly_name] = type_results
                searched_types.append(obj_type)

        # Calculate totals
        total_results = sum(len(v) for v in results.values())

        # Extract zone from FQDN for zone info suggestion
        zone_hint = None
        if detected_type == "fqdn" and '.' in clean_query:
            parts = clean_query.split('.')
            if len(parts) >= 2:
                zone_hint = '.'.join(parts[-2:])  # e.g., "marriott.com"

        # Build suggestions for no results
        suggestions = []
        if total_results == 0:
            if detected_type == "fqdn":
                suggestions.append(f"Try: ptr:{clean_query}")
                suggestions.append(f"Try: zone:{zone_hint}" if zone_hint else "Try zone search")
                suggestions.append(f"Try: all:{clean_query}")
            elif detected_type == "ip_address":
                suggestions.append(f"Try: all:{clean_query}")
            else:
                suggestions.append(f"Try: all:{clean_query}")

        return {
            "query": query,
            "clean_query": clean_query,
            "detected_type": detected_type,
            "searched_types": searched_types,
            "results": results,
            "statistics": {
                "total_results": total_results,
                "categories": len(results),
                "by_type": {k: len(v) for k, v in results.items()}
            },
            "zone_hint": zone_hint,
            "suggestions": suggestions,
            "_summary": {
                "Search Term": clean_query,
                "Detected Type": detected_type,
                "Total Results": total_results,
                "Categories": len(results)
            }
        }


# Register command
command = SearchCommand
