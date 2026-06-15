"""Interactive analysis screen for query execution and visualization - v2.1.0."""

from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid, Horizontal, Vertical
from textual.markup import escape as markup_escape
from textual.screen import Screen
from textual.widgets import Button, Footer, Static, TabbedContent, TabPane

from query_analyzer.adapters import QueryAnalysisError
from query_analyzer.adapters.models import AIAnalysisResult, QueryAnalysisReport
from query_analyzer.cli.commands.analyze import validate_query
from query_analyzer.tui.connection_state import ConnectionManager
from query_analyzer.tui.history_manager import AnalysisRecord, get_history_manager
from query_analyzer.tui.screens.history_screen import HistoryScreen
from query_analyzer.tui.widgets import (
    AIInsightsPanel,
    MetricsPanel,
    PlanTreeWidget,
    QuerySummary,
)
from query_analyzer.tui.widgets.export_dialog import ExportDialog
from query_analyzer.tui.widgets.query_editor import QueryEditor


class AnalysisScreen(Screen[None]):
    """Analysis screen with 45/55 split layout.

    Layout:
        - Top: Context label (profile + engine)
        - Main area (horizontal split):
          - Left (45%): Query editor + buttons
          - Right (55%): Tabbed interface (Summary, Metrics, Plan, AI)
    """

    BINDINGS = [
        Binding("1", "select_tab_summary", "Res", priority=True),
        Binding("2", "select_tab_metrics", "Met", priority=True),
        Binding("3", "select_tab_plan", "Plan", priority=True),
        Binding("4", "select_tab_ai", "IA", priority=True),
        Binding("b", "focus_buttons", "Botones", priority=True),
        Binding("a", "button_left", "Btn←", priority=True),
        Binding("d", "button_right", "Btn→", priority=True),
        Binding("w", "button_up", "Btn↑", priority=True),
        Binding("s", "button_down", "Btn↓", priority=True),
        Binding("left", "button_left", "Btn←"),
        Binding("right", "button_right", "Btn→"),
        Binding("up", "button_up", "Btn↑"),
        Binding("down", "button_down", "Btn↓"),
        Binding("h,ctrl+left", "previous_tab", "Ctrl+←:Ant", priority=True),
        Binding("l,ctrl+right", "next_tab", "Ctrl+→:Sig", priority=True),
        Binding("H", "show_history", "Hist", priority=True),
        Binding("c", "copy_query", "Copiar Q", priority=True),
        Binding("e", "focus_editor", "Edic", priority=True),
        Binding("x", "export", "Export", priority=True),
        Binding("escape", "go_back", "Atrás"),
        Binding("q", "quit", show=False),
    ]

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
        min-height: 15;
    }

    AnalysisScreen #editor-column {
        width: 45%;
        height: 1fr;
        margin-right: 1;
    }

    AnalysisScreen #editor-column QueryEditor {
        height: 1fr;
        min-height: 6;
        margin-bottom: 1;
    }

    AnalysisScreen #actions-grid {
        layout: grid;
        grid-size: 2 2;
        grid-columns: 1fr 1fr;
        grid-rows: 3 3;
        grid-gutter: 1 0;
        height: auto;
        min-height: 7;
        width: 100%;
        margin-bottom: 1;
    }

    AnalysisScreen #actions-grid Button {
        width: 1fr;
        height: 3;
        padding: 0 1;
    }

    AnalysisScreen #status-container {
        height: auto;
        margin-bottom: 1;
    }

    AnalysisScreen #run-status {
        width: 100%;
        text-align: left;
        height: auto;
    }

    AnalysisScreen #details-tabbed {
        width: 55%;
        height: 1fr;
        border: solid $accent;
    }

    AnalysisScreen TabPane {
        padding: 1;
        overflow-y: auto;
        scrollbar-size-vertical: 0;
    }

    AnalysisScreen TabPane:focus {
        scrollbar-size-vertical: 1;
    }

    AnalysisScreen QuerySummary {
        height: auto;
    }

    AnalysisScreen MetricsPanel {
        height: auto;
    }

    AnalysisScreen PlanTreeWidget {
        height: auto;
        overflow-y: auto;
        scrollbar-size-vertical: 0;
    }

    AnalysisScreen PlanTreeWidget:focus {
        scrollbar-size-vertical: 1;
    }

    AnalysisScreen AIInsightsPanel {
        height: auto;
        overflow-y: auto;
        scrollbar-size-vertical: 0;
    }

    AnalysisScreen AIInsightsPanel:focus {
        scrollbar-size-vertical: 1;
    }
    """

    def __init__(self, profile_name: str) -> None:
        super().__init__()
        self._manager = ConnectionManager.get()
        self._profile_name = profile_name
        self._engine = self._get_engine_from_profile(profile_name)
        self._current_report: QueryAnalysisReport | None = None
        self._current_ai_error: str | None = None

    @staticmethod
    def _get_engine_from_profile(profile_name: str) -> str:
        """Get engine name from profile.

        Args:
            profile_name: Profile name

        Returns:
            Engine name or "-" if not found
        """
        try:
            manager = ConnectionManager.get()
            return manager.get_profile(profile_name).engine
        except Exception:
            return "-"

    def _update_engine_label(self) -> None:
        """Update context label with current profile and engine."""
        self._engine = self._get_engine_from_profile(self._profile_name)
        context = self.query_one("#context-label", Static)
        context.update(f"[ Perfil: {self._profile_name} | Motor: {self._engine.upper()} ]")

    def compose(self) -> ComposeResult:
        """Compose screen layout - v2.1.0 with tabs."""
        context_text = f"[ Perfil: {self._profile_name} | Motor: {self._engine.upper()} ]"
        with Vertical(id="analysis-root"):
            yield Static(context_text, id="context-label")

            with Horizontal(id="workspace"):
                # LEFT: Editor column (45%)
                with Vertical(id="editor-column"):
                    yield QueryEditor(language="sql")

                    # Action buttons
                    with Grid(id="actions-grid"):
                        yield Button("Analizar", variant="primary", id="btn-analyze")
                        yield Button("Limpiar", id="btn-clear")
                        yield Button("Histórico", id="btn-history")
                        yield Button("Exportar", id="btn-export")

                    # Status
                    with Container(id="status-container"):
                        yield Static(
                            "[dim]Esperando consulta...[/dim]",
                            id="run-status",
                        )

                # RIGHT: Tabbed analysis panel (55%)
                with TabbedContent(
                    initial="tab-metrics",
                    id="details-tabbed",
                ):
                    with TabPane("Resumen", id="tab-summary"):
                        yield QuerySummary()

                    with TabPane("Métricas", id="tab-metrics"):
                        yield MetricsPanel()

                    with TabPane("Plan", id="tab-plan"):
                        yield PlanTreeWidget()

                    with TabPane("IA", id="tab-ai"):
                        yield AIInsightsPanel()

        yield Footer()

    def on_mount(self) -> None:
        """Mount screen and connect to profile if needed."""
        self._update_engine_label()
        self.query_one(QueryEditor).focus_editor()
        self._connect_profile_if_needed()

    def action_go_back(self) -> None:
        """Go back to previous screen."""
        self.app.pop_screen()

    def _button_ids(self) -> list[str]:
        """Return button IDs in visual grid order."""
        return ["btn-analyze", "btn-clear", "btn-history", "btn-export"]

    def _focused_button_index(self) -> int | None:
        """Get focused button index if focus is on an action button."""
        focused = self.focused
        if not isinstance(focused, Button) or focused.id is None:
            return None
        try:
            return self._button_ids().index(focused.id)
        except ValueError:
            return None

    def action_focus_buttons(self) -> None:
        """Focus first action button."""
        self.query_one("#btn-analyze", Button).focus()

    def _focus_button_by_index(self, index: int) -> None:
        """Focus action button by index in the grid order."""
        button_id = self._button_ids()[index]
        self.query_one(f"#{button_id}", Button).focus()

    def action_button_left(self) -> None:
        """Move focus to left button in grid."""
        idx = self._focused_button_index()
        if idx is None:
            self.action_focus_buttons()
            return
        if idx % 2 == 1:
            self._focus_button_by_index(idx - 1)

    def action_button_right(self) -> None:
        """Move focus to right button in grid."""
        idx = self._focused_button_index()
        if idx is None:
            self.action_focus_buttons()
            return
        if idx % 2 == 0:
            self._focus_button_by_index(idx + 1)

    def action_button_up(self) -> None:
        """Move focus to upper button in grid."""
        idx = self._focused_button_index()
        if idx is None:
            self.action_focus_buttons()
            return
        if idx >= 2:
            self._focus_button_by_index(idx - 2)

    def action_button_down(self) -> None:
        """Move focus to lower button in grid."""
        idx = self._focused_button_index()
        if idx is None:
            self.action_focus_buttons()
            return
        if idx <= 1:
            self._focus_button_by_index(idx + 2)

    def action_show_history(self) -> None:
        """Show analysis history."""
        history = get_history_manager()
        if len(history.get_all_for_profile(self._profile_name)) == 0:
            self._set_status("[yellow]No hay análisis en el histórico[/yellow]")
        else:
            self.app.push_screen(
                HistoryScreen(self._profile_name),
                self._on_history_selected,
            )

    def action_export(self) -> None:
        """Export analysis to file."""
        if self._current_report is None:
            self._set_status("[yellow]Sin análisis para exportar[/yellow]")
        else:
            self.app.push_screen(
                ExportDialog(self._current_report),
                self._on_export_complete,
            )

    def action_quit(self) -> None:
        """Exit the application."""
        self.app.exit()

    def action_copy_query(self) -> None:
        """Copy current query to clipboard."""
        query_editor = self.query_one(QueryEditor)
        query_text = query_editor.query_text
        if query_text.strip():
            try:
                self.app.copy_to_clipboard(query_text)
                self.app.notify("Consulta copiada al portapapeles")
            except Exception as e:
                self.app.notify(f"No se pudo copiar: {e}", severity="error")
        else:
            self._set_status("[yellow]No hay consulta para copiar[/yellow]")

    def action_focus_editor(self) -> None:
        """Focus the query editor."""
        self.query_one(QueryEditor).focus_editor()

    @on(Button.Pressed, "#btn-analyze")
    def on_analyze_pressed(self) -> None:
        """Handle analyze button press."""
        query_text = self.query_one(QueryEditor).query_text
        self._trigger_analysis(query_text)

    @on(Button.Pressed, "#btn-clear")
    def on_clear_pressed(self) -> None:
        """Clear query and results."""
        self.query_one(QueryEditor).clear()
        self._clear_results()
        self._set_status("[dim]Esperando consulta...[/dim]")

    @on(Button.Pressed, "#btn-history")
    def on_history_pressed(self) -> None:
        """Show analysis history."""
        self.action_show_history()

    @on(Button.Pressed, "#btn-export")
    def on_export_pressed(self) -> None:
        """Export analysis."""
        self.action_export()

    def _connect_profile_if_needed(self) -> None:
        """Connect to profile if not already connected."""
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
            self._set_status(f"[red]Error de conexión: {error}[/red]")

    def _trigger_analysis(self, query: str) -> None:
        """Trigger query analysis.

        Args:
            query: SQL query to analyze
        """
        text = query.strip()
        if not text:
            self._set_status("[red]Error: query vacía[/red]")
            return
        try:
            validate_query(text)
        except ValueError as error:
            self._set_status(f"[red]Error: {error}[/red]")
            return

        self.query_one(QueryEditor).set_busy(True)
        self.query_one("#btn-analyze", Button).disabled = True
        self._set_status("[yellow]Analizando...[/yellow]")
        self._set_loading_state()
        self.run_analysis_worker(text)

    @work(exclusive=True, thread=True)
    def run_analysis_worker(self, query_text: str) -> None:
        """Worker task to execute analysis in background.

        Args:
            query_text: SQL query to analyze
        """
        try:
            adapter = self._manager.active_adapter
            if adapter is None:
                self._manager.connect(self._profile_name)
                adapter = self._manager.active_adapter

            if adapter is None:
                raise QueryAnalysisError("No se pudo inicializar un adapter activo")

            report = adapter.execute_explain(query_text)

            self.app.call_from_thread(self._on_analysis_success, query_text, report, None)
        except Exception as error:
            self.app.call_from_thread(self._on_analysis_error, str(error))

    def _on_analysis_success(
        self, query_text: str, report: QueryAnalysisReport, ai_error: str | None = None
    ) -> None:
        """Handle successful analysis.

        Args:
            query_text: Original query text
            report: Analysis report
            ai_error: Error message from AI analyzer if any
        """
        self._current_report = report
        self._current_ai_error = ai_error

        # Save to history
        history_manager = get_history_manager()
        history_manager.add(
            query=query_text,
            report=report,
            profile_name=self._profile_name,
        )

        self._render_report(query_text, report, ai_error)

        # Update status
        self.query_one(QueryEditor).set_busy(False)
        self.query_one("#btn-analyze", Button).disabled = False
        self._set_status(f"[green]✓ Análisis completado ({report.execution_time_ms:.2f}ms)[/green]")
        self._start_ai_analysis(report)

    def _start_ai_analysis(self, report: QueryAnalysisReport) -> None:
        """Start AI analysis after factual results are already visible."""
        try:
            from query_analyzer.core.ai_analyzer import AIAnalyzer

            if not AIAnalyzer().available:
                self.query_one(AIInsightsPanel).render_ai_analysis(None, None)
                return
        except Exception:
            self.query_one(AIInsightsPanel).render_ai_analysis(None, None)
            return

        self.query_one(AIInsightsPanel).set_loading_state()
        try:
            self.run_ai_analysis_worker(report)
        except Exception:
            self.query_one(AIInsightsPanel).render_ai_analysis(None, None)

    @work(thread=True)
    def run_ai_analysis_worker(self, report: QueryAnalysisReport) -> None:
        """Run optional AI analysis without blocking factual EXPLAIN results."""
        try:
            from query_analyzer.core.ai_analyzer import AIAnalyzer

            ai_result = AIAnalyzer().analyze(
                plan_json=report.raw_plan or report.plan_summary or "No plan available",
                query=report.query,
                engine=report.engine,
            )

            if ai_result is None:
                self.app.call_from_thread(self._on_ai_analysis_complete, report, None, None)
                return

            model_result = AIAnalysisResult(
                summary=ai_result.summary,
                observations=ai_result.observations,
                recommendations=ai_result.recommendations,
                suggested_query=ai_result.suggested_query,
                raw_response=ai_result.raw_response,
            )
            self.app.call_from_thread(self._on_ai_analysis_complete, report, model_result, None)
        except Exception as error:
            self.app.call_from_thread(self._on_ai_analysis_complete, report, None, str(error))

    def _on_ai_analysis_complete(
        self,
        report: QueryAnalysisReport,
        ai_analysis: AIAnalysisResult | None,
        ai_error: str | None,
    ) -> None:
        """Render AI results only if they belong to the active report."""
        if self._current_report is not report:
            return

        report.ai_analysis = ai_analysis
        self._current_ai_error = ai_error
        self.query_one(AIInsightsPanel).render_ai_analysis(ai_analysis, ai_error)

    def _on_analysis_error(self, error_message: str) -> None:
        """Handle analysis error.

        Args:
            error_message: Error message
        """
        self.query_one(QueryEditor).set_busy(False)
        self.query_one("#btn-analyze", Button).disabled = False
        self._set_status(f"[red]✗ Error: {markup_escape(error_message)}[/red]")
        self._clear_results()

    def _set_status(self, message: str) -> None:
        """Update status message.

        Args:
            message: Status message with markup
        """
        status = self.query_one("#run-status", Static)
        status.update(message)

    def _set_loading_state(self) -> None:
        """Set all panels to loading state."""
        self.query_one(QuerySummary).set_loading_state()
        self.query_one(MetricsPanel).set_loading_state()
        self.query_one(PlanTreeWidget).set_loading_state()
        self.query_one(AIInsightsPanel).set_loading_state()

    def _clear_results(self) -> None:
        """Clear all analysis results."""
        self.query_one(QuerySummary).clear()
        self.query_one(MetricsPanel).clear()
        self.query_one(PlanTreeWidget).clear()
        self.query_one(AIInsightsPanel).clear()
        self._current_report = None
        self._current_ai_error = None

    def _on_export_complete(self, result: str | None) -> None:
        """Handle export dialog completion.

        Args:
            result: Export path if successful, None if cancelled
        """
        if result:
            self._set_status(f"[green]✓ Exported to {result}[/green]")
        else:
            self._set_status("[yellow]Export cancelled[/yellow]")

    def _on_history_selected(self, record: AnalysisRecord | None) -> None:
        """Load selected history record into the analysis view."""
        if record is None:
            return

        self._current_report = record.report
        self._current_ai_error = None
        editor = self.query_one(QueryEditor)
        editor.set_query_text(record.query)
        self._render_report(record.query, record.report, None)
        self._set_status("[green]✓ Análisis cargado desde historial[/green]")

    def _render_report(
        self, query_text: str, report: QueryAnalysisReport, ai_error: str | None = None
    ) -> None:
        """Render report widgets for analysis or history loads."""
        summary_widget = self.query_one(QuerySummary)
        summary_widget.render_summary(query_text, report, self._profile_name)

        metrics_widget = self.query_one(MetricsPanel)
        metrics_widget.render_metrics(
            report.execution_time_ms,
            report.plan_tree,
            report.metrics,
        )

        plan_widget = self.query_one(PlanTreeWidget)
        plan_widget.render_plan(report.plan_tree, report.raw_plan)

        ai_widget = self.query_one(AIInsightsPanel)
        ai_widget.render_ai_analysis(report.ai_analysis, ai_error)

    def _get_tabbed_content(self) -> TabbedContent:
        """Get the right-side tabbed content widget."""
        return self.query_one("#details-tabbed", TabbedContent)

    # Tab navigation actions
    def action_select_tab_summary(self) -> None:
        """Switch to Summary tab."""
        try:
            tabbed = self._get_tabbed_content()
            tabbed.active = "tab-summary"
        except Exception:
            pass

    def action_select_tab_metrics(self) -> None:
        """Switch to Metrics tab."""
        try:
            tabbed = self._get_tabbed_content()
            tabbed.active = "tab-metrics"
        except Exception:
            pass

    def action_select_tab_plan(self) -> None:
        """Switch to Plan tab."""
        try:
            tabbed = self._get_tabbed_content()
            tabbed.active = "tab-plan"
        except Exception:
            pass

    def action_select_tab_ai(self) -> None:
        """Switch to AI tab."""
        try:
            tabbed = self._get_tabbed_content()
            tabbed.active = "tab-ai"
        except Exception:
            pass

    def action_next_tab(self) -> None:
        """Move to next tab."""
        try:
            tabbed = self._get_tabbed_content()
            tab_ids = ["tab-summary", "tab-metrics", "tab-plan", "tab-ai"]
            current_idx = tab_ids.index(tabbed.active)
            next_idx = (current_idx + 1) % len(tab_ids)
            tabbed.active = tab_ids[next_idx]
        except Exception:
            pass

    def action_previous_tab(self) -> None:
        """Move to previous tab."""
        try:
            tabbed = self._get_tabbed_content()
            tab_ids = ["tab-summary", "tab-metrics", "tab-plan", "tab-ai"]
            current_idx = tab_ids.index(tabbed.active)
            prev_idx = (current_idx - 1) % len(tab_ids)
            tabbed.active = tab_ids[prev_idx]
        except Exception:
            pass
