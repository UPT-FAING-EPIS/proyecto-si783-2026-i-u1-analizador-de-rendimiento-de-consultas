"""Comandos CLI para gestionar perfiles."""

import typer
from typing import Optional
from rich.console import Console
from rich.prompt import Prompt, Confirm

from query_analyzer.config import (
    ConfigManager,
    ProfileConfig,
    ProfileNotFoundError,
    ConfigValidationError,
)
from query_analyzer.adapters import (
    BaseAdapter,
    ConnectionError as AdapterConnectionError,
)
from query_analyzer.cli.utils import OutputFormatter

app = typer.Typer(help="Gestionar perfiles de conexión")
console = Console()


def _get_adapter(engine: str) -> type[BaseAdapter]:
    """
    Obtiene la clase del adapter para un engine.

    Nota: Por ahora retornamos un mock. En producción,
    cargaríamos dinámicamente desde query_analyzer.adapters.sql, etc.
    """
    # TODO: Implementar factory de adapters cuando existan
    # Por ahora retornamos None para indicar que no está implementado
    if engine.lower() not in ("postgresql", "mysql"):
        raise ValueError(f"Engine {engine} no soportado")
    return None  # type: ignore


@app.command()
def add(
    name: str = typer.Argument(..., help="Nombre del nuevo perfil"),
    engine: Optional[str] = typer.Option(
        None, "--engine", "-e", help="postgresql | mysql"
    ),
    host: Optional[str] = typer.Option(None, "--host", "-h", help="Host de la BD"),
    port: Optional[int] = typer.Option(None, "--port", "-p", help="Puerto"),
    database: Optional[str] = typer.Option(
        None, "--database", "-d", help="Nombre de DB"
    ),
    username: Optional[str] = typer.Option(None, "--username", "-u", help="Usuario"),
    password: Optional[str] = typer.Option(
        None, "--password", "-pw", help="Password (interactivo si omitido)"
    ),
) -> None:
    """
    Agregar nuevo perfil de conexión.

    Modo interactivo si se omiten parámetros:

    \b
    $ qa profile add staging
    Engine [postgresql]: mysql
    Host [localhost]: prod-db.example.com
    Port [3306]:
    Database: myapp
    Username: analyst
    Password (hidden): ****
    """
    try:
        config_mgr = ConfigManager()

        # Modo interactivo: pedir datos faltantes
        if engine is None:
            engine = Prompt.ask(
                "Engine", choices=["postgresql", "mysql"], default="postgresql"
            )

        if host is None:
            host = Prompt.ask("Host", default="localhost")

        if port is None:
            port = int(
                Prompt.ask("Port", default="5432" if engine == "postgresql" else "3306")
            )

        if database is None:
            database = Prompt.ask("Database")

        if username is None:
            username = Prompt.ask(
                "Username", default="postgres" if engine == "postgresql" else "root"
            )

        if password is None:
            password = Prompt.ask("Password", password=True)

        # Crear perfil
        profile = ProfileConfig(
            engine=engine,
            host=host,
            port=port,
            database=database,
            username=username,
            password=password,
        )

        # Agregar a configuración
        config_mgr.add_profile(name, profile)

        OutputFormatter.print_success(f"Perfil '{name}' agregado exitosamente")

    except ConfigValidationError as e:
        OutputFormatter.print_error(f"Error de validación: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        OutputFormatter.print_error(f"Error: {e}")
        raise typer.Exit(code=1)


@app.command()
def list(
    show_passwords: bool = typer.Option(
        False, "--show-passwords", help="Mostrar passwords sin enmascarar"
    ),
) -> None:
    """
    Listar todos los perfiles.

    Muestra el perfil default con ✓.
    """
    try:
        config_mgr = ConfigManager()
        config = config_mgr.load_config()
        profiles = config_mgr.list_profiles()

        if not profiles:
            OutputFormatter.print_info("No hay perfiles configurados")
            return

        console.print()
        table = OutputFormatter.create_profiles_table(profiles, config.default_profile)
        console.print(table)
        console.print()

    except Exception as e:
        OutputFormatter.print_error(f"Error: {e}")
        raise typer.Exit(code=1)


@app.command()
def test(
    name: str = typer.Argument(..., help="Nombre del perfil a probar"),
) -> None:
    """
    Probar conexión a un perfil.

    Ejecuta:
    1. test_connection() del adapter
    2. Query diagnóstica según el engine

    \b
    $ qa profile test local-postgres
    Testing connection to 'local-postgres'...
    ✓ Connection successful
    ✓ PostgreSQL 14.2
    ✓ 1 active connection
    """
    try:
        config_mgr = ConfigManager()
        profile = config_mgr.get_profile(name)

        # Convertir a ConnectionConfig
        conn_config = config_mgr.get_connection_config(name)

        console.print(f"Testing connection to '[bold]{name}[/bold]'...")

        # TODO: Una vez que tengamos los adapters implementados:
        # 1. Crear instancia del adapter
        # 2. Llamar test_connection()
        # 3. Ejecutar query diagnóstica

        OutputFormatter.print_warning(
            "Adapters aún no implementados, saltando prueba de conexión"
        )
        OutputFormatter.print_info(
            f"Profile {name}: {profile.engine}@{profile.host}:{profile.port}"
        )

    except ProfileNotFoundError:
        OutputFormatter.print_error(f"Perfil '{name}' no encontrado")
        raise typer.Exit(code=1)
    except Exception as e:
        OutputFormatter.print_error(f"Error: {e}")
        raise typer.Exit(code=1)


@app.command()
def set_default(
    name: str = typer.Argument(..., help="Nombre del perfil"),
) -> None:
    """Establecer perfil por defecto."""
    try:
        config_mgr = ConfigManager()
        config_mgr.set_default_profile(name)
        OutputFormatter.print_success(f"Perfil default establecido a '{name}'")

    except ProfileNotFoundError:
        OutputFormatter.print_error(f"Perfil '{name}' no encontrado")
        raise typer.Exit(code=1)
    except Exception as e:
        OutputFormatter.print_error(f"Error: {e}")
        raise typer.Exit(code=1)


@app.command()
def delete(
    name: str = typer.Argument(..., help="Nombre del perfil a eliminar"),
    force: bool = typer.Option(False, "--force", "-f", help="Sin confirmación"),
) -> None:
    """Eliminar un perfil."""
    try:
        # Pedir confirmación si no hay --force
        if not force:
            if not Confirm.ask(f"¿Eliminar perfil '{name}'?"):
                OutputFormatter.print_info("Cancelado")
                return

        config_mgr = ConfigManager()
        config_mgr.delete_profile(name)
        OutputFormatter.print_success(f"Perfil '{name}' eliminado")

    except ProfileNotFoundError:
        OutputFormatter.print_error(f"Perfil '{name}' no encontrado")
        raise typer.Exit(code=1)
    except Exception as e:
        OutputFormatter.print_error(f"Error: {e}")
        raise typer.Exit(code=1)


@app.command()
def show(
    name: str = typer.Argument(..., help="Nombre del perfil"),
    show_password: bool = typer.Option(
        False, "--show-password", help="Mostrar password sin enmascarar"
    ),
) -> None:
    """
    Mostrar detalles de un perfil (sin password por defecto).
    """
    try:
        config_mgr = ConfigManager()
        config = config_mgr.load_config()
        profile = config_mgr.get_profile(name)

        is_default = name == config.default_profile
        console.print()
        console.print(
            OutputFormatter.format_profile(
                name, profile, is_default, mask_pwd=not show_password
            )
        )
        console.print()

    except ProfileNotFoundError:
        OutputFormatter.print_error(f"Perfil '{name}' no encontrado")
        raise typer.Exit(code=1)
    except Exception as e:
        OutputFormatter.print_error(f"Error: {e}")
        raise typer.Exit(code=1)
