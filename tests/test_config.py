"""
Tests for configuration management.
"""

import pytest
import json
import os
from pathlib import Path
from unittest.mock import patch, mock_open

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from ddi_toolkit.config import (
    encode_password,
    decode_password,
    load_config,
    save_config,
    config_exists,
    is_configured,
    DEFAULT_CONFIG
)


class TestPasswordEncoding:
    """Tests for password encoding/decoding."""

    def test_encode_password_basic(self):
        """Test basic password encoding."""
        password = "admin"
        encoded = encode_password(password)
        assert encoded == "YWRtaW4="  # base64 of 'admin'

    def test_encode_password_empty(self):
        """Test encoding empty password."""
        assert encode_password("") == ""

    def test_decode_password_basic(self):
        """Test basic password decoding."""
        encoded = "YWRtaW4="
        decoded = decode_password(encoded)
        assert decoded == "admin"

    def test_decode_password_empty(self):
        """Test decoding empty string."""
        assert decode_password("") == ""

    def test_encode_decode_roundtrip(self):
        """Test encoding then decoding returns original."""
        original = "MySecretP@ssw0rd!"
        encoded = encode_password(original)
        decoded = decode_password(encoded)
        assert decoded == original

    def test_decode_invalid_base64(self):
        """Test decoding invalid base64 returns original."""
        invalid = "not-valid-base64!!!"
        result = decode_password(invalid)
        assert result == invalid  # Returns original on failure


class TestConfigFile:
    """Tests for config file operations."""

    def test_load_config_default(self, tmp_path):
        """Test loading config when file doesn't exist returns defaults."""
        with patch('ddi_toolkit.config.CONFIG_FILE', tmp_path / "nonexistent.json"):
            config = load_config()
            assert config == DEFAULT_CONFIG

    def test_load_config_existing(self, temp_config_file, mock_config):
        """Test loading existing config file."""
        with patch('ddi_toolkit.config.CONFIG_FILE', temp_config_file):
            config = load_config()
            assert config["infoblox"]["grid_master"] == "192.168.1.100"
            assert config["infoblox"]["username"] == "admin"

    def test_save_config(self, tmp_path, mock_config):
        """Test saving config to file."""
        config_path = tmp_path / "test_config.json"
        with patch('ddi_toolkit.config.CONFIG_FILE', config_path):
            save_config(mock_config)

            assert config_path.exists()

            # Verify permissions (owner read/write only)
            stat = os.stat(config_path)
            assert stat.st_mode & 0o777 == 0o600

            # Verify content
            with open(config_path) as f:
                saved = json.load(f)
            assert saved["infoblox"]["grid_master"] == mock_config["infoblox"]["grid_master"]

    def test_config_exists_true(self, temp_config_file):
        """Test config_exists returns True when file exists."""
        with patch('ddi_toolkit.config.CONFIG_FILE', temp_config_file):
            assert config_exists() is True

    def test_config_exists_false(self, tmp_path):
        """Test config_exists returns False when file doesn't exist."""
        with patch('ddi_toolkit.config.CONFIG_FILE', tmp_path / "nonexistent.json"):
            assert config_exists() is False


class TestIsConfigured:
    """Tests for is_configured function."""

    def test_is_configured_true(self, temp_config_file, mock_config):
        """Test is_configured returns True with valid config."""
        with patch('ddi_toolkit.config.CONFIG_FILE', temp_config_file):
            assert is_configured() is True

    def test_is_configured_no_file(self, tmp_path):
        """Test is_configured returns False when no config file."""
        with patch('ddi_toolkit.config.CONFIG_FILE', tmp_path / "nonexistent.json"):
            assert is_configured() is False

    def test_is_configured_missing_grid_master(self, tmp_path):
        """Test is_configured returns False when grid_master missing."""
        config = DEFAULT_CONFIG.copy()
        config["infoblox"]["grid_master"] = ""
        config["infoblox"]["username"] = "admin"
        config["infoblox"]["password"] = "test"

        config_path = tmp_path / "config.json"
        with open(config_path, 'w') as f:
            json.dump(config, f)

        with patch('ddi_toolkit.config.CONFIG_FILE', config_path):
            assert is_configured() is False

    def test_is_configured_missing_password(self, tmp_path):
        """Test is_configured returns False when password missing."""
        config = DEFAULT_CONFIG.copy()
        config["infoblox"]["grid_master"] = "192.168.1.100"
        config["infoblox"]["username"] = "admin"
        config["infoblox"]["password"] = ""

        config_path = tmp_path / "config.json"
        with open(config_path, 'w') as f:
            json.dump(config, f)

        with patch('ddi_toolkit.config.CONFIG_FILE', config_path):
            assert is_configured() is False
