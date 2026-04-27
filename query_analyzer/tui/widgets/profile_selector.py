"""Profile selector widget for TUI.

Displays a table of connection profiles and status.
"""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.widgets import Button, DataTable, Label

from query_analyzer.tui.connection_state import ConnectionManager, ConnectionStatus


class ProfileAction(Message):
    """Sent when a profile action is triggered."""

    def __init__(self, action: str, profile_name: str | None = None) -> None:
        self.action = action
        self.profile_name = profile_name
        super().__init__()


class ProfileSelector(Container):
    """Widget para seleccionar perfiles de conexión en tabla."""

    DEFAULT_CSS = """
    ProfileSelector {
        height: auto;
        width: 100%;
        background: $surface;
        border: solid $primary;
        padding: 1;
    }

    ProfileSelector > Label {
        text-style: bold;
        margin-bottom: 1;
    }

    ProfileSelector DataTable {
        height: 10;
        width: 1fr;
        background: $panel;
        margin-bottom: 1;
        border: solid $surface-lighten-1;
    }

    ProfileSelector .actions {
        height: auto;
    }

    ProfileSelector Button {
        margin-right: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__(id="profile-selector")
        self._manager = ConnectionManager.get()
        self._selected_profile: str | None = None
        self._columns_initialized = False

    def compose(self) -> ComposeResult:
        yield Label("Perfil de conexión")
        yield DataTable(id="profile-table")
        with Horizontal(classes="actions"):
            yield Button("+ Agregar", variant="primary", id="btn-add")
            yield Button("✏ Editar", variant="default", id="btn-edit")
            yield Button("✕ Eliminar", variant="default", id="btn-delete")
            yield Button("▶ Analizar", variant="success", id="btn-analyze")

    def on_mount(self) -> None:
        table = self.query_one("#profile-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        self._refresh_profile_list()

    def _refresh_profile_list(self) -> None:
        profiles = self._manager.list_profiles()
        default_name = self._manager.default_profile_name
        table = self.query_one("#profile-table", DataTable)

        if not self._columns_initialized:
            table.add_column("Perfil", width=20)
            table.add_column("Engine", width=12)
            table.add_column("Host:Port", width=22)
            table.add_column("Estado", width=14)
            self._columns_initialized = True

        table.clear(columns=False)

        if not profiles:
            self._selected_profile = None
            table.add_row("-", "No hay perfiles", "", "", "desconectado")
            return

        selected_name = self._selected_profile or default_name or next(iter(profiles))
        selected_row_index = 0

        for idx, (name, profile) in enumerate(profiles.items()):
            status = self._format_status(self._manager.status_for_profile(name))
            endpoint = f"{profile.host or 'local'}:{profile.port or '-'}"

            table.add_row(
                self._truncate(name, 20),
                profile.engine.upper(),
                self._truncate(endpoint, 22),
                status,
                key=name,
            )

            if name == selected_name:
                selected_row_index = idx

        table.move_cursor(row=selected_row_index, column=0)
        self._selected_profile = selected_name

    def _format_status(self, status: ConnectionStatus | None) -> str:
        if status is None or status == ConnectionStatus.DISCONNECTED:
            return "desconectado"
        if status == ConnectionStatus.CONNECTING:
            return "conectando..."
        if status == ConnectionStatus.CONNECTED:
            return "conectado"
        if status == ConnectionStatus.ERROR:
            return "error"
        return "desconectado"

    def _truncate(self, text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        if max_len <= 1:
            return text[:max_len]
        return f"{text[: max_len - 1]}…"

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key is None:
            return
        self._selected_profile = str(event.row_key.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "btn-add":
            self.post_message(ProfileAction("add"))
        elif button_id == "btn-edit":
            if self._selected_profile:
                self.post_message(ProfileAction("edit", self._selected_profile))
        elif button_id == "btn-delete":
            if self._selected_profile:
                self.post_message(ProfileAction("delete", self._selected_profile))
        elif button_id == "btn-analyze":
            if self._selected_profile:
                self.post_message(ProfileAction("analyze", self._selected_profile))

    @property
    def selected_profile(self) -> str | None:
        return self._selected_profile

    def get_connection_status(self) -> ConnectionStatus:
        return self._manager.status

    def get_error_message(self) -> str | None:
        return self._manager.error_message

    def reload_profiles(self) -> None:
        self._refresh_profile_list()
