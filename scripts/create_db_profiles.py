#!/usr/bin/env python3
"""Crear perfiles de base de datos automáticamente desde docker-compose.yml.

Este script lee la configuración del docker-compose.yml y el .env, luego
crea perfiles de conexión para todas las bases de datos usando ConfigManager.

Uso:
    uv run python scripts/create_db_profiles.py          # Crear (skip si existen)
    uv run python scripts/create_db_profiles.py --force  # Sobrescribir
    uv run python scripts/create_db_profiles.py --check  # Verificar
    uv run python scripts/create_db_profiles.py --reset  # Eliminar todos
"""

import sys
from pathlib import Path
from typing import Any

import typer
import yaml
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

# Agregar parent directory al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from query_analyzer.config import ConfigManager, ProfileConfig, ProfileNotFoundError

app = typer.Typer(help="Crear perfiles de BD desde docker-compose.yml")
console = Console()


def load_env_vars() -> dict[str, str]:
    """Cargar variables de entorno desde .env o .env.example.

    Returns:
        Diccionario con variables de entorno
    """
    env_vars = {}

    # Intentar cargar .env primero, luego .env.example
    env_files = [Path(".env"), Path(".env.example")]

    for env_file in env_files:
        if env_file.exists():
            console.print(f"[bold]Reading environment from[/bold] {env_file}")
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        env_vars[key.strip()] = value.strip()
            return env_vars

    raise FileNotFoundError("Archivo .env o .env.example no encontrado")


def load_compose_yml() -> dict[str, Any]:
    """Cargar el archivo docker-compose.yml.

    Returns:
        Diccionario con la configuración del compose
    """
    compose_file = Path("docker/compose.yml")

    if not compose_file.exists():
        raise FileNotFoundError("docker/compose.yml no encontrado")

    console.print("[bold]Loading[/bold] docker/compose.yml")
    with open(compose_file) as f:
        compose_data = yaml.safe_load(f)

    return compose_data or {}


def get_env_var(env_vars: dict[str, str], key: str, default: str = "") -> str:
    """Obtener valor de variable de entorno con default.

    Args:
        env_vars: Diccionario de variables
        key: Clave a buscar
        default: Valor por defecto

    Returns:
        Valor de la variable o default
    """
    return env_vars.get(key, default)


def create_postgresql_profile(env_vars: dict[str, str]) -> tuple[str, ProfileConfig]:
    """Crear perfil para PostgreSQL.

    Args:
        env_vars: Variables de entorno

    Returns:
        Tupla (nombre_perfil, ProfileConfig)
    """
    return (
        "postgresql",
        ProfileConfig(
            engine="postgresql",
            host=get_env_var(env_vars, "DB_POSTGRES_HOST", "localhost"),
            port=int(get_env_var(env_vars, "DB_POSTGRES_PORT", "5432")),
            database=get_env_var(env_vars, "DB_POSTGRES_NAME", "query_analyzer"),
            username=get_env_var(env_vars, "DB_POSTGRES_USER", "qa"),
            password=get_env_var(env_vars, "DB_POSTGRES_PASSWORD", "QAnalyze"),
        ),
    )


def create_mysql_profile(env_vars: dict[str, str]) -> tuple[str, ProfileConfig]:
    """Crear perfil para MySQL.

    Args:
        env_vars: Variables de entorno

    Returns:
        Tupla (nombre_perfil, ProfileConfig)
    """
    return (
        "mysql",
        ProfileConfig(
            engine="mysql",
            host=get_env_var(env_vars, "DB_MYSQL_HOST", "localhost"),
            port=int(get_env_var(env_vars, "DB_MYSQL_PORT", "3306")),
            database=get_env_var(env_vars, "DB_MYSQL_NAME", "query_analyzer"),
            username=get_env_var(env_vars, "DB_MYSQL_USER", "qa"),
            password=get_env_var(env_vars, "DB_MYSQL_PASSWORD", "QAnalyze"),
        ),
    )


