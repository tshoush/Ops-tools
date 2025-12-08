"""
Audit information retrieval from Splunk and WAPI fileop.

Audit sources (in order of preference):
1. Splunk - If configured, queries Splunk for audit logs forwarded via syslog
2. WAPI fileop - Downloads and parses audit logs directly from InfoBlox

Note: InfoBlox WAPI does not expose 'auditlog' as a queryable object type.
The fileop method uses get_log_files to download the audit log archive.
"""

import json
import re
import requests
import urllib3
import tarfile
import io
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from .config import load_config, get_infoblox_creds, decode_password

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class AuditClient:
    """Retrieve audit information from Splunk or WAPI fileop."""

    def __init__(self):
        """Initialize audit client."""
        self.config = load_config()
        self._audit_log_cache = None
        self._audit_log_cache_time = None
        self._cache_ttl = 300  # 5 minute cache for audit log

    def get_object_audit(
        self,
        object_ref: str,
        object_type: str = None,
        object_name: str = None,
        max_results: int = 10
    ) -> Dict[str, Any]:
        """
        Get audit information for an object.

        Tries Splunk first (if configured), then falls back to WAPI fileop.

        Args:
            object_ref: The _ref of the object (used to extract search term)
            object_type: Object type (network, zone, etc.)
            object_name: Object name/identifier for searching

        Returns:
            Dict with audit information
        """
        audit_info = {
            "splunk_audit": [],
            "fileop_audit": [],
            "timestamps": {},
            "created_by": None,
            "last_modified_by": None,
            "source": "none"
        }

        # Determine search term
        search_term = object_name
        if not search_term and object_ref:
            search_term = self._extract_search_term(object_ref)

        if not search_term:
            audit_info["message"] = "No search term available for audit lookup"
            return audit_info

        # Try Splunk first if configured
        splunk_config = self.config.get("splunk", {})
        if splunk_config.get("enabled"):
            splunk_results = self._get_splunk_audit(search_term, object_type, max_results)

            # Check if Splunk returned valid results (not just errors)
            has_valid_splunk = (
                splunk_results and
                not (len(splunk_results) == 1 and splunk_results[0].get("error"))
            )

            if has_valid_splunk:
                audit_info["splunk_audit"] = splunk_results
                audit_info["source"] = "splunk"
                self._extract_audit_metadata(audit_info, splunk_results)
                return audit_info
            else:
                # Splunk failed or returned no results, store error for reference
                if splunk_results and splunk_results[0].get("error"):
                    audit_info["splunk_error"] = splunk_results[0]["error"]

        # Fall back to WAPI fileop
        fileop_results = self._get_fileop_audit(search_term, object_type, max_results)

        if fileop_results:
            audit_info["fileop_audit"] = fileop_results
            audit_info["source"] = "fileop"
            self._extract_audit_metadata(audit_info, fileop_results)
            return audit_info

        # Neither source returned results
        if not splunk_config.get("enabled"):
            audit_info["message"] = "Splunk not configured. WAPI audit log empty or unavailable."
        else:
            audit_info["message"] = "No audit records found in Splunk or WAPI."

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
        audit_results: List[Dict]
    ):
        """Extract creation/modification metadata from audit results."""
        if not audit_results:
            return

        # Skip if first result is an error
        if isinstance(audit_results[0], dict) and audit_results[0].get("error"):
            return

        # Sort by timestamp to find first (created) and last (modified)
        sorted_results = []
        for entry in audit_results:
            ts = (
                entry.get("_time") or
                entry.get("timestamp") or
                entry.get("_indextime") or
                entry.get("time")
            )
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

    # =========================================================================
    # Splunk Methods
    # =========================================================================

    def _get_splunk_audit(
        self,
        object_name: str,
        object_type: str = None,
        max_results: int = 20
    ) -> List[Dict]:
        """
        Get audit entries from Splunk.

        Searches the configured Splunk index for InfoBlox audit events.
        Supports both token-based and username/password authentication.
        """
        splunk_config = self.config.get("splunk", {})

        if not splunk_config.get("enabled"):
            return []

        host = splunk_config.get("host", "")
        token = splunk_config.get("token", "")
        username = splunk_config.get("username", "")
        password = decode_password(splunk_config.get("password", ""))
        index = splunk_config.get("index", "")
        sourcetype = splunk_config.get("sourcetype", "")

        # Check authentication - need either token OR username/password
        has_token = bool(token)
        has_userpass = bool(username and password)

        if not host:
            return [{"error": "Splunk host not configured"}]

        if not has_token and not has_userpass:
            return [{"error": "Splunk not fully configured (need token OR username/password)"}]

        if not index:
            return [{"error": "Splunk index not configured"}]

        try:
            # Build Splunk search query
            search_parts = [f'search index="{index}"']

            if sourcetype:
                search_parts.append(f'sourcetype="{sourcetype}"')

            # Search for object name
            object_search = f'("{object_name}")'
            search_parts.append(object_search)

            # Add object type filter if provided
            if object_type:
                type_filter = f'(object_type="{object_type}" OR object_type="{object_type.upper()}" OR object_type="{object_type.lower()}")'
                search_parts.append(type_filter)

            search_query = " ".join(search_parts)
            search_query += f" | sort -_time | head {max_results}"
            search_query += ' | table _time, admin, user, src_user, action, object_type, object_name, message, src, dest, _raw'

            # Splunk REST API endpoint
            url = f"https://{host}/services/search/jobs/export"

            # Set up authentication
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            auth = None

            if has_token:
                # Token-based authentication
                headers["Authorization"] = f"Bearer {token}"
            else:
                # Username/password basic authentication
                auth = (username, password)

            data = {
                "search": search_query,
                "output_mode": "json",
                "earliest_time": "-90d",
                "latest_time": "now"
            }

            response = requests.post(
                url,
                headers=headers,
                auth=auth,
                data=data,
                verify=False,
                timeout=30
            )

            if response.status_code == 200:
                results = []
                for line in response.text.strip().split("\n"):
                    if line:
                        try:
                            event = json.loads(line)
                            if "result" in event:
                                result = event["result"]
                                normalized = self._normalize_splunk_result(result)
                                results.append(normalized)
                        except json.JSONDecodeError:
                            pass
                return results
            elif response.status_code == 401:
                return [{"error": "Splunk authentication failed. Check your credentials."}]
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

        if normalized["timestamp"]:
            try:
                ts = datetime.fromisoformat(normalized["timestamp"].replace("Z", "+00:00"))
                normalized["timestamp_formatted"] = ts.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, AttributeError):
                normalized["timestamp_formatted"] = normalized["timestamp"]

        return normalized

    # =========================================================================
    # WAPI Fileop Methods
    # =========================================================================

    def _get_fileop_audit(
        self,
        object_name: str,
        object_type: str = None,
        max_results: int = 20
    ) -> List[Dict]:
        """
        Get audit entries from WAPI fileop (download audit log).

        Downloads the audit log archive from InfoBlox and searches for
        entries matching the object name.
        """
        try:
            # Get or refresh audit log cache
            audit_entries = self._get_cached_audit_log()

            if not audit_entries:
                return []

            # Filter entries by object name
            matching_entries = []
            search_pattern = re.compile(re.escape(object_name), re.IGNORECASE)

            for entry in audit_entries:
                # Search in various fields
                searchable_text = " ".join([
                    str(entry.get("message", "")),
                    str(entry.get("object_name", "")),
                    str(entry.get("object", "")),
                    str(entry.get("raw", ""))
                ])

                if search_pattern.search(searchable_text):
                    # Optionally filter by object type
                    if object_type:
                        entry_type = entry.get("object_type", "").upper()
                        if object_type.upper() not in entry_type:
                            continue
                    matching_entries.append(entry)

                    if len(matching_entries) >= max_results:
                        break

            return matching_entries

        except Exception as e:
            return [{"error": f"WAPI fileop audit error: {str(e)}"}]

    def _get_cached_audit_log(self) -> List[Dict]:
        """Get audit log entries, using cache if available."""
        now = datetime.now()

        # Check if cache is valid
        if (self._audit_log_cache is not None and
            self._audit_log_cache_time is not None and
            (now - self._audit_log_cache_time).total_seconds() < self._cache_ttl):
            return self._audit_log_cache

        # Download fresh audit log
        audit_entries = self._download_audit_log()

        # Update cache
        self._audit_log_cache = audit_entries
        self._audit_log_cache_time = now

        return audit_entries

    def _download_audit_log(self) -> List[Dict]:
        """Download and parse audit log from InfoBlox via WAPI fileop."""
        try:
            gm, user, pw, ver, ssl_verify, timeout = get_infoblox_creds()
            base_url = f"https://{gm}/wapi/v{ver}"
            auth = (user, pw)

            # Step 1: Request the audit log download
            resp = requests.post(
                f"{base_url}/fileop",
                auth=auth,
                params={"_function": "get_log_files"},
                json={
                    "log_type": "AUDITLOG",
                    "node_type": "ACTIVE"
                },
                verify=False,
                timeout=timeout
            )

            if resp.status_code != 200:
                return []

            data = resp.json()
            download_url = data.get("url")
            token = data.get("token", "").replace("\n", "")

            if not download_url:
                return []

            # Step 2: Download the archive using POST
            headers = {
                "Accept": "application/octet-stream, application/x-gzip, */*",
                "Content-Type": "application/json"
            }
            cookies = {"ibapauth": token}

            download_resp = requests.post(
                download_url,
                auth=auth,
                headers=headers,
                cookies=cookies,
                verify=False,
                timeout=60
            )

            if download_resp.status_code != 200 or len(download_resp.content) == 0:
                return []

            # Step 3: Extract and parse the audit log
            return self._parse_audit_archive(download_resp.content)

        except Exception as e:
            return []

    def _parse_audit_archive(self, archive_content: bytes) -> List[Dict]:
        """Parse audit log entries from tar.gz archive."""
        entries = []

        try:
            with tarfile.open(fileobj=io.BytesIO(archive_content), mode='r:gz') as tar:
                for member in tar.getnames():
                    if 'audit' in member.lower():
                        f = tar.extractfile(member)
                        if f:
                            content = f.read().decode('utf-8', errors='ignore')
                            entries.extend(self._parse_audit_log_content(content))
        except Exception:
            pass

        return entries

    def _parse_audit_log_content(self, content: str) -> List[Dict]:
        """Parse individual audit log entries from log file content."""
        entries = []

        for line in content.strip().split('\n'):
            if not line.strip():
                continue

            entry = self._parse_audit_line(line)
            if entry:
                entries.append(entry)

        return entries

    def _parse_audit_line(self, line: str) -> Optional[Dict]:
        """
        Parse a single audit log line.

        InfoBlox audit log format varies, but typically includes:
        - Timestamp
        - Admin user
        - Action (INSERT, UPDATE, DELETE)
        - Object type and name
        - Details
        """
        if not line.strip():
            return None

        entry = {
            "raw": line,
            "timestamp": None,
            "admin": None,
            "action": None,
            "object_type": None,
            "object_name": None,
            "message": line
        }

        # Try to extract timestamp (common formats)
        # Format: 2024-01-15 10:30:00 or Jan 15 10:30:00 or ISO format
        timestamp_patterns = [
            r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})',  # ISO-like
            r'(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})',      # Syslog format
        ]

        for pattern in timestamp_patterns:
            match = re.search(pattern, line)
            if match:
                entry["timestamp"] = match.group(1)
                break

        # Try to extract admin user
        admin_patterns = [
            r'admin[=:](\S+)',
            r'user[=:](\S+)',
            r'by\s+(\S+@\S+|\w+)',
        ]

        for pattern in admin_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                entry["admin"] = match.group(1)
                break

        # Try to extract action
        action_patterns = [
            r'\b(INSERT|UPDATE|DELETE|CREATE|MODIFY|REMOVE|ADD|CHANGE)\b',
        ]

        for pattern in action_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                entry["action"] = match.group(1).upper()
                break

        # Try to extract object type
        type_patterns = [
            r'object_type[=:\s]+(\S+)',
            r'\b(NETWORK|ZONE|HOST|RECORD|RANGE|FIXEDADDRESS|LEASE)\b',
        ]

        for pattern in type_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                entry["object_type"] = match.group(1).upper()
                break

        return entry


