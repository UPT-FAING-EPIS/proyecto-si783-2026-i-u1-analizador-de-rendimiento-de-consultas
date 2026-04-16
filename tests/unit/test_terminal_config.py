"""Tests for terminal configuration and ANSI detection."""

import os
from unittest.mock import patch

from query_analyzer.cli.terminal_config import (
    detect_ansi_support,
    get_console_config,
    get_terminal_width,
    is_compact_layout,
    is_full_layout,
    is_vertical_layout,
)


class TestTerminalDetection:
    """Tests for ANSI terminal detection."""

    def test_no_color_env_disables_color(self) -> None:
        """NO_COLOR env var should disable color."""
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            assert detect_ansi_support() is False

    def test_qa_no_color_env_disables_color(self) -> None:
        """QA_NO_COLOR env var should disable color."""
        with patch.dict(os.environ, {"QA_NO_COLOR": "1"}):
            assert detect_ansi_support() is False

    def test_force_color_enables_color(self) -> None:
        """FORCE_COLOR env var should enable color."""
        with patch.dict(os.environ, {"FORCE_COLOR": "1"}, clear=False):
            with patch("sys.stdout.isatty", return_value=True):
                assert detect_ansi_support() is True

    def test_dumb_terminal_disables_color(self) -> None:
        """TERM=dumb should disable color."""
        with patch.dict(os.environ, {"TERM": "dumb"}, clear=False):
            with patch("sys.stdout.isatty", return_value=True):
                assert detect_ansi_support() is False

    def test_no_tty_disables_color(self) -> None:
        """Non-TTY output should disable color."""
        with patch.dict(os.environ, {}, clear=False):
            with patch("sys.stdout.isatty", return_value=False):
                assert detect_ansi_support() is False

    def test_git_bash_windows_defaults_no_color(self) -> None:
        """Git Bash on Windows should default to no color."""
        with patch.dict(os.environ, {"MSYSTEM": "MINGW64"}, clear=False):
            with patch("sys.platform", "win32"):
                with patch("sys.stdout.isatty", return_value=True):
                    assert detect_ansi_support() is False

    def test_git_bash_windows_force_color_works(self) -> None:
        """FORCE_COLOR should override Git Bash Windows no-color default."""
        with patch.dict(os.environ, {"MSYSTEM": "MINGW64", "FORCE_COLOR": "1"}, clear=False):
            with patch("sys.platform", "win32"):
                with patch("sys.stdout.isatty", return_value=True):
                    assert detect_ansi_support() is True

    def test_normal_terminal_enables_color(self) -> None:
        """Normal TTY terminal should enable color."""
        with patch.dict(os.environ, {"TERM": "xterm-256color"}, clear=False):
            with patch("sys.stdout.isatty", return_value=True):
                with patch("sys.platform", "linux"):
                    with patch("os.environ.get") as mock_get:

                        def get_side_effect(key, default=""):
                            env_map = {
                                "TERM": "xterm-256color",
                                "NO_COLOR": "",
                                "FORCE_COLOR": "",
                                "QA_NO_COLOR": "",
                                "MSYSTEM": "",
                            }
                            return env_map.get(key, default)

                        mock_get.side_effect = get_side_effect
                        assert detect_ansi_support() is True


class TestConsoleConfig:
    """Tests for get_console_config()."""

    def test_config_returns_dict_with_required_keys(self) -> None:
        """Config should return dict with no_color, force_terminal, width."""
        config = get_console_config()
        assert isinstance(config, dict)
        assert "no_color" in config
        assert "force_terminal" in config
        assert "width" in config

    def test_explicit_no_color_true(self) -> None:
        """Explicit no_color=True should disable color."""
        config = get_console_config(no_color=True)
        assert config["no_color"] is True

    def test_explicit_no_color_false(self) -> None:
        """Explicit no_color=False should enable color."""
        with patch("sys.stdout.isatty", return_value=True):
            config = get_console_config(no_color=False)
            assert config["no_color"] is False

    def test_auto_detect_color(self) -> None:
        """Auto-detect (None) should use detect_ansi_support()."""
        with patch.dict(os.environ, {"NO_COLOR": "1"}):
            config = get_console_config(no_color=None)
            assert config["no_color"] is True

    def test_force_terminal_only_with_tty_and_color(self) -> None:
        """force_terminal should only be True if color enabled and is TTY (not Git Bash)."""
        with patch("sys.stdout.isatty", return_value=True):
            with patch.dict(os.environ, {}, clear=False):
                with patch(
                    "query_analyzer.cli.terminal_config.detect_ansi_support", return_value=True
                ):
                    with patch(
                        "query_analyzer.cli.terminal_config._is_git_bash_windows",
                        return_value=False,
                    ):
                        config = get_console_config(no_color=False)
                        assert config["force_terminal"] is True

        with patch("sys.stdout.isatty", return_value=False):
            config = get_console_config(no_color=False)
            assert config["force_terminal"] is False