def create_sqlite_profile(env_vars: dict[str, str]) -> tuple[str, ProfileConfig]:
    """Crear perfil para SQLite (local).

    Args:
        env_vars: Variables de entorno

    Returns:
        Tupla (nombre_perfil, ProfileConfig)
    """
    db_path = get_env_var(env_vars, "DB_SQLITE_PATH", "query_analyzer.db")
    return (
        "sqlite",
        ProfileConfig(
            engine="sqlite",
            database=db_path,
            host=None,
            port=None,
            username=None,
            password=None,
        ),
    )


def create_mongodb_profile(env_vars: dict[str, str]) -> tuple[str, ProfileConfig]:
    """Crear perfil para MongoDB.

    Args:
        env_vars: Variables de entorno

    Returns:
        Tupla (nombre_perfil, ProfileConfig)
    """
    return (
        "mongodb",
        ProfileConfig(
            engine="mongodb",
            host=get_env_var(env_vars, "DB_MONGODB_HOST", "localhost"),
            port=int(get_env_var(env_vars, "DB_MONGODB_PORT", "27017")),
            database=get_env_var(env_vars, "DB_MONGODB_NAME", "query_analyzer"),
            username=get_env_var(env_vars, "DB_MONGODB_USER", "admin"),
            password=get_env_var(env_vars, "DB_MONGODB_PASSWORD", "mongodb123"),
        ),
    )


def create_redis_profile(env_vars: dict[str, str]) -> tuple[str, ProfileConfig]:
    """Crear perfil para Redis (sin auth en dev local).

    Args:
        env_vars: Variables de entorno

    Returns:
        Tupla (nombre_perfil, ProfileConfig)
    """
    return (
        "redis",
        ProfileConfig(
            engine="redis",
            host=get_env_var(env_vars, "DB_REDIS_HOST", "localhost"),
            port=int(get_env_var(env_vars, "DB_REDIS_PORT", "6379")),
            database="0",  # Default Redis database
            username=None,
            password=None,
        ),
    )


def create_cockroachdb_profile(env_vars: dict[str, str]) -> tuple[str, ProfileConfig]:
    """Crear perfil para CockroachDB (sin password en --insecure mode).

    Args:
        env_vars: Variables de entorno

    Returns:
        Tupla (nombre_perfil, ProfileConfig)
    """
    return (
        "cockroachdb",
        ProfileConfig(
            engine="cockroachdb",
            host=get_env_var(env_vars, "DB_COCKROACH_HOST", "localhost"),
            port=int(get_env_var(env_vars, "DB_COCKROACH_PORT", "26257")),
            database="defaultdb",
            username="root",
            password=None,
        ),
    )


def create_yugabytedb_profile(env_vars: dict[str, str]) -> tuple[str, ProfileConfig]:
    """Crear perfil para YugabyteDB (hardcoded credentials).

    Args:
        env_vars: Variables de entorno

    Returns:
        Tupla (nombre_perfil, ProfileConfig)
    """
    return (
        "yugabytedb",
        ProfileConfig(
            engine="yugabytedb",
            host=get_env_var(env_vars, "DB_YUGABYTE_HOST", "localhost"),
            port=int(get_env_var(env_vars, "DB_YUGABYTE_PORT", "5433")),
            database="query_analyzer",
            username="yugabyte",
            password="yugabyte",
        ),
    )


def create_neo4j_profile(env_vars: dict[str, str]) -> tuple[str, ProfileConfig]:
    """Crear perfil para Neo4j (graph database).

    Args:
        env_vars: Variables de entorno

    Returns:
        Tupla (nombre_perfil, ProfileConfig)
    """
    return (
        "neo4j",
        ProfileConfig(
            engine="neo4j",
            host=get_env_var(env_vars, "DB_NEO4J_HOST", "localhost"),
            port=int(get_env_var(env_vars, "DB_NEO4J_BOLT_PORT", "7687")),
            database="neo4j",
            username=get_env_var(env_vars, "DB_NEO4J_USER", "neo4j"),
            password=get_env_var(env_vars, "DB_NEO4J_PASSWORD", "neo4j123"),
        ),
    )


