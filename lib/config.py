"""
Configuration management - load, save, and prompt for settings.
"""

import json
import os
import sys
import base64
from pathlib import Path
from typing import Optional, Dict, Any

# Config file location (same directory as this file's parent)
CONFIG_FILE = Path(__file__).parent.parent / "config.json"

DEFAULT_CONFIG = {
    "version": "1.0",
    "infoblox": {
        "grid_master": "",
        "username": "admin",
        "password": "",
        "wapi_version": "2.13.1",
        "verify_ssl": False,
        "timeout": 30
    },
    "splunk": {
        "enabled": False,
        "host": "",
        "token": "",
        "index": "infoblox_audit",
        "sourcetype": ""
    },
    "output": {
        "default_dir": "./output",
        "timestamp_files": True
    },
    "defaults": {
        "network_view": "default",
        "dns_view": "default",
        "view_mode": "default"  # "default", "all", or "specific"
    }
}


def config_exists() -> bool:
    """Check if config file exists."""
    return CONFIG_FILE.exists()


def load_config() -> Dict[str, Any]:
    """Load config from file or return defaults."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> None:
    """Save config to file with restricted permissions."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    # Restrict permissions (owner read/write only)
    os.chmod(CONFIG_FILE, 0o600)


def encode_password(password: str) -> str:
    """
    Encode password for storage.
    Note: This is basic obfuscation, not encryption.
    For production, consider using keyring or vault.
    """
    if not password:
        return ""
    return base64.b64encode(password.encode()).decode()


def decode_password(encoded: str) -> str:
    """Decode stored password."""
    if not encoded:
        return ""
    try:
        return base64.b64decode(encoded.encode()).decode()
    except Exception:
        return encoded


def get_infoblox_creds() -> tuple:
    """
    Get InfoBlox credentials from config.

    Returns:
        Tuple of (grid_master, username, password, wapi_version, verify_ssl, timeout)
    """
    config = load_config()
    ib = config.get("infoblox", {})
    return (
        ib.get("grid_master", ""),
        ib.get("username", ""),
        decode_password(ib.get("password", "")),
        ib.get("wapi_version", "2.13.1"),
        ib.get("verify_ssl", False),
        ib.get("timeout", 30)
    )


def is_configured() -> bool:
    """Check if minimum required config is present."""
    if not config_exists():
        return False

    config = load_config()
    ib = config.get("infoblox", {})
    return bool(ib.get("grid_master") and ib.get("username") and ib.get("password"))


def get_view_settings() -> Dict[str, Any]:
    """
    Get current network view settings.

    Returns:
        Dict with view_mode, network_view, and dns_view
    """
    config = load_config()
    defaults = config.get("defaults", {})
    return {
        "view_mode": defaults.get("view_mode", "default"),
        "network_view": defaults.get("network_view", "default"),
        "dns_view": defaults.get("dns_view", "default")
    }


def set_view_settings(view_mode: str, network_view: str = "default", dns_view: str = "default") -> None:
    """
    Update network view settings.

    Args:
        view_mode: "default", "all", or "specific"
        network_view: Network view name (used when mode is "default" or "specific")
        dns_view: DNS view name
    """
    config = load_config()
    if "defaults" not in config:
        config["defaults"] = {}

    config["defaults"]["view_mode"] = view_mode
    config["defaults"]["network_view"] = network_view
    config["defaults"]["dns_view"] = dns_view

    save_config(config)


def run_first_time_setup() -> Dict[str, Any]:
    """
    Run first-time configuration wizard.
    Called when no config.json exists.
    """
    from .ui.display import clear_screen, print_welcome
    from .ui.prompts import prompt_input, prompt_confirm, validate_ip
    from .ui.colors import success, bold, dim, header

    clear_screen()
    print_welcome()

    config = DEFAULT_CONFIG.copy()
    ib = config["infoblox"]

    print(f"\n  {bold('InfoBlox Grid Master Configuration')}\n")

    # Grid Master
    ib["grid_master"] = prompt_input(
        "Grid Master IP or Hostname",
        validator=validate_ip,
        error_msg="Enter a valid IP address or hostname",
        hint="Example: 192.168.1.100 or gm.example.com"
    )

    # Username
    ib["username"] = prompt_input(
        "Admin Username",
        default="admin"
    )

    # Password
    ib["password"] = encode_password(prompt_input(
        "Admin Password",
        secret=True
    ))

    # WAPI Version
    ib["wapi_version"] = prompt_input(
        "WAPI Version",
        default="2.13.1",
        hint="Check your InfoBlox version for supported WAPI"
    )

    # SSL Verification
    ib["verify_ssl"] = prompt_confirm(
        "Verify SSL Certificate?",
        default=False
    )

    config["infoblox"] = ib

    # Splunk (optional but recommended for audit)
    print(f"\n  {bold('Splunk Integration (Optional)')}\n")
    print(f"    {dim('Splunk provides audit history: who created/modified objects')}\n")

    splunk = config["splunk"]
    if prompt_confirm("Enable Splunk audit integration?", default=False):
        splunk["enabled"] = True
        splunk["host"] = prompt_input(
            "Splunk Host:Port",
            hint="Example: splunk.marriott.com:8089"
        )
        splunk["token"] = prompt_input(
            "Splunk API Token",
            hint="Bearer token for Splunk REST API",
            secret=True
        )
        splunk["index"] = prompt_input(
            "Splunk Index",
            hint="Index where InfoBlox audit logs are stored",
            default="infoblox_audit"
        )
        splunk["sourcetype"] = prompt_input(
            "Splunk Sourcetype",
            hint="Optional - leave empty for any",
            default="",
            required=False
        )
    config["splunk"] = splunk

    # Output settings
    print(f"\n  {bold('Output Settings')}\n")
    output = config["output"]
    output["default_dir"] = prompt_input(
        "Output Directory",
        default="./output"
    )
    output["timestamp_files"] = prompt_confirm(
        "Add timestamp to output filenames?",
        default=True
    )
    config["output"] = output

    # Save config
    save_config(config)

    print(f"\n  {success('Configuration saved successfully!')}")
    print(f"  {dim(f'Config file: {CONFIG_FILE}')}\n")

    input("  Press Enter to continue...")

    return config


