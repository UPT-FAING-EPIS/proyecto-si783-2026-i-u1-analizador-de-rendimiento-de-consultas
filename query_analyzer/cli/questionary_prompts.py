"""Interactive questionary prompts with arrow-key navigation.

Provides menu-driven selection with arrow keys (↑/↓) + Enter for:
- Database engine selection
- Profile selection
- Profile name input
- Generic list selection

All functions check for TTY (terminal) and fallback gracefully to non-interactive
mode for CI/scripts where no TTY is available.
"""

import sys

import questionary  # type: ignore[import-not-found]
from questionary import Style

from query_analyzer.config import ConfigManager, ProfileNotFoundError

# ═══════════════════════════════════════════════════════════════
# THEME & STYLING (Matches Rich color scheme)
# ═══════════════════════════════════════════════════════════════

ANALYSIS_STYLE = Style(
    [
        ("qmark", "fg:#2ecc71 bold"),  # Green question mark (Rich success)
        ("question", "bold"),  # Bold question text
        ("answer", "fg:#2ecc71 bold"),  # Green selected answer
        ("pointer", "fg:#2ecc71 bold"),  # Green pointer »
        ("highlighted", "fg:#3498db bold"),  # Blue for navigation
        ("selected", "fg:#2ecc71"),  # Green for selections
        ("separator", "fg:#6c757d"),  # Gray separators
        ("instruction", "fg:#95a5a6 italic"),  # Muted instruction
        ("disabled", "fg:#6c757d italic"),  # Gray disabled items
    ]
)


# ═══════════════════════════════════════════════════════════════
# HELPER: Check TTY Availability
# ═══════════════════════════════════════════════════════════════


def _is_interactive() -> bool:
    """Check if running in interactive terminal (not piped/CI).

    Returns:
        True if stdin is a TTY (interactive terminal), False otherwise.
    """
    return sys.stdin.isatty()


# ═══════════════════════════════════════════════════════════════
# ENGINE SELECTION WITH ARROW KEYS
# ═══════════════════════════════════════════════════════════════


def engine_selector_menu(engine: str | None = None) -> str:
    """Select database engine using arrow keys menu.

    If engine provided, returns immediately (non-interactive).
    If not interactive (no TTY), falls back to default.
    Otherwise shows arrow-key menu.

    Args:
        engine: Engine name if already provided via CLI args

    Returns:
        Selected engine name (e.g., 'postgresql', 'mysql')

    Raises:
        KeyboardInterrupt: If user cancels with Ctrl+C

    Example:
        >>> engine_selector_menu()  # Interactive
        Select database engine:
        ▶ PostgreSQL
          MySQL
          SQLite
          CockroachDB
          YugabyteDB

        >>> engine_selector_menu("postgresql")  # Non-interactive
        'postgresql'
    """
    if engine is not None:
        return engine

    if not _is_interactive():
        return "postgresql"  # Default for non-TTY

    engines = [
        "postgresql",
        "mysql",
        "sqlite",
        "cockroachdb",
        "yugabytedb",
        "mssql",
    ]

    try:
        selected = questionary.select(
            "Select database engine:",
            choices=engines,
            default="postgresql",
            pointer="»",
            use_arrow_keys=True,
            use_jk_keys=True,  # j/k vim keys
            use_emacs_keys=True,  # Ctrl+N/Ctrl+P
            show_selected=True,
            style=ANALYSIS_STYLE,
        ).ask()

        if selected is None:
            raise KeyboardInterrupt

        return str(selected)

    except KeyboardInterrupt:
        raise
    except Exception:
        # Fallback if questionary fails (e.g., on Git Bash Windows)
        return "postgresql"


# ═══════════════════════════════════════════════════════════════
# PROFILE NAME INPUT
# ═══════════════════════════════════════════════════════════════


def profile_name_prompt(default: str | None = None) -> str:
    """Prompt for profile name interactively.

    If name provided, returns immediately.
    If not interactive (no TTY), raises error.
    Otherwise shows text input prompt.

    Args:
        default: Default profile name to show in prompt

    Returns:
        Profile name (non-empty string)

    Raises:
        KeyboardInterrupt: If user cancels
        ValueError: If no name provided and non-interactive

    Example:
        >>> profile_name_prompt()  # Interactive
        Profile Name: staging
        'staging'
    """
    if not _is_interactive():
        raise ValueError(
            "Profile name required (in non-interactive mode).\n"
            "Provide: qa profile add <name> [options]"
        )

    def validate_name(text: str) -> bool | str:
        if not text.strip():
            return "Profile name cannot be empty"
        if len(text.strip()) < 2:
            return "Profile name must be at least 2 characters"
        if not all(c.isalnum() or c in "-_" for c in text.strip()):
            return "Profile name can only contain alphanumeric, dash, underscore"
        return True

    try:
        name = questionary.text(
            "Profile Name:",
            default=default or "",
            validate=validate_name,
            style=ANALYSIS_STYLE,
        ).ask()

        if name is None:
            raise KeyboardInterrupt

        return str(name).strip()

    except KeyboardInterrupt:
        raise


