"""
Audit information retrieval from Splunk.

Note: InfoBlox WAPI does not expose 'auditlog' as a queryable object type.
Audit information must be retrieved from Splunk (or other SIEM) where
InfoBlox forwards its audit logs via syslog.

To enable audit in your environment:
1. Configure InfoBlox to send audit logs to Splunk via syslog
2. Enable Splunk integration in DDI Toolkit config
3. Provide Splunk host, token, and index name
"""

import json
import requests
import urllib3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from .config import load_config

# Suppress SSL warnings for Splunk
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class AuditClient:
    """Retrieve audit information from Splunk."""

    def __init__(self):
        """Initialize audit client."""
        self.config = load_config()

    def get_object_audit(
        self,
        object_ref: str,
        object_type: str = None,
        object_name: str = None,
        max_results: int = 10
    ) -> Dict[str, Any]:
        """
        Get audit information for an object from Splunk.

        Args:
            object_ref: The _ref of the object (used to extract search term)
            object_type: Object type (network, zone, etc.)
            object_name: Object name/identifier for Splunk search

        Returns:
            Dict with audit information from Splunk
        """
        audit_info = {
            "splunk_audit": [],
            "timestamps": {},
            "created_by": None,
            "last_modified_by": None,
            "source": "splunk"
        }

        # Get Splunk audit if enabled
        splunk_config = self.config.get("splunk", {})
        if not splunk_config.get("enabled"):
            audit_info["source"] = "none"
            audit_info["message"] = "Splunk integration not enabled. Configure via [C] Configuration menu."
            return audit_info

        # Determine search term
        search_term = object_name
        if not search_term and object_ref:
            # Extract searchable part from ref
            # e.g., "network/ZG5zLm5ldH:10.0.0.0/8/default" -> "10.0.0.0/8"
            search_term = self._extract_search_term(object_ref)

        if not search_term:
            return audit_info

        # Query Splunk
        splunk_results = self._get_splunk_audit(
            search_term, object_type, max_results
        )
        audit_info["splunk_audit"] = splunk_results

        # Extract timestamps and users from Splunk results
        self._extract_audit_metadata(audit_info, splunk_results)

        return audit_info

    def _extract_search_term(self, object_ref: str) -> Optional[str]:
        """Extract searchable term from object reference."""
        if not object_ref:
            return None

        parts = object_ref.split(":")
        if len(parts) > 1:
            ref_data = parts[1]
            # Handle network CIDR (e.g., 10.0.0.0/8/default -> 10.0.0.0/8)
            if "/" in ref_data:
                segments = ref_data.split("/")
                if len(segments) >= 2:
                    return f"{segments[0]}/{segments[1]}"
            return ref_data.split("/")[0]
        return None

    def _extract_audit_metadata(
        self,
        audit_info: Dict[str, Any],
        splunk_results: List[Dict]
    ):
        """Extract creation/modification metadata from Splunk results."""
        if not splunk_results or isinstance(splunk_results[0], dict) and splunk_results[0].get("error"):
            return

        # Sort by timestamp to find first (created) and last (modified)
        sorted_results = []
        for entry in splunk_results:
            ts = entry.get("_time") or entry.get("timestamp") or entry.get("_indextime")
            if ts:
                sorted_results.append((ts, entry))

        if not sorted_results:
            return

        sorted_results.sort(key=lambda x: x[0])

        # First entry = creation
        first_ts, first_entry = sorted_results[0]
        audit_info["timestamps"]["created"] = first_ts
        audit_info["created_by"] = (
            first_entry.get("admin") or
            first_entry.get("user") or
            first_entry.get("src_user") or
            first_entry.get("Admin")
        )

        # Last entry = most recent modification
        last_ts, last_entry = sorted_results[-1]
        audit_info["timestamps"]["last_modified"] = last_ts
        audit_info["last_modified_by"] = (
            last_entry.get("admin") or
            last_entry.get("user") or
            last_entry.get("src_user") or
            last_entry.get("Admin")
        )

    def _get_splunk_audit(
        self,
        object_name: str,
        object_type: str = None,
        max_results: int = 20
    ) -> List[Dict]:
        """
        Get audit entries from Splunk.

        Searches the configured Splunk index for InfoBlox audit events.
        Supports multiple common InfoBlox audit log formats.
        """
        splunk_config = self.config.get("splunk", {})

        if not splunk_config.get("enabled"):
            return []

        host = splunk_config.get("host", "")
        token = splunk_config.get("token", "")
        index = splunk_config.get("index", "infoblox_audit")
        sourcetype = splunk_config.get("sourcetype", "")

        if not host or not token:
            return [{"error": "Splunk not fully configured (need host and token)"}]

        try:
            # Build comprehensive Splunk search query
            # Search for the object name in various fields common to InfoBlox logs
            search_parts = [f'search index="{index}"']

            # Add sourcetype filter if configured
            if sourcetype:
                search_parts.append(f'sourcetype="{sourcetype}"')

            # Search for object name in multiple fields
            # InfoBlox logs can have different formats depending on how they're ingested
            object_search = f'("{object_name}")'
            search_parts.append(object_search)

            # Add object type filter if provided
            if object_type:
                type_filter = f'(object_type="{object_type}" OR object_type="{object_type.upper()}" OR object_type="{object_type.lower()}")'
                search_parts.append(type_filter)

            # Sort by time and limit results
            search_query = " ".join(search_parts)
            search_query += f" | sort -_time | head {max_results}"

            # Add field extraction for common InfoBlox audit fields
            search_query += ' | table _time, admin, user, src_user, action, object_type, object_name, message, src, dest, _raw'

            # Splunk REST API endpoint
            url = f"https://{host}/services/search/jobs/export"

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/x-www-form-urlencoded"
            }

            data = {
                "search": search_query,
                "output_mode": "json",
                "earliest_time": "-90d",  # Extended to 90 days for better audit history
                "latest_time": "now"
            }

            response = requests.post(
                url,
                headers=headers,
                data=data,
                verify=False,
                timeout=30
            )

            if response.status_code == 200:
                # Parse Splunk JSON response (streaming format)
                results = []
                for line in response.text.strip().split("\n"):
                    if line:
                        try:
                            event = json.loads(line)
                            if "result" in event:
                                result = event["result"]
                                # Normalize field names
                                normalized = self._normalize_splunk_result(result)
                                results.append(normalized)
                        except json.JSONDecodeError:
                            pass
                return results
            elif response.status_code == 401:
                return [{"error": "Splunk authentication failed. Check your token."}]
            elif response.status_code == 403:
                return [{"error": "Splunk access denied. Check token permissions."}]
            else:
                return [{"error": f"Splunk query failed: HTTP {response.status_code}"}]

        except requests.exceptions.ConnectionError:
            return [{"error": f"Cannot connect to Splunk at {host}"}]
        except requests.exceptions.Timeout:
            return [{"error": "Splunk query timed out"}]
        except Exception as e:
            return [{"error": f"Splunk query error: {str(e)}"}]

    def _normalize_splunk_result(self, result: Dict) -> Dict:
        """Normalize Splunk result fields for consistent output."""
        normalized = {
            "timestamp": result.get("_time", ""),
            "admin": (
                result.get("admin") or
                result.get("user") or
                result.get("src_user") or
                result.get("Admin") or
                "unknown"
            ),
            "action": result.get("action", ""),
            "object_type": result.get("object_type", ""),
            "object_name": result.get("object_name", ""),
            "message": result.get("message") or result.get("_raw", ""),
            "source": result.get("src", ""),
            "destination": result.get("dest", "")
        }

        # Format timestamp if present
        if normalized["timestamp"]:
            try:
                # Try to parse ISO format
                ts = datetime.fromisoformat(normalized["timestamp"].replace("Z", "+00:00"))
                normalized["timestamp_formatted"] = ts.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, AttributeError):
                normalized["timestamp_formatted"] = normalized["timestamp"]

        return normalized


