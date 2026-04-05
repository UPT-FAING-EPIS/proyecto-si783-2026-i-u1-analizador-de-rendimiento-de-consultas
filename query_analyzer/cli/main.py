"""Query Analyzer CLI - Main entry point.

Provides command-line interface for database query performance analysis with
support for PostgreSQL, MySQL, and SQLite databases.
"""

import typer

from .commands import profile

app = typer.Typer(
    name="qa",
    help="Query Analyzer - Herramienta de análisis de rendimiento de consultas",
    no_args_is_help=True,
)

# Agregar grupo de comandos
app.add_typer(profile.app, name="profile", help="Gestionar perfiles de conexión")


def main() -> None:
    """Entry point for the Query Analyzer CLI application.

    Initializes and runs the Typer CLI application with all configured
    commands and subcommands.
    """
    app()


if __name__ == "__main__":
    main()
