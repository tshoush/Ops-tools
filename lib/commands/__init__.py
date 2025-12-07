"""
Command registry - Auto-discovers and loads command modules.
"""

import importlib
import pkgutil
from pathlib import Path
from typing import Dict, Type, Optional, List
from .base import BaseCommand

# Command registry
_commands: Dict[str, Type[BaseCommand]] = {}
_discovered = False


def _discover_commands():
    """Auto-discover command modules in this package."""
    global _discovered

    if _discovered:
        return

    package_dir = Path(__file__).parent

    for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
        if module_name == "base":
            continue

        try:
            module = importlib.import_module(f".{module_name}", package=__name__)

            if hasattr(module, "command"):
                cmd_class = module.command
                _commands[cmd_class.name] = cmd_class

                # Register aliases
                for alias in getattr(cmd_class, "aliases", []):
                    _commands[alias] = cmd_class
        except ImportError as e:
            print(f"Warning: Failed to load command module {module_name}: {e}")

    _discovered = True


def get_command(name: str) -> Optional[Type[BaseCommand]]:
    """
    Get command class by name or alias.

    Args:
        name: Command name or alias

    Returns:
        Command class or None if not found
    """
    _discover_commands()
    return _commands.get(name)


def list_commands() -> Dict[str, str]:
    """
    List all available commands with descriptions.

    Returns:
        Dict mapping command names to descriptions
    """
    _discover_commands()

    # Deduplicate (aliases point to same class)
    seen = set()
    result = {}

    for name, cls in _commands.items():
        if cls.name not in seen:
            result[cls.name] = cls.description
            seen.add(cls.name)

    return result


def get_command_names() -> List[str]:
    """Get list of all command names (excluding aliases)."""
    _discover_commands()
    seen = set()
    names = []

    for name, cls in _commands.items():
        if cls.name not in seen:
            names.append(cls.name)
            seen.add(cls.name)

    return sorted(names)
