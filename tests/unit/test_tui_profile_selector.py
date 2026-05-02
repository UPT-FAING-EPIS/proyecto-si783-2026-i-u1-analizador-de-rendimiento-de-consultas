"""Unit tests for TUI profile selector widget."""

from unittest.mock import MagicMock

from query_analyzer.tui.connection_state import ConnectionStatus
from query_analyzer.tui.widgets.profile_selector import ProfileSelector


class _FakeConnectionManager:
    default_profile_name = None

    def list_profiles(self) -> dict[str, object]:
        return {}

    def status_for_profile(self, profile_name: str) -> ConnectionStatus | None:
        return ConnectionStatus.DISCONNECTED


def test_profile_selector_empty_state_row_matches_columns(monkeypatch) -> None:
    """Empty profile list should render a row with the same number of columns."""
    fake_manager = _FakeConnectionManager()
    monkeypatch.setattr(
        "query_analyzer.tui.widgets.profile_selector.ConnectionManager.get",
        lambda: fake_manager,
    )

    selector = ProfileSelector()
    table = MagicMock()
    monkeypatch.setattr(selector, "query_one", lambda *_args, **_kwargs: table)

    selector._refresh_profile_list()

    assert table.add_column.call_count == 4
    table.add_row.assert_called_once_with("-", "No hay perfiles", "", "desconectado")
    table.clear.assert_called_once_with(columns=False)
