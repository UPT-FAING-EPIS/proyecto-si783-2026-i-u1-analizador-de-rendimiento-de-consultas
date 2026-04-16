"""Tests for questionary-based interactive CLI prompts."""

from unittest.mock import MagicMock, patch

import pytest

from query_analyzer.cli.questionary_prompts import (
    _is_interactive,
    confirm_action,
    engine_selector_menu,
    output_format_menu,
    profile_name_prompt,
    select_from_list,
    select_profile_menu,
    timeout_presets_menu,
)
from query_analyzer.config import ProfileConfig, ProfileNotFoundError

# ═══════════════════════════════════════════════════════════════
# TTY DETECTION TESTS
# ═══════════════════════════════════════════════════════════════


def test_is_interactive_with_tty() -> None:
    """Test TTY detection when stdin is a terminal."""
    with patch("sys.stdin.isatty", return_value=True):
        assert _is_interactive() is True


def test_is_interactive_without_tty() -> None:
    """Test TTY detection when stdin is not a terminal (piped)."""
    with patch("sys.stdin.isatty", return_value=False):
        assert _is_interactive() is False


# ═══════════════════════════════════════════════════════════════
# ENGINE SELECTOR MENU TESTS
# ═══════════════════════════════════════════════════════════════


def test_engine_selector_menu_returns_provided_engine() -> None:
    """Test that providing engine skips interactive prompt."""
    result = engine_selector_menu("postgresql")
    assert result == "postgresql"

    result = engine_selector_menu("mysql")
    assert result == "mysql"

    result = engine_selector_menu("sqlite")
    assert result == "sqlite"


def test_engine_selector_menu_non_interactive_default() -> None:
    """Test that non-TTY mode returns default engine."""
    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=False):
        result = engine_selector_menu()
        assert result == "postgresql"  # Default


@patch("query_analyzer.cli.questionary_prompts.questionary.select")
def test_engine_selector_menu_interactive_default(mock_select: MagicMock) -> None:
    """Test interactive engine selection defaults to PostgreSQL."""
    mock_select.return_value.ask.return_value = "postgresql"

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        result = engine_selector_menu()
        assert result == "postgresql"
        mock_select.assert_called_once()


@patch("query_analyzer.cli.questionary_prompts.questionary.select")
def test_engine_selector_menu_interactive_user_selection(mock_select: MagicMock) -> None:
    """Test user can select different engine via menu."""
    mock_select.return_value.ask.return_value = "mysql"

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        result = engine_selector_menu()
        assert result == "mysql"


@patch("query_analyzer.cli.questionary_prompts.questionary.select")
def test_engine_selector_menu_keyboard_interrupt(mock_select: MagicMock) -> None:
    """Test KeyboardInterrupt handling (Ctrl+C)."""
    mock_select.return_value.ask.return_value = None

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        with pytest.raises(KeyboardInterrupt):
            engine_selector_menu()


# ═══════════════════════════════════════════════════════════════
# PROFILE NAME PROMPT TESTS
# ═══════════════════════════════════════════════════════════════


def test_profile_name_prompt_non_interactive_raises() -> None:
    """Test that non-TTY mode raises error."""
    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=False):
        with pytest.raises(ValueError, match="Profile name required.*non-interactive"):
            profile_name_prompt()


@patch("query_analyzer.cli.questionary_prompts.questionary.text")
def test_profile_name_prompt_interactive_valid(mock_text: MagicMock) -> None:
    """Test valid profile name input."""
    mock_text.return_value.ask.return_value = "staging"

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        result = profile_name_prompt()
        assert result == "staging"


@patch("query_analyzer.cli.questionary_prompts.questionary.text")
def test_profile_name_prompt_strips_whitespace(mock_text: MagicMock) -> None:
    """Test that profile name is stripped of whitespace."""
    mock_text.return_value.ask.return_value = "  production  "

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        result = profile_name_prompt()
        assert result == "production"


