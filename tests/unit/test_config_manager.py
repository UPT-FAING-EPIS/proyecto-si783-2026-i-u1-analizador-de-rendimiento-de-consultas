"""Tests unitarios para ConfigManager."""

import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from pydantic import ValidationError

from query_analyzer.config import (
    AppConfig,
    AppDefaults,
    ConfigManager,
    ConfigValidationError,
    EnvVarNotFoundError,
    ProfileConfig,
    ProfileNotFoundError,
)
from query_analyzer.config.crypto import CryptoManager


@pytest.fixture
def temp_config_dir() -> Generator[Path, None, None]:
    """Crea directorio temporal para config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def config_manager(temp_config_dir: Path) -> ConfigManager:
    """Crea ConfigManager con directorio temporal."""
    config_path = temp_config_dir / "config.yaml"
    return ConfigManager(str(config_path))


@pytest.fixture
def sample_profile() -> ProfileConfig:
    """Crea un perfil de ejemplo."""
    return ProfileConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="testdb",
        username="testuser",
        password="testpass",
    )


# ============================================================================
# Tests: Creación automática de archivo
# ============================================================================


def test_config_file_created_if_not_exists(temp_config_dir: Path) -> None:
    """Verifica que el archivo de config se crea si no existe."""
    config_path = temp_config_dir / "config.yaml"
    assert not config_path.exists()

    # Crear ConfigManager (sin guardar)
    manager = ConfigManager(str(config_path))
    config = manager.load_config()

    assert config.profiles == {}
    assert not config_path.exists()  # Solo se crea al guardar


def test_config_saved_creates_file(
    temp_config_dir: Path, sample_profile: ProfileConfig
) -> None:
    """Verifica que guardar config crea el archivo."""
    config_path = temp_config_dir / "config.yaml"
    assert not config_path.exists()

    manager = ConfigManager(str(config_path))
    manager.add_profile("test", sample_profile)

    assert config_path.exists()


def test_config_dir_created_if_not_exists(temp_config_dir: Path) -> None:
    """Verifica que el directorio se crea si no existe."""
    nested_path = temp_config_dir / "nested" / "dir" / "config.yaml"
    assert not nested_path.parent.exists()

    ConfigManager(str(nested_path))

    assert nested_path.parent.exists()


# ============================================================================
# Tests: Carga de configuración
# ============================================================================


def test_load_empty_config(config_manager: ConfigManager) -> None:
    """Verifica carga de config vacía."""
    config = config_manager.load_config()

    assert isinstance(config, AppConfig)
    assert config.profiles == {}
    assert config.default_profile is None


def test_add_profile_valid(
    config_manager: ConfigManager, sample_profile: ProfileConfig
) -> None:
    """Verifica agregación de perfil válido."""
    config_manager.add_profile("local", sample_profile)

    # Recargar y verificar
    manager2 = ConfigManager(str(config_manager.config_path))
    profile = manager2.get_profile("local")

    assert profile.engine == "postgresql"
    assert profile.host == "localhost"


def test_add_profile_invalid_engine(config_manager: ConfigManager) -> None:
    """Verifica que rechaza engine inválido."""
    with pytest.raises(ValidationError):
        ProfileConfig(
            engine="oracle",  # No soportado
            host="localhost",
            port=1521,
            database="test",
            username="user",
            password="pass",
        )


def test_add_duplicate_profile_raises_error(
    config_manager: ConfigManager, sample_profile: ProfileConfig
) -> None:
    """Verifica que no se pueden agregar perfiles con el mismo nombre."""
    config_manager.add_profile("test", sample_profile)

    with pytest.raises(ConfigValidationError, match="ya existe"):
        config_manager.add_profile("test", sample_profile)


def test_get_profile_not_found(config_manager: ConfigManager) -> None:
    """Verifica error cuando perfil no existe."""
    with pytest.raises(ProfileNotFoundError, match="no encontrado"):
        config_manager.get_profile("nonexistent")


def test_list_profiles(
    config_manager: ConfigManager, sample_profile: ProfileConfig
) -> None:
    """Verifica listado de perfiles."""
    config_manager.add_profile("local", sample_profile)
    config_manager.add_profile("prod", sample_profile)

    profiles = config_manager.list_profiles()

    assert len(profiles) == 2
    assert "local" in profiles
    assert "prod" in profiles


def test_delete_profile(
    config_manager: ConfigManager, sample_profile: ProfileConfig
) -> None:
    """Verifica eliminación de perfil."""
    config_manager.add_profile("test", sample_profile)
    assert "test" in config_manager.list_profiles()

    config_manager.delete_profile("test")

    assert "test" not in config_manager.list_profiles()


def test_delete_nonexistent_profile(config_manager: ConfigManager) -> None:
    """Verifica error al eliminar perfil inexistente."""
    with pytest.raises(ProfileNotFoundError):
        config_manager.delete_profile("nonexistent")


# ============================================================================
# Tests: Interpolación de variables de entorno
# ============================================================================


def test_env_var_interpolation(temp_config_dir: Path) -> None:
    """Verifica interpolación de variables de entorno."""
    config_path = temp_config_dir / "config.yaml"

    # Crear archivo con variable de entorno
    config_yaml = """
