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
