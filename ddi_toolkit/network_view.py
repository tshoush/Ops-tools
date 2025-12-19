"""
Network View management - fetch and select network views from InfoBlox.
"""

from typing import List, Dict, Any, Optional
from .wapi import get_client, WAPIError


# Constants for view mode
VIEW_MODE_DEFAULT = "default"      # Use configured default view
VIEW_MODE_ALL = "all"              # Query all network views
VIEW_MODE_SPECIFIC = "specific"    # Use a specific selected view


def get_network_views() -> List[Dict[str, Any]]:
    """
    Fetch all network views from InfoBlox.

    Returns:
        List of network view objects with name, comment, and extattrs
    """
    client = get_client()

    views = client.get(
        "networkview",
        return_fields=["name", "comment", "extattrs", "is_default"]
    )

    return views


def get_network_view_names() -> List[str]:
    """
    Get list of network view names.

    Returns:
        List of network view names
    """
    views = get_network_views()
    return [v.get("name", "") for v in views if v.get("name")]


def get_default_network_view() -> Optional[str]:
    """
    Get the default network view name.

    Returns:
        Name of the default network view, or "default" if not found
    """
    views = get_network_views()

    for view in views:
        if view.get("is_default"):
            return view.get("name")

    # Fallback to "default" if no is_default flag found
    return "default"


def get_dns_views() -> List[Dict[str, Any]]:
    """
    Fetch all DNS views from InfoBlox.

    Returns:
        List of DNS view objects
    """
    client = get_client()

    views = client.get(
        "view",
        return_fields=["name", "comment", "is_default", "network_view"]
    )

    return views


def get_dns_view_names() -> List[str]:
    """
    Get list of DNS view names.

    Returns:
        List of DNS view names
    """
    views = get_dns_views()
    return [v.get("name", "") for v in views if v.get("name")]


def resolve_view_for_query(
    view_mode: str,
    selected_view: Optional[str] = None,
    default_view: str = "default"
) -> Optional[str]:
    """
    Resolve which view(s) to use for a query based on mode.

    Args:
        view_mode: One of VIEW_MODE_DEFAULT, VIEW_MODE_ALL, VIEW_MODE_SPECIFIC
        selected_view: Specific view name (when mode is SPECIFIC)
        default_view: Default view from config

    Returns:
        View name to use, or None for all views
    """
    if view_mode == VIEW_MODE_ALL:
        return None  # None means query all views
    elif view_mode == VIEW_MODE_SPECIFIC and selected_view:
        return selected_view
    else:
        return default_view


def format_view_list(views: List[Dict[str, Any]]) -> List[tuple]:
    """
    Format views for display in selection menu.

    Args:
        views: List of view objects from WAPI

    Returns:
        List of (value, display_label) tuples
    """
    formatted = []

    for view in views:
        name = view.get("name", "")
        comment = view.get("comment", "")
        is_default = view.get("is_default", False)

        label = name
        if is_default:
            label += " (default)"
        if comment:
            label += f" - {comment[:30]}"

        formatted.append((name, label))

    return formatted
