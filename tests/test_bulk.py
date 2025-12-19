"""Tests for bulk operations command."""

import pytest
import json
import csv
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from ddi_toolkit.commands import get_command
from ddi_toolkit.commands.bulk import BulkCommand, SUPPORTED_OBJECT_TYPES
from ddi_toolkit.wapi import WAPIError


class TestBulkCommandBasics:
    """Tests for bulk command basic functionality."""

    @pytest.fixture
    def bulk_command(self):
        """Get bulk command class."""
        return get_command("bulk")

    def test_bulk_command_exists(self, bulk_command):
        """Test bulk command is registered."""
        assert bulk_command is not None
        assert bulk_command.name == "bulk"

    def test_bulk_command_aliases(self, bulk_command):
        """Test bulk command aliases."""
        assert "import" in bulk_command.aliases
        assert "batch" in bulk_command.aliases

    def test_supported_object_types(self):
        """Test supported object types are defined."""
        assert "network" in SUPPORTED_OBJECT_TYPES
        assert "host" in SUPPORTED_OBJECT_TYPES
        assert "a" in SUPPORTED_OBJECT_TYPES
        assert "cname" in SUPPORTED_OBJECT_TYPES
        assert "ptr" in SUPPORTED_OBJECT_TYPES
        assert "fixedaddress" in SUPPORTED_OBJECT_TYPES
        assert "zone" in SUPPORTED_OBJECT_TYPES

    def test_object_type_config(self):
        """Test object type configuration structure."""
        for obj_type, config in SUPPORTED_OBJECT_TYPES.items():
            assert "wapi_type" in config
            assert "required_fields" in config
            assert "optional_fields" in config
            assert "identifier_field" in config