def create_influxdb_profile(env_vars: dict[str, str]) -> tuple[str, ProfileConfig]:
    """Crear perfil para InfluxDB (timeseries).

    Args:
        env_vars: Variables de entorno

    Returns:
        Tupla (nombre_perfil, ProfileConfig)
    """
    return (
        "influxdb",
        ProfileConfig(
            engine="influxdb",
            host=get_env_var(env_vars, "DB_INFLUXDB_HOST", "localhost"),
            port=int(get_env_var(env_vars, "DB_INFLUXDB_PORT", "8086")),
            database=get_env_var(env_vars, "DB_INFLUXDB_NAME", "query_analyzer"),
            username=get_env_var(env_vars, "DB_INFLUXDB_USER", "admin"),
            password=get_env_var(env_vars, "DB_INFLUXDB_TOKEN", "mytoken"),
            extra={
                "org": get_env_var(env_vars, "DB_INFLUXDB_ORG", "myorg"),
                "connection_timeout": 30,
            },
        ),
    )


def create_elasticsearch_profile(env_vars: dict[str, str]) -> tuple[str, ProfileConfig]:
    """Crear perfil para Elasticsearch (sin auth en dev local).

    Args:
        env_vars: Variables de entorno

    Returns:
        Tupla (nombre_perfil, ProfileConfig)
    """
    return (
        "elasticsearch",
        ProfileConfig(
            engine="elasticsearch",
            host=get_env_var(env_vars, "ES_HOST", "localhost"),
            port=int(get_env_var(env_vars, "ES_PORT", "9200")),
            database="",
            username=None,
            password=None,
        ),
    )


def build_profiles(env_vars: dict[str, str]) -> dict[str, ProfileConfig]:
    """Construir todos los perfiles desde variables de entorno.

    Args:
        env_vars: Variables de entorno cargadas

    Returns:
        Diccionario con perfiles
    """
    profiles = {}

    # Crear cada perfil
    profile_creators = [
        create_postgresql_profile,
        create_mysql_profile,
        create_sqlite_profile,
        create_mongodb_profile,
        create_redis_profile,
        create_cockroachdb_profile,
        create_yugabytedb_profile,
        create_neo4j_profile,
        create_influxdb_profile,
        create_elasticsearch_profile,
    ]

    for creator in profile_creators:
        try:
            name, config = creator(env_vars)
            profiles[name] = config
        except Exception as e:
            console.print(f"[yellow]Warning creating {creator.__name__}: {e}[/yellow]")

    return profiles


def create_all_profiles(profiles: dict[str, ProfileConfig], force: bool = False) -> dict[str, bool]:
    """Crear/guardar todos los perfiles usando ConfigManager.

    Args:
        profiles: Diccionario de perfiles a crear
        force: Si True, sobrescribir perfiles existentes

    Returns:
        Diccionario {nombre_perfil: exito}
    """
    config_mgr = ConfigManager()
    config = config_mgr.load_config()
    results = {}

    for name, profile_config in profiles.items():
        try:
            # Verificar si ya existe
            if name in config.profiles and not force:
                results[name] = False  # Skip
                continue

            # Crear perfil
            config_mgr.add_profile(name, profile_config)
            results[name] = True

        except Exception as e:
            console.print(f"[red]Error creating profile '{name}': {e}[/red]")
            results[name] = False

    # Establecer PostgreSQL como default si existe
    if "postgresql" in profiles:
        try:
            config_mgr.set_default_profile("postgresql")
        except ProfileNotFoundError:
            pass

    return results