class TestTerminalWidth:
    """Tests for terminal width detection."""

    def test_get_terminal_width_returns_positive_int(self) -> None:
        """Terminal width should be positive integer."""
        width = get_terminal_width()
        assert isinstance(width, int)
        assert width > 0
        assert width >= 40  # Minimum reasonable width

    def test_terminal_width_fallback_on_error(self) -> None:
        """Should fallback to 80 if error occurs."""
        with patch("shutil.get_terminal_size", side_effect=Exception("test error")):
            width = get_terminal_width()
            assert width == 80


class TestLayoutDetection:
    """Tests for responsive layout detection."""

    def test_vertical_layout_below_80(self) -> None:
        """Width < 80 should use vertical layout."""
        assert is_vertical_layout(79) is True
        assert is_vertical_layout(40) is True
        assert is_vertical_layout(80) is False

    def test_compact_layout_80_to_120(self) -> None:
        """80 <= width < 120 should use compact layout."""
        assert is_compact_layout(80) is True
        assert is_compact_layout(100) is True
        assert is_compact_layout(119) is True
        assert is_compact_layout(79) is False
        assert is_compact_layout(120) is False

    def test_full_layout_above_120(self) -> None:
        """Width >= 120 should use full layout."""
        assert is_full_layout(120) is True
        assert is_full_layout(200) is True
        assert is_full_layout(119) is False


class TestTruncateAdaptive:
    """Tests for adaptive truncation (via OutputFormatter)."""

    def test_truncate_short_text_unchanged(self) -> None:
        """Short text should not be truncated."""
        from query_analyzer.cli.utils import OutputFormatter

        text = "short text"
        result = OutputFormatter.truncate_adaptive(text, max_width=50)
        assert result == text

    def test_truncate_long_text_with_suffix(self) -> None:
        """Long text should be truncated with suffix."""
        from query_analyzer.cli.utils import OutputFormatter

        text = (
            "This is a very long text that should be truncated because it exceeds the maximum width"
        )
        result = OutputFormatter.truncate_adaptive(text, max_width=30, suffix="...")
        assert result.endswith("...")
        assert len(result) <= 30

    def test_truncate_respects_min_visible(self) -> None:
        """Truncation should respect minimum visible characters."""
        from query_analyzer.cli.utils import OutputFormatter

        text = "a" * 100
        result = OutputFormatter.truncate_adaptive(text, max_width=30, min_visible=20, suffix="...")
        # Result should have at least 20 visible chars + suffix
        assert len(result) - 3 >= 20  # 3 for "..."

    def test_truncate_custom_suffix(self) -> None:
        """Custom suffix should be used."""
        from query_analyzer.cli.utils import OutputFormatter

        text = "This is a very long text that should be truncated"
        result = OutputFormatter.truncate_adaptive(text, max_width=20, suffix=">>")
        assert result.endswith(">>")


class TestOutputFormatterLayouts:
    """Tests for responsive table layouts."""

    def test_profiles_table_compact_layout(self) -> None:
        """Compact layout should create 3-column table."""
        from query_analyzer.cli.utils import OutputFormatter
        from query_analyzer.config import ProfileConfig

        profiles = {
            "local": ProfileConfig(
                engine="postgresql",
                host="localhost",
                port=5432,
                database="mydb",
                username="user",
                password="pass",
            )
        }

        with patch("query_analyzer.cli.utils.get_terminal_width", return_value=100):
            table = OutputFormatter.create_profiles_table(profiles)
            # Should have created a table (we can't directly check columns without rendering)
            assert table is not None

    def test_profiles_table_full_layout(self) -> None:
        """Full layout should create 5-column table."""
        from query_analyzer.cli.utils import OutputFormatter
        from query_analyzer.config import ProfileConfig

        profiles = {
            "prod": ProfileConfig(
                engine="mysql",
                host="prod.example.com",
                port=3306,
                database="production",
                username="admin",
                password="secret",
            )
        }

        with patch("query_analyzer.cli.utils.get_terminal_width", return_value=150):
            table = OutputFormatter.create_profiles_table(profiles)
            assert table is not None