@patch("query_analyzer.cli.questionary_prompts.questionary.text")
def test_profile_name_prompt_with_dashes_underscores(mock_text: MagicMock) -> None:
    """Test profile names with dashes and underscores."""
    mock_text.return_value.ask.return_value = "my-prod_db-01"

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        result = profile_name_prompt()
        assert result == "my-prod_db-01"


@patch("query_analyzer.cli.questionary_prompts.questionary.text")
def test_profile_name_prompt_keyboard_interrupt(mock_text: MagicMock) -> None:
    """Test KeyboardInterrupt handling."""
    mock_text.return_value.ask.return_value = None

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        with pytest.raises(KeyboardInterrupt):
            profile_name_prompt()


@patch("query_analyzer.cli.questionary_prompts.questionary.text")
def test_profile_name_prompt_with_default(mock_text: MagicMock) -> None:
    """Test profile name prompt with default value."""
    mock_text.return_value.ask.return_value = "default_name"

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        result = profile_name_prompt("default_name")
        assert result == "default_name"


# ═══════════════════════════════════════════════════════════════
# PROFILE SELECTION MENU TESTS
# ═══════════════════════════════════════════════════════════════


def test_select_profile_menu_returns_provided_name() -> None:
    """Test that providing profile name skips interactive prompt."""
    result = select_profile_menu("staging")
    assert result == "staging"


def test_select_profile_menu_non_interactive_raises() -> None:
    """Test that non-TTY mode raises error."""
    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=False):
        with pytest.raises(ValueError, match="Profile name required.*non-interactive"):
            select_profile_menu()


@patch("query_analyzer.cli.questionary_prompts.ConfigManager")
def test_select_profile_menu_no_profiles_raises(mock_config_mgr: MagicMock) -> None:
    """Test error when no profiles exist."""
    mock_instance = MagicMock()
    mock_config_mgr.return_value = mock_instance
    mock_instance.list_profiles.return_value = {}

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        with pytest.raises(ProfileNotFoundError, match="No hay perfiles"):
            select_profile_menu()


@patch("query_analyzer.cli.questionary_prompts.questionary.select")
@patch("query_analyzer.cli.questionary_prompts.ConfigManager")
def test_select_profile_menu_interactive_selection(
    mock_config_mgr: MagicMock,
    mock_select: MagicMock,
) -> None:
    """Test interactive profile selection from menu."""
    mock_instance = MagicMock()
    mock_config_mgr.return_value = mock_instance

    # Mock profiles
    profiles = {
        "local-dev": ProfileConfig(
            engine="postgresql",
            host="localhost",
            port=5432,
            database="dev_db",
            username="postgres",
            password="secret",
        ),
        "staging": ProfileConfig(
            engine="mysql",
            host="staging-db.example.com",
            port=3306,
            database="staging_db",
            username="root",
            password="secret",
        ),
    }
    mock_instance.list_profiles.return_value = profiles
    mock_instance.load_config.return_value.default_profile = None

    # User selects "staging"
    mock_select.return_value.ask.return_value = "staging (mysql)"

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        result = select_profile_menu()
        assert result == "staging"


@patch("query_analyzer.cli.questionary_prompts.questionary.select")
@patch("query_analyzer.cli.questionary_prompts.ConfigManager")
def test_select_profile_menu_marks_default_profile(
    mock_config_mgr: MagicMock,
    mock_select: MagicMock,
) -> None:
    """Test that default profile is marked in menu."""
    mock_instance = MagicMock()
    mock_config_mgr.return_value = mock_instance

    profiles = {
        "production": ProfileConfig(
            engine="postgresql",
            host="prod-db.example.com",
            port=5432,
            database="prod_db",
            username="analyst",
            password="secret",
        ),
    }
    mock_instance.list_profiles.return_value = profiles
    mock_instance.load_config.return_value.default_profile = "production"

    mock_select.return_value.ask.return_value = "production (postgresql) [DEFAULT]"

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        result = select_profile_menu()
        assert result == "production"

        # Verify DEFAULT marker was in the choice
        call_args = mock_select.call_args
        choices = call_args[1]["choices"]
        assert any("[DEFAULT]" in choice for choice in choices)


