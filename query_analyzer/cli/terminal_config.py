"""Terminal capability detection and Rich console configuration.

This module detects terminal ANSI color support and provides configuration
for Rich console instances. Handles edge cases like Git Bash on Windows,
NO_COLOR environment variable, and explicit color override options.
"""

import os
import sys
from typing import TypedDict


class ConsoleConfig(TypedDict):
    """Configuration dictionary for Rich Console initialization."""

    no_color: bool
    force_terminal: bool | None
    width: int | None
    legacy_windows: bool


def _is_git_bash_windows() -> bool:
    """Check if running in Git Bash on Windows.

    Git Bash on Windows may not properly report terminal capabilities.
    We detect this by checking MSYSTEM environment variable and platform.

    Returns:
        True if running in Git Bash on Windows, False otherwise.
    """
    if sys.platform != "win32":
        return False

    # Git Bash sets MSYSTEM to MINGW64 or MINGW32
    msystem = os.environ.get("MSYSTEM", "").upper()
    return msystem in ("MINGW64", "MINGW32", "MSYS")


def detect_ansi_support() -> bool:
    """Detect if terminal supports ANSI color codes.

    Implements priority-based detection:
    1. Check NO_COLOR environment variable (disables color)
    2. Check FORCE_COLOR environment variable (enables color)
    3. Check QA_NO_COLOR environment variable (disables color)
    4. Check if stdin is a TTY
    5. Special handling for Git Bash on Windows (assume no color)
    6. Fallback to check if terminal emulation is available

    Returns:
        True if ANSI colors should be enabled, False otherwise.

    See:
        - https://no-color.org/
        - https://bixense.com/clicolors/
    """
    # Highest priority: explicit NO_COLOR (standard convention)
    if os.environ.get("NO_COLOR"):
        return False

    # QA_NO_COLOR for query_analyzer specific override
    if os.environ.get("QA_NO_COLOR"):
        return False

    # FORCE_COLOR can override NO_COLOR in some contexts
    if os.environ.get("FORCE_COLOR"):
        return True

    # Git Bash on Windows typically doesn't support ANSI reliably
    if _is_git_bash_windows():
        # Unless explicitly forced
        if os.environ.get("FORCE_COLOR"):
            return True
        # Default to no color for safety
        return False

    # Check if output is to a TTY (terminal)
    # If not TTY (piped, redirected), assume no color support
    if not sys.stdout.isatty():
        return False

    # Check TERM environment variable for color support
    term = os.environ.get("TERM", "").lower()
    # Common non-color terminals
    if term in ("dumb", ""):
        return False

    # If we get here, assume terminal supports colors
    return True


def get_terminal_width() -> int:
    """Get terminal width in characters.

    Attempts to get actual terminal width, falls back to 80 if unable.

    Returns:
        Terminal width in characters (minimum 40, typical 80-200).
    """
    try:
        import shutil

        width = shutil.get_terminal_size(fallback=(80, 24))[0]
        # Ensure minimum reasonable width
        return max(40, width)
    except Exception:
        # Fallback to standard width
        return 80


def is_vertical_layout(width: int) -> bool:
    """Check if width requires vertical layout.

    Vertical layout suitable for very narrow terminals.

    Args:
        width: Terminal width in characters

    Returns:
        True if width < 80 (very narrow terminal)
    """
    return width < 80


def is_compact_layout(width: int) -> bool:
    """Check if width requires compact layout.

    Compact layout with reduced columns for medium-width terminals.

    Args:
        width: Terminal width in characters

    Returns:
        True if 80 <= width < 120
    """
    return 80 <= width < 120


def is_full_layout(width: int) -> bool:
    """Check if width supports full layout.

    Full layout with all columns for wide terminals.

    Args:
        width: Terminal width in characters

    Returns:
        True if width >= 120
    """
    return width >= 120


def get_console_config(no_color: bool | None = None) -> ConsoleConfig:
    """Get configuration dictionary for Rich Console.

    Combines automatic detection with explicit override option.

    Args:
        no_color: Explicit override (True=disable color, False=enable color, None=auto-detect)

    Returns:
        Dictionary with 'no_color', 'force_terminal', and 'width' keys
        suitable for Rich Console initialization.

    Example:
        >>> config = get_console_config()
        >>> console = Console(**config)

        >>> config = get_console_config(no_color=True)
        >>> console = Console(**config)  # No colors regardless of terminal
    """
    # Determine color support
    if no_color is None:
        # Auto-detect
        use_color = detect_ansi_support()
    else:
        # Explicit override
        use_color = not no_color

    # Determine if we should force terminal emulation
    # Don't force terminal on Git Bash - it causes issues with Windows console API
    force_terminal_enabled = use_color and sys.stdout.isatty() and not _is_git_bash_windows()

    return {
        "no_color": not use_color,
        "force_terminal": force_terminal_enabled,
        "legacy_windows": False,  # Don't use Windows console API, use ANSI instead
        "width": None,  # Let Rich auto-detect terminal width
    }
