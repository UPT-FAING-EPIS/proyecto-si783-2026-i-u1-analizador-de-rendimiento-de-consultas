"""Interactive analysis screen for query execution and visualization."""

from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from query_analyzer.adapters import QueryAnalysisError
from query_analyzer.adapters.models import QueryAnalysisReport
from query_analyzer.tui.connection_state import ConnectionManager
from query_analyzer.tui.widgets.analysis_result import RecommendationsPanel, WarningsPanel
from query_analyzer.tui.widgets.query_editor import QueryEditor


class AnalysisScreen(Screen[None]):
    """Screen that allows writing queries and visualizing analysis."""

    BINDINGS = [
        ("escape", "go_back", "Volver"),
        ("tab", "focus_next", "Siguiente"),
        ("q", "quit", "Salir"),
    ]

    def action_focus_next(self) -> None:
        """Move focus to next focusable widget."""
        self.screen.focus_next()

    def action_quit(self) -> None:
        """Exit the application."""
        self.app.exit()

    DEFAULT_CSS = """
    AnalysisScreen {
        background: $background;
    }

    AnalysisScreen #analysis-root {
        layout: vertical;
        height: 1fr;
        width: 1fr;
        padding: 0 1;
    }

    AnalysisScreen #context-label {
        width: 100%;
        height: auto;
        content-align: center middle;
        text-style: bold;
        color: $text-muted;
        margin-bottom: 1;
    }

    AnalysisScreen #workspace {
        layout: horizontal;
        height: 1fr;
        min-height: 20;
    }

    AnalysisScreen #main-column {
        width: 3fr;
        height: 1fr;
        margin-right: 1;
    }

    AnalysisScreen #side-column {
        width: 2fr;
        height: 1fr;
    }

    AnalysisScreen .actions-row {
        height: auto;
        margin-top: 1;
        margin-bottom: 1;
        align: left top;
    }

    AnalysisScreen #btn-analyze {
        width: 10;
        margin-right: 2;
    }

    AnalysisScreen #metrics-column {
        width: 1fr;
        height: auto;
        margin-left: 1;
    }

    AnalysisScreen #metrics-line {
        width: 100%;
        text-align: left;
        margin-bottom: 1;
    }

    AnalysisScreen #run-status {
        width: 100%;
        text-align: left;
        margin-top: 0;
    }

    AnalysisScreen #main-column WarningsPanel {
        height: 1fr;
        min-height: 12;
    }

    AnalysisScreen #side-column RecommendationsPanel {
        height: 1fr;
        min-height: 12;
    }
    """

    def __init__(self, profile_name: str) -> None:
        super().__init__()
        self._manager = ConnectionManager.get()
        self._profile_name = profile_name
        self._engine = self._get_engine_from_profile(profile_name)

    @staticmethod
    def _get_engine_from_profile(profile_name: str) -> str:
        try:
            manager = ConnectionManager.get()
            return manager.get_profile(profile_name).engine
        except Exception:
            return "-"

    def _update_engine_label(self) -> None:
        self._engine = self._get_engine_from_profile(self._profile_name)
        context = self.query_one("#context-label", Static)
        context.update(f"[ Perfil: {self._profile_name} | Motor: {self._engine.upper()} ]")

    def compose(self) -> ComposeResult:
        context_text = f"[ Perfil: {self._profile_name} | Motor: {self._engine.upper()} ]"
        with Vertical(id="analysis-root"):
            yield Static(context_text, id="context-label")

            with Horizontal(id="workspace"):
                with Vertical(id="main-column"):
                    yield QueryEditor(language="sql")
                    yield WarningsPanel()

                with Vertical(id="side-column"):
                    with Horizontal(classes="actions-row"):
                        yield Button("Analizar", variant="primary", id="btn-analyze")
                        with Vertical(id="metrics-column"):
                            yield Static("Score: --/100  Tiempo: -- ms", id="metrics-line")
                            yield Static("Estado: listo", id="run-status")

                    yield RecommendationsPanel()

        yield Footer()

    def on_mount(self) -> None:
        self._update_engine_label()
        self.query_one(QueryEditor).focus_editor()
        self._connect_profile_if_needed()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-back")
    def on_back_pressed(self) -> None:
        self.action_go_back()

    @on(Button.Pressed, "#btn-analyze")
    def on_analyze_pressed(self) -> None:
        self._trigger_analysis(self.query_one(QueryEditor).query_text)

    def _connect_profile_if_needed(self) -> None:
        try:
            profile = self._manager.get_profile(self._profile_name)
            engine = profile.engine
        except Exception:
            engine = "-"

        if (
            self._manager.last_profile_name == self._profile_name
            and self._manager.active_adapter is not None
        ):
            current_adapter_engine = getattr(self._manager.active_adapter, "_config", None)
            if current_adapter_engine:
                current_engine = getattr(current_adapter_engine, "engine", None)
                if current_engine == engine:
                    return

        try:
            self._manager.connect(self._profile_name)
            self._engine = self._manager.get_profile(self._profile_name).engine
            context = self.query_one("#context-label", Static)
            context.update(f"[ Perfil: {self._profile_name} | Motor: {self._engine.upper()} ]")
        except Exception as error:
            self.query_one(WarningsPanel).set_error(str(error))
            self.query_one(RecommendationsPanel).set_error()

    def _trigger_analysis(self, query: str) -> None:
        text = query.strip()
        if not text:
            self.query_one("#run-status", Static).update("[red]Estado: query vacía[/red]")
            self.query_one(WarningsPanel).set_error("La query no puede estar vacía")
            return

        self.query_one(QueryEditor).set_busy(True)
        self.query_one("#btn-analyze", Button).disabled = True
        self.query_one("#metrics-line", Static).update("Score: --/100  Tiempo: -- ms")
        self.query_one("#run-status", Static).update("[yellow]Estado: analizando...[/yellow]")
        self.query_one(WarningsPanel).set_running()
        self.query_one(WarningsPanel).set_loading(True)
        self.query_one(RecommendationsPanel).set_running()
        self.query_one(RecommendationsPanel).set_loading(True)
        self.run_analysis_worker(text)

    @work(exclusive=True, thread=True)
    def run_analysis_worker(self, query_text: str) -> None:
        try:
            adapter = self._manager.active_adapter
            if adapter is None:
                self._manager.connect(self._profile_name)
                adapter = self._manager.active_adapter

            if adapter is None:
                raise QueryAnalysisError("No se pudo inicializar un adapter activo")

            report = adapter.execute_explain(query_text)
            self.app.call_from_thread(self._on_analysis_success, query_text, report)
        except Exception as error:
            self.app.call_from_thread(self._on_analysis_error, str(error))

    def _on_analysis_success(self, query_text: str, report: QueryAnalysisReport) -> None:
        warnings_panel = self.query_one(WarningsPanel)
        recommendations_panel = self.query_one(RecommendationsPanel)
        warnings_panel.set_loading(False)
        recommendations_panel.set_loading(False)
        warnings_panel.render_warnings(report.warnings)
        recommendations_panel.render_recommendations(report.recommendations)
        self.query_one(QueryEditor).set_busy(False)
        self.query_one("#btn-analyze", Button).disabled = False
        self.query_one("#metrics-line", Static).update(
            f"{self._score_markup(report.score)}  Tiempo: {report.execution_time_ms:.2f} ms"
        )
        self.query_one("#run-status", Static).update("[green]Estado: completado[/green]")

    def _on_analysis_error(self, error_message: str) -> None:
        warnings_panel = self.query_one(WarningsPanel)
        recommendations_panel = self.query_one(RecommendationsPanel)
        warnings_panel.set_loading(False)
        recommendations_panel.set_loading(False)
        warnings_panel.set_error(error_message)
        recommendations_panel.set_error()
        self.query_one(QueryEditor).set_busy(False)
        self.query_one("#btn-analyze", Button).disabled = False
        self.query_one("#run-status", Static).update("[red]Estado: error[/red]")

    def _score_markup(self, score: int) -> str:
        if score < 50:
            color = "red"
        elif score < 80:
            color = "yellow"
        else:
            color = "green"
        return f"Score: [{color}]{score}/100[/{color}]"