def get_audit_for_object(
    object_ref: str,
    object_type: str = None,
    object_name: str = None,
    max_results: int = 10
) -> Dict[str, Any]:
    """
    Convenience function to get audit info for an object.

    Args:
        object_ref: Object _ref from WAPI
        object_type: Object type (network, zone, etc.)
        object_name: Human-readable name for searching
        max_results: Max audit entries to return

    Returns:
        Audit information dict
    """
    client = AuditClient()
    return client.get_object_audit(object_ref, object_type, object_name, max_results)


def format_audit_summary(audit_info: Dict[str, Any]) -> Dict[str, str]:
    """
    Format audit info into a simple summary dict.

    Returns:
        Dict with Created, Created By, Modified, Modified By
    """
    summary = {
        "Created": "N/A",
        "Created By": "N/A",
        "Last Modified": "N/A",
        "Modified By": "N/A"
    }

    timestamps = audit_info.get("timestamps", {})

    if timestamps.get("created"):
        try:
            ts = datetime.fromtimestamp(int(timestamps["created"]))
            summary["Created"] = ts.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            summary["Created"] = str(timestamps["created"])

    if audit_info.get("created_by"):
        summary["Created By"] = audit_info["created_by"]

    if timestamps.get("last_modified"):
        try:
            ts = datetime.fromtimestamp(int(timestamps["last_modified"]))
            summary["Last Modified"] = ts.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            summary["Last Modified"] = str(timestamps["last_modified"])

    if audit_info.get("last_modified_by"):
        summary["Modified By"] = audit_info["last_modified_by"]

    return summary
