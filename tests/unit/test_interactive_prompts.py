"""Tests for interactive CLI prompts module."""

from unittest.mock import MagicMock, patch

import pytest

from query_analyzer.cli.prompts import (
    confirm_deletion,
    database_prompt,
    engine_selector,
    host_prompt,
    interactive_profile_config,
    password_prompt,
    port_prompt_with_validation,
    query_input_prompt,
    select_profile_from_menu,
    username_prompt,
)
from query_analyzer.config import ProfileConfig, ProfileNotFoundError

# ═══════════════════════════════════════════════════════════════
# ENGINE SELECTOR TESTS
# ═══════════════════════════════════════════════════════════════


def test_engine_selector_non_interactive():
    """Test that providing engine skips prompt."""
    result = engine_selector("postgresql")
    assert result == "postgresql"

    result = engine_selector("mysql")
    assert result == "mysql"


@patch("query_analyzer.cli.prompts.Prompt.ask")
def test_engine_selector_interactive(mock_ask: MagicMock) -> None:
    """Test interactive engine selection."""
    mock_ask.return_value = "mysql"
    result = engine_selector(None)
    assert result == "mysql"
    mock_ask.assert_called_once()


# ═══════════════════════════════════════════════════════════════
# HOST PROMPT TESTS
# ═══════════════════════════════════════════════════════════════


def test_host_prompt_non_interactive():
    """Test that providing host skips prompt."""
    result = host_prompt("prod-db.example.com")
    assert result == "prod-db.example.com"

    result = host_prompt("localhost")
    assert result == "localhost"


@patch("query_analyzer.cli.prompts.Prompt.ask")
def test_host_prompt_interactive(mock_ask: MagicMock) -> None:
    """Test interactive host input."""
    mock_ask.return_value = "custom-host.com"
    result = host_prompt(None)
    assert result == "custom-host.com"
    mock_ask.assert_called_once_with("Host", default="localhost")


# ═══════════════════════════════════════════════════════════════
# PORT PROMPT TESTS
# ═══════════════════════════════════════════════════════════════


def test_port_prompt_non_interactive():
    """Test that providing port skips prompt."""
    result = port_prompt_with_validation(5432, "postgresql")
    assert result == 5432

    result = port_prompt_with_validation(3306, "mysql")
    assert result == 3306


def test_port_prompt_validation_invalid_range():
    """Test that invalid port raises ValueError."""
    with pytest.raises(ValueError, match="must be between 1 and 65535"):
        port_prompt_with_validation(0, "postgresql")

    with pytest.raises(ValueError, match="must be between 1 and 65535"):
        port_prompt_with_validation(99999, "postgresql")


@patch("query_analyzer.cli.prompts.IntPrompt.ask")
def test_port_prompt_interactive_postgresql(mock_ask: MagicMock) -> None:
    """Test interactive port selection for PostgreSQL."""
    mock_ask.return_value = 5432
    result = port_prompt_with_validation(None, "postgresql")
    assert result == 5432
    mock_ask.assert_called_once_with("Port", default=5432)


@patch("query_analyzer.cli.prompts.IntPrompt.ask")
def test_port_prompt_interactive_mysql(mock_ask: MagicMock) -> None:
    """Test interactive port selection for MySQL."""
    mock_ask.return_value = 3306
    result = port_prompt_with_validation(None, "mysql")
    assert result == 3306
    mock_ask.assert_called_once_with("Port", default=3306)


@patch("query_analyzer.cli.prompts.OutputFormatter.print_error")
@patch("query_analyzer.cli.prompts.IntPrompt.ask")
def test_port_prompt_invalid_then_valid(
    mock_ask: MagicMock,
    mock_error: MagicMock,
) -> None:
    """Test port validation re-prompting on invalid input."""
    # First call returns invalid, second returns valid
    mock_ask.side_effect = [65536, 5432]
    result = port_prompt_with_validation(None, "postgresql")
    assert result == 5432
    assert mock_ask.call_count == 2
    mock_error.assert_called_with("Port must be between 1 and 65535")


# ═══════════════════════════════════════════════════════════════
# DATABASE PROMPT TESTS
# ═══════════════════════════════════════════════════════════════


