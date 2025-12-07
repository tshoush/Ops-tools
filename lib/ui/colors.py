"""
Terminal colors and styling - graceful fallback if not TTY.
"""

import sys
import os

# Check if we're in a real terminal
IS_TTY = sys.stdout.isatty() and os.environ.get("TERM") != "dumb"


class Colors:
    """ANSI color codes with TTY detection."""

    if IS_TTY:
        HEADER = '\033[95m'
        BLUE = '\033[94m'
        CYAN = '\033[96m'
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        RED = '\033[91m'
        BOLD = '\033[1m'
        DIM = '\033[2m'
        RESET = '\033[0m'
        UNDERLINE = '\033[4m'
    else:
        HEADER = BLUE = CYAN = GREEN = YELLOW = RED = ""
        BOLD = DIM = RESET = UNDERLINE = ""


def style(text: str, *styles: str) -> str:
    """Apply styles to text."""
    if not IS_TTY:
        return text
    prefix = "".join(styles)
    return f"{prefix}{text}{Colors.RESET}"


def header(text: str) -> str:
    """Header style - bold cyan."""
    return style(text, Colors.BOLD, Colors.CYAN)


def success(text: str) -> str:
    """Success style - green."""
    return style(text, Colors.GREEN)


def warning(text: str) -> str:
    """Warning style - yellow."""
    return style(text, Colors.YELLOW)


def error(text: str) -> str:
    """Error style - red."""
    return style(text, Colors.RED)


def dim(text: str) -> str:
    """Dim style - muted text."""
    return style(text, Colors.DIM)


def bold(text: str) -> str:
    """Bold style."""
    return style(text, Colors.BOLD)