def run_config_editor() -> Dict[str, Any]:
    """
    Edit existing configuration.
    Shows current values as defaults.
    """
    from .ui.display import clear_screen
    from .ui.prompts import prompt_input, prompt_confirm, validate_ip
    from .ui.colors import success, bold, dim, header

    clear_screen()
    print(header("\n  ═══ CONFIGURATION ═══\n"))

    config = load_config()
    ib = config.get("infoblox", DEFAULT_CONFIG["infoblox"].copy())

    print(f"  {bold('InfoBlox Settings')}")
    print(f"  {dim('Press Enter to keep current value')}\n")

    # Grid Master
    ib["grid_master"] = prompt_input(
        "Grid Master IP/Hostname",
        default=ib.get("grid_master", ""),
        validator=validate_ip,
        error_msg="Enter a valid IP address or hostname"
    )

    # Username
    ib["username"] = prompt_input(
        "Admin Username",
        default=ib.get("username", "admin")
    )

    # Password
    current_pw = ib.get("password", "")
    new_pw = prompt_input(
        "Admin Password",
        default="********" if current_pw else "",
        secret=True,
        required=False
    )
    if new_pw and new_pw != "********":
        ib["password"] = encode_password(new_pw)

    # WAPI Version
    ib["wapi_version"] = prompt_input(
        "WAPI Version",
        default=ib.get("wapi_version", "2.13.1")
    )

    # SSL Verification
    ib["verify_ssl"] = prompt_confirm(
        "Verify SSL Certificate?",
        default=ib.get("verify_ssl", False)
    )

    config["infoblox"] = ib

    # Splunk settings
    print(f"\n  {bold('Splunk Integration')}\n")

    splunk = config.get("splunk", DEFAULT_CONFIG["splunk"].copy())
    splunk["enabled"] = prompt_confirm(
        "Enable Splunk integration?",
        default=splunk.get("enabled", False)
    )

    if splunk["enabled"]:
        print(f"    {dim('Splunk is used for audit history (who created/modified objects)')}")
        splunk["host"] = prompt_input(
            "Splunk Host:Port",
            hint="Example: splunk.marriott.com:8089",
            default=splunk.get("host", "")
        )
        current_token = splunk.get("token", "")
        new_token = prompt_input(
            "Splunk API Token",
            hint="Bearer token for Splunk REST API",
            default="********" if current_token else "",
            secret=True,
            required=False
        )
        if new_token and new_token != "********":
            splunk["token"] = new_token
        splunk["index"] = prompt_input(
            "Splunk Index",
            hint="Index where InfoBlox audit logs are stored",
            default=splunk.get("index", "infoblox_audit")
        )
        splunk["sourcetype"] = prompt_input(
            "Splunk Sourcetype",
            hint="Optional - leave empty for any sourcetype",
            default=splunk.get("sourcetype", ""),
            required=False
        )

    config["splunk"] = splunk

    # Output settings
    print(f"\n  {bold('Output Settings')}\n")

    output = config.get("output", DEFAULT_CONFIG["output"].copy())
    output["default_dir"] = prompt_input(
        "Output Directory",
        default=output.get("default_dir", "./output")
    )
    output["timestamp_files"] = prompt_confirm(
        "Timestamp output files?",
        default=output.get("timestamp_files", True)
    )
    config["output"] = output

    # Save
    save_config(config)

    print(f"\n  {success('Configuration updated!')}\n")
    input("  Press Enter to continue...")

    return config