@patch("query_analyzer.cli.questionary_prompts.questionary.select")
@patch("query_analyzer.cli.questionary_prompts.ConfigManager")
def test_select_profile_menu_keyboard_interrupt(
    mock_config_mgr: MagicMock,
    mock_select: MagicMock,
) -> None:
    """Test KeyboardInterrupt handling."""
    mock_instance = MagicMock()
    mock_config_mgr.return_value = mock_instance
    mock_instance.list_profiles.return_value = {
        "test": ProfileConfig(
            engine="postgresql",
            host="localhost",
            port=5432,
            database="test",
            username="user",
            password="pass",
        ),
    }
    mock_instance.load_config.return_value.default_profile = None
    mock_select.return_value.ask.return_value = None

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        with pytest.raises(KeyboardInterrupt):
            select_profile_menu()


# ═══════════════════════════════════════════════════════════════
# GENERIC LIST SELECTION TESTS
# ═══════════════════════════════════════════════════════════════


def test_select_from_list_empty_choices_raises() -> None:
    """Test that empty choices list raises ValueError."""
    with pytest.raises(ValueError, match="Choices list cannot be empty"):
        select_from_list("Pick one:", [])


def test_select_from_list_invalid_default_raises() -> None:
    """Test that invalid default raises ValueError."""
    with pytest.raises(ValueError, match="Default .* not in choices"):
        select_from_list(
            "Pick one:",
            ["Option A", "Option B"],
            default="Option C",
        )


def test_select_from_list_non_interactive_returns_default() -> None:
    """Test that non-TTY returns default if provided."""
    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=False):
        result = select_from_list(
            "Pick one:",
            ["Option A", "Option B"],
            default="Option A",
        )
        assert result == "Option A"


def test_select_from_list_non_interactive_no_default_raises() -> None:
    """Test that non-TTY raises if no default provided."""
    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=False):
        with pytest.raises(ValueError, match="Interactive selection required"):
            select_from_list("Pick one:", ["Option A", "Option B"])


@patch("query_analyzer.cli.questionary_prompts.questionary.select")
def test_select_from_list_interactive_selection(mock_select: MagicMock) -> None:
    """Test interactive list selection."""
    mock_select.return_value.ask.return_value = "Option B"

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        result = select_from_list(
            "Pick one:",
            ["Option A", "Option B", "Option C"],
        )
        assert result == "Option B"


@patch("query_analyzer.cli.questionary_prompts.questionary.select")
def test_select_from_list_keyboard_interrupt(mock_select: MagicMock) -> None:
    """Test KeyboardInterrupt handling."""
    mock_select.return_value.ask.side_effect = KeyboardInterrupt

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        with pytest.raises(KeyboardInterrupt):
            select_from_list("Pick one:", ["Option A", "Option B"])


# ═══════════════════════════════════════════════════════════════
# CONFIRM ACTION TESTS
# ═══════════════════════════════════════════════════════════════


def test_confirm_action_non_interactive_returns_default() -> None:
    """Test that non-TTY returns default."""
    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=False):
        result = confirm_action("Delete profile?", default=False)
        assert result is False

        result = confirm_action("Delete profile?", default=True)
        assert result is True


@patch("query_analyzer.cli.questionary_prompts.questionary.confirm")
def test_confirm_action_interactive_yes(mock_confirm: MagicMock) -> None:
    """Test user confirms (yes)."""
    mock_confirm.return_value.ask.return_value = True

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        result = confirm_action("Delete profile?")
        assert result is True


