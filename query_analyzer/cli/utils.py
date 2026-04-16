"""Utilidades para la interfaz CLI."""

from io import StringIO

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from query_analyzer.adapters import QueryAnalysisReport
from query_analyzer.config import ProfileConfig

console = Console()


def truncate_text(text: str, max_width: int = 80) -> str:
    """Truncate text with ellipsis if too long."""
    if len(text) <= max_width:
        return text
    return text[: max_width - 1] + "…"


class OutputFormatter:
    """Formatea output para CLI con estilos."""

    @staticmethod
    def mask_password(password: str, visible_chars: int = 2) -> str:
        """Enmascara un password en output.

        Args:
            password: Password a enmascarar
            visible_chars: Número de caracteres visibles al inicio

        Returns:
            Password enmascarado. Ej: "my**********"
        """
        if not password:
            return ""

        if len(password) <= visible_chars:
            return "*" * len(password)

        visible = password[:visible_chars]
        masked = "*" * (len(password) - visible_chars)
        return visible + masked

    @staticmethod
    def format_profile(
        name: str,
        profile: ProfileConfig,
        is_default: bool = False,
        mask_pwd: bool = True,
    ) -> str:
        """Formatea un perfil para mostrar.

        Returns:
            Cadena formateada del perfil
        """
        default_marker = " [bold green](default)[/bold green]" if is_default else ""
        password_display = (
            OutputFormatter.mask_password(profile.password) if mask_pwd else profile.password
        )

        return (
            f"[bold]{name}[/bold]{default_marker}\n"
            f"  Engine: {profile.engine}\n"
            f"  Host: {profile.host}:{profile.port}\n"
            f"  Database: {profile.database}\n"
            f"  Username: {profile.username}\n"
            f"  Password: {password_display}"
        )

    @staticmethod
    def print_success(message: str) -> None:
        """Imprime mensaje de exito con [OK]."""
        console.print(f"[green][OK][/green] {message}")

    @staticmethod
    def print_error(message: str) -> None:
        """Imprime mensaje de error con [ERROR]."""
        console.print(f"[red][ERROR][/red] {message}")

    @staticmethod
    def print_info(message: str) -> None:
        """Imprime mensaje informativo."""
        console.print(f"[blue][INFO][/blue] {message}")

    @staticmethod
    def print_warning(message: str) -> None:
        """Imprime mensaje de warning."""
        console.print(f"[yellow][WARN][/yellow] {message}")

    @staticmethod
    def create_profiles_table(
        profiles: dict[str, ProfileConfig], default_profile: str | None = None
    ) -> Table:
        """Crea una tabla para mostrar perfiles.

        Args:
            profiles: Diccionario de perfiles
            default_profile: Nombre del perfil default

        Returns:
            Tabla de rich
        """
        table = Table(title="Perfiles de Conexion", show_header=True, header_style="bold")
        table.add_column("Nombre", style="cyan")
        table.add_column("Engine", style="magenta")
        table.add_column("Host", style="green")
        table.add_column("Database", style="yellow")
        table.add_column("Usuario", style="blue")

        for name, profile in profiles.items():
            default_marker = "[DEFAULT]" if name == default_profile else ""
            table.add_row(
                f"{name} {default_marker}",
                profile.engine,
                f"{profile.host}:{profile.port}",
                profile.database,
                profile.username,
            )

        return table

    @staticmethod
    def format_report(
        report: QueryAnalysisReport,
        format: str = "rich",
        profile_name: str = "",
        is_default: bool = False,
        verbose: bool = False,
    ) -> str:
        """Format query analysis report.

        Args:
            report: QueryAnalysisReport to format
            format: Output format ('rich', 'json', 'text')
            profile_name: Profile name used (optional)
            is_default: Whether profile is default (optional)
            verbose: Verbose output (optional)

        Returns:
            Formatted report string
        """
        if format == "rich":
            return OutputFormatter._format_report_rich(report)
        elif format == "json":
            import json

            return json.dumps(
                report.to_dict() if hasattr(report, "to_dict") else str(report), indent=2
            )
        else:
            return str(report)

    @staticmethod
    def _format_report_rich(report: QueryAnalysisReport) -> str:
        """Format report using Rich with Panel header.

        Args:
            report: QueryAnalysisReport to format

        Returns:
            Rich-formatted string
        """
        lines = []

        # Header panel - let Rich handle wrapping naturally
        score_emoji = "🟢" if report.score >= 70 else "🟡" if report.score >= 50 else "🔴"
        header_content = (
            f"[cyan]Engine:[/cyan] [bold]{report.engine}[/bold]\n"
            f"[cyan]Score:[/cyan] [bold]{score_emoji} {report.score}/100[/bold]\n"
            f"[cyan]Execution Time:[/cyan] {report.execution_time_ms:.2f} ms\n"
            f"[cyan]Query:[/cyan] {report.query}"
        )

        panel = Panel(header_content, title="QUERY ANALYSIS REPORT", expand=True)
        buffer = StringIO()
        panel_console = Console(file=buffer, force_terminal=True, width=80)
        panel_console.print(panel)
        lines.append(buffer.getvalue().rstrip())

        # Warnings section
        if report.warnings:
            lines.append("")
            lines.append(f"[bold yellow]⚠️  WARNINGS ({len(report.warnings)})[/bold yellow]")
            warnings_table = Table(show_header=True, header_style="bold")
            warnings_table.add_column("Severity", width=10)
            warnings_table.add_column("Message", no_wrap=False)
            for w in report.warnings:
                warnings_table.add_row(w.severity.upper(), w.message)
            buffer = StringIO()
            table_console = Console(file=buffer, force_terminal=True, width=80)
            table_console.print(warnings_table)
            lines.append(buffer.getvalue().rstrip())

        # Recommendations section
        if report.recommendations:
            lines.append("")
            lines.append(
                f"[bold cyan]💡 RECOMMENDATIONS ({len(report.recommendations)})[/bold cyan]"
            )
            recs_table = Table(show_header=True, header_style="bold")
            recs_table.add_column("Priority", width=10)
            recs_table.add_column("Action", no_wrap=False)
            for r in report.recommendations:
                priority_emoji = "🔴" if r.priority <= 3 else "🟡" if r.priority <= 7 else "🔵"
                recs_table.add_row(f"{priority_emoji} {r.priority}", r.title)
            buffer = StringIO()
            table_console = Console(file=buffer, force_terminal=True, width=80)
            table_console.print(recs_table)
            lines.append(buffer.getvalue().rstrip())

        # Metrics section
        if report.metrics:
            lines.append("")
            lines.append("[bold blue]📊 METRICS[/bold blue]")
            metrics_table = Table(show_header=True, header_style="bold")
            metrics_table.add_column("Metric", width=20)
            metrics_table.add_column("Value", width=15)
            for key, value in list(report.metrics.items())[:5]:
                metrics_table.add_row(key, str(value))
            buffer = StringIO()
            table_console = Console(file=buffer, force_terminal=True, width=80)
            table_console.print(metrics_table)
            lines.append(buffer.getvalue().rstrip())

        return "\n".join(lines)

    @staticmethod
    def print_report(
        report: QueryAnalysisReport,
        format: str = "rich",
        profile_name: str = "",
        is_default: bool = False,
        verbose: bool = False,
        console_instance: Console | None = None,
    ) -> None:
        """Print formatted report.

        Args:
            report: QueryAnalysisReport to print
            format: Output format ('rich', 'json', 'text')
            profile_name: Profile name used (optional)
            is_default: Whether profile is default (optional)
            verbose: Verbose output (optional)
            console_instance: Rich console instance to use (optional)
        """
        target_console = console_instance if console_instance else console

        if format == "rich":
            # Header panel
            score_emoji = "🟢" if report.score >= 70 else "🟡" if report.score >= 50 else "🔴"
            header_content = (
                f"[cyan]Engine:[/cyan] [bold]{report.engine}[/bold]\n"
                f"[cyan]Score:[/cyan] [bold]{score_emoji} {report.score}/100[/bold]\n"
                f"[cyan]Execution Time:[/cyan] {report.execution_time_ms:.2f} ms\n"
                f"[cyan]Query:[/cyan] {report.query}"
            )
            panel = Panel(header_content, title="QUERY ANALYSIS REPORT", expand=True)
            target_console.print(panel)

            # Warnings section
            if report.warnings:
                target_console.print()
                target_console.print(
                    f"[bold yellow]⚠️  WARNINGS ({len(report.warnings)})[/bold yellow]"
                )
                warnings_table = Table(show_header=True, header_style="bold")
                warnings_table.add_column("Severity", width=10)
                warnings_table.add_column("Message", no_wrap=False)
                for w in report.warnings:
                    warnings_table.add_row(w.severity.upper(), w.message)
                target_console.print(warnings_table)

            # Recommendations section
            if report.recommendations:
                target_console.print()
                target_console.print(
                    f"[bold cyan]💡 RECOMMENDATIONS ({len(report.recommendations)})[/bold cyan]"
                )
                recs_table = Table(show_header=True, header_style="bold")
                recs_table.add_column("Priority", width=10)
                recs_table.add_column("Action", no_wrap=False)
                for r in report.recommendations:
                    priority_emoji = "🔴" if r.priority <= 3 else "🟡" if r.priority <= 7 else "🔵"
                    recs_table.add_row(f"{priority_emoji} {r.priority}", r.title)
                target_console.print(recs_table)

            # Metrics section
            if report.metrics:
                target_console.print()
                target_console.print("[bold blue]📊 METRICS[/bold blue]")
                metrics_table = Table(show_header=True, header_style="bold")
                metrics_table.add_column("Metric", width=20)
                metrics_table.add_column("Value", width=15)
                for key, value in list(report.metrics.items())[:5]:
                    metrics_table.add_row(key, str(value))
                target_console.print(metrics_table)
        elif format == "json":
            import json

            output = json.dumps(
                report.to_dict() if hasattr(report, "to_dict") else str(report),
                indent=2,
            )
            target_console.print(output)
        else:
            target_console.print(str(report))
