"""
Tests for output handlers.
"""

import pytest
import json
import csv
from pathlib import Path
from unittest.mock import patch, Mock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from ddi_toolkit.output import OutputWriter, flatten_dict, write_output


class TestFlattenDict:
    """Tests for flatten_dict function."""

    def test_flatten_simple_dict(self):
        """Test flattening a simple dict."""
        data = {"a": 1, "b": 2}
        result = flatten_dict(data)

        assert result == {"a": 1, "b": 2}

    def test_flatten_nested_dict(self):
        """Test flattening a nested dict."""
        data = {
            "a": 1,
            "nested": {
                "b": 2,
                "c": 3
            }
        }
        result = flatten_dict(data)

        assert result == {"a": 1, "nested.b": 2, "nested.c": 3}

    def test_flatten_deeply_nested(self):
        """Test flattening deeply nested dict."""
        data = {
            "level1": {
                "level2": {
                    "level3": "value"
                }
            }
        }
        result = flatten_dict(data)

        assert result == {"level1.level2.level3": "value"}

    def test_flatten_with_list(self):
        """Test flattening dict with simple list."""
        data = {"tags": ["a", "b", "c"]}
        result = flatten_dict(data)

        assert result["tags"] == "a; b; c"

    def test_flatten_with_list_of_dicts(self):
        """Test flattening dict with list of dicts."""
        data = {"items": [{"name": "item1"}, {"name": "item2"}]}
        result = flatten_dict(data)

        # Should be JSON stringified
        assert "items" in result
        assert isinstance(result["items"], str)

    def test_flatten_custom_separator(self):
        """Test flattening with custom separator."""
        data = {"a": {"b": 1}}
        result = flatten_dict(data, sep="_")

        assert result == {"a_b": 1}


class TestOutputWriter:
    """Tests for OutputWriter class."""

    @pytest.fixture
    def mock_output_config(self, tmp_path):
        """Mock output configuration."""
        return {
            "output": {
                "default_dir": str(tmp_path / "output"),
                "timestamp_files": False
            }
        }

    def test_writer_creates_directory(self, mock_output_config, tmp_path):
        """Test writer creates output directory."""
        output_dir = tmp_path / "output"

        with patch('ddi_toolkit.output.load_config', return_value=mock_output_config):
            writer = OutputWriter("test", "query")

            assert output_dir.exists()

    def test_writer_write_json(self, mock_output_config, tmp_path):
        """Test writing JSON output."""
        with patch('ddi_toolkit.output.load_config', return_value=mock_output_config):
            writer = OutputWriter("test", "query", quiet=True)
            result = writer.write({"key": "value"})

            assert "json" in result
            json_path = Path(result["json"])
            assert json_path.exists()

            with open(json_path) as f:
                data = json.load(f)

            assert data["metadata"]["command"] == "test"
            assert data["metadata"]["query"] == "query"
            assert data["data"]["key"] == "value"

    def test_writer_write_csv(self, mock_output_config, tmp_path):
        """Test writing CSV output."""
        with patch('ddi_toolkit.output.load_config', return_value=mock_output_config):
            writer = OutputWriter("test", "query", quiet=True)
            result = writer.write({"key": "value", "num": 123})

            assert "csv" in result
            csv_path = Path(result["csv"])
            assert csv_path.exists()

            with open(csv_path) as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 1
            assert rows[0]["key"] == "value"
            assert rows[0]["num"] == "123"

    def test_writer_write_list(self, mock_output_config, tmp_path):
        """Test writing list of records."""
        records = [
            {"name": "item1", "value": 1},
            {"name": "item2", "value": 2}
        ]

        with patch('ddi_toolkit.output.load_config', return_value=mock_output_config):
            writer = OutputWriter("test", "query", quiet=True)
            result = writer.write(records)

            csv_path = Path(result["csv"])
            with open(csv_path) as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 2
            assert rows[0]["name"] == "item1"
            assert rows[1]["name"] == "item2"

    def test_writer_sanitize_filename(self, mock_output_config, tmp_path):
        """Test filename sanitization."""
        with patch('ddi_toolkit.output.load_config', return_value=mock_output_config):
            writer = OutputWriter("test", "10.20.30.0/24", quiet=True)

            # Should handle slashes in query
            result = writer.write({"data": "test"})
            assert Path(result["json"]).exists()

    def test_writer_with_timestamp(self, tmp_path):
        """Test writing with timestamp in filename."""
        config = {
            "output": {
                "default_dir": str(tmp_path / "output"),
                "timestamp_files": True
            }
        }

        with patch('ddi_toolkit.output.load_config', return_value=config):
            writer = OutputWriter("test", "query", quiet=True)
            result = writer.write({"data": "test"})

            # Filename should contain timestamp pattern
            json_path = Path(result["json"])
            assert "_2" in json_path.name  # Year starts with 2

    def test_writer_empty_results(self, mock_output_config, tmp_path):
        """Test writing empty results."""
        with patch('ddi_toolkit.output.load_config', return_value=mock_output_config):
            writer = OutputWriter("test", "query", quiet=True)
            result = writer.write([])

            json_path = Path(result["json"])
            with open(json_path) as f:
                data = json.load(f)

            assert data["metadata"]["count"] == 0


class TestWriteOutputFunction:
    """Tests for write_output convenience function."""

    def test_write_output(self, tmp_path):
        """Test write_output function."""
        config = {
            "output": {
                "default_dir": str(tmp_path / "output"),
                "timestamp_files": False
            }
        }

        with patch('ddi_toolkit.output.load_config', return_value=config):
            result = write_output(
                command="test",
                query="query",
                data={"key": "value"},
                quiet=True
            )

            assert "json" in result
            assert "csv" in result
            assert Path(result["json"]).exists()
            assert Path(result["csv"]).exists()
