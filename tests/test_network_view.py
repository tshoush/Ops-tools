"""
Tests for network view module.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, Mock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from ddi_toolkit.network_view import (
    get_network_views,
    get_network_view_names,
    get_default_network_view,
    get_dns_views,
    get_dns_view_names,
    resolve_view_for_query,
    format_view_list,
    VIEW_MODE_DEFAULT,
    VIEW_MODE_ALL,
    VIEW_MODE_SPECIFIC
)


class TestGetNetworkViews:
    """Tests for network view fetching."""

    @pytest.fixture
    def mock_network_views(self):
        """Mock network view response."""
        return [
            {
                "_ref": "networkview/ZG5zLm5ldHdvcmtfdmlldyQw:default/true",
                "name": "default",
                "comment": "The default network view",
                "is_default": True
            },
            {
                "_ref": "networkview/ZG5zLm5ldHdvcmtfdmlldyQx:production/false",
                "name": "production",
                "comment": "Production networks",
                "is_default": False
            },
            {
                "_ref": "networkview/ZG5zLm5ldHdvcmtfdmlldyQy:development/false",
                "name": "development",
                "comment": "Development networks",
                "is_default": False
            }
        ]

    def test_get_network_views(self, mock_network_views):
        """Test fetching network views."""
        mock_client = Mock()
        mock_client.get = Mock(return_value=mock_network_views)

        with patch('ddi_toolkit.network_view.get_client', return_value=mock_client):
            views = get_network_views()

            assert len(views) == 3
            assert views[0]["name"] == "default"
            assert views[1]["name"] == "production"
            mock_client.get.assert_called_once()

    def test_get_network_view_names(self, mock_network_views):
        """Test getting view names."""
        mock_client = Mock()
        mock_client.get = Mock(return_value=mock_network_views)

        with patch('ddi_toolkit.network_view.get_client', return_value=mock_client):
            names = get_network_view_names()

            assert len(names) == 3
            assert "default" in names
            assert "production" in names
            assert "development" in names

    def test_get_default_network_view(self, mock_network_views):
        """Test getting default view."""
        mock_client = Mock()
        mock_client.get = Mock(return_value=mock_network_views)

        with patch('ddi_toolkit.network_view.get_client', return_value=mock_client):
            default = get_default_network_view()

            assert default == "default"

    def test_get_default_network_view_fallback(self):
        """Test fallback when no default flag found."""
        mock_client = Mock()
        mock_client.get = Mock(return_value=[
            {"name": "view1", "is_default": False},
            {"name": "view2", "is_default": False}
        ])

        with patch('ddi_toolkit.network_view.get_client', return_value=mock_client):
            default = get_default_network_view()

            assert default == "default"


class TestGetDNSViews:
    """Tests for DNS view fetching."""

    @pytest.fixture
    def mock_dns_views(self):
        """Mock DNS view response."""
        return [
            {
                "_ref": "view/ZG5zLnZpZXckLl9kZWZhdWx0:default/true",
                "name": "default",
                "is_default": True,
                "network_view": "default"
            },
            {
                "_ref": "view/ZG5zLnZpZXckLmludGVybmFs:internal/false",
                "name": "internal",
                "is_default": False,
                "network_view": "default"
            }
        ]

    def test_get_dns_views(self, mock_dns_views):
        """Test fetching DNS views."""
        mock_client = Mock()
        mock_client.get = Mock(return_value=mock_dns_views)

        with patch('ddi_toolkit.network_view.get_client', return_value=mock_client):
            views = get_dns_views()

            assert len(views) == 2
            assert views[0]["name"] == "default"

    def test_get_dns_view_names(self, mock_dns_views):
        """Test getting DNS view names."""
        mock_client = Mock()
        mock_client.get = Mock(return_value=mock_dns_views)

        with patch('ddi_toolkit.network_view.get_client', return_value=mock_client):
            names = get_dns_view_names()

            assert len(names) == 2
            assert "default" in names
            assert "internal" in names


class TestResolveViewForQuery:
    """Tests for view resolution."""

    def test_resolve_default_mode(self):
        """Test default mode resolution."""
        result = resolve_view_for_query(
            VIEW_MODE_DEFAULT,
            selected_view=None,
            default_view="default"
        )
        assert result == "default"

    def test_resolve_all_mode(self):
        """Test all views mode resolution."""
        result = resolve_view_for_query(
            VIEW_MODE_ALL,
            selected_view="production",
            default_view="default"
        )
        assert result is None

    def test_resolve_specific_mode(self):
        """Test specific mode resolution."""
        result = resolve_view_for_query(
            VIEW_MODE_SPECIFIC,
            selected_view="production",
            default_view="default"
        )
        assert result == "production"

    def test_resolve_specific_mode_no_selection(self):
        """Test specific mode falls back to default."""
        result = resolve_view_for_query(
            VIEW_MODE_SPECIFIC,
            selected_view=None,
            default_view="default"
        )
        assert result == "default"


class TestFormatViewList:
    """Tests for view list formatting."""

    def test_format_view_list_basic(self):
        """Test basic view list formatting."""
        views = [
            {"name": "default", "is_default": True},
            {"name": "production", "is_default": False}
        ]

        result = format_view_list(views)

        assert len(result) == 2
        assert result[0][0] == "default"
        assert "(default)" in result[0][1]
        assert result[1][0] == "production"

    def test_format_view_list_with_comments(self):
        """Test view list with comments."""
        views = [
            {"name": "production", "comment": "Production networks", "is_default": False}
        ]

        result = format_view_list(views)

        assert result[0][0] == "production"
        assert "Production networks" in result[0][1]

    def test_format_view_list_empty(self):
        """Test empty view list."""
        result = format_view_list([])
        assert result == []


class TestViewModeConstants:
    """Tests for view mode constants."""

    def test_constants_defined(self):
        """Test that constants are properly defined."""
        assert VIEW_MODE_DEFAULT == "default"
        assert VIEW_MODE_ALL == "all"
        assert VIEW_MODE_SPECIFIC == "specific"