def get_audit_for_object(
    object_ref: str,
    object_type: str = None,
    object_name: str = None,
    max_results: int = 10
) -> Dict[str, Any]:
    """
    Convenience function to get audit info for an object.

    Tries Splunk first (if configured), then WAPI fileop.

    Args:
        object_ref: Object _ref from WAPI
        object_type: Object type (network, zone, etc.)
        object_name: Human-readable name for searching
        max_results: Max audit entries to return

    Returns:
        Audit information dict with source indicator
    """
    client = AuditClient()
    return client.get_object_audit(object_ref, object_type, object_name, max_results)


def format_audit_summary(audit_info: Dict[str, Any]) -> Dict[str, str]:
    """
    Format audit info into a simple summary dict.

    Returns:
        Dict with Created, Created By, Modified, Modified By, Source
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
            # Try parsing as Unix timestamp first
            ts = datetime.fromtimestamp(int(timestamps["created"]))
            summary["Created"] = ts.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            # Otherwise use as string
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


def download_full_audit_log(output_path: str = None) -> Tuple[bool, str]:
    """
    Download the complete audit log from InfoBlox.

    Args:
        output_path: Path to save the audit log archive (optional)

    Returns:
        Tuple of (success, message_or_path)
    """
    try:
        gm, user, pw, ver, ssl_verify, timeout = get_infoblox_creds()
        base_url = f"https://{gm}/wapi/v{ver}"
        auth = (user, pw)

        # Request the audit log download
        resp = requests.post(
            f"{base_url}/fileop",
            auth=auth,
            params={"_function": "get_log_files"},
            json={
                "log_type": "AUDITLOG",
                "node_type": "ACTIVE"
            },
            verify=False,
            timeout=timeout
        )

        if resp.status_code != 200:
            return False, f"Failed to initiate download: HTTP {resp.status_code}"

        data = resp.json()
        download_url = data.get("url")
        token = data.get("token", "").replace("\n", "")

        if not download_url:
            return False, "No download URL returned"

        # Download the archive
        headers = {
            "Accept": "application/octet-stream, application/x-gzip, */*",
            "Content-Type": "application/json"
        }
        cookies = {"ibapauth": token}

        download_resp = requests.post(
            download_url,
            auth=auth,
            headers=headers,
            cookies=cookies,
            verify=False,
            timeout=60
        )

        if download_resp.status_code != 200:
            return False, f"Download failed: HTTP {download_resp.status_code}"

        if len(download_resp.content) == 0:
            return False, "Audit log is empty"

        # Save to file if path provided
        if output_path:
            with open(output_path, 'wb') as f:
                f.write(download_resp.content)
            return True, output_path
        else:
            return True, f"Downloaded {len(download_resp.content)} bytes"

    except Exception as e:
        return False, f"Error: {str(e)}"
