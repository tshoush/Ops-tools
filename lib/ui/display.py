"""
Display helpers for interactive mode.
"""

import os
import sys
from typing import List, Optional
from .colors import header, dim, bold, success, warning, error, Colors, IS_TTY


def clear_screen():
    """Clear terminal screen."""
    if IS_TTY:
        os.system('cls' if os.name == 'nt' else 'clear')


def print_banner():
    """Print application banner."""
    banner = """
    ╔════════════════════════════════════════════╗
    ║       DDI Toolkit - Marriott DDI Team      ║
    ║              WAPI v2.13.1                  ║
    ╚════════════════════════════════════════════╝
    """
    print(header(banner))


def print_box(title: str, content: List[str], width: int = 60):
    """Print content in a bordered box."""
    print(f"\n┌{'─' * (width - 2)}┐")
    print(f"│ {bold(title):<{width - 4}} │")
    print(f"├{'─' * (width - 2)}┤")
    for line in content:
        # Truncate line if too long
        display_line = line[:width - 4] if len(line) > width - 4 else line
        print(f"│ {display_line:<{width - 4}} │")
    print(f"└{'─' * (width - 2)}┘")


def print_status(grid_master: str, username: str, connected: bool = False):
    """Print connection status bar."""
    status_icon = "●" if connected else "○"
    status_color = Colors.GREEN if connected else Colors.RED
    state_text = "Connected" if connected else "Not Connected"

    print(dim("─" * 60))
    gm_display = grid_master if grid_master else "Not Configured"
    user_display = username if username else "N/A"
    print(f"  Grid Master: {bold(gm_display)}")
    print(f"  User: {bold(user_display)}  |  Status: {status_color}{status_icon}{Colors.RESET} {state_text}")
    print(dim("─" * 60))


def print_section(title: str):
    """Print a section header."""
    print(f"\n  {bold(title)}")
    print(f"  {'─' * (len(title) + 2)}\n")


def print_result_summary(command: str, query: str, count: int, json_path: str, csv_path: str):
    """Print query result summary."""
    print(f"\n{'═' * 60}")
    print(f"  Command: {bold(command)}")
    print(f"  Query:   {query}")
    print(f"  Results: {count} record(s)")
    print(f"{'═' * 60}")
    print(f"\n  Output Files:")
    print(f"    JSON: {success(json_path)}")
    print(f"    CSV:  {success(csv_path)}")


def print_welcome():
    """Print welcome message for first-time setup."""
    print(header("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║              WELCOME TO DDI TOOLKIT                       ║
    ║                                                           ║
    ║   First-time setup detected. Let's configure your        ║
    ║   InfoBlox Grid Master connection.                        ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """))
