"""Punto de entrada principal de la CLI."""

import typer

app = typer.Typer(
    name="qa",
    help="Query Analyzer - Herramienta de análisis de rendimiento de consultas",
    no_args_is_help=True,
)

# Importar subcomandos
from .commands import profile

# Agregar grupo de comandos
app.add_typer(profile.app, name="profile", help="Gestionar perfiles de conexión")


def main() -> None:
    """Punto de entrada del CLI."""
    app()


if __name__ == "__main__":
    main()
