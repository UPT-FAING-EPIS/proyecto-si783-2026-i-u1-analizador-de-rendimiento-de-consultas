"""Serializador agnóstico para QueryAnalysisReport.

Mantiene estructura jerárquica en JSON (ISO UTC)
y genera Markdown legible con árboles usando Rich.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Literal

from rich.console import Console
from rich.tree import Tree

from .models import PlanNode, QueryAnalysisReport


class ReportSerializer:
    """Serializador agnóstico para QueryAnalysisReport v2.

    Soporta:
    - JSON con timezone handling (ISO UTC)
    - Markdown con tree visualization (usando Rich)
    - Roundtrip serialization sin pérdida de datos
    """

    @staticmethod
    def to_json(report: QueryAnalysisReport, indent: int = 2) -> str:
        """Exporta reporte a JSON con estructura completa.

        Características:
        - analyzed_at en ISO 8601 UTC
        - PlanNode tree preservado recursivamente
        - Metadatos completos de Warning y Recommendation

        Args:
            report: QueryAnalysisReport a serializar
            indent: Indentación para legibilidad (default 2)

        Returns:
            String JSON válido y bien formateado
        """
        return report.model_dump_json(indent=indent, exclude_none=False)

    @staticmethod
    def from_json(json_str: str) -> QueryAnalysisReport:
        """Importa reporte desde JSON.

        Características:
        - Reconstruye datetime desde ISO string (preserva UTC)
        - Reconvierte PlanNode tree
        - Valida estructura según schema Pydantic

        Args:
            json_str: JSON válido del reporte

        Returns:
            QueryAnalysisReport con todas las dataclasses

        Raises:
            ValueError: Si JSON es inválido o no cumple schema
        """
        try:
            return QueryAnalysisReport.model_validate_json(json_str)
        except Exception as e:
            raise ValueError(f"Error deserializando JSON: {str(e)}") from e

    # ========== MARKDOWN EXPORT (con Rich Console Delegation) ==========

    @staticmethod
    def to_markdown(report: QueryAnalysisReport) -> str:
        """Genera Markdown formateado con visualización de árbol.

        Usa rich.Console + StringIO para garantizar que el árbol
        en Markdown sea idéntico al de la TUI.

        Estructura:
        # Query Analysis Report

        | Metric | Value |
        | Engine | PostgreSQL |
        | Score | 75/100 |
        | Execution | 145ms |
        | Analyzed | 2024-01-15T10:30:00Z |

        ## Query
        ```sql
        SELECT * FROM users WHERE age > 30
        ```

        ## Warnings (3)
        - [CRITICAL] Full table scan on users → users
        - [HIGH] Sort without index → users

        ## Recommendations (2)
        1. [Priority 1] Add index on users(age)
           Creating an index on the age column...
           ```sql
           CREATE INDEX idx_users_age ON users(age);
           ```

        ## Execution Plan
        ```
        ├── Seq Scan (cost=0..1000 rows=50000)
        │   └── Filter: age > 30
        └── Aggregate
        ```

        ## Metrics
        | Metric | Value |
        |--------|-------|
        | node_count | 3 |
        | buffers | 1200 |

        Args:
            report: QueryAnalysisReport a convertir

        Returns:
            String Markdown bien formateado
        """
        lines = []

        lines.append("# Query Analysis Report")
        lines.append("")

        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| **Engine** | {report.engine.upper()} |")
        lines.append(f"| **Score** | {report.score}/100 |")
        lines.append(f"| **Execution Time** | {report.execution_time_ms:.2f}ms |")
        analyzed_str = report.analyzed_at.isoformat() if report.analyzed_at else "Unknown"
        lines.append(f"| **Analyzed** | {analyzed_str} |")
        lines.append("")

        lines.append("## Query")
        lines.append("```sql")
        lines.append(report.query)
        lines.append("```")
        lines.append("")

        if report.warnings:
            lines.append(f"## Warnings ({len(report.warnings)})")
            for warning in report.warnings:
                severity_icon = {
                    "critical": "[RED]CRITICAL[/RED]",
                    "high": "[ORANGE1]HIGH[/ORANGE1]",
                    "medium": "[YELLOW]MEDIUM[/YELLOW]",
                    "low": "[BLUE]LOW[/BLUE]",
                }.get(warning.severity, "•")

                obj_str = f" → {warning.affected_object}" if warning.affected_object else ""
                lines.append(f"- {severity_icon}: {warning.message}{obj_str}")
            lines.append("")

        if report.recommendations:
            lines.append(f"## Recommendations ({len(report.recommendations)})")
            for rec in sorted(report.recommendations, key=lambda r: r.priority):
                lines.append(f"### {rec.priority}. {rec.title}")
                lines.append(rec.description)
                if rec.code_snippet:
                    # Detectar lenguaje
                    lang = ReportSerializer._detect_code_language(rec.code_snippet)
                    lines.append(f"```{lang}")
                    lines.append(rec.code_snippet)
                    lines.append("```")
                lines.append("")

        if report.plan_tree:
            lines.append("## Execution Plan")
            ascii_tree = ReportSerializer._render_plan_tree_ascii(report.plan_tree)
            lines.append("```")
            lines.append(ascii_tree)
            lines.append("```")
            lines.append("")

        if report.metrics:
            lines.append("## Metrics")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            for key, value in report.metrics.items():
                lines.append(f"| {key} | {value} |")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def to_dict(report: QueryAnalysisReport) -> dict[str, Any]:
        """Exporta a diccionario JSON-serializable.

        Args:
            report: QueryAnalysisReport

        Returns:
            dict con estructura completa
        """
        return report.model_dump()

    @staticmethod
    def from_dict(data: dict[str, Any]) -> QueryAnalysisReport:
        """Importa desde diccionario.

        Args:
            data: dict con estructura QueryAnalysisReport

        Returns:
            QueryAnalysisReport validado

        Raises:
            ValueError: Si dict no cumple schema
        """
        try:
            return QueryAnalysisReport.model_validate(data)
        except Exception as e:
            raise ValueError(f"Error validando dict: {str(e)}") from e

    # ========== FILE EXPORT ==========

    @staticmethod
    def export_file(
        report: QueryAnalysisReport,
        filepath: str,
        format: Literal["json", "md"] = "json",
    ) -> None:
        """Exporta reporte a archivo.

        Características:
        - Crea directorio si no existe
        - UTF-8 encoding
        - Manejo de rutas relativas y absolutas

        Args:
            report: QueryAnalysisReport a exportar
            filepath: Ruta del archivo
            format: "json" o "md"

        Raises:
            ValueError: Si format no es válido
            IOError: Si no puede escribir al archivo
        """
        if format not in ["json", "md"]:
            raise ValueError(f"Format debe ser 'json' o 'md', recibido: {format}")

        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        content = (
            ReportSerializer.to_json(report)
            if format == "json"
            else ReportSerializer.to_markdown(report)
        )

        try:
            path.write_text(content, encoding="utf-8")
        except OSError as e:
            raise OSError(f"No se puede escribir a {filepath}: {str(e)}") from e

    # ========== TREE VISUALIZATION (DELEGADO A RICH) ==========

    @staticmethod
    def _render_plan_tree_ascii(plan: PlanNode) -> str:
        """Renderiza árbol PlanNode como ASCII usando Rich.Console.

        ESTRATEGIA: Usa rich.tree.Tree + Console + StringIO
        para garantizar que el Markdown sea idéntico al de la TUI.

        Args:
            plan: PlanNode raíz

        Returns:
            String ASCII del árbol
        """
        # Construir Rich Tree
        tree = ReportSerializer._build_rich_tree(plan)

        # Capturar output a StringIO (sin terminal escape codes)
        string_buffer = io.StringIO()
        console = Console(
            file=string_buffer,
            force_terminal=False,  # Sin escape codes
            width=100,
            legacy_windows=False,
        )
        console.print(tree)

        # Retornar ASCII puro
        return string_buffer.getvalue().strip()

    @staticmethod
    def _build_rich_tree(node: PlanNode, parent_tree: Tree | None = None) -> Tree:
        """Construye Rich Tree recursivamente desde PlanNode.

        Args:
            node: PlanNode actual
            parent_tree: Parent Tree node (uso interno)

        Returns:
            Rich Tree (root o subtree)
        """
        if parent_tree is None:
            # Nodo raíz
            tree = Tree(ReportSerializer._format_node_label(node))
        else:
            tree = parent_tree

        # Crear labels para children
        for child in node.children:
            child_label = ReportSerializer._format_node_label(child)
            child_tree = tree.add(child_label)

            # Recursión
            if child.children:
                ReportSerializer._build_rich_tree(child, child_tree)

        return tree

    @staticmethod
    def _format_node_label(node: PlanNode) -> str:
        """Formatea un nodo para display.

        Ejemplo: "Seq Scan (cost=0..1000 rows=50000)"

        Args:
            node: PlanNode a formatear

        Returns:
            String formateado para Rich Tree
        """
        label = f"{node.node_type}"

        details = []
        if node.cost is not None:
            details.append(f"cost={node.cost:.2f}")
        if node.actual_rows is not None:
            details.append(f"rows={node.actual_rows}")
        if node.actual_time_ms is not None:
            details.append(f"time={node.actual_time_ms:.2f}ms")

        if details:
            label += f" ({', '.join(details)})"

        return label

    # ========== HELPER METHODS ==========

    @staticmethod
    def _detect_code_language(snippet: str) -> str:
        """Detecta lenguaje de código: SQL, Flux, Cypher, etc.

        Args:
            snippet: Código a analizar

        Returns:
            Lenguaje detectado (sql, flux, cypher, text)
        """
        snippet_upper = snippet.upper()

        if snippet_upper.startswith(("SELECT", "CREATE", "INSERT", "UPDATE", "DELETE")):
            return "sql"
        elif "|>" in snippet:  # Flux pipe operator
            return "flux"
        elif any(word in snippet_upper for word in ["MATCH", "CREATE", "RETURN", "MERGE"]):
            return "cypher"

        return "text"
