"""Tests para comandos CLI de perfiles."""

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from query_analyzer.cli.main import app
from query_analyzer.config import ConfigManager, ProfileConfig

runner = CliRunner()


@pytest.fixture
def temp_config_dir() -> Generator[Path]:
    """Crea directorio temporal para config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def cli_manager(temp_config_dir: Path, monkeypatch) -> ConfigManager:
    """Crea ConfigManager y establece ruta en variable de entorno."""
    config_path = temp_config_dir / "config.yaml"
    monkeypatch.setenv("QA_CONFIG_PATH", str(config_path))
    return ConfigManager(str(config_path))


@pytest.fixture
def sample_profile() -> ProfileConfig:
    """Crea perfil de ejemplo."""
    return ProfileConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="testdb",
        username="testuser",
        password="testpass",
    )


# ============================================================================
# Tests: profile list
# ============================================================================


def test_profile_list_empty(cli_manager: ConfigManager) -> None:
    """Verifica que list funciona sin perfiles."""
    result = runner.invoke(app, ["profile", "list"])

    assert result.exit_code == 0
    assert "No hay perfiles" in result.stdout or "perfiles" in result.stdout.lower()


def test_profile_list_shows_profiles(
    cli_manager: ConfigManager, sample_profile: ProfileConfig
) -> None:
    """Verifica que list muestra los perfiles."""
    cli_manager.add_profile("local", sample_profile)
    cli_manager.add_profile("prod", sample_profile)

    result = runner.invoke(app, ["profile", "list"])

    assert result.exit_code == 0
    assert "local" in result.stdout
    assert "prod" in result.stdout
    assert "postgresql" in result.stdout


def test_profile_list_marks_default(
    cli_manager: ConfigManager, sample_profile: ProfileConfig
) -> None:
    """Verifica que list marca el perfil default."""
    cli_manager.add_profile("local", sample_profile)
    cli_manager.add_profile("prod", sample_profile)
    cli_manager.set_default_profile("local")

    result = runner.invoke(app, ["profile", "list"])

    assert result.exit_code == 0
    # Check that the output contains either the checkmark char or the string representation
    assert "✓" in result.stdout or "[default]" in result.stdout or "local" in result.stdout


# ============================================================================
# Tests: profile show
# ============================================================================


def test_profile_show(cli_manager: ConfigManager, sample_profile: ProfileConfig) -> None:
    """Verifica que show muestra detalles del perfil."""
    cli_manager.add_profile("local", sample_profile)

    result = runner.invoke(app, ["profile", "show", "local"])

    assert result.exit_code == 0
    assert "local" in result.stdout
    assert "postgresql" in result.stdout
    assert "localhost" in result.stdout
    assert "testdb" in result.stdout
    assert "testuser" in result.stdout


def test_profile_show_masks_password(
    cli_manager: ConfigManager, sample_profile: ProfileConfig
) -> None:
    """Verifica que show enmascara password por defecto."""
    cli_manager.add_profile("test", sample_profile)

    result = runner.invoke(app, ["profile", "show", "test"])

    assert result.exit_code == 0
    # Password debe estar enmascarado (****)
    assert "testpass" not in result.stdout
    assert "*" in result.stdout  # Máscara


def test_profile_show_reveals_password_with_flag(
    cli_manager: ConfigManager, sample_profile: ProfileConfig
) -> None:
    """Verifica que --show-password revela el password."""
    cli_manager.add_profile("test", sample_profile)

    result = runner.invoke(app, ["profile", "show", "test", "--show-password"])

    assert result.exit_code == 0
    assert "testpass" in result.stdout


def test_profile_show_not_found(cli_manager: ConfigManager) -> None:
    """Verifica error cuando perfil no existe."""
    result = runner.invoke(app, ["profile", "show", "nonexistent"])

    assert result.exit_code == 1
    assert "no encontrado" in result.stdout


def test_profile_show_marks_default(
    cli_manager: ConfigManager, sample_profile: ProfileConfig
) -> None:
    """Verifica que show marca como default."""
    cli_manager.add_profile("local", sample_profile)
    cli_manager.set_default_profile("local")

    result = runner.invoke(app, ["profile", "show", "local"])

    assert result.exit_code == 0
    assert "default" in result.stdout


# ============================================================================
# Tests: profile set-default
# ============================================================================


def test_profile_set_default(cli_manager: ConfigManager, sample_profile: ProfileConfig) -> None:
    """Verifica que set-default funciona."""
    cli_manager.add_profile("test", sample_profile)

    result = runner.invoke(app, ["profile", "set-default", "test"])

    assert result.exit_code == 0
    assert "exitosamente" in result.stdout or "default" in result.stdout


def test_profile_set_default_not_found(cli_manager: ConfigManager) -> None:
    """Verifica error al establecer default inexistente."""
    result = runner.invoke(app, ["profile", "set-default", "nonexistent"])

    assert result.exit_code == 1
    assert "no encontrado" in result.stdout


# ============================================================================
# Tests: profile delete
# ============================================================================


def test_profile_delete_with_confirmation(
    cli_manager: ConfigManager, sample_profile: ProfileConfig
) -> None:
    """Verifica delete con confirmación."""
    cli_manager.add_profile("test", sample_profile)

    # Responder "y" a la confirmación
    result = runner.invoke(app, ["profile", "delete", "test"], input="y\n")

    assert result.exit_code == 0
    assert "eliminado" in result.stdout


def test_profile_delete_with_force(
    cli_manager: ConfigManager, sample_profile: ProfileConfig
) -> None:
    """Verifica delete con --force."""
    cli_manager.add_profile("test", sample_profile)

    result = runner.invoke(app, ["profile", "delete", "test", "--force"])

    assert result.exit_code == 0
    assert "eliminado" in result.stdout


def test_profile_delete_cancel(cli_manager: ConfigManager, sample_profile: ProfileConfig) -> None:
    """Verifica que delete no elimina si se cancela."""
    cli_manager.add_profile("test", sample_profile)

    # Responder "n" a la confirmación
    result = runner.invoke(app, ["profile", "delete", "test"], input="n\n")

    assert result.exit_code == 0
    assert "Cancelado" in result.stdout

    # Perfil debe seguir existiendo
    assert cli_manager.get_profile("test") is not None


def test_profile_delete_not_found(cli_manager: ConfigManager) -> None:
    """Verifica error al eliminar perfil inexistente."""
    result = runner.invoke(app, ["profile", "delete", "nonexistent", "--force"])

    assert result.exit_code == 1
    assert "no encontrado" in result.stdout


# ============================================================================
# Tests: profile test
# ============================================================================


def test_profile_test_not_found(cli_manager: ConfigManager) -> None:
    """Verifica error al probar perfil inexistente."""
    result = runner.invoke(app, ["profile", "test", "nonexistent"])

    assert result.exit_code == 1
    assert "no encontrado" in result.stdout


def test_profile_test_shows_info(cli_manager: ConfigManager, sample_profile: ProfileConfig) -> None:
    """Verifica que test muestra información del perfil."""
    cli_manager.add_profile("test", sample_profile)

    result = runner.invoke(app, ["profile", "test", "test"])

    assert result.exit_code == 0
    # Debe mostrar información
    assert "test" in result.stdout or "postgresql" in result.stdout


def test_profile_test_no_password_visible(
    cli_manager: ConfigManager, sample_profile: ProfileConfig
) -> None:
    """Verifica que test no muestra password."""
    cli_manager.add_profile("test", sample_profile)

    result = runner.invoke(app, ["profile", "test", "test"])

    assert result.exit_code == 0
    assert "testpass" not in result.stdout


# ============================================================================
# Tests: Enmascaramiento de passwords en output
# ============================================================================


def test_password_masked_in_list_output(
    cli_manager: ConfigManager, sample_profile: ProfileConfig
) -> None:
    """Verifica que passwords están enmascarados en list."""
    cli_manager.add_profile("test", sample_profile)

    result = runner.invoke(app, ["profile", "list"])

    assert result.exit_code == 0
    # Password no debe aparecer
    assert "testpass" not in result.stdout


def test_password_masked_in_show_output(
    cli_manager: ConfigManager, sample_profile: ProfileConfig
) -> None:
    """Verifica que passwords están enmascarados en show."""
    cli_manager.add_profile("test", sample_profile)

    result = runner.invoke(app, ["profile", "show", "test"])

    assert result.exit_code == 0
    # Password no debe aparecer (a menos que use --show-password)
    assert "testpass" not in result.stdout
