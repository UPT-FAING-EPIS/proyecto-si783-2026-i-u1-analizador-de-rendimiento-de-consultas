"""Interactive prompts module for Query Analyzer CLI.

Provides reusable interactive components for gathering user input with validation,
defaults, and error recovery. All prompts follow these patterns:
- Graceful degradation: if a value is provided, return it immediately
- Interactive mode: if value is None, prompt the user with defaults
- Validation: validate during input and re-prompt on error
- Guidance: show defaults, examples, and helpful hints
"""

from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt

from query_analyzer.cli.utils import OutputFormatter
from query_analyzer.config import ConfigManager, ProfileConfig, ProfileNotFoundError

console = Console()


# ═══════════════════════════════════════════════════════════════
# DATABASE CONNECTION PROMPTS
# ═══════════════════════════════════════════════════════════════


def engine_selector(engine: str | None = None) -> str:
    """Prompt for database engine selection.

    If engine is provided, returns it immediately (non-interactive).
    Otherwise, shows a menu of supported engines.

    Args:
        engine: Engine name if already provided via CLI args

    Returns:
        Selected engine name ('postgresql', 'mysql', 'sqlite', 'cockroachdb',
        'yugabytedb')

    Example:
        >>> engine_selector()  # Interactive
        Engine [postgresql]: mysql
        'mysql'

        >>> engine_selector("postgresql")  # Non-interactive
        'postgresql'
    """
    if engine is not None:
        return engine

    engines = ["postgresql", "mysql", "sqlite", "cockroachdb", "yugabytedb"]
    selected: str = Prompt.ask(
        "Engine",
        choices=engines,
        default="postgresql",
    )
    return selected


def host_prompt(host: str | None = None) -> str:
    """Prompt for database host.

    If host is provided, returns it immediately (non-interactive).
    Otherwise, prompts with 'localhost' as default.

    Args:
        host: Host name/IP if already provided via CLI args

    Returns:
        Host name or IP address

    Example:
        >>> host_prompt()  # Interactive
        Host [localhost]: prod-db.example.com
        'prod-db.example.com'
    """
    if host is not None:
        return host

    return Prompt.ask("Host", default="localhost")