# ═══════════════════════════════════════════════════════════════
# PROFILE SELECTION WITH ARROW KEYS
# ═══════════════════════════════════════════════════════════════


def select_profile_menu(profile_name: str | None = None) -> str:
    """Select profile from list using arrow keys.

    If profile_name provided, returns immediately (non-interactive).
    If not interactive (no TTY), raises error.
    Otherwise shows arrow-key menu of profiles.

    Args:
        profile_name: Profile name if already provided via CLI args

    Returns:
        Selected profile name

    Raises:
        ProfileNotFoundError: If no profiles exist
        KeyboardInterrupt: If user cancels
        ValueError: If non-interactive without profile name

    Example:
        >>> select_profile_menu()  # Interactive
        Select Profile:
        ▶ local-dev (postgresql)
          staging (mysql)
          production (postgresql) [DEFAULT]
        'local-dev'
    """
    if profile_name is not None:
        return profile_name

    if not _is_interactive():
        raise ValueError(
            "Profile name required (in non-interactive mode).\nProvide: qa profile <command> <name>"
        )

    try:
        config_mgr = ConfigManager()
        profiles = config_mgr.list_profiles()

        if not profiles:
            raise ProfileNotFoundError("No hay perfiles configurados")

        config = config_mgr.load_config()

        # Build choices with visual indicators
        choices = []
        profile_list = list(profiles.items())

        for name, profile in profile_list:
            is_default = name == config.default_profile
            default_marker = " [DEFAULT]" if is_default else ""
            choice_text = f"{name} ({profile.engine}){default_marker}"
            choices.append(choice_text)

        # Show menu
        selected_choice = questionary.select(
            "Select Profile:",
            choices=choices,
            pointer="»",
            use_arrow_keys=True,
            use_jk_keys=True,
            use_emacs_keys=True,
            show_selected=True,
            style=ANALYSIS_STYLE,
        ).ask()

        if selected_choice is None:
            raise KeyboardInterrupt

        # Extract profile name from choice text
        selected_name = str(selected_choice).split(" (")[0]
        return selected_name

    except KeyboardInterrupt:
        raise
    except ProfileNotFoundError:
        raise
    except Exception as e:
        # Fallback if questionary fails (e.g., on Git Bash Windows)
        # Return first profile if available
        if profiles:
            return next(iter(profiles.keys()))
        raise ProfileNotFoundError(f"Error selecting profile: {e}") from e

    # Unreachable, but satisfies mypy's return type checking
    raise ProfileNotFoundError("Profile selection failed")


# ═══════════════════════════════════════════════════════════════
# GENERIC LIST SELECTION
# ═══════════════════════════════════════════════════════════════


def select_from_list(
    message: str,
    choices: list[str],
    default: str | None = None,
) -> str | None:
    """Generic menu to select from a list using arrow keys.

    Args:
        message: Prompt message to display
        choices: List of choices to select from
        default: Default choice (must be in choices)

    Returns:
        Selected choice string, or None if cancelled

    Raises:
        ValueError: If default not in choices or choices empty
        KeyboardInterrupt: If user cancels with Ctrl+C

    Example:
        >>> select_from_list(
        ...     "Pick one:",
        ...     ["Option A", "Option B", "Option C"],
        ...     default="Option A"
        ... )
        'Option B'
    """
    if not choices:
        raise ValueError("Choices list cannot be empty")

    if default and default not in choices:
        raise ValueError(f"Default '{default}' not in choices")

    if not _is_interactive():
        if default:
            return default
        raise ValueError(f"Interactive selection required. Choices: {', '.join(choices)}")

    try:
        selected = questionary.select(
            message,
            choices=choices,
            default=default or choices[0],
            pointer="»",
            use_arrow_keys=True,
            use_jk_keys=True,
            use_emacs_keys=True,
            show_selected=True,
            style=ANALYSIS_STYLE,
        ).ask()

        return str(selected) if selected is not None else None

    except KeyboardInterrupt:
        raise
    except Exception:
        # Fallback if questionary fails (e.g., on Git Bash Windows)
        return default or (choices[0] if choices else None)


# ═══════════════════════════════════════════════════════════════
# CONFIRMATION DIALOG
# ═══════════════════════════════════════════════════════════════


def confirm_action(message: str, default: bool = False) -> bool:
    """Confirm yes/no action using arrow keys.

    Args:
        message: Question to ask
        default: Default choice (True=yes, False=no)

    Returns:
        True if user selects 'Yes', False otherwise

    Raises:
        KeyboardInterrupt: If user cancels with Ctrl+C

    Example:
        >>> confirm_action("Delete profile 'staging'?", default=False)
        True  # if user selects 'Yes'
    """
    if not _is_interactive():
        return default

    try:
        result = questionary.confirm(
            message,
            default=default,
            auto_enter=False,
            style=ANALYSIS_STYLE,
        ).ask()

        return bool(result)

    except KeyboardInterrupt:
        raise
    except Exception:
        # Fallback if questionary fails (e.g., on Git Bash Windows)
        return default


