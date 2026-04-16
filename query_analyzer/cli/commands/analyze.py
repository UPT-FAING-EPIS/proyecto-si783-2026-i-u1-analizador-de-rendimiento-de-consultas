"""CLI command for analyzing query performance."""

import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from query_analyzer.adapters import (
    AdapterRegistry,
    QueryAnalysisError,
    UnsupportedEngineError,
)
from query_analyzer.cli.utils import OutputFormatter
from query_analyzer.config import (
    ConfigManager,
    ConfigValidationError,
    ProfileNotFoundError,
)

console = Console()
err_console = Console(file=sys.stderr)


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════


def validate_query(query: str) -> None:
    """Validate SQL query syntax.

    Performs basic validation to catch common errors early:
    - Non-empty after whitespace stripping
    - Starts with SELECT, UPDATE, DELETE, INSERT, or WITH (case-insensitive)
    - No obvious multi-statement injection patterns

    Args:
        query: SQL query string to validate

    Raises:
        ValueError: If query is invalid with descriptive message

    Example:
        >>> validate_query("SELECT * FROM users")  # OK
        >>> validate_query("SELEC * FROM users")   # Raises ValueError
        >>> validate_query("")                      # Raises ValueError
    """
    query = query.strip()

    if not query:
        raise ValueError("Query cannot be empty")

    # Check valid SQL statement start
    valid_starts = ("SELECT", "UPDATE", "DELETE", "INSERT", "WITH")
    query_upper = query.upper()

    if not query_upper.startswith(valid_starts):
        raise ValueError(
            f"Query must start with {', '.join(valid_starts)}\nReceived: {query[:50]}..."
        )

    # Basic check for multi-statement injection (semicolon outside string/comment)
    # This is a simple heuristic; full parsing can be added later
    in_single_quote = False
    in_double_quote = False
    prev_char = ""

    for i, char in enumerate(query):
        if char == "'" and prev_char != "\\":
            in_single_quote = not in_single_quote
        elif char == '"' and prev_char != "\\":
            in_double_quote = not in_double_quote
        elif char == ";" and not in_single_quote and not in_double_quote and i < len(query) - 1:
            # Semicolon found before end of string (potential multi-statement)
            raise ValueError(
                "Multiple SQL statements not supported. "
                "Provide a single query.\n"
                f"Query: {query[:100]}..."
            )

        prev_char = char


def get_query_from_input(
    query_arg: str | None,
    file_path: Path | None,
) -> str:
    """Get query from argument, file, or stdin.

    Implements priority-based resolution with validation:
    1. Positional argument (highest priority)
    2. File path (if --file provided)
    3. stdin (lowest priority, if piped/redirected)

    Raises error if multiple sources provided.

    Args:
        query_arg: Positional argument (if provided)
        file_path: File path from --file option (if provided)

    Returns:
        Validated query string

    Raises:
        ValueError: If validation fails or multiple/no sources provided

    Example:
        >>> get_query_from_input("SELECT * FROM users", None)
        'SELECT * FROM users'

        >>> # With stdin piped
        >>> get_query_from_input(None, None)  # reads from stdin
        'SELECT * FROM orders'
    """
    # Count available sources
    stdin_available = not sys.stdin.isatty()
    sources_provided = sum([query_arg is not None, file_path is not None, stdin_available])

    if sources_provided == 0:
        raise ValueError(
            "No query provided.\n\n"
            "Use one of:\n"
            '  qa analyze "SELECT..."             # Positional argument\n'
            "  qa analyze --file query.sql          # From file\n"
            "  cat query.sql | qa analyze           # From stdin\n\n"
            "For help: qa analyze --help"
        )

    if sources_provided > 1:
        raise ValueError(
            "Query provided from multiple sources.\n\n"
            "Use exactly ONE of:\n"
            "  - Positional argument\n"
            "  - --file option\n"
            "  - stdin (piped or redirected)\n\n"
            "Example:\n"
            "  qa analyze --file query.sql          # File only\n"
            "  qa analyze < query.sql               # Stdin only"
        )

    # Get query from highest priority source
    if query_arg is not None:
        query = query_arg
    elif file_path is not None:
        try:
            query = file_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise ValueError(f"File not found: {file_path}") from None
        except PermissionError:
            raise ValueError(f"Permission denied: {file_path}\nTry: chmod +r {file_path}") from None
        except Exception as e:
            raise ValueError(f"Failed to read file: {file_path}\n{e}") from None
    else:
        # Read from stdin
        try:
            query = sys.stdin.read()
        except KeyboardInterrupt:
            raise ValueError("Interrupted while reading from stdin") from None
        except Exception as e:
            raise ValueError(f"Failed to read from stdin: {e}") from None

    # Validate the query
    validate_query(query)

    return query.strip()


