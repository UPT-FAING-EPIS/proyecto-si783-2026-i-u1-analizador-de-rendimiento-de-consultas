"""Report renderer for displaying QueryAnalysisReport using Rich components.

Provides methods to render query analysis reports as formatted Rich components,
including summaries, warnings, recommendations, execution plans, and metrics.
"""

from __future__ import annotations

from typing import Any

from rich.console import Group
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree

from query_analyzer.adapters.models import (
    PlanNode,
    QueryAnalysisReport,
    Recommendation,
    Warning,
)


class ReportRenderer:
    """Renderiza reportes agnósticamente usando Rich.

    Cada método retorna un componente Rich que puede ser
    mostrado en CLI sin conocer el motor BD específico.
    """

    @staticmethod
    def render_summary(report: QueryAnalysisReport) -> Panel:
        """Panel con resumen: engine, score, execution_time.

        Ejemplo:
        ┌─ Query Analysis Summary ──────────────────┐
        │ POSTGRESQL | Score: 75/100 | Time: 145ms  │
        └───────────────────────────────────────────┘

        Args:
            report: QueryAnalysisReport

        Returns:
            Rich Panel
        """
        score_color = ReportRenderer._get_score_color(report.score)

        content = (
            f"[bold]{report.engine.upper()}[/bold] | "
            f"Score: [{score_color}]{report.score}[/{score_color}]/100 | "
            f"Execution: {report.execution_time_ms:.2f}ms | "
            f"Analyzed: {report.analyzed_at.isoformat()}"
        )

        return Panel(content, title="Query Analysis Summary", expand=False)

    @staticmethod
    def render_warnings(warnings: list[Warning]) -> Table:
        """Tabla de Warnings ordenada por severidad.

        Columns: Severity | Message | Affected Object

        Args:
            warnings: Lista de Warning

        Returns:
            Rich Table (vacía si no hay warnings)
        """
        if not warnings:
            return Table()

        table = Table(title=f"Warnings ({len(warnings)})")
        table.add_column("Severity", style="bold")
        table.add_column("Message")
        table.add_column("Object", style="dim")

        severity_colors = {
            "critical": "red",
            "high": "orange1",
            "medium": "yellow",
            "low": "blue",
        }

        severity_order = ["critical", "high", "medium", "low"]

        sorted_warnings = sorted(
            warnings,
            key=lambda w: severity_order.index(w.severity) if w.severity in severity_order else 999,
        )

        for warning in sorted_warnings:
            color = severity_colors.get(warning.severity, "white")
            table.add_row(
                f"[{color}]{warning.severity.upper()}[/{color}]",
                warning.message,
                warning.affected_object or "—",
            )

        return table

    @staticmethod
    def render_recommendations(recommendations: list[Recommendation]) -> Group:
        """Lista de Recommendations ordenada por priority (1 → 10).

        Formato:
        [Priority 1] Title
        Description...
        ```
        code_snippet
        ```

        Args:
            recommendations: Lista de Recommendation

        Returns:
            Rich Group (componente composable)
        """
        if not recommendations:
            return Group()

        components: list[Any] = []

        for rec in sorted(recommendations, key=lambda r: r.priority):
            title_text = (
                f"[bold magenta][Priority {rec.priority}][/bold magenta] [bold]{rec.title}[/bold]"
            )
            components.append(title_text)

            components.append(f"  {rec.description}")

            if rec.code_snippet:
                lang = ReportRenderer._detect_code_language(rec.code_snippet)
                syntax = Syntax(
                    rec.code_snippet,
                    lang,
                    theme="monokai",
                    line_numbers=False,
                    word_wrap=True,
                )
                components.append(syntax)

            components.append("")

        return Group(*components)

    @staticmethod
    def render_plan_tree(plan: PlanNode | None) -> Tree:
        """Renderiza árbol PlanNode como Rich Tree visual.

        Ejemplo:
        Query Execution Plan
        └── Seq Scan on users (cost=0..1000 rows=50000)
            └── Filter: age > 30

        Args:
            plan: PlanNode raíz o None

        Returns:
            Rich Tree component
        """
        if not plan:
            return Tree("[dim]No execution plan available[/dim]")

        root_tree = Tree(ReportRenderer._format_plan_node(plan))
        ReportRenderer._build_plan_tree_recursively(plan, root_tree)

        return root_tree

    @staticmethod
    def render_full_report(report: QueryAnalysisReport) -> Group:
        """Composición completa del reporte.

        Estructura:
        1. Summary Panel
        2. Query (Syntax)
        3. Warnings Table
        4. Recommendations
        5. Plan Tree
        6. Metrics

        Args:
            report: QueryAnalysisReport completo

        Returns:
            Rich Group con todos los componentes
        """
        components = [
            ReportRenderer.render_summary(report),
            "",
        ]

        query_syntax = Syntax(
            report.query, "sql", theme="monokai", line_numbers=True, word_wrap=True
        )
        components.append(Panel(query_syntax, title="Query", expand=False))

        if report.warnings:
            components.extend(["", ReportRenderer.render_warnings(report.warnings)])

        if report.recommendations:
            components.extend(
                [
                    "",
                    Panel(
                        ReportRenderer.render_recommendations(report.recommendations),
                        title="Recommendations",
                        expand=False,
                    ),
                ]
            )

        if report.plan_tree:
            components.extend(
                [
                    "",
                    Panel(
                        ReportRenderer.render_plan_tree(report.plan_tree),
                        title="Execution Plan",
                        expand=False,
                    ),
                ]
            )

        if report.metrics:
            components.extend(["", ReportRenderer._render_metrics_table(report.metrics)])

        return Group(*components)  # type: ignore[arg-type]

    @staticmethod
    def _format_plan_node(node: PlanNode) -> str:
        """Formatea un PlanNode para display en Rich Tree.

        Args:
            node: PlanNode a formatear

        Returns:
            String formateado
        """
        label = f"[bold]{node.node_type}[/bold]"

        details = []
        if node.cost is not None:
            details.append(f"cost={node.cost:.2f}")
        if node.actual_rows is not None:
            details.append(f"rows={node.actual_rows}")
        if node.actual_time_ms is not None:
            details.append(f"time={node.actual_time_ms:.2f}ms")

        if details:
            label += f" [dim]({', '.join(details)})[/dim]"

        if node.properties:
            for key, value in list(node.properties.items())[:2]:
                label += f"\n  [cyan]{key}[/cyan]: {value}"

        return label

    @staticmethod
    def _build_plan_tree_recursively(node: PlanNode, parent_tree: Tree) -> None:
        """Construye árbol recursivamente.

        Args:
            node: PlanNode actual
            parent_tree: Árbol padre donde agregar
        """
        for child in node.children:
            child_label = ReportRenderer._format_plan_node(child)
            child_tree = parent_tree.add(child_label)

            if child.children:
                ReportRenderer._build_plan_tree_recursively(child, child_tree)

    @staticmethod
    def _detect_code_language(snippet: str) -> str:
        """Detecta lenguaje: SQL, Flux, Cypher, etc.

        Args:
            snippet: Código a analizar

        Returns:
            Lenguaje (sql, flux, cypher, text)
        """
        snippet_upper = snippet.upper()

        if snippet_upper.startswith(("SELECT", "CREATE", "INSERT", "UPDATE", "DELETE")):
            return "sql"
        elif "|>" in snippet:
            return "flux"
        elif any(word in snippet_upper for word in ["MATCH", "CREATE", "RETURN", "MERGE"]):
            return "cypher"

        return "text"

    @staticmethod
    def _get_score_color(score: int) -> str:
        """Determina color Rich según score.

        Args:
            score: Score 0-100

        Returns:
            Color Rich (red, orange1, yellow, green, etc.)
        """
        if score >= 90:
            return "bright_green"
        elif score >= 70:
            return "green"
        elif score >= 50:
            return "yellow"
        elif score >= 30:
            return "orange1"
        else:
            return "red"

    @staticmethod
    def _render_metrics_table(metrics: dict[str, Any]) -> Panel:
        """Renderiza tabla de métricas.

        Args:
            metrics: dict con métricas

        Returns:
            Rich Panel con tabla
        """
        table = Table(title="Metrics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value")

        for key, value in metrics.items():
            table.add_row(key, str(value))

        return Panel(table, expand=False)
