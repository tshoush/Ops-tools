"""
InfoBlox WAPI Client - Reusable wrapper for all API calls.
"""

import requests
import urllib3
from typing import Optional, Dict, List, Any, Union
from .config import get_infoblox_creds

# Suppress SSL warnings when verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class WAPIError(Exception):
    """Custom exception for WAPI errors."""

    def __init__(self, message: str, status_code: int = None, response: dict = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


class WAPIClient:
    """InfoBlox WAPI REST Client."""

    def __init__(self):
        """Initialize client with credentials from config."""
        host, user, password, version, verify_ssl, timeout = get_infoblox_creds()

        if not host or not user or not password:
            raise WAPIError(
                "InfoBlox not configured. Run 'ddi' to configure.",
                status_code=0
            )

        self.base_url = f"https://{host}/wapi/v{version}"
        self.auth = (user, password)
        self.verify = verify_ssl
        self.timeout = timeout

        # Create session for connection pooling
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.verify = self.verify
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None
    ) -> Any:
        """
        Make an HTTP request to WAPI.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., 'network', 'ipv4address')
            params: Query parameters
            data: Request body for POST/PUT

        Returns:
            Parsed JSON response

        Raises:
            WAPIError: On API errors
        """
        url = f"{self.base_url}/{endpoint}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=data,
                timeout=self.timeout
            )

            # Handle errors
            if response.status_code == 401:
                raise WAPIError("Authentication failed. Check credentials.", 401)
            elif response.status_code == 404:
                return []  # Not found is often valid (empty result)
            elif response.status_code >= 400:
                error_text = response.text
                try:
                    error_json = response.json()
                    error_text = error_json.get('text', error_text)
                except Exception:
                    pass
                raise WAPIError(f"API Error: {error_text}", response.status_code)

            # Parse response
            if response.text:
                result = response.json()
                # Handle _return_as_object wrapper
                if isinstance(result, dict) and 'result' in result:
                    return result['result']
                return result
            return []

        except requests.exceptions.ConnectionError as e:
            raise WAPIError(f"Connection failed: {e}")
        except requests.exceptions.Timeout:
            raise WAPIError(f"Request timed out after {self.timeout}s")
        except requests.exceptions.RequestException as e:
            raise WAPIError(f"Request failed: {e}")

    def get(
        self,
        object_type: str,
        params: Optional[Dict] = None,
        return_fields: Optional[List[str]] = None,
        max_results: Optional[int] = None,
        paging: bool = False,
        page_size: int = 1000
    ) -> List[Dict]:
        """
        GET objects from WAPI with optional paging for large datasets.

        Args:
            object_type: WAPI object type (e.g., 'network', 'ipv4address')
            params: Query parameters for filtering
            return_fields: Additional fields to return (uses _return_fields+)
            max_results: Maximum number of results (None = unlimited with paging)
            paging: Enable paging for large result sets
            page_size: Number of results per page (default 1000)

        Returns:
            List of matching objects
        """
        query_params = params.copy() if params else {}
        query_params["_return_as_object"] = "1"

        if return_fields:
            query_params["_return_fields+"] = ",".join(return_fields)

        if paging:
            # Use WAPI paging for large datasets
            query_params["_paging"] = "1"
            query_params["_max_results"] = str(page_size)
            return self._get_paged(object_type, query_params, max_results)

        if max_results:
            query_params["_max_results"] = str(max_results)

        result = self._request("GET", object_type, params=query_params)

        # Ensure we return a list
        if isinstance(result, dict):
            return [result]
        return result if result else []

    def _get_paged(
        self,
        object_type: str,
        query_params: Dict,
        max_results: Optional[int] = None
    ) -> List[Dict]:
        """
        Fetch results using WAPI paging for large datasets.

        Args:
            object_type: WAPI object type
            query_params: Query parameters (must include _paging=1)
            max_results: Maximum total results (None = all)

        Returns:
            List of all matching objects
        """
        all_results = []
        next_page_id = None
        total_fetched = 0

        while True:
            params = query_params.copy()
            if next_page_id:
                params["_page_id"] = next_page_id

            response = self._request("GET", object_type, params=params)

            # Handle paged response format
            if isinstance(response, dict):
                results = response.get("result", [])
                next_page_id = response.get("next_page_id")
            else:
                results = response if response else []
                next_page_id = None

            if not results:
                break

            all_results.extend(results)
            total_fetched += len(results)

            # Check if we've hit max_results
            if max_results and total_fetched >= max_results:
                all_results = all_results[:max_results]
                break

            # No more pages
            if not next_page_id:
                break

        return all_results

    def get_streamed(
        self,
        object_type: str,
        params: Optional[Dict] = None,
        return_fields: Optional[List[str]] = None,
        page_size: int = 1000
    ):
        """
        Generator that yields results in batches for memory efficiency.

        Use this for very large datasets where you want to process
        results incrementally without loading all into memory.

        Args:
            object_type: WAPI object type
            params: Query parameters
            return_fields: Fields to return
            page_size: Results per batch

        Yields:
            Batches of results (lists)
        """
        query_params = params.copy() if params else {}
        query_params["_return_as_object"] = "1"
        query_params["_paging"] = "1"
        query_params["_max_results"] = str(page_size)

        if return_fields:
            query_params["_return_fields+"] = ",".join(return_fields)

        next_page_id = None

        while True:
            page_params = query_params.copy()
            if next_page_id:
                page_params["_page_id"] = next_page_id

            response = self._request("GET", object_type, params=page_params)

            if isinstance(response, dict):
                results = response.get("result", [])
                next_page_id = response.get("next_page_id")
            else:
                results = response if response else []
                next_page_id = None

            if results:
                yield results

            if not next_page_id:
                break

    def get_by_ref(
        self,
        ref: str,
        return_fields: Optional[List[str]] = None
    ) -> Dict:
        """
        Get a single object by its _ref.

        Args:
            ref: Object reference string
            return_fields: Additional fields to return

        Returns:
            Object dict
        """
        params = {"_return_as_object": "1"}

        if return_fields:
            params["_return_fields+"] = ",".join(return_fields)

        result = self._request("GET", ref, params=params)

        if isinstance(result, list):
            return result[0] if result else {}
        return result

    def search(
        self,
        search_string: str,
        object_types: Optional[List[str]] = None,
        max_results: int = 100
    ) -> List[Dict]:
        """
        Global search across object types.

        Args:
            search_string: Search term
            object_types: Limit to specific object types
            max_results: Maximum results to return

        Returns:
            List of matching objects
        """
        params = {
            "search_string~": search_string,
            "_max_results": str(max_results)
        }

        if object_types:
            params["objtype"] = ",".join(object_types)

        return self.get("search", params=params)

    def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to Grid Master.

        Returns:
            Grid info dict on success

        Raises:
            WAPIError: On connection failure
        """
        result = self.get("grid", return_fields=["name", "service_status"])
        if result:
            return result[0]
        raise WAPIError("Connected but no grid info returned")


# Singleton pattern for client reuse
_client: Optional[WAPIClient] = None


def get_client() -> WAPIClient:
    """Get or create WAPI client singleton."""
    global _client
    if _client is None:
        _client = WAPIClient()
    return _client


def reset_client():
    """Reset client (e.g., after config change)."""
    global _client
    _client = None