profiles:
  prod-mysql:
    engine: mysql
    host: prod-db.example.com
    port: 3306
    database: myapp
    username: analyst
    password: "${MYSQL_PASSWORD}"
"""
    config_path.write_text(config_yaml)

    # Establecer variable
    os.environ["MYSQL_PASSWORD"] = "secretpass123"

    try:
        manager = ConfigManager(str(config_path))
        profile = manager.get_profile("prod-mysql")

        assert profile.password == "secretpass123"
    finally:
        del os.environ["MYSQL_PASSWORD"]


def test_env_var_with_default(temp_config_dir: Path) -> None:
    """Verifica variable de entorno con default."""
    config_path = temp_config_dir / "config.yaml"

    config_yaml = """
profiles:
  local:
    engine: postgresql
    host: localhost
    port: 5432
    database: testdb
    username: user
    password: "${DB_PASSWORD:-defaultpass}"
"""
    config_path.write_text(config_yaml)

    # Variable no existe, debe usar default
    if "DB_PASSWORD" in os.environ:
        del os.environ["DB_PASSWORD"]

    manager = ConfigManager(str(config_path))
    profile = manager.get_profile("local")

    assert profile.password == "defaultpass"


def test_env_var_not_found_raises_error(temp_config_dir: Path) -> None:
    """Verifica error cuando variable no existe y no hay default."""
    config_path = temp_config_dir / "config.yaml"

    config_yaml = """
profiles:
  test:
    engine: postgresql
    host: localhost
    port: 5432
    database: testdb
    username: user
    password: "${NONEXISTENT_VAR}"