def test_database_prompt_non_interactive():
    """Test that providing database skips prompt."""
    result = database_prompt("myapp_db")
    assert result == "myapp_db"


@patch("query_analyzer.cli.prompts.Prompt.ask")
def test_database_prompt_interactive(mock_ask: MagicMock) -> None:
    """Test interactive database input."""
    mock_ask.return_value = "test_database"
    result = database_prompt(None)
    assert result == "test_database"
    mock_ask.assert_called_once()


@patch("query_analyzer.cli.prompts.OutputFormatter.print_error")
@patch("query_analyzer.cli.prompts.Prompt.ask")
def test_database_prompt_empty_re_prompt(
    mock_ask: MagicMock,
    mock_error: MagicMock,
) -> None:
    """Test database re-prompting on empty input."""
    mock_ask.side_effect = ["", "  ", "valid_db"]
    result = database_prompt(None)
    assert result == "valid_db"
    assert mock_ask.call_count == 3
    assert mock_error.call_count == 2


# ═══════════════════════════════════════════════════════════════
# USERNAME PROMPT TESTS
# ═══════════════════════════════════════════════════════════════


def test_username_prompt_non_interactive():
    """Test that providing username skips prompt."""
    result = username_prompt("myuser", "postgresql")
    assert result == "myuser"


@patch("query_analyzer.cli.prompts.Prompt.ask")
def test_username_prompt_interactive_postgresql(mock_ask: MagicMock) -> None:
    """Test interactive username selection for PostgreSQL."""
    mock_ask.return_value = "analyst"
    result = username_prompt(None, "postgresql")
    assert result == "analyst"
    mock_ask.assert_called_once_with("Username", default="postgres")


@patch("query_analyzer.cli.prompts.Prompt.ask")
def test_username_prompt_interactive_mysql(mock_ask: MagicMock) -> None:
    """Test interactive username selection for MySQL."""
    mock_ask.return_value = "app_user"
    result = username_prompt(None, "mysql")
    assert result == "app_user"
    mock_ask.assert_called_once_with("Username", default="root")


# ═══════════════════════════════════════════════════════════════
# PASSWORD PROMPT TESTS
# ═══════════════════════════════════════════════════════════════


def test_password_prompt_non_interactive():
    """Test that providing password skips prompt."""
    result = password_prompt("secret123", require_confirmation=False)
    assert result == "secret123"


@patch("query_analyzer.cli.prompts.Prompt.ask")
def test_password_prompt_interactive_no_confirmation(mock_ask: MagicMock) -> None:
    """Test interactive password input without confirmation."""
    mock_ask.return_value = "mypassword"
    result = password_prompt(None, require_confirmation=False)
    assert result == "mypassword"
    mock_ask.assert_called_once_with("Password", password=True)


@patch("query_analyzer.cli.prompts.Prompt.ask")
def test_password_prompt_interactive_with_confirmation(mock_ask: MagicMock) -> None:
    """Test interactive password input with confirmation."""
    mock_ask.side_effect = ["mypassword", "mypassword"]
    result = password_prompt(None, require_confirmation=True)
    assert result == "mypassword"
    assert mock_ask.call_count == 2


@patch("query_analyzer.cli.prompts.OutputFormatter.print_error")
@patch("query_analyzer.cli.prompts.Prompt.ask")
def test_password_prompt_confirmation_mismatch(
    mock_ask: MagicMock,
    mock_error: MagicMock,
) -> None:
    """Test password re-prompting on confirmation mismatch."""
    mock_ask.side_effect = ["pass1", "pass2", "pass3", "pass3"]
    result = password_prompt(None, require_confirmation=True)
    assert result == "pass3"
    assert mock_ask.call_count == 4
    mock_error.assert_called_once_with("Passwords do not match")


# ═══════════════════════════════════════════════════════════════
# CONFIRM DELETION TESTS
# ═══════════════════════════════════════════════════════════════


@patch("query_analyzer.cli.prompts.Confirm.ask")
def test_confirm_deletion_yes(mock_ask: MagicMock) -> None:
    """Test deletion confirmation when user says yes."""
    mock_ask.return_value = True
    result = confirm_deletion("staging")
    assert result is True
    # The actual message format may vary
    mock_ask.assert_called_once()
    call_args = mock_ask.call_args
    assert "staging" in str(call_args)
    assert call_args[1]["default"] is False


