"""Connection form screen for adding/editing profiles.

Display a form for entering connection profile details.
"""

from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from query_analyzer.config import ProfileConfig
from query_analyzer.tui.connection_state import ConnectionManager

ENGINE_OPTIONS = [
    ("PostgreSQL", "postgresql"),
    ("MySQL", "mysql"),
    ("SQLite", "sqlite"),
    ("MongoDB", "mongodb"),
    ("Redis", "redis"),
    ("CockroachDB", "cockroachdb"),
    ("YugabyteDB", "yugabytedb"),
    ("Neo4j", "neo4j"),
    ("InfluxDB", "influxdb"),
    ("Elasticsearch", "elasticsearch"),
]

DEFAULT_PORTS = {
    "postgresql": 5432,
    "mysql": 3306,
    "sqlite": 0,
    "mongodb": 27017,
    "redis": 6379,
    "cockroachdb": 26257,
    "yugabytedb": 5433,
    "neo4j": 7687,
    "influxdb": 8086,
    "elasticsearch": 9200,
}


class ConnectionForm(ModalScreen[bool]):
    """Screen para agregar o editar un perfil de conexión."""

    DEFAULT_CSS = """
    ConnectionForm {
        align: center middle;
    }

    ConnectionForm > Container {
        width: 50;
        height: auto;
        border: solid $primary;
        padding: 1 2;
    }

    ConnectionForm .form-title {
        text-style: bold;
        margin-bottom: 1;
    }

    ConnectionForm .form-field {
        margin-bottom: 1;
    }

    ConnectionForm .form-field > Label {
        width: 16;
    }

    ConnectionForm Input, ConnectionForm Select {
        width: 1fr;
    }

    ConnectionForm .form-actions {
        height: auto;
        margin-top: 1;
    }

    ConnectionForm .error-message {
        color: $error;
        display: none;
    }

    ConnectionForm .error-message.visible {
        display: block;
    }
    """

    def __init__(
        self,
        edit_profile_name: str | None = None,
        on_save: Callable[[bool], None] | None = None,
    ) -> None:
        super().__init__()
        self._edit_profile_name = edit_profile_name
        self._on_save_callback = on_save
        self._manager = ConnectionManager.get()
        self._error: str | None = None

    def compose(self) -> ComposeResult:
        title_text = "Editar perfil" if self._edit_profile_name else "Agregar conexión"
        with Container(classes="form-container"):
            yield Static(title_text, classes="form-title")
            with Vertical(classes="form-fields"):
                with Horizontal(classes="form-field"):
                    yield Label("Nombre:")
                    yield Input(placeholder="mi-perfil", id="input-name")

                with Horizontal(classes="form-field"):
                    yield Label("Engine:")
                    yield Select(ENGINE_OPTIONS, id="input-engine")

                with Horizontal(classes="form-field"):
                    yield Label("Host:")
                    yield Input(placeholder="localhost", id="input-host")

                with Horizontal(classes="form-field"):
                    yield Label("Puerto:")
                    yield Input(placeholder="5432", id="input-port")

                with Horizontal(classes="form-field"):
                    yield Label("Database:")
                    yield Input(placeholder="mydb", id="input-database")

                with Horizontal(classes="form-field"):
                    yield Label("Usuario:")
                    yield Input(placeholder="postgres", id="input-username")

                with Horizontal(classes="form-field"):
                    yield Label("Password:")
                    yield Input(placeholder="******", id="input-password", password=True)

            yield Static("", classes="error-message", id="error-display")

            with Horizontal(classes="form-actions"):
                yield Button("Cancelar", variant="default", id="btn-cancel")
                yield Button("Guardar", variant="primary", id="btn-save")

    def on_mount(self) -> None:
        if self._edit_profile_name:
            self._populate_form(self._edit_profile_name)

    def _populate_form(self, profile_name: str) -> None:
        profile = self._manager.get_profile(profile_name)

        self.query_one("#input-name", Input).value = profile_name
        self.query_one("#input-name", Input).disabled = True
        engine_select = self.query_one("#input-engine", Select)
        engine_values = {value for _, value in ENGINE_OPTIONS}
        if profile.engine in engine_values:
            engine_select.value = profile.engine
        else:
            engine_select.clear()
        self.query_one("#input-host", Input).value = profile.host or ""
        self.query_one("#input-port", Input).value = str(profile.port) if profile.port else ""
        self.query_one("#input-database", Input).value = profile.database
        self.query_one("#input-username", Input).value = profile.username or ""
        self.query_one("#input-password", Input).value = profile.password or ""

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "input-engine":
            engine = str(event.value)
            if engine in DEFAULT_PORTS:
                port_input = self.query_one("#input-port", Input)
                if not port_input.value:
                    port_input.value = str(DEFAULT_PORTS.get(engine, ""))

    def on_input_changed(self, event: Input.Changed) -> None:
        """Restringe el campo de puerto a dígitos."""
        if event.input.id != "input-port":
            return

        digits_only = "".join(ch for ch in event.value if ch.isdigit())
        if digits_only != event.value:
            event.input.value = digits_only

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(False)
        elif event.button.id == "btn-save":
            self._save_profile()

    def _save_profile(self) -> None:
        name = self.query_one("#input-name", Input).value.strip()
        select_engine = self.query_one("#input-engine", Select)
        engine = str(select_engine.value) if select_engine.value else ""
        host = self.query_one("#input-host", Input).value.strip() or None
        port_str = self.query_one("#input-port", Input).value.strip()
        if port_str and not port_str.isdigit():
            self._show_error("El puerto debe contener solo números")
            return
        port = int(port_str) if port_str else None
        database = self.query_one("#input-database", Input).value.strip()
        username = self.query_one("#input-username", Input).value.strip() or None
        password = self.query_one("#input-password", Input).value or None

        if not name:
            self._show_error("El nombre es requerido")
            return
        if not engine:
            self._show_error("El engine es requerido")
            return
        if not database:
            self._show_error("La base de datos es requerida")
            return
        if not self._edit_profile_name and name in self._manager.list_profiles():
            self._show_error(f"El perfil '{name}' ya existe")
            return

        try:
            profile = ProfileConfig(
                engine=engine,
                host=host,
                port=port,
                database=database,
                username=username,
                password=password,
            )

            if self._edit_profile_name:
                self._manager.update_profile(name, profile)
            else:
                self._manager.add_profile(name, profile)

            if self._on_save_callback:
                self._on_save_callback(True)

            self.dismiss(True)

        except Exception as e:
            self._show_error(str(e))

    def _show_error(self, message: str) -> None:
        self._error = message
        error_display = self.query_one("#error-display", Static)
        error_display.update(message)
        error_display.add_class("visible")