"""
    config_path.write_text(config_yaml)

    # Asegurar que la variable no existe
    if "NONEXISTENT_VAR" in os.environ:
        del os.environ["NONEXISTENT_VAR"]

    with pytest.raises(EnvVarNotFoundError, match="no encontrada"):
        ConfigManager(str(config_path))


# ============================================================================
# Tests: Cifrado de credenciales
# ============================================================================


def test_password_encrypted_on_save(
    temp_config_dir: Path, sample_profile: ProfileConfig
) -> None:
    """Verifica que password se cifra al guardar."""
    config_path = temp_config_dir / "config.yaml"
    manager = ConfigManager(str(config_path))
    manager.add_profile("test", sample_profile)

    # Leer archivo directamente
    content = config_path.read_text()

    # Password no debe aparecer en texto plano
    assert "testpass" not in content
    # Pero debe tener prefijo "enc:"
    assert "enc:" in content


def test_password_decrypted_on_load(
    temp_config_dir: Path, sample_profile: ProfileConfig
) -> None:
    """Verifica que password se descifra al cargar."""
    config_path = temp_config_dir / "config.yaml"

    # Guardar con un manager
    manager1 = ConfigManager(str(config_path))
    manager1.add_profile("test", sample_profile)

    # Cargar con otro manager (para probar descifrado)
    manager2 = ConfigManager(str(config_path))
    profile = manager2.get_profile("test")

    # Password debe estar en claro en memoria
    assert profile.password == "testpass"


def test_password_in_memory_is_plain(
    config_manager: ConfigManager, sample_profile: ProfileConfig
) -> None:
    """Verifica que password en memoria está en claro (no cifrado)."""
    config_manager.add_profile("test", sample_profile)

    config = config_manager.load_config()
    profile = config.profiles["test"]

    # Debe ser el password original, no cifrado
    assert profile.password == "testpass"
    assert not profile.password.startswith("enc:")


# ============================================================================
# Tests: Default profile
# ============================================================================


def test_set_default_profile(
    config_manager: ConfigManager, sample_profile: ProfileConfig
) -> None:
    """Verifica establecimiento de perfil default."""
    config_manager.add_profile("local", sample_profile)
    config_manager.set_default_profile("local")

    config = config_manager.load_config()
    assert config.default_profile == "local"


def test_set_default_nonexistent_profile(config_manager: ConfigManager) -> None:
    """Verifica error al establecer default inexistente."""
    with pytest.raises(ProfileNotFoundError):
        config_manager.set_default_profile("nonexistent")


def test_get_default_profile(
    config_manager: ConfigManager, sample_profile: ProfileConfig
) -> None:
    """Verifica obtención de perfil default."""
    config_manager.add_profile("prod", sample_profile)
    config_manager.set_default_profile("prod")

    default = config_manager.get_default_profile()

    assert default is not None
    assert default.host == "localhost"


def test_get_default_profile_none(config_manager: ConfigManager) -> None:
    """Verifica que retorna None si no hay default."""
    default = config_manager.get_default_profile()
    assert default is None


def test_delete_default_profile_clears_default(
    config_manager: ConfigManager, sample_profile: ProfileConfig
) -> None:
    """Verifica que eliminar default profile limpia la configuración."""
    config_manager.add_profile("test", sample_profile)
    config_manager.set_default_profile("test")

    config_manager.delete_profile("test")

    config = config_manager.load_config()
    assert config.default_profile is None


# ============================================================================
# Tests: Conversión a ConnectionConfig
# ============================================================================


def test_get_connection_config(
    config_manager: ConfigManager, sample_profile: ProfileConfig
) -> None:
    """Verifica conversión a ConnectionConfig."""
    config_manager.add_profile("test", sample_profile)

    conn_config = config_manager.get_connection_config("test")

    assert conn_config.engine == "postgresql"
    assert conn_config.host == "localhost"
    assert conn_config.port == 5432
    assert conn_config.database == "testdb"
    assert conn_config.username == "testuser"
    assert conn_config.password == "testpass"


def test_get_connection_config_nonexistent(config_manager: ConfigManager) -> None:
    """Verifica error al convertir perfil inexistente."""
    with pytest.raises(ProfileNotFoundError):
        config_manager.get_connection_config("nonexistent")


# ============================================================================
# Tests: Configuración con defaults
# ============================================================================


def test_app_defaults_values(config_manager: ConfigManager) -> None:
    """Verifica valores default de AppDefaults."""
    defaults = config_manager.get_defaults()

    assert defaults.slow_query_threshold_ms == 1000
    assert defaults.explain_format == "json"
    assert defaults.output_format == "rich"


def test_custom_config_path_via_env(
    temp_config_dir: Path, sample_profile: ProfileConfig
) -> None:
    """Verifica override de ruta con variable de entorno."""
    config_path = temp_config_dir / "custom.yaml"

    # Establecer variable de entorno
    old_path = os.environ.get("QA_CONFIG_PATH")
    os.environ["QA_CONFIG_PATH"] = str(config_path)

    try:
        manager = ConfigManager()
        manager.add_profile("test", sample_profile)

        assert config_path.exists()
    finally:
        # Restaurar variable
        if old_path:
            os.environ["QA_CONFIG_PATH"] = old_path
        else:
            del os.environ["QA_CONFIG_PATH"]
