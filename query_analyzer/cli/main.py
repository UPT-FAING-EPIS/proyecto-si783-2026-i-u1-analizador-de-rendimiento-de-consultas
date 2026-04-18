"""Query Analyzer CLI - Main entry point.

Provides command-line interface for database query performance analysis with
support for PostgreSQL, MySQL, and SQLite databases.
"""

from pathlib import Path

import typer

from .commands import analyze, profile

tui_app = typer.Typer(
    name="tui",
    help="Abrir interfaz TUI",
    no_args_is_help=True,
)

app = typer.Typer(
    name="qa",
    help="Query Analyzer - Herramienta de análisis de rendimiento de consultas",
    no_args_is_help=True,
)

# Register command groups
app.add_typer(profile.app, name="profile", help="Gestionar perfiles de conexión")


# Register tui as a command in main app
@app.command(name="tui", help="Abrir interfaz TUI interactiva")
def tui_command() -> None:
    """Ejecutar la interfaz TUI."""
    from query_analyzer import tui as tui_module

    tui_module.run()


@app.command(name="analyze", help="Analizar rendimiento de consultas")
def analyze_command(
    query: str | None = typer.Argument(None, help="SQL query string (or use --file or stdin)"),
    profile: str | None = typer.Option(
        None, "--profile", "-p", help="Profile name (uses default if omitted)"
    ),
    file: str | None = typer.Option(None, "--file", "-f", help="Read query from file"),
    output: str = typer.Option("rich", "--output", "-o", help="Output format: rich|json|markdown"),
    timeout: int = typer.Option(
        30, "--timeout", "-t", help="Query timeout in seconds (default: 30)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output for debugging"),
) -> None:
    """Analyze database query performance using EXPLAIN."""
    analyze.analyze(query, profile, Path(file) if file else None, output, timeout, verbose)


def main() -> None:
    r"""Punto de entrada principal para el CLI de Query Analyzer.

    Inicializa y ejecuta la aplicación Typer con todos los comandos y
    subcomandos configurados. Esta función es el punto de inicio cuando
    se ejecuta el paquete como módulo o como aplicación instalada.

    La aplicación soporta análisis de rendimiento de queries para múltiples
    motores de base de datos (PostgreSQL, MySQL, SQLite, CockroachDB, etc.)
    a través de perfiles de conexión configurables.

    Raises:
        SystemExit: Con código 0 en salida exitosa, >0 en caso de error.

    Example:
        \b
        # Llamar directamente
        $ python -m query_analyzer

        # O si está instalado como paquete:
        $ qa --help
        $ qa profile list
        $ qa profile add mydb --engine postgresql
    """
    app()


if __name__ == "__main__":
    main()
