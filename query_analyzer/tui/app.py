"""Query Analyzer TUI - Main App.

Textual-based terminal interface for connection profile management.
"""

from collections.abc import Callable
from threading import Thread

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Static

from query_analyzer.tui.connection_state import ConnectionManager, ConnectionStatus
from query_analyzer.tui.widgets.connection_form import ConnectionForm
from query_analyzer.tui.widgets.profile_selector import ProfileAction, ProfileSelector


class StatusBar(Static):
    """Barra de estado inferior."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        background: $surface-darken-1;
        content-align: center middle;
    }
    """

    def __init__(self) -> None:
        super().__init__("", id="status-bar")
        self._manager = ConnectionManager.get()

    def update_status(self) -> None:
        status = self._manager.status

        if status == ConnectionStatus.CONNECTED:
            msg = f"✓ Conectado ({self._manager.last_profile_name})"
        elif status == ConnectionStatus.CONNECTING:
            msg = "Conectando..."
        elif status == ConnectionStatus.ERROR:
            msg = f"✗ Error: {self._manager.error_message or 'Desconocido'}"
        else:
            msg = "Sin conectar"

        self.update(msg)


class DeleteConfirm(ModalScreen[bool]):
    """Pantalla de confirmación de eliminación."""

    DEFAULT_CSS = """
    DeleteConfirm {
        align: center middle;
    }

    DeleteConfirm > Container {
        width: 40;
        height: auto;
        border: solid $error;
        padding: 1 2;
    }

    DeleteConfirm .message {
        margin-bottom: 2;
    }

    DeleteConfirm .buttons {
        height: auto;
    }
    """

    def __init__(self, profile_name: str, on_confirm: Callable[[], None]) -> None:
        super().__init__()
        self._profile_name = profile_name
        self._on_confirm = on_confirm

    def compose(self) -> ComposeResult:
        with Container(classes="confirm-container"):
            yield Static(
                f"¿Eliminar perfil '{self._profile_name}'?",
                classes="message",
            )
            with Container(classes="buttons"):
                yield Button("Cancelar", variant="default", id="btn-cancel")
                yield Button("Eliminar", variant="error", id="btn-confirm")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(False)
        elif event.button.id == "btn-confirm":
            self._on_confirm()
            self.dismiss(True)


class ConnectionScreen(Container):
    """Pantalla principal de selección de perfiles."""

    def __init__(self) -> None:
        super().__init__(id="connection-screen")
        self._manager = ConnectionManager.get()

    def compose(self) -> ComposeResult:
        yield ProfileSelector()
        yield StatusBar()

    def on_mount(self) -> None:
        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.update_status()
        self._start_initial_probe()

    def on_profile_action(self, event: ProfileAction) -> None:
        action = event.action
        profile_name = event.profile_name

        if action == "add":
            self.app.push_screen(ConnectionForm(), self._on_form_return)
        elif action == "edit" and profile_name:
            self.app.push_screen(
                ConnectionForm(edit_profile_name=profile_name), self._on_form_return
            )
        elif action == "delete" and profile_name:
            self._delete_profile(profile_name)

    def _on_form_return(self, saved: bool | None) -> None:
        if saved:
            selector = self.query_one(ProfileSelector)
            selector.reload_profiles()
            status_bar = self.query_one("#status-bar", StatusBar)
            status_bar.update_status()

    def _delete_profile(self, name: str) -> None:
        def on_confirm() -> None:
            self._manager.delete_profile(name)
            selector = self.query_one(ProfileSelector)
            selector.reload_profiles()
            status_bar = self.query_one("#status-bar", StatusBar)
            status_bar.update_status()

        self.app.push_screen(DeleteConfirm(name, on_confirm))

    def _start_initial_probe(self) -> None:
        probe_thread = Thread(target=self._probe_all_profiles_background, daemon=True)
        probe_thread.start()

    def _probe_all_profiles_background(self) -> None:
        profiles = self._manager.list_profiles()
        for name in profiles:
            self._manager.mark_connecting(name)
            self.app.call_from_thread(self._refresh_ui_status)
            self._manager.probe_profile(name)
            self.app.call_from_thread(self._refresh_ui_status)

    def _refresh_ui_status(self) -> None:
        selector = self.query_one(ProfileSelector)
        selector.reload_profiles()
        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.update_status()


class QueryAnalyzerApp(App):
    """App principal de Query Analyzer TUI."""

    TITLE = "Query Analyzer"
    SUB_TITLE = "Gestión de conexiones"
    CSS_PATH = None

    DEFAULT_CSS = """
    Screen {
        background: $background;
    }

    #connection-screen {
        align: center middle;
    }

    #connection-screen > ProfileSelector {
        width: 1fr;
        max-width: 120;
        height: auto;
        background: $surface;
    }

    #main-title {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        background: $primary;
        color: $text;
        padding: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Salir"),
        ("c", "app.pop_screen", "Cancelar"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._manager = ConnectionManager.get()

    def compose(self) -> ComposeResult:
        yield Header()
        yield ConnectionScreen()
        yield Footer()

    def on_mount(self) -> None:
        pass


def run() -> None:
    """Entry point para ejecutar la TUI."""
    app = QueryAnalyzerApp()
    app.run()


if __name__ == "__main__":
    run()