@patch("query_analyzer.cli.questionary_prompts.questionary.confirm")
def test_confirm_action_interactive_no(mock_confirm: MagicMock) -> None:
    """Test user declines (no)."""
    mock_confirm.return_value.ask.return_value = False

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        result = confirm_action("Delete profile?", default=False)
        assert result is False


@patch("query_analyzer.cli.questionary_prompts.questionary.confirm")
def test_confirm_action_keyboard_interrupt(mock_confirm: MagicMock) -> None:
    """Test KeyboardInterrupt handling."""
    mock_confirm.return_value.ask.side_effect = KeyboardInterrupt

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        with pytest.raises(KeyboardInterrupt):
            confirm_action("Delete profile?")


@patch("query_analyzer.cli.questionary_prompts.questionary.confirm")
def test_confirm_action_with_custom_message(mock_confirm: MagicMock) -> None:
    """Test custom confirmation message."""
    mock_confirm.return_value.ask.return_value = True

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        result = confirm_action("Continue with operation?")
        assert result is True

        # Verify message was passed
        call_args = mock_confirm.call_args
        assert "Continue with operation?" in str(call_args)


# ═══════════════════════════════════════════════════════════════
# INTEGRATION-LIKE TESTS (Style & Behavior)
# ═══════════════════════════════════════════════════════════════


@patch("query_analyzer.cli.questionary_prompts.questionary.select")
def test_engine_selector_menu_uses_arrow_keys(mock_select: MagicMock) -> None:
    """Test that arrow keys are enabled in menu."""
    mock_select.return_value.ask.return_value = "postgresql"

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        engine_selector_menu()

        call_args = mock_select.call_args
        assert call_args[1]["use_arrow_keys"] is True
        assert call_args[1]["use_jk_keys"] is True  # vim keys
        assert call_args[1]["use_emacs_keys"] is True  # Ctrl+N/P


@patch("query_analyzer.cli.questionary_prompts.questionary.select")
def test_profile_selector_menu_uses_pointer(mock_select: MagicMock) -> None:
    """Test that pointer is set to » (right arrow)."""
    mock_select.return_value.ask.return_value = "staging (mysql)"

    with patch("query_analyzer.cli.questionary_prompts.ConfigManager"):
        with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
            mock_config = MagicMock()
            mock_config.list_profiles.return_value = {
                "staging": ProfileConfig(
                    engine="mysql",
                    host="localhost",
                    port=3306,
                    database="db",
                    username="user",
                    password="pass",
                ),
            }
            mock_config.load_config.return_value.default_profile = None

            with patch(
                "query_analyzer.cli.questionary_prompts.ConfigManager", return_value=mock_config
            ):
                select_profile_menu()

                call_args = mock_select.call_args
                assert call_args[1]["pointer"] == "»"


# ═══════════════════════════════════════════════════════════════
# OUTPUT FORMAT MENU TESTS
# ═══════════════════════════════════════════════════════════════


def test_output_format_menu_returns_provided_format() -> None:
    """Test that providing format skips interactive prompt."""
    result = output_format_menu("rich")
    assert result == "rich"

    result = output_format_menu("json")
    assert result == "json"

    result = output_format_menu("markdown")
    assert result == "markdown"


def test_output_format_menu_non_interactive_default() -> None:
    """Test that non-TTY mode returns default json format."""
    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=False):
        result = output_format_menu()
        assert result == "json"  # Default for non-TTY (most portable)


@patch("query_analyzer.cli.questionary_prompts.questionary.select")
def test_output_format_menu_interactive_default(mock_select: MagicMock) -> None:
    """Test interactive output format selection defaults to rich."""
    mock_select.return_value.ask.return_value = "rich (formatted table)"

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        result = output_format_menu()
        assert result == "rich"
        mock_select.assert_called_once()


@patch("query_analyzer.cli.questionary_prompts.questionary.select")
def test_output_format_menu_interactive_json_selection(mock_select: MagicMock) -> None:
    """Test user can select json format via menu."""
    mock_select.return_value.ask.return_value = "json (machine-readable)"

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        result = output_format_menu()
        assert result == "json"