def port_prompt_with_validation(
    port: int | None = None,
    engine: str | None = None,
) -> int:
    """Prompt for database port with validation.

    If port is provided, returns it immediately (non-interactive).
    Otherwise, prompts with engine-aware default and validates range (1-65535).
    Re-prompts on invalid input.

    Args:
        port: Port number if already provided via CLI args
        engine: Database engine (used to set smart default)

    Returns:
        Valid port number (1-65535)

    Raises:
        ValueError: If max retries exceeded (unlikely with IntPrompt)

    Example:
        >>> port_prompt_with_validation(None, "postgresql")  # Interactive
        Port [5432]: invalid
        Please enter a valid integer
        Port [5432]: 5432
        5432

        >>> port_prompt_with_validation(3306, "mysql")  # Non-interactive
        3306
    """
    if port is not None:
        if not (1 <= port <= 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {port}")
        return port

    # Determine smart default based on engine
    default_ports = {
        "postgresql": 5432,
        "mysql": 3306,
        "sqlite": 0,  # N/A for SQLite
        "cockroachdb": 26257,
        "yugabytedb": 5433,
    }
    default_port = default_ports.get(engine or "postgresql", 5432)

    while True:
        try:
            port_value: int = IntPrompt.ask(
                "Port",
                default=default_port,
            )
            if not (1 <= port_value <= 65535):
                OutputFormatter.print_error("Port must be between 1 and 65535")
                continue
            return port_value
        except ValueError:
            OutputFormatter.print_error("Please enter a valid number")
            continue


def database_prompt(database: str | None = None) -> str:
    """Prompt for database name (required).

    If database is provided, returns it immediately (non-interactive).
    Otherwise, prompts (no default). Re-prompts if empty.

    Args:
        database: Database name if already provided via CLI args

    Returns:
        Non-empty database name

    Example:
        >>> database_prompt()  # Interactive
        Database: myapp_db
        'myapp_db'

        >>> database_prompt("myapp_db")  # Non-interactive
        'myapp_db'
    """
    if database is not None and database.strip():
        return database.strip()

    while True:
        db_name: str = Prompt.ask("Database")
        if db_name.strip():
            return db_name.strip()
        OutputFormatter.print_error("Database name cannot be empty")


def username_prompt(
    username: str | None = None,
    engine: str | None = None,
) -> str:
    """Prompt for database username with engine-aware default.

    If username is provided, returns it immediately (non-interactive).
    Otherwise, prompts with engine-aware default.

    Args:
        username: Username if already provided via CLI args
        engine: Database engine (used to set smart default)

    Returns:
        Username string

    Example:
        >>> username_prompt(None, "postgresql")  # Interactive
        Username [postgres]: analyst
        'analyst'

        >>> username_prompt("myuser", "mysql")  # Non-interactive
        'myuser'
    """
    if username is not None:
        return username

    # Smart defaults based on engine
    default_users = {
        "postgresql": "postgres",
        "mysql": "root",
        "sqlite": "sqlite",
        "cockroachdb": "root",
        "yugabytedb": "postgres",
    }
    default_user = default_users.get(engine or "postgresql", "postgres")

    return Prompt.ask("Username", default=default_user)


def password_prompt(
    password: str | None = None,
    require_confirmation: bool = False,
) -> str:
    """Prompt for password (hidden input).

    If password is provided, returns it immediately (non-interactive).
    Otherwise, prompts with password masking. Optionally requires
    confirmation re-entry for password security.

    Args:
        password: Password if already provided via CLI args
        require_confirmation: If True, ask to re-enter password for confirmation

    Returns:
        Password string

    Example:
        >>> password_prompt()  # Interactive, single entry
        Password (hidden):
        'my_secret_password'

        >>> password_prompt(require_confirmation=True)  # Interactive, with confirmation
        Password (hidden):
        Confirm Password (hidden):
        'my_secret_password'
    """
    if password is not None:
        return password

    while True:
        pwd: str = Prompt.ask("Password", password=True)

        if require_confirmation:
            pwd_confirm: str = Prompt.ask("Confirm Password", password=True)
            if pwd != pwd_confirm:
                OutputFormatter.print_error("Passwords do not match")
                continue

        return pwd


def confirm_deletion(resource_name: str) -> bool:
    """Prompt for confirmation before deleting a resource.

    Shows a confirmation dialog with the resource name. Default is 'N' (no).

    Args:
        resource_name: Name of the resource to delete (e.g., profile name)

    Returns:
        True if user confirms deletion, False otherwise

    Example:
        >>> confirm_deletion("staging")  # Interactive
        Delete resource 'staging'? [y/N]: y
        True

        >>> confirm_deletion("production")  # Interactive
        Delete resource 'production'? [y/N]: n
        False
    """
    return Confirm.ask(f"¿Eliminar {resource_name}?", default=False)


# ═══════════════════════════════════════════════════════════════
# PROFILE & MENU PROMPTS
# ═══════════════════════════════════════════════════════════════


def select_profile_from_menu(profile_name: str | None = None) -> str:
    """Prompt to select a profile from a numbered menu.

    If profile_name is provided, returns it immediately (non-interactive).
    Otherwise, shows a table of all configured profiles and lets user
    select by number.

    Args:
        profile_name: Profile name if already provided via CLI args

    Returns:
        Selected profile name

    Raises:
        ProfileNotFoundError: If no profiles exist or selection invalid

    Example:
        >>> select_profile_from_menu()  # Interactive
        Perfiles Disponibles:
        1. local-dev (postgresql)
        2. staging (mysql)
        3. production (postgresql) [DEFAULT]

        Seleccionar perfil [1-3]: 2
        'staging'
    """
    if profile_name is not None:
        return profile_name

    try:
        config_mgr = ConfigManager()
        profiles = config_mgr.list_profiles()

        if not profiles:
            raise ProfileNotFoundError("No hay perfiles configurados")

        # Get config to find default profile
        config = config_mgr.load_config()

        # Create numbered list for user selection
        console.print()
        OutputFormatter.print_info("Perfiles Disponibles:")
        console.print()

        profile_list = list(profiles.items())
        for idx, (name, profile) in enumerate(profile_list, start=1):
            is_default = name == config.default_profile
            default_marker = " [DEFAULT]" if is_default else ""
            console.print(f"  {idx}. {name} ({profile.engine}){default_marker}")

        console.print()

        # Prompt for selection
        while True:
            try:
                choice: int = IntPrompt.ask(
                    "Seleccionar perfil",
                    default=1,
                )
                if 1 <= choice <= len(profile_list):
                    selected_name, _ = profile_list[choice - 1]
                    return selected_name
                else:
                    OutputFormatter.print_error(
                        f"Seleccione un número entre 1 y {len(profile_list)}"
                    )
            except ValueError:
                OutputFormatter.print_error("Por favor ingrese un número válido")

    except ProfileNotFoundError as e:
        raise e
    except Exception as e:
        raise ProfileNotFoundError(f"Error al listar perfiles: {e}") from e


def query_input_prompt(query: str | None = None) -> str:
    """Prompt for SQL query input in interactive mode.

    If query is provided, returns it immediately (non-interactive).
    Otherwise, prompts for multiline query input with hints.

    This is used as a fallback when query is not provided via positional arg,
    --file, or stdin. Shows helpful hints for entering multi-line queries.

    Args:
        query: Query string if already provided via CLI args

    Returns:
        Validated SQL query string

    Raises:
        ValueError: If query is empty or invalid

    Example:
        >>> query_input_prompt()  # Interactive
        Ingrese su consulta SQL (termine con Ctrl+D en Unix o Ctrl+Z en Windows):
        SELECT * FROM users
        WHERE created_at > NOW() - INTERVAL '1 day'

        'SELECT * FROM users WHERE created_at > ...'
    """
    if query is not None and query.strip():
        return query.strip()

    console.print()
    OutputFormatter.print_info(
        "Ingrese su consulta SQL (termine con Ctrl+D en Unix o Ctrl+Z en Windows):"
    )
    console.print()

    lines: list[str] = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass

    query_text = "\n".join(lines).strip()

    if not query_text:
        raise ValueError("La consulta no puede estar vacía")

    return query_text


# ═══════════════════════════════════════════════════════════════
# PROFILE CREATION HELPER
# ═══════════════════════════════════════════════════════════════


def interactive_profile_config(
    engine: str | None = None,
    host: str | None = None,
    port: int | None = None,
    database: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> ProfileConfig:
    """Gather all connection config interactively or from args.

    This is a convenience function that prompts for missing connection
    parameters and returns a ProfileConfig object ready to be saved.

    Uses graceful degradation: if all args are provided, returns immediately
    without any prompts. If any are missing, prompts for those specific values.

    Args:
        engine: Database engine (if provided, skip prompt)
        host: Host name/IP (if provided, skip prompt)
        port: Port number (if provided, skip prompt)
        database: Database name (if provided, skip prompt)
        username: Username (if provided, skip prompt)
        password: Password (if provided, skip prompt)

    Returns:
        ProfileConfig object with all connection details

    Raises:
        ValueError: If any validation fails

    Example:
        >>> config = interactive_profile_config()  # All prompts
        >>> config = interactive_profile_config("postgresql", "localhost")  # Skip 2 prompts
    """
    # Gather engine first (needed for smart defaults)
    selected_engine = engine_selector(engine)

    # Gather remaining parameters with engine-aware defaults
    selected_host = host_prompt(host)
    selected_port = port_prompt_with_validation(port, selected_engine)
    selected_database = database_prompt(database)
    selected_username = username_prompt(username, selected_engine)
    selected_password = password_prompt(password, require_confirmation=False)

    return ProfileConfig(
        engine=selected_engine,
        host=selected_host,
        port=selected_port,
        database=selected_database,
        username=selected_username,
        password=selected_password,
    )
