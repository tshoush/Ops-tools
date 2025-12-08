"""
Audit information retrieval from InfoBlox WAPI and Splunk.

InfoBlox stores audit data in the auditlog object.
Splunk can be queried for historical audit trail.
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from .config import load_config, decode_password


class AuditClient:
    """Retrieve audit information from InfoBlox and Splunk."""

    def __init__(self):
        """Initialize audit client."""
        self.config = load_config()
        self._wapi_client = None
        self._splunk_session = None

    @property
    def wapi_client(self):
        """Lazy load WAPI client."""
        if self._wapi_client is None:
            from .wapi import get_client
            self._wapi_client = get_client()
        return self._wapi_client

    def get_object_audit(
        self,
        object_ref: str,
        object_type: str = None,
        object_name: str = None,
        max_results: int = 10
    ) -> Dict[str, Any]:
        """
        Get audit information for an object.

        Args:
            object_ref: The _ref of the object
            object_type: Object type (network, zone, etc.)
            object_name: Object name/identifier for Splunk search

        Returns:
            Dict with audit information from WAPI and optionally Splunk
        """
        audit_info = {
            "wapi_audit": self._get_wapi_audit(object_ref, object_type, max_results),
            "timestamps": {},
            "last_modified_by": None
        }

        # Extract key timestamps from audit
        wapi_audit = audit_info["wapi_audit"]
        if wapi_audit:
            # Most recent action
            latest = wapi_audit[0] if wapi_audit else None
            if latest:
                audit_info["last_modified_by"] = latest.get("admin")
                audit_info["timestamps"]["last_modified"] = latest.get("timestamp")

            # Find creation (INSERT action)
            for entry in reversed(wapi_audit):
                if entry.get("action") == "INSERT":
                    audit_info["timestamps"]["created"] = entry.get("timestamp")
                    audit_info["created_by"] = entry.get("admin")
                    break

        # Get Splunk audit if enabled
        splunk_config = self.config.get("splunk", {})
        if splunk_config.get("enabled") and object_name:
            audit_info["splunk_audit"] = self._get_splunk_audit(
                object_name, object_type, max_results
            )

        return audit_info

    def _get_wapi_audit(
        self,
        object_ref: str,
        object_type: str = None,
        max_results: int = 10
    ) -> List[Dict]:
        """
        Get audit log entries from InfoBlox WAPI.

        Note: The auditlog object may not be available in all WAPI versions
        or may require specific permissions. This method handles failures
        gracefully by returning an empty list.
        """
        try:
            # Query auditlog for this object
            params = {"_max_results": str(max_results)}

            if object_type:
                params["object_type"] = object_type.upper()

            # Try to extract object name from ref for search
            if object_ref:
                # Extract searchable part from ref
                # e.g., "network/ZG5zLm5ldH:10.0.0.0/8/default" -> "10.0.0.0/8"
                parts = object_ref.split(":")
                if len(parts) > 1:
                    name_part = parts[1].split("/")[0]
                    if "/" in parts[1]:
                        # Network CIDR
                        name_part = "/".join(parts[1].split("/")[:2])
                    params["object_name~"] = name_part

            audit_entries = self.wapi_client.get(
                "auditlog",
                params=params,
                return_fields=[
                    "timestamp", "admin", "action", "object_type",
                    "object_name", "message"
                ]
            )

            # Format timestamps
            for entry in audit_entries:
                if entry.get("timestamp"):
                    try:
                        # InfoBlox timestamp format
                        ts = datetime.fromtimestamp(int(entry["timestamp"]))
                        entry["timestamp_formatted"] = ts.strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, TypeError):
                        entry["timestamp_formatted"] = entry.get("timestamp")

            return audit_entries

        except Exception:
            # auditlog object not available in this WAPI version or no permission
            # Return empty list - audit info will show as N/A
            return []

    def _get_splunk_audit(
        self,
        object_name: str,
        object_type: str = None,
        max_results: int = 10
    ) -> List[Dict]:
        """
        Get audit entries from Splunk.

        Searches the configured Splunk index for InfoBlox audit events.
        """
        splunk_config = self.config.get("splunk", {})

        if not splunk_config.get("enabled"):
            return []

        host = splunk_config.get("host", "")
        token = splunk_config.get("token", "")
        index = splunk_config.get("index", "infoblox_audit")

        if not host or not token:
            return [{"error": "Splunk not fully configured"}]

        try:
            # Build Splunk search query
            search_query = f'search index="{index}" "{object_name}"'
            if object_type:
                search_query += f' object_type="{object_type}"'
            search_query += f" | head {max_results}"

            # Splunk REST API endpoint
            url = f"https://{host}/services/search/jobs/export"

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/x-www-form-urlencoded"
            }

            data = {
                "search": search_query,
                "output_mode": "json",
                "earliest_time": "-30d",
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
                # Parse Splunk JSON response
                results = []
                for line in response.text.strip().split("\n"):
                    if line:
                        try:
                            import json
                            event = json.loads(line)
                            if "result" in event:
                                results.append(event["result"])
                        except Exception:
                            pass
                return results
            else:
                return [{"error": f"Splunk query failed: {response.status_code}"}]

        except Exception as e:
            return [{"error": f"Splunk query error: {e}"}]


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
