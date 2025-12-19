"""
Interactive input prompts with defaults and validation.
"""

import getpass
import sys
import re
from typing import Optional, List, Callable, Any, Tuple
from .colors import Colors, dim, bold, warning, error, IS_TTY


def prompt_input(
    label: str,
    default: Optional[str] = None,
    secret: bool = False,
    required: bool = True,
    validator: Optional[Callable[[str], bool]] = None,
    hint: Optional[str] = None,
    error_msg: str = "Invalid input"
) -> str:
    """
    Prompt for input with default value support.

    Args:
        label: The prompt label
        default: Default value (shown in brackets)
        secret: Hide input (for passwords)
        required: Require non-empty input
        validator: Optional validation function
        hint: Optional hint text
        error_msg: Custom error message for validation failure

    Returns:
        The user's input or default value
    """
    # Show hint if provided
    if hint:
        print(f"    {dim(hint)}")

    # Build prompt string
    if default:
        if secret:
            default_display = "********"
        else:
            default_display = default
        prompt_str = f"  {label} [{dim(default_display)}]: "
    else:
        prompt_str = f"  {label}: "

    while True:
        try:
            if secret:
                value = getpass.getpass(prompt_str)
            else:
                value = input(prompt_str)
        except (KeyboardInterrupt, EOFError):
            print()
            return default or ""

        # Use default if empty
        value = value.strip() if value.strip() else (default or "")

        # Validation
        if required and not value:
            print(warning("    This field is required"))
            continue

        if validator and value and not validator(value):
            print(warning(f"    {error_msg}"))
            continue

        return value


def prompt_choice(
    label: str,
    options: List[Tuple[str, str]],  # [(key, display_text), ...]
    default: Optional[str] = None
) -> str:
    """
    Prompt for a choice from options.

    Args:
        label: The prompt label
        options: List of (key, display_text) tuples
        default: Default key

    Returns:
        Selected option key
    """
    print(f"\n  {bold(label)}")

    for i, (key, display) in enumerate(options, 1):
        marker = ">" if key == default else " "
        print(f"    {marker} [{i}] {display}")

    while True:
        try:
            choice = input(f"\n  Enter choice [1-{len(options)}]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return default or options[0][0]

        if not choice and default:
            return default

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx][0]
        except ValueError:
            # Check if they typed the key directly
            for key, _ in options:
                if choice.lower() == key.lower():
                    return key

        print(warning(f"    Please enter 1-{len(options)}"))


def prompt_confirm(label: str, default: bool = True) -> bool:
    """
    Yes/No confirmation prompt.

    Args:
        label: The prompt label
        default: Default value (True = Yes)

    Returns:
        Boolean result
    """
    suffix = "[Y/n]" if default else "[y/N]"

    while True:
        try:
            choice = input(f"  {label} {suffix}: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return default

        if not choice:
            return default
        if choice in ('y', 'yes'):
            return True
        if choice in ('n', 'no'):
            return False

        print(warning("    Please enter y or n"))


# Validators

def validate_ip(value: str) -> bool:
    """Validate IP address or hostname."""
    # Simple IP pattern
    ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    # Hostname pattern
    hostname_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-\.]*[a-zA-Z0-9])?$'

    return bool(re.match(ip_pattern, value) or re.match(hostname_pattern, value))


def validate_cidr(value: str) -> bool:
    """Validate CIDR notation."""
    pattern = r'^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$'
    if not re.match(pattern, value):
        return False

    # Check valid IP octets and prefix
    try:
        ip, prefix = value.split('/')
        octets = [int(o) for o in ip.split('.')]
        prefix = int(prefix)
        return all(0 <= o <= 255 for o in octets) and 0 <= prefix <= 32
    except ValueError:
        return False


def validate_ipv4(value: str) -> bool:
    """Validate IPv4 address."""
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, value):
        return False

    try:
        octets = [int(o) for o in value.split('.')]
        return all(0 <= o <= 255 for o in octets)
    except ValueError:
        return False


def validate_fqdn(value: str) -> bool:
    """Validate FQDN (zone name)."""
    pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*\.?$'
    return bool(re.match(pattern, value)) and len(value) <= 253
