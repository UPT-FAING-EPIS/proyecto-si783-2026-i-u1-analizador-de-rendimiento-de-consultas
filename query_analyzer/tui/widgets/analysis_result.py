"""Widgets for rendering analysis output in TUI."""

from rich.syntax import Syntax
from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Label, ListItem, ListView, Static

from query_analyzer.adapters import Recommendation, Warning

WARNING_ICON = {
    "critical": "[red]![/red]",
    "high": "[red]![/red]",
    "medium": "[yellow]![/yellow]",
    "low": "[blue]i[/blue]",
}


class WarningsPanel(Container):
    """Sidebar warnings list."""

    DEFAULT_CSS = """
    WarningsPanel {
        width: 1fr;
        height: 1fr;
        border: solid $accent;
        padding: 1;
        background: $panel;
        overflow-y: auto;
    }

    WarningsPanel:focus {
        border: solid $primary;
    }

    WarningsPanel .section-title {
        text-style: bold;
        margin-bottom: 1;
    }

    WarningsPanel ListView {
        height: 1fr;
        border: solid $surface-lighten-1;
        overflow-y: auto;
    }

    WarningsPanel ListItem {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
    }

    WarningsPanel Label {
        width: 1fr;
    }

    WarningsPanel #warnings-list {
        scrollbar-size-vertical: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("Advertencias", classes="section-title")
        yield ListView(id="warnings-list")

    def set_running(self) -> None:
        self._set_single_message("Analizando query...")

    def set_error(self, message: str) -> None:
        self._set_single_message(f"[red]Error:[/red] {message}")

    def render_warnings(self, warnings: list[Warning]) -> None:
        list_view = self.query_one("#warnings-list", ListView)
        list_view.clear()

        if not warnings:
            list_view.append(ListItem(Label("Sin advertencias detectadas.")))
            return

        sorted_warnings = sorted(warnings, key=lambda warning: _severity_order(warning.severity))
        for idx, warning in enumerate(sorted_warnings, start=1):
            icon = WARNING_ICON.get(warning.severity, "-")

            # Get affected object with better fallback
            affected = warning.affected_object or ""
            if not affected or affected.lower() in ("unknown", "none", ""):
                # Try to get from metadata
                metadata = warning.metadata or {}
                table_from_meta = (
                    metadata.get("table_name")
                    or metadata.get("outer_table")
                    or metadata.get("inner_table")
                )
                if table_from_meta:
                    affected = table_from_meta
                else:
                    # Special handling for sort_without_index - it affects the ORDER BY result, not a table
                    if warning.node_type == "sort_without_index":
                        affected = "resultado del ORDER BY"
                    elif warning.node_type == "select_star":
                        affected = "todas las columnas (SELECT *)"
                    else:
                        affected = "consulta"

            severity_label = warning.severity.upper()
            message = f"{idx}. {icon} [{severity_label}] {warning.message}\n   Afecta: {affected}"
            list_view.append(ListItem(Static(message)))

    def set_loading(self, loading: bool) -> None:
        self.loading = loading

    def _set_single_message(self, message: str) -> None:
        list_view = self.query_one("#warnings-list", ListView)
        list_view.clear()
        list_view.append(ListItem(Static(message)))


class RecommendationsPanel(Container):
    """Recommendations shown below query editor."""

    DEFAULT_CSS = """
    RecommendationsPanel {
        width: 1fr;
        height: 1fr;
        border: solid $accent;
        padding: 1;
        background: $panel;
        overflow-y: auto;
    }

    RecommendationsPanel:focus {
        border: solid $primary;
    }

    RecommendationsPanel .section-title {
        text-style: bold;
        margin-bottom: 1;
    }

    RecommendationsPanel ListView {
        height: 1fr;
        border: solid $surface-lighten-1;
        overflow-y: auto;
    }

    RecommendationsPanel ListItem {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
    }

    RecommendationsPanel .snippet {
        color: $text-muted;
        width: 1fr;
    }

    RecommendationsPanel .rec-title {
        text-style: bold;
    }

    RecommendationsPanel .rec-description {
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("Recomendaciones", classes="section-title")
        yield ListView(id="recommendations-list")

    def set_running(self) -> None:
        self._set_single_message("Analizando recomendaciones...")

    def set_error(self) -> None:
        self._set_single_message("No se pudo generar recomendaciones.")

    def render_recommendations(self, recommendations: list[Recommendation]) -> None:
        list_view = self.query_one("#recommendations-list", ListView)
        list_view.clear()

        if not recommendations:
            list_view.append(ListItem(Label("No hay recomendaciones.")))
            return

        ordered = sorted(
            recommendations,
            key=lambda recommendation: (recommendation.priority, recommendation.title.lower()),
        )
        for idx, recommendation in enumerate(ordered, start=1):
            # Convert priority to readable text
            priority_map = {
                1: "ALTA",
                2: "ALTA",
                3: "ALTA",
                4: "ALTA",
                5: "ALTA",
                6: "MEDIA",
                7: "MEDIA",
                8: "MEDIA",
                9: "BAJA",
                10: "BAJA",
            }
            readable_priority = priority_map.get(
                recommendation.priority, f"P{recommendation.priority}"
            )

            # Get affected object
            affected = recommendation.affected_object or ""
            if not affected or affected.lower() in ("unknown", "none", ""):
                metadata = recommendation.metadata or {}
                table_from_meta = metadata.get("table_name")
                if table_from_meta:
                    affected = table_from_meta
                else:
                    # Similar fallback for recommendations
                    if recommendation.title and "ORDER BY" in recommendation.title:
                        affected = "ORDER BY"
                    elif recommendation.title and "SELECT *" in recommendation.title:
                        affected = "SELECT *"
                    else:
                        affected = "-"

            title = f"{idx}. [{readable_priority}] {recommendation.title}"
            # Fix title if it contains 'unknown' - replace with better text
            title = title.replace("'unknown'", "(ORDER BY)")
            title = title.replace("'todas las tablas'", "(todas las tablas)")
            if affected and affected != "-":
                title += f" ({affected})"
            description = recommendation.description.strip()
            show_description = bool(description) and description != recommendation.title.strip()
            if recommendation.code_snippet:
                sql_syntax = Syntax(
                    recommendation.code_snippet,
                    "sql",
                    theme="monokai",
                    line_numbers=False,
                    word_wrap=True,
                )
                list_view.append(
                    ListItem(
                        Static(title, classes="rec-title"),
                        *(
                            [Static(recommendation.description, classes="rec-description")]
                            if show_description
                            else []
                        ),
                        Static(sql_syntax),
                    )
                )
            else:
                list_view.append(
                    ListItem(
                        Static(title, classes="rec-title"),
                        *(
                            [Static(recommendation.description, classes="rec-description")]
                            if show_description
                            else []
                        ),
                    )
                )

    def set_loading(self, loading: bool) -> None:
        self.loading = loading

    def _set_single_message(self, message: str) -> None:
        list_view = self.query_one("#recommendations-list", ListView)
        list_view.clear()
        list_view.append(ListItem(Static(message)))


def _severity_order(severity: str) -> int:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return order.get(severity, 99)