@patch("query_analyzer.cli.prompts.Confirm.ask")
def test_confirm_deletion_no(mock_ask: MagicMock) -> None:
    """Test deletion confirmation when user says no."""
    mock_ask.return_value = False
    result = confirm_deletion("production")
    assert result is False


# ═══════════════════════════════════════════════════════════════
# SELECT PROFILE FROM MENU TESTS
# ═══════════════════════════════════════════════════════════════


def test_select_profile_non_interactive():
    """Test that providing profile skips prompt."""
    result = select_profile_from_menu("staging")
    assert result == "staging"


@patch("query_analyzer.cli.prompts.ConfigManager")
def test_select_profile_menu_no_profiles(mock_config_mgr: MagicMock) -> None:
    """Test profile menu when no profiles exist."""
    mock_instance = MagicMock()
    mock_config_mgr.return_value = mock_instance
    mock_instance.list_profiles.return_value = {}

    with pytest.raises(ProfileNotFoundError, match="No hay perfiles configurados"):
        select_profile_from_menu(None)


@patch("query_analyzer.cli.prompts.IntPrompt.ask")
@patch("query_analyzer.cli.prompts.ConfigManager")
def test_select_profile_menu_selection(
    mock_config_mgr: MagicMock,
    mock_ask: MagicMock,
) -> None:
    """Test interactive profile selection."""
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

    # User selects second profile
    mock_ask.return_value = 2

    result = select_profile_from_menu(None)
    assert result == "staging"


# ═══════════════════════════════════════════════════════════════
# QUERY INPUT PROMPT TESTS
# ═══════════════════════════════════════════════════════════════


def test_query_input_prompt_non_interactive():
    """Test that providing query skips prompt."""
    query = "SELECT * FROM users"
    result = query_input_prompt(query)
    assert result == query


@patch("query_analyzer.cli.prompts.input")
def test_query_input_prompt_interactive(mock_input: MagicMock) -> None:
    """Test interactive query input."""
    mock_input.side_effect = ["SELECT *", "FROM users", EOFError]
    result = query_input_prompt(None)
    assert "SELECT *" in result
    assert "FROM users" in result


# ═══════════════════════════════════════════════════════════════
# INTERACTIVE PROFILE CONFIG TESTS
# ═══════════════════════════════════════════════════════════════


def test_interactive_profile_config_full_args() -> None:
    """Test profile config with all args provided (non-interactive)."""
    config = interactive_profile_config(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="mydb",
        username="postgres",
        password="secret",
    )

    assert config.engine == "postgresql"
    assert config.host == "localhost"
    assert config.port == 5432
    assert config.database == "mydb"
    assert config.username == "postgres"
    assert config.password == "secret"


@patch("query_analyzer.cli.prompts.password_prompt", return_value="pwd123")
@patch("query_analyzer.cli.prompts.username_prompt", return_value="user123")
@patch("query_analyzer.cli.prompts.database_prompt", return_value="db123")
@patch("query_analyzer.cli.prompts.port_prompt_with_validation", return_value=5432)
@patch("query_analyzer.cli.prompts.host_prompt", return_value="host123")
@patch("query_analyzer.cli.prompts.engine_selector", return_value="postgresql")
def test_interactive_profile_config_all_prompts(
    mock_engine: MagicMock,
    mock_host: MagicMock,
    mock_port: MagicMock,
    mock_db: MagicMock,
    mock_user: MagicMock,
    mock_pwd: MagicMock,
) -> None:
    """Test profile config with no args (all interactive)."""
    config = interactive_profile_config()

    assert config.engine == "postgresql"
    assert config.host == "host123"
    assert config.port == 5432
    assert config.database == "db123"
    assert config.username == "user123"
    assert config.password == "pwd123"

    # All prompts should be called
    mock_engine.assert_called_once()
    mock_host.assert_called_once()
    mock_port.assert_called_once()
    mock_db.assert_called_once()
    mock_user.assert_called_once()
    mock_pwd.assert_called_once()