# ═══════════════════════════════════════════════════════════════
# OUTPUT FORMAT SELECTION
# ═══════════════════════════════════════════════════════════════


def output_format_menu(output_format: str | None = None) -> str:
    """Select output format using arrow keys menu.

    If output_format provided, returns immediately (non-interactive).
    If not interactive (no TTY), defaults to 'json' (most portable).
    Otherwise shows arrow-key menu.

    Args:
        output_format: Output format if already provided via CLI args

    Returns:
        Selected output format ('rich', 'json', or 'markdown')

    Raises:
        KeyboardInterrupt: If user cancels with Ctrl+C

    Example:
        >>> output_format_menu()  # Interactive
        Select output format:
        ▶ rich (formatted table)
          json (machine-readable)
          markdown (for documentation)

        >>> output_format_menu("json")  # Non-interactive
        'json'
    """
    if output_format is not None:
        return output_format

    if not _is_interactive():
        return "json"  # Default for non-TTY (most portable)

    formats = [
        "rich (formatted table)",
        "json (machine-readable)",
        "markdown (for documentation)",
    ]

    try:
        selected = questionary.select(
            "Select output format:",
            choices=formats,
            default="rich (formatted table)",
            pointer="»",
            use_arrow_keys=True,
            use_jk_keys=True,
            use_emacs_keys=True,
            show_selected=True,
            style=ANALYSIS_STYLE,
        ).ask()

        if selected is None:
            raise KeyboardInterrupt

        # Extract format name from choice text (e.g., "rich (formatted table)" -> "rich")
        format_name = str(selected).split(" (")[0]
        return format_name

    except KeyboardInterrupt:
        raise
    except Exception:
        # Fallback if questionary fails (e.g., on Git Bash Windows with xterm)
        # Return default format
        return "rich"


# ═══════════════════════════════════════════════════════════════
# TIMEOUT PRESETS MENU
# ═══════════════════════════════════════════════════════════════


def timeout_presets_menu(timeout: int | None = None) -> int:
    """Select query timeout using presets menu with custom option.

    If timeout provided, returns immediately (non-interactive).
    If not interactive (no TTY), defaults to 30 seconds.
    Otherwise shows arrow-key menu with presets and custom option.

    Args:
        timeout: Timeout in seconds if already provided via CLI args

    Returns:
        Selected timeout in seconds (int)

    Raises:
        KeyboardInterrupt: If user cancels with Ctrl+C
        ValueError: If custom timeout invalid

    Example:
        >>> timeout_presets_menu()  # Interactive
        Select timeout:
        ▶ 30 seconds (default)
          60 seconds
          120 seconds
          Custom (enter value)

        >>> timeout_presets_menu(45)  # Non-interactive
        45
    """
    if timeout is not None:
        # Validate the provided timeout
        if timeout < 1 or timeout > 300:
            raise ValueError(f"Timeout must be between 1-300 seconds. Received: {timeout}")
        return timeout

    if not _is_interactive():
        return 30  # Default for non-TTY

    presets = [
        "30 seconds (default)",
        "60 seconds",
        "120 seconds",
        "Custom (enter value)",
    ]

    try:
        selected = questionary.select(
            "Select query timeout:",
            choices=presets,
            default="30 seconds (default)",
            pointer="»",
            use_arrow_keys=True,
            use_jk_keys=True,
            use_emacs_keys=True,
            show_selected=True,
            style=ANALYSIS_STYLE,
        ).ask()

        if selected is None:
            raise KeyboardInterrupt

        selected_text = str(selected)

        # Parse preset or handle custom
        if selected_text == "30 seconds (default)":
            return 30
        elif selected_text == "60 seconds":
            return 60
        elif selected_text == "120 seconds":
            return 120
        elif selected_text == "Custom (enter value)":
            # Get custom timeout from user
            def validate_timeout(text: str) -> bool | str:
                try:
                    val = int(text.strip())
                    if val < 1 or val > 300:
                        return "Timeout must be between 1-300 seconds"
                    return True
                except ValueError:
                    return "Please enter a valid integer"

            custom_timeout = questionary.text(
                "Enter timeout in seconds (1-300):",
                validate=validate_timeout,
                style=ANALYSIS_STYLE,
            ).ask()

            if custom_timeout is None:
                raise KeyboardInterrupt

            return int(custom_timeout.strip())

        # Fallback (shouldn't reach here)
        return 30

    except KeyboardInterrupt:
        raise
    except Exception:
        # Fallback if questionary fails (e.g., on Git Bash Windows)
        return 30