@patch("query_analyzer.cli.questionary_prompts.questionary.select")
def test_output_format_menu_interactive_markdown_selection(mock_select: MagicMock) -> None:
    """Test user can select markdown format via menu."""
    mock_select.return_value.ask.return_value = "markdown (for documentation)"

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        result = output_format_menu()
        assert result == "markdown"


@patch("query_analyzer.cli.questionary_prompts.questionary.select")
def test_output_format_menu_keyboard_interrupt(mock_select: MagicMock) -> None:
    """Test KeyboardInterrupt handling (Ctrl+C)."""
    mock_select.return_value.ask.return_value = None

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        with pytest.raises(KeyboardInterrupt):
            output_format_menu()


# ═══════════════════════════════════════════════════════════════
# TIMEOUT PRESETS MENU TESTS
# ═══════════════════════════════════════════════════════════════


def test_timeout_presets_menu_returns_provided_timeout() -> None:
    """Test that providing timeout skips interactive prompt."""
    assert timeout_presets_menu(30) == 30
    assert timeout_presets_menu(60) == 60
    assert timeout_presets_menu(120) == 120


def test_timeout_presets_menu_invalid_timeout_below_range() -> None:
    """Test that timeout below 1 raises error."""
    with pytest.raises(ValueError, match="between 1-300"):
        timeout_presets_menu(0)


def test_timeout_presets_menu_invalid_timeout_above_range() -> None:
    """Test that timeout above 300 raises error."""
    with pytest.raises(ValueError, match="between 1-300"):
        timeout_presets_menu(301)


def test_timeout_presets_menu_non_interactive_default() -> None:
    """Test that non-TTY mode returns default 30 seconds."""
    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=False):
        result = timeout_presets_menu()
        assert result == 30


@patch("query_analyzer.cli.questionary_prompts.questionary.select")
def test_timeout_presets_menu_interactive_default(mock_select: MagicMock) -> None:
    """Test interactive timeout selection defaults to 30 seconds."""
    mock_select.return_value.ask.return_value = "30 seconds (default)"

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        result = timeout_presets_menu()
        assert result == 30
        mock_select.assert_called_once()


@patch("query_analyzer.cli.questionary_prompts.questionary.select")
def test_timeout_presets_menu_interactive_60_seconds(mock_select: MagicMock) -> None:
    """Test user can select 60 seconds via menu."""
    mock_select.return_value.ask.return_value = "60 seconds"

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        result = timeout_presets_menu()
        assert result == 60


@patch("query_analyzer.cli.questionary_prompts.questionary.select")
def test_timeout_presets_menu_interactive_120_seconds(mock_select: MagicMock) -> None:
    """Test user can select 120 seconds via menu."""
    mock_select.return_value.ask.return_value = "120 seconds"

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        result = timeout_presets_menu()
        assert result == 120


@patch("query_analyzer.cli.questionary_prompts.questionary.text")
@patch("query_analyzer.cli.questionary_prompts.questionary.select")
def test_timeout_presets_menu_custom_timeout(mock_select: MagicMock, mock_text: MagicMock) -> None:
    """Test user can enter custom timeout."""
    mock_select.return_value.ask.return_value = "Custom (enter value)"
    mock_text.return_value.ask.return_value = "45"

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        result = timeout_presets_menu()
        assert result == 45


@patch("query_analyzer.cli.questionary_prompts.questionary.select")
def test_timeout_presets_menu_keyboard_interrupt(mock_select: MagicMock) -> None:
    """Test KeyboardInterrupt handling (Ctrl+C)."""
    mock_select.return_value.ask.return_value = None

    with patch("query_analyzer.cli.questionary_prompts._is_interactive", return_value=True):
        with pytest.raises(KeyboardInterrupt):
            timeout_presets_menu()