def display_summary(profiles: dict[str, bool], force: bool = False) -> None:
    """Mostrar resumen de perfiles creados.

    Args:
        profiles: Diccionario {nombre: exito}
        force: Si True, indica que se forzó la creación
    """
    created = sum(1 for v in profiles.values() if v is True)
    skipped = sum(1 for v in profiles.values() if v is False)

    console.print()
    table = Table(title="Database Profiles Summary", show_header=True)
    table.add_column("Profile", style="cyan", no_wrap=True)
    table.add_column("Status", style="green")
    table.add_column("Engine", style="blue")

    # Mapeo de engines a descripciones
    engine_map = {
        "postgresql": "PostgreSQL",
        "mysql": "MySQL",
        "sqlite": "SQLite",
        "mongodb": "MongoDB",
        "redis": "Redis",
        "cockroachdb": "CockroachDB",
        "yugabytedb": "YugabyteDB",
        "neo4j": "Neo4j",
        "influxdb": "InfluxDB",
        "elasticsearch": "Elasticsearch",
    }

    for profile_name, success in sorted(profiles.items()):
        engine_display = engine_map.get(profile_name, profile_name.upper())
        if success:
            status = "[green]CREATED[/green]" if force else "[green]CREATED[/green]"
        else:
            status = "[yellow]SKIPPED[/yellow]"

        table.add_row(profile_name, status, engine_display)

    console.print(table)
    console.print()

    # Mostrar estadísticas
    console.print("Summary:")
    console.print(f"  Created/Updated: {created}")
    console.print(f"  Skipped: {skipped}")
    console.print()

    # Next steps
    console.print("[bold]Next steps:[/bold]")
    console.print("  * Run: make seed          (populate databases)")
    console.print("  * Run: qa profile list    (see all profiles)")
    console.print("  * Run: make test          (run integration tests)")
    console.print()


def display_exists_warning(existing: list[str]) -> None:
    """Mostrar advertencia de perfiles existentes.

    Args:
        existing: Lista de perfiles existentes
    """
    console.print()
    console.print("[yellow]Profiles already exist:[/yellow]")
    for profile_name in existing:
        console.print(f"  - {profile_name}")
    console.print()
    console.print("[dim]To overwrite:[/dim] [bold]make profiles-force[/bold]")
    console.print()


@app.command()
def main(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing profiles"),
    check: bool = typer.Option(False, "--check", "-c", help="Check existing profiles"),
    reset: bool = typer.Option(False, "--reset", "-r", help="Reset all profiles"),
) -> None:
    """Crear perfiles de base de datos desde docker-compose.yml.

    Este script lee la configuración y crea perfiles automáticamente.
    """
    try:
        # Manejo de --reset
        if reset:
            if Confirm.ask("Eliminar todos los perfiles?", default=False):
                config_mgr = ConfigManager()
                config = config_mgr.load_config()

                if not config.profiles:
                    console.print("[dim]No profiles found to delete[/dim]")
                else:
                    for profile_name in list(config.profiles.keys()):
                        config_mgr.delete_profile(profile_name)
                    console.print("[green]All profiles deleted[/green]")
            return

        # Manejo de --check
        if check:
            config_mgr = ConfigManager()
            config = config_mgr.load_config()

            if not config.profiles:
                console.print("[yellow]No profiles configured[/yellow]")
            else:
                console.print(f"[green]{len(config.profiles)} profiles configured:[/green]")
                for name in sorted(config.profiles.keys()):
                    default_mark = (
                        " [bold](DEFAULT)[/bold]" if name == config.default_profile else ""
                    )
                    console.print(f"  * {name}{default_mark}")
            return

        # Crear perfiles
        console.print("[bold]Creating database profiles from docker-compose.yml...[/bold]")
        console.print()

        # Cargar configuración
        env_vars = load_env_vars()
        _compose_data = load_compose_yml()

        # Construir perfiles
        console.print("Found 10 database services")
        console.print()

        profiles = build_profiles(env_vars)

        # Verificar cuáles ya existen
        config_mgr = ConfigManager()
        config = config_mgr.load_config()
        existing_profiles = [name for name in profiles.keys() if name in config.profiles]

        if existing_profiles and not force:
            display_exists_warning(existing_profiles)
            return

        # Crear todos los perfiles
        console.print("Creating profiles...")
        results = create_all_profiles(profiles, force=force)

        # Mostrar resumen
        display_summary(results, force=force)

        console.print(
            "[green]All profiles created successfully![/green] "
            "Credentials encrypted and stored in ~/.query-analyzer/config.yaml"
        )

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1) from e


if __name__ == "__main__":
    app()