class TestBulkFileLoading:
    """Tests for file loading functionality."""

    @pytest.fixture
    def bulk_cmd(self):
        """Get bulk command instance."""
        cmd_class = get_command("bulk")
        return cmd_class()

    def test_load_json_array(self, bulk_cmd, tmp_path):
        """Test loading JSON array file."""
        json_file = tmp_path / "test.json"
        data = [
            {"network": "10.0.0.0/24", "comment": "Test 1"},
            {"network": "10.0.1.0/24", "comment": "Test 2"}
        ]
        json_file.write_text(json.dumps(data))

        result = bulk_cmd._load_file(json_file)
        assert len(result) == 2
        assert result[0]["network"] == "10.0.0.0/24"

    def test_load_json_single_object(self, bulk_cmd, tmp_path):
        """Test loading JSON single object file."""
        json_file = tmp_path / "test.json"
        data = {"network": "10.0.0.0/24", "comment": "Test"}
        json_file.write_text(json.dumps(data))

        result = bulk_cmd._load_file(json_file)
        assert len(result) == 1
        assert result[0]["network"] == "10.0.0.0/24"

    def test_load_json_with_data_wrapper(self, bulk_cmd, tmp_path):
        """Test loading JSON with data wrapper."""
        json_file = tmp_path / "test.json"
        data = {
            "data": [
                {"network": "10.0.0.0/24"},
                {"network": "10.0.1.0/24"}
            ]
        }
        json_file.write_text(json.dumps(data))

        result = bulk_cmd._load_file(json_file)
        assert len(result) == 2

    def test_load_csv_file(self, bulk_cmd, tmp_path):
        """Test loading CSV file."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("network,comment\n10.0.0.0/24,Test 1\n10.0.1.0/24,Test 2\n")

        result = bulk_cmd._load_file(csv_file)
        assert len(result) == 2
        assert result[0]["network"] == "10.0.0.0/24"
        assert result[0]["comment"] == "Test 1"

    def test_load_csv_with_json_field(self, bulk_cmd, tmp_path):
        """Test loading CSV with embedded JSON field."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text('name,ipv4addrs\ntest.example.com,"[{""ipv4addr"": ""10.0.0.1""}]"\n')

        result = bulk_cmd._load_file(csv_file)
        assert len(result) == 1
        assert isinstance(result[0]["ipv4addrs"], list)

    def test_load_unsupported_format(self, bulk_cmd, tmp_path):
        """Test loading unsupported file format."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("test data")

        with pytest.raises(ValueError, match="Unsupported file format"):
            bulk_cmd._load_file(txt_file)


class TestBulkValidation:
    """Tests for object validation."""

    @pytest.fixture
    def bulk_cmd(self):
        """Get bulk command instance."""
        cmd_class = get_command("bulk")
        return cmd_class()

    def test_validate_create_success(self, bulk_cmd):
        """Test validation passes for valid create data."""
        objects = [
            {"network": "10.0.0.0/24", "comment": "Test"}
        ]
        type_config = SUPPORTED_OBJECT_TYPES["network"]

        errors = bulk_cmd._validate_objects(objects, type_config, "create")
        assert len(errors) == 0

    def test_validate_create_missing_required(self, bulk_cmd):
        """Test validation fails for missing required field."""
        objects = [
            {"comment": "Test"}  # Missing "network"
        ]
        type_config = SUPPORTED_OBJECT_TYPES["network"]

        errors = bulk_cmd._validate_objects(objects, type_config, "create")
        assert len(errors) == 1
        assert "Missing required field" in errors[0]["error"]

    def test_validate_modify_needs_identifier(self, bulk_cmd):
        """Test validation requires _ref or identifier for modify."""
        objects = [
            {"comment": "Updated"}  # Missing network and _ref
        ]
        type_config = SUPPORTED_OBJECT_TYPES["network"]

        errors = bulk_cmd._validate_objects(objects, type_config, "modify")
        assert len(errors) == 1
        assert "Missing _ref" in errors[0]["error"]

    def test_validate_delete_needs_identifier(self, bulk_cmd):
        """Test validation requires _ref or identifier for delete."""
        objects = [
            {"comment": "To delete"}  # Missing network and _ref
        ]
        type_config = SUPPORTED_OBJECT_TYPES["network"]

        errors = bulk_cmd._validate_objects(objects, type_config, "delete")
        assert len(errors) == 1


class TestBulkCreate:
    """Tests for bulk create operations."""

    @pytest.fixture
    def bulk_cmd(self):
        """Get bulk command instance."""
        cmd_class = get_command("bulk")
        cmd = cmd_class()
        cmd._client = Mock()
        return cmd

    def test_bulk_create_dry_run(self, bulk_cmd):
        """Test bulk create in dry run mode."""
        objects = [
            {"network": "10.0.0.0/24", "comment": "Test"}
        ]
        type_config = SUPPORTED_OBJECT_TYPES["network"]

        result = bulk_cmd._bulk_create(objects, type_config, dry_run=True, continue_on_error=True)

        assert len(result["successful"]) == 1
        assert result["successful"][0]["action"] == "would_create"
        assert len(result["errors"]) == 0
        bulk_cmd._client.create.assert_not_called()

    def test_bulk_create_success(self, bulk_cmd):
        """Test successful bulk create."""
        bulk_cmd._client.create.return_value = "network/ZG5z:10.0.0.0/24/default"

        objects = [
            {"network": "10.0.0.0/24", "comment": "Test"}
        ]
        type_config = SUPPORTED_OBJECT_TYPES["network"]

        result = bulk_cmd._bulk_create(objects, type_config, dry_run=False, continue_on_error=True)

        assert len(result["successful"]) == 1
        assert result["successful"][0]["action"] == "created"
        assert "_ref" in result["successful"][0]

    def test_bulk_create_with_error(self, bulk_cmd):
        """Test bulk create handles API errors."""
        bulk_cmd._client.create.side_effect = WAPIError("Already exists", 400)

        objects = [
            {"network": "10.0.0.0/24", "comment": "Test"}
        ]
        type_config = SUPPORTED_OBJECT_TYPES["network"]

        result = bulk_cmd._bulk_create(objects, type_config, dry_run=False, continue_on_error=True)

        assert len(result["successful"]) == 0
        assert len(result["errors"]) == 1
        assert "Already exists" in result["errors"][0]["error"]

    def test_bulk_create_stop_on_error(self, bulk_cmd):
        """Test bulk create stops on first error when configured."""
        bulk_cmd._client.create.side_effect = [
            WAPIError("Error 1", 400),
            "network/ZG5z:10.0.1.0/24/default"  # This should not be called
        ]

        objects = [
            {"network": "10.0.0.0/24"},
            {"network": "10.0.1.0/24"}
        ]
        type_config = SUPPORTED_OBJECT_TYPES["network"]

        result = bulk_cmd._bulk_create(objects, type_config, dry_run=False, continue_on_error=False)

        assert len(result["errors"]) == 1
        assert bulk_cmd._client.create.call_count == 1


class TestBulkModify:
    """Tests for bulk modify operations."""

    @pytest.fixture
    def bulk_cmd(self):
        """Get bulk command instance."""
        cmd_class = get_command("bulk")
        cmd = cmd_class()
        cmd._client = Mock()
        return cmd

    def test_bulk_modify_dry_run(self, bulk_cmd):
        """Test bulk modify in dry run mode."""
        objects = [
            {"_ref": "network/ZG5z:10.0.0.0/24/default", "comment": "Updated"}
        ]
        type_config = SUPPORTED_OBJECT_TYPES["network"]

        result = bulk_cmd._bulk_modify(objects, type_config, dry_run=True, continue_on_error=True)

        assert len(result["successful"]) == 1
        assert result["successful"][0]["action"] == "would_modify"
        bulk_cmd._client.update.assert_not_called()

    def test_bulk_modify_with_ref(self, bulk_cmd):
        """Test bulk modify with _ref provided."""
        bulk_cmd._client.update.return_value = "network/ZG5z:10.0.0.0/24/default"

        objects = [
            {"_ref": "network/ZG5z:10.0.0.0/24/default", "comment": "Updated"}
        ]
        type_config = SUPPORTED_OBJECT_TYPES["network"]

        result = bulk_cmd._bulk_modify(objects, type_config, dry_run=False, continue_on_error=True)

        assert len(result["successful"]) == 1
        assert result["successful"][0]["action"] == "modified"

    def test_bulk_modify_lookup_by_identifier(self, bulk_cmd):
        """Test bulk modify looks up object by identifier."""
        bulk_cmd._client.get.return_value = [{"_ref": "network/ZG5z:10.0.0.0/24/default"}]
        bulk_cmd._client.update.return_value = "network/ZG5z:10.0.0.0/24/default"

        objects = [
            {"network": "10.0.0.0/24", "comment": "Updated"}
        ]
        type_config = SUPPORTED_OBJECT_TYPES["network"]

        result = bulk_cmd._bulk_modify(objects, type_config, dry_run=False, continue_on_error=True)

        assert len(result["successful"]) == 1
        bulk_cmd._client.get.assert_called_once()


class TestBulkDelete:
    """Tests for bulk delete operations."""

    @pytest.fixture
    def bulk_cmd(self):
        """Get bulk command instance."""
        cmd_class = get_command("bulk")
        cmd = cmd_class()
        cmd._client = Mock()
        return cmd

    def test_bulk_delete_dry_run(self, bulk_cmd):
        """Test bulk delete in dry run mode."""
        objects = [
            {"_ref": "network/ZG5z:10.0.0.0/24/default"}
        ]
        type_config = SUPPORTED_OBJECT_TYPES["network"]

        result = bulk_cmd._bulk_delete(objects, type_config, dry_run=True, continue_on_error=True)

        assert len(result["successful"]) == 1
        assert result["successful"][0]["action"] == "would_delete"
        bulk_cmd._client.delete.assert_not_called()

    def test_bulk_delete_with_ref(self, bulk_cmd):
        """Test bulk delete with _ref provided."""
        bulk_cmd._client.delete.return_value = "network/ZG5z:10.0.0.0/24/default"

        objects = [
            {"_ref": "network/ZG5z:10.0.0.0/24/default"}
        ]
        type_config = SUPPORTED_OBJECT_TYPES["network"]

        result = bulk_cmd._bulk_delete(objects, type_config, dry_run=False, continue_on_error=True)

        assert len(result["successful"]) == 1
        assert result["successful"][0]["action"] == "deleted"

    def test_bulk_delete_lookup_by_identifier(self, bulk_cmd):
        """Test bulk delete looks up object by identifier."""
        bulk_cmd._client.get.return_value = [{"_ref": "network/ZG5z:10.0.0.0/24/default"}]
        bulk_cmd._client.delete.return_value = "network/ZG5z:10.0.0.0/24/default"

        objects = [
            {"network": "10.0.0.0/24"}
        ]
        type_config = SUPPORTED_OBJECT_TYPES["network"]

        result = bulk_cmd._bulk_delete(objects, type_config, dry_run=False, continue_on_error=True)

        assert len(result["successful"]) == 1
        bulk_cmd._client.get.assert_called_once()


class TestBulkExecute:
    """Tests for bulk execute method."""

    @pytest.fixture
    def bulk_cmd(self):
        """Get bulk command instance."""
        cmd_class = get_command("bulk")
        cmd = cmd_class()
        cmd._client = Mock()
        return cmd

    def test_execute_invalid_operation(self, bulk_cmd):
        """Test execute with invalid operation."""
        result = bulk_cmd.execute("invalid", object_type="network", file="test.json")
        assert "error" in result
        assert "Invalid operation" in result["error"]

    def test_execute_invalid_object_type(self, bulk_cmd):
        """Test execute with invalid object type."""
        result = bulk_cmd.execute("create", object_type="invalid", file="test.json")
        assert "error" in result
        assert "Unsupported object type" in result["error"]

    def test_execute_missing_file(self, bulk_cmd):
        """Test execute with missing file."""
        result = bulk_cmd.execute("create", object_type="network")
        assert "error" in result
        assert "No file specified" in result["error"]

    def test_execute_file_not_found(self, bulk_cmd):
        """Test execute with non-existent file."""
        result = bulk_cmd.execute("create", object_type="network", file="/nonexistent/file.json")
        assert "error" in result
        assert "File not found" in result["error"]

    def test_execute_success(self, bulk_cmd, tmp_path):
        """Test successful execute."""
        # Create test file
        json_file = tmp_path / "test.json"
        json_file.write_text('[{"network": "10.0.0.0/24", "comment": "Test"}]')

        bulk_cmd._client.create.return_value = "network/ZG5z:10.0.0.0/24/default"

        result = bulk_cmd.execute(
            "create",
            object_type="network",
            file=str(json_file),
            dry_run=False
        )

        assert result["operation"] == "create"
        assert result["object_type"] == "network"
        assert result["total"] == 1
        assert result["successful"] == 1
        assert result["failed"] == 0


class TestWAPIClientMutations:
    """Tests for WAPI client create/update/delete methods."""

    @pytest.fixture
    def mock_session(self):
        """Create mock session."""
        with patch('ddi_toolkit.wapi.requests.Session') as mock:
            session = Mock()
            mock.return_value = session
            yield session

    def test_create_returns_ref(self, mock_session):
        """Test create method returns _ref."""
        from ddi_toolkit.wapi import WAPIClient

        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.text = '"network/ZG5z:10.0.0.0/24/default"'
        mock_response.json.return_value = "network/ZG5z:10.0.0.0/24/default"
        mock_session.request.return_value = mock_response

        with patch('ddi_toolkit.wapi.get_infoblox_creds') as mock_creds:
            mock_creds.return_value = ("host", "user", "pass", "2.13.1", False, 30)
            client = WAPIClient()
            ref = client.create("network", {"network": "10.0.0.0/24"})

        assert ref == "network/ZG5z:10.0.0.0/24/default"

    def test_update_returns_ref(self, mock_session):
        """Test update method returns _ref."""
        from ddi_toolkit.wapi import WAPIClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '"network/ZG5z:10.0.0.0/24/default"'
        mock_response.json.return_value = "network/ZG5z:10.0.0.0/24/default"
        mock_session.request.return_value = mock_response

        with patch('ddi_toolkit.wapi.get_infoblox_creds') as mock_creds:
            mock_creds.return_value = ("host", "user", "pass", "2.13.1", False, 30)
            client = WAPIClient()
            ref = client.update("network/ZG5z:10.0.0.0/24/default", {"comment": "Updated"})

        assert ref == "network/ZG5z:10.0.0.0/24/default"

    def test_delete_returns_ref(self, mock_session):
        """Test delete method returns _ref."""
        from ddi_toolkit.wapi import WAPIClient

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '"network/ZG5z:10.0.0.0/24/default"'
        mock_response.json.return_value = "network/ZG5z:10.0.0.0/24/default"
        mock_session.request.return_value = mock_response

        with patch('ddi_toolkit.wapi.get_infoblox_creds') as mock_creds:
            mock_creds.return_value = ("host", "user", "pass", "2.13.1", False, 30)
            client = WAPIClient()
            ref = client.delete("network/ZG5z:10.0.0.0/24/default")

        assert ref == "network/ZG5z:10.0.0.0/24/default"