def resolve_profile(
    explicit_profile: str | None,
) -> tuple[str, bool]:
    """Resolve which profile to use.

    Implements priority-based profile resolution:
    1. Explicit --profile option (if provided)
    2. Configured default_profile (if exists)
    3. Error if none found

    Args:
        explicit_profile: Value from --profile option (if provided)

    Returns:
        Tuple of (profile_name, is_default)
        - profile_name: Name of the profile to use
        - is_default: True if using the configured default profile

    Raises:
        ProfileNotFoundError: If no profile available
        ConfigValidationError: If config is invalid

    Example:
        >>> resolve_profile("staging")
        ('staging', False)

        >>> resolve_profile(None)  # Falls back to default
        ('production', True)
    """
    if explicit_profile:
        return explicit_profile, False

    try:
        config_mgr = ConfigManager()
        config = config_mgr.load_config()

        if config.default_profile:
            return config.default_profile, True

        raise ProfileNotFoundError(
            "No profile specified.\n\n"
            "No --profile provided and no default profile configured.\n\n"
            "Usage:\n"
            '  qa analyze --profile mydb "SELECT..."\n\n'
            "Or set a default profile:\n"
            "  qa profile set-default staging\n"
            '  qa analyze "SELECT..."\n\n'
            "To see configured profiles:\n"
            "  qa profile list"
        )

    except ConfigValidationError as e:
        raise ProfileNotFoundError(f"Configuration invalid: {e}") from e


def get_profile_details(profile_name: str) -> dict[str, Any]:
    """Get profile details for display and validation.

    Args:
        profile_name: Name of the profile

    Returns:
        Dictionary with profile details

    Raises:
        ProfileNotFoundError: If profile not found
        ConfigValidationError: If config invalid
    """
    try:
        config_mgr = ConfigManager()

        # Validate profile exists
        profile_config = config_mgr.get_profile(profile_name)

        # Get connection config (validates credentials, etc.)
        connection_config = config_mgr.get_connection_config(profile_name)

        return {
            "name": profile_name,
            "engine": profile_config.engine,
            "host": profile_config.host,
            "port": profile_config.port,
            "database": profile_config.database,
            "username": profile_config.username,
            "connection_config": connection_config,
        }

    except ProfileNotFoundError:
        # List available profiles for user
        config_mgr = ConfigManager()
        profiles = config_mgr.list_profiles()

        if profiles:
            profile_list = "\n".join([f"  • {name}" for name in profiles.keys()])
            raise ProfileNotFoundError(
                f"Profile '{profile_name}' not found.\n\n"
                f"Available profiles:\n{profile_list}\n\n"
                f"To create a new profile:\n"
                f"  qa profile add {profile_name} -e postgresql ...\n\n"
                f"To list all profiles:\n"
                f"  qa profile list"
            ) from None
        else:
            raise ProfileNotFoundError(
                f"Profile '{profile_name}' not found.\n\n"
                f"No profiles configured yet.\n\n"
                f"Create a profile:\n"
                f"  qa profile add {profile_name} -e postgresql -h localhost "
                f"-p 5432 -d mydb -u user -pw pass"
            ) from None

    except ConfigValidationError as e:
        raise ProfileNotFoundError(
            f"Profile validation failed: {e}\n\n"
            f"Check profile configuration:\n"
            f"  qa profile show {profile_name}"
        ) from e


