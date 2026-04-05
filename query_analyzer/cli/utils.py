"""Utilidades para la interfaz CLI."""

from rich.console import Console
from rich.table import Table

from query_analyzer.config import ProfileConfig

console = Console()


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
        default_marker = " [bold green]✓ (default)[/bold green]" if is_default else ""
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
        """Imprime mensaje de éxito con check verde."""
        console.print(f"[green]✓[/green] {message}")

    @staticmethod
    def print_error(message: str) -> None:
        """Imprime mensaje de error con X roja."""
        console.print(f"[red]✗[/red] {message}")

    @staticmethod
    def print_info(message: str) -> None:
        """Imprime mensaje informativo."""
        console.print(f"[blue]ℹ[/blue] {message}")

    @staticmethod
    def print_warning(message: str) -> None:
        """Imprime mensaje de warning."""
        console.print(f"[yellow]⚠[/yellow] {message}")

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
        table = Table(title="Perfiles de Conexión", show_header=True, header_style="bold")
        table.add_column("Nombre", style="cyan")
        table.add_column("Engine", style="magenta")
        table.add_column("Host", style="green")
        table.add_column("Database", style="yellow")
        table.add_column("Usuario", style="blue")

        for name, profile in profiles.items():
            default_marker = "✓" if name == default_profile else ""
            table.add_row(
                f"{name} {default_marker}",
                profile.engine,
                f"{profile.host}:{profile.port}",
                profile.database,
                profile.username,
            )

        return table