def print_error_details(
    title: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Print formatted error message with optional details.

    Args:
        title: Error title
        message: Main error message
        details: Optional details dictionary
    """
    console.print(f"[red][ERROR][/red] {title}")
    console.print(f"{message}")

    if details:
        console.print("\nDetails:")
        for key, value in details.items():
            console.print(f"  {key}: {value}")


# ═══════════════════════════════════════════════════════════════
# MAIN COMMAND
# ═══════════════════════════════════════════════════════════════


def analyze(
    query: str | None = typer.Argument(None, help="SQL query string (or use --file or stdin)"),
    profile: str | None = typer.Option(
        None, "--profile", "-p", help="Profile name (uses default if omitted)"
    ),
    file: Path | None = typer.Option(None, "--file", "-f", help="Read query from file"),
    output: str = typer.Option("rich", "--output", "-o", help="Output format: rich|json|markdown"),
    timeout: int = typer.Option(
        30, "--timeout", "-t", help="Query timeout in seconds (default: 30)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output for debugging"),
) -> None:
    r"""Analyze database query performance using EXPLAIN.

    Query input (exactly one required):
    - Positional argument: qa analyze "SELECT..."
    - From file: qa analyze --file query.sql
    - From stdin: cat query.sql | qa analyze

    Profile selection:
    - Explicit: qa analyze --profile mydb "SELECT..."
    - Default: qa analyze "SELECT..."  (uses configured default)

    Output formats:
    - Rich table (default): qa analyze "SELECT..." --output rich
    - JSON (minified): qa analyze "SELECT..." --output json
    - Markdown: qa analyze "SELECT..." --output markdown

    Connection options:
    - Timeout: qa analyze "SELECT..." --timeout 60
    - Verbose: qa analyze "SELECT..." --verbose

    Examples:
        \b
        # Analyze with explicit profile
        $ qa analyze "SELECT * FROM users" --profile staging

        # Use default profile
        $ qa analyze "SELECT * FROM orders WHERE status = 'pending'"

        # From file with default profile
        $ qa analyze --file complex_query.sql

        # Via stdin with JSON output
        $ cat query.sql | qa analyze --output json | jq .

        # With custom timeout
        $ qa analyze "SELECT * FROM huge_table" --timeout 60

        # Verbose debugging
        $ qa analyze "SELECT * FROM orders" --verbose
    """
    try:
        # ═══════════════════════════════════════════════════════════
        # STEP 1: GET QUERY FROM INPUT
        # ═══════════════════════════════════════════════════════════
        if verbose:
            err_console.print("[blue][INFO][/blue] Parsing query input...")

        query_text = get_query_from_input(query, file)

        if verbose:
            err_console.print(f"[blue][INFO][/blue] Query received: {len(query_text)} chars")

        # ═══════════════════════════════════════════════════════════
        # STEP 2: RESOLVE PROFILE
        # ═══════════════════════════════════════════════════════════
        if verbose:
            err_console.print("[blue][INFO][/blue] Resolving profile...")

        profile_name, is_default = resolve_profile(profile)

        if verbose:
            profile_indicator = " (default)" if is_default else ""
            err_console.print(
                f"[blue][INFO][/blue] Using profile: {profile_name}{profile_indicator}"
            )

        # ═══════════════════════════════════════════════════════════
        # STEP 3: GET PROFILE DETAILS & VALIDATE
        # ═══════════════════════════════════════════════════════════
        if verbose:
            err_console.print("[blue][INFO][/blue] Loading profile configuration...")

        profile_details = get_profile_details(profile_name)

        if verbose:
            err_console.print(
                f"[blue][INFO][/blue] Engine: {profile_details['engine']} "
                f"@ {profile_details['host']}:{profile_details['port']}"
            )

        # ═══════════════════════════════════════════════════════════
        # STEP 4: CREATE ADAPTER
        # ═══════════════════════════════════════════════════════════
        if verbose:
            err_console.print("[blue][INFO][/blue] Creating adapter...")

        try:
            adapter = AdapterRegistry.create(
                profile_details["engine"],
                profile_details["connection_config"],
            )
        except UnsupportedEngineError:
            supported = ", ".join(AdapterRegistry.list_engines())
            print_error_details(
                "Unsupported Engine",
                f"Engine '{profile_details['engine']}' not supported for EXPLAIN analysis.\n\n"
                f"Supported engines:\n  {supported}",
                {
                    "Profile": profile_name,
                    "Engine": profile_details["engine"],
                },
            )
            raise typer.Exit(code=1) from None

        # ═══════════════════════════════════════════════════════════
        # STEP 5: CONNECT & EXECUTE
        # ═══════════════════════════════════════════════════════════
        if verbose:
            err_console.print(f"[blue][INFO][/blue] Connecting with {timeout}s timeout...")

        try:
            # TODO: Set timeout on adapter connection
            # For now, adapter manages its own timeout
            with adapter:
                if verbose:
                    err_console.print("[blue][INFO][/blue] Connection established")

                if verbose:
                    err_console.print("[blue][INFO][/blue] Executing EXPLAIN...")

                report = adapter.execute_explain(query_text)

                if verbose:
                    err_console.print(
                        f"[blue][INFO][/blue] Analysis complete: "
                        f"score={report.score}, "
                        f"warnings={len(report.warnings)}, "
                        f"recommendations={len(report.recommendations)}"
                    )

        except ConnectionError as e:
            print_error_details(
                "Connection Failed",
                str(e),
                {
                    "Profile": profile_name,
                    "Engine": profile_details["engine"],
                    "Host": f"{profile_details['host']}:{profile_details['port']}",
                    "Database": profile_details["database"],
                    "User": profile_details["username"],
                },
            )
            console.print(
                "\n[yellow]Troubleshooting:[/yellow]\n"
                f"  1. Check profile: qa profile show {profile_name}\n"
                f"  2. Test connection: qa profile test {profile_name}\n"
                f"  3. Verify credentials: qa profile show {profile_name} --show-password"
            )
            raise typer.Exit(code=1) from None

        except QueryAnalysisError as e:
            print_error_details(
                "Query Analysis Failed",
                f"Query execution failed: {e}",
                {
                    "Profile": profile_name,
                    "Query": query_text[:100] + ("..." if len(query_text) > 100 else ""),
                },
            )
            raise typer.Exit(code=1) from None

        except TimeoutError:
            print_error_details(
                "Connection Timeout",
                f"Query did not complete within {timeout} seconds.",
                {
                    "Profile": profile_name,
                    "Engine": profile_details["engine"],
                    "Host": f"{profile_details['host']}:{profile_details['port']}",
                },
            )
            console.print(
                "\n[yellow]Options:[/yellow]\n"
                f"  - Increase timeout: qa analyze ... --timeout {timeout * 2}\n"
                f"  - Check network connectivity\n"
                f"  - Verify database is running"
            )
            raise typer.Exit(code=1) from None

        # ═══════════════════════════════════════════════════════════
        # STEP 6: VALIDATE OUTPUT FORMAT
        # ═══════════════════════════════════════════════════════════
        valid_formats = ("rich", "json", "markdown")
        if output not in valid_formats:
            OutputFormatter.print_error(
                f"Invalid output format: '{output}'\n"
                f"Valid formats: {', '.join(valid_formats)}\n\n"
                f'Example: qa analyze "SELECT..." --output json'
            )
            raise typer.Exit(code=1)

        # ═══════════════════════════════════════════════════════════
        # STEP 7: FORMAT & PRINT OUTPUT
        # ═══════════════════════════════════════════════════════════
        if verbose:
            err_console.print(f"[blue][INFO][/blue] Formatting output as {output}...")

        OutputFormatter.print_report(
            report=report,
            format=output,
            profile_name=profile_name,
            is_default=is_default,
            verbose=verbose,
        )

        if verbose:
            err_console.print("[green][INFO][/green] Done!")

        raise typer.Exit(code=0)

    except ValueError as e:
        OutputFormatter.print_error(str(e))
        raise typer.Exit(code=1) from None

    except ProfileNotFoundError as e:
        OutputFormatter.print_error(str(e))
        raise typer.Exit(code=1) from None

    except ConfigValidationError as e:
        OutputFormatter.print_error(f"Configuration error: {e}")
        raise typer.Exit(code=1) from None

    except typer.Exit:
        raise

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        raise typer.Exit(code=130) from None

    except Exception as e:
        OutputFormatter.print_error(
            f"Unexpected error: {e}\n\n"
            "Please report this issue at: "
            "https://github.com/anomalyco/opencode"
        )
        if verbose:
            import traceback

            err_console.print(traceback.format_exc())
        raise typer.Exit(code=1) from None
