"""Tests unitarios para el servicio de diagnóstico de conexiones."""

import socket
from unittest.mock import MagicMock, patch

from query_analyzer.adapters.models import ConnectionConfig
from query_analyzer.core.connection_diagnostics import (
    ConnectionDiagnosticsService,
)


def test_sanitize_secrets() -> None:
    """Verifica que el sanitizador de secretos oculte correctamente contraseñas y tokens."""
    config = ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="mydb",
        username="postgres",
        password="mysecretpassword",
        extra={"api_key": "secret_token_123"},
    )

    raw_text = (
        "Failed to connect using user postgres with password mysecretpassword: "
        "auth token secret_token_123 was invalid."
    )
    sanitized = ConnectionDiagnosticsService.sanitize_secrets(raw_text, config)

    assert "mysecretpassword" not in sanitized
    assert "secret_token_123" not in sanitized
    assert "********" in sanitized


def test_configuration_validation_checks() -> None:
    """Verifica que fallos de configuración sean diagnosticados adecuadamente."""
    # Falta host en motor de red
    config = ConnectionConfig(
        engine="postgresql",
        host=None,
        port=5432,
        database="mydb",
    )

    diagnostic = ConnectionDiagnosticsService.run_diagnostics("test_profile", config)

    assert diagnostic.status == "configuration_error"
    assert diagnostic.checks[0].status == "failed"
    assert "requiere un host" in diagnostic.checks[0].message
    # Otras comprobaciones no se ejecutan pero deben estar en skipped para mantener salida estable
    assert len(diagnostic.checks) == 4
    for check in diagnostic.checks[1:]:
        assert check.status == "skipped"


@patch("socket.getaddrinfo")
def test_network_tcp_failure(mock_getaddrinfo: MagicMock) -> None:
    """Verifica que fallos de resolución de DNS y de conexión TCP sean diagnosticados."""
    config = ConnectionConfig(
        engine="postgresql",
        host="invalid-host-name",
        port=5432,
        database="mydb",
    )

    # Simular fallo de DNS (gaierror)
    mock_getaddrinfo.side_effect = socket.gaierror(-2, "Name or service not known")

    diagnostic = ConnectionDiagnosticsService.run_diagnostics("test_profile", config)

    assert diagnostic.status == "service_unreachable"
    # Configuración exitosa, TCP fallido
    assert diagnostic.checks[0].status == "success"
    assert diagnostic.checks[1].status == "failed"
    assert "No se pudo resolver" in diagnostic.checks[1].message
    # Comprobaciones posteriores deben estar en 'skipped'
    assert diagnostic.checks[2].status == "skipped"
    assert diagnostic.checks[3].status == "skipped"


@patch("socket.getaddrinfo")
@patch("socket.socket")
@patch("query_analyzer.core.connection_diagnostics.AdapterRegistry")
def test_postgresql_authentication_failure(
    mock_registry: MagicMock, mock_socket_class: MagicMock, mock_getaddrinfo: MagicMock
) -> None:
    """Verifica la clasificación precisa de fallos de autenticación de PostgreSQL."""
    config = ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="mydb",
        username="wrong_user",
        password="wrong_password",
    )

    # Configurar mocks de red para que pasen exitosamente
    mock_getaddrinfo.return_value = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 5432))
    ]
    mock_socket = MagicMock()
    mock_socket_class.return_value = mock_socket

    # Configurar mock del adapter para que lance error de auth
    mock_adapter = MagicMock()
    import psycopg2

    class MockOperationalError(psycopg2.OperationalError):
        def __init__(self, message: str, pgcode: str) -> None:
            super().__init__(message)
            self._pgcode = pgcode

        @property
        def pgcode(self) -> str:
            return self._pgcode

    exc = MockOperationalError('password authentication failed for user "wrong_user"', "28P01")
    mock_adapter.connect.side_effect = exc
    mock_registry.is_registered.return_value = True
    mock_registry.create.return_value = mock_adapter

    diagnostic = ConnectionDiagnosticsService.run_diagnostics("test_profile", config)

    assert diagnostic.status == "authentication_failed"
    assert diagnostic.checks[0].status == "success"  # Config
    assert diagnostic.checks[1].status == "success"  # Red TCP
    assert diagnostic.checks[2].status == "failed"  # Driver Connection (auth)
    assert diagnostic.checks[3].status == "skipped"  # Operatividad
    assert "autenticación" in diagnostic.safe_message.lower()


@patch("socket.getaddrinfo")
@patch("socket.socket")
@patch("query_analyzer.core.connection_diagnostics.AdapterRegistry")
def test_mysql_database_missing_failure(
    mock_registry: MagicMock, mock_socket_class: MagicMock, mock_getaddrinfo: MagicMock
) -> None:
    """Verifica la clasificación precisa de base de datos inexistente en MySQL."""
    config = ConnectionConfig(
        engine="mysql",
        host="localhost",
        port=3306,
        database="nonexistent_db",
        username="root",
        password="password",
    )

    # Configurar mocks de red
    mock_getaddrinfo.return_value = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 3306))
    ]
    mock_socket = MagicMock()
    mock_socket_class.return_value = mock_socket

    # Mock del adapter de MySQL fallando con error 1049 (Unknown database)
    mock_adapter = MagicMock()
    import pymysql

    exc = pymysql.err.OperationalError(1049, "Unknown database 'nonexistent_db'")
    mock_adapter.connect.side_effect = exc
    mock_registry.is_registered.return_value = True
    mock_registry.create.return_value = mock_adapter

    diagnostic = ConnectionDiagnosticsService.run_diagnostics("test_profile", config)

    assert diagnostic.status == "database_missing"
    assert diagnostic.checks[2].status == "failed"
    assert "no existe" in diagnostic.safe_message.lower()


@patch("socket.getaddrinfo")
@patch("socket.socket")
@patch("query_analyzer.core.connection_diagnostics.AdapterRegistry")
def test_diagnostics_success(
    mock_registry: MagicMock, mock_socket_class: MagicMock, mock_getaddrinfo: MagicMock
) -> None:
    """Verifica el flujo completo exitoso de diagnóstico de conexión."""
    config = ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="mydb",
        username="postgres",
        password="password",
    )

    # Configurar mocks de red
    mock_getaddrinfo.return_value = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 5432))
    ]
    mock_socket = MagicMock()
    mock_socket_class.return_value = mock_socket

    # Mock del adapter exitoso
    mock_adapter = MagicMock()
    mock_adapter.test_connection.return_value = True
    mock_registry.is_registered.return_value = True
    mock_registry.create.return_value = mock_adapter

    diagnostic = ConnectionDiagnosticsService.run_diagnostics("test_profile", config)

    assert diagnostic.status == "connected"
    assert len(diagnostic.checks) == 4
    for check in diagnostic.checks:
        assert check.status == "success"
    assert diagnostic.safe_message == "Conexión exitosa"
    mock_adapter.disconnect.assert_called_once()


def test_unknown_error_never_leaks_password_in_safe_message() -> None:
    """Verifica que unknown_error use un mensaje fijo y no filtre contraseñas."""
    config = ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="mydb",
        username="postgres",
        password="supersecretpassword",
    )

    # Lanzar una excepción genérica que contiene la contraseña
    exc = Exception("Some unknown error occurred with secret password supersecretpassword here")
    status, safe_message = ConnectionDiagnosticsService._classify_error(config.engine, exc)

    assert status == "unknown_error"
    assert "supersecretpassword" not in safe_message
    assert safe_message == "Error de conexión inesperado."


def test_unknown_error_sanitizes_technical_detail() -> None:
    """Verifica que technical_detail sea debidamente sanitizado en unknown_error."""
    config = ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="mydb",
        username="postgres",
        password="supersecretpassword",
    )

    raw_detail = "Error detail: password=supersecretpassword"
    sanitized = ConnectionDiagnosticsService.sanitize_secrets(raw_detail, config)

    assert "supersecretpassword" not in sanitized
    assert "password=********" in sanitized


def test_sanitizes_short_secret_and_connection_uri() -> None:
    """Verifica la sanitización de secretos cortos (1-2 caracteres) y URIs de conexión."""
    config = ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="mydb",
        username="postgres",
        password="x",  # Contraseña de 1 caracter
        extra={"api_key": "ab"},  # Token extra de 2 caracteres
    )

    # Texto de prueba con URI, Bearer token, password= y secretos cortos
    raw_text = (
        "Connection URI is postgresql://postgres:x@localhost:5432/mydb. "
        "Error in password=x. Authorization: Bearer ab. "
        "Let's see if x is replaced and ab is replaced."
    )

    sanitized = ConnectionDiagnosticsService.sanitize_secrets(raw_text, config)

    # No deben aparecer los secretos individuales
    # Pero no debe destruir palabras que contengan "x" o "ab" si son parte de otra palabra
    assert "postgres:x" not in sanitized
    assert "password=x" not in sanitized
    assert "Bearer ab" not in sanitized
    assert "postgres:********" in sanitized
    assert "password=********" in sanitized
    assert "Bearer ********" in sanitized

    # Las palabras normales "Connection", "localhost", "replaced" no deben ser destruidas
    assert "Connection" in sanitized
    assert "localhost" in sanitized
    assert "replaced" in sanitized


def test_timeout_error_is_classified_as_timeout() -> None:
    """Verifica que TimeoutError sea clasificado como timeout."""
    exc = TimeoutError("Connection timed out after 10 seconds")
    status, safe_message = ConnectionDiagnosticsService._classify_error("postgresql", exc)
    assert status == "timeout"
    assert "Tiempo de espera agotado" in safe_message


def test_socket_timeout_is_classified_as_timeout() -> None:
    """Verifica que socket.timeout sea clasificado como timeout."""
    exc = TimeoutError("timed out")
    status, safe_message = ConnectionDiagnosticsService._classify_error("postgresql", exc)
    assert status == "timeout"
    assert "Tiempo de espera agotado" in safe_message


@patch("query_analyzer.core.connection_diagnostics.AdapterRegistry")
def test_adapter_disconnects_when_connect_raises(mock_registry: MagicMock) -> None:
    """Verifica que se llame a disconnect cuando connect lanza una excepción."""
    config = ConnectionConfig(
        engine="sqlite",
        database="mydb",
    )

    mock_adapter = MagicMock()
    mock_adapter.connect.side_effect = Exception("Connect failed partially")
    mock_registry.is_registered.return_value = True
    mock_registry.create.return_value = mock_adapter

    diagnostic = ConnectionDiagnosticsService.run_diagnostics("test_profile", config)

    # Debe intentar conectarse
    mock_adapter.connect.assert_called_once()
    # Y debe invocar disconnect para limpiar recursos parcialmente asignados
    mock_adapter.disconnect.assert_called_once()
    assert diagnostic.status == "unknown_error"


def test_checked_at_and_durations_format() -> None:
    """Verifica que checked_at tenga zona UTC y duración sea no negativa."""
    config = ConnectionConfig(
        engine="sqlite",
        database=":memory:",
    )

    diagnostic = ConnectionDiagnosticsService.run_diagnostics("sqlite_test", config)

    from datetime import UTC

    assert diagnostic.checked_at is not None
    assert diagnostic.checked_at.tzinfo == UTC
    assert diagnostic.duration_ms >= 0.0


def test_all_defined_statuses() -> None:
    """Verifica la clasificación para cada uno de los estados posibles definidos."""
    # connected
    # service_unreachable
    # authentication_failed
    # database_missing
    # timeout
    # configuration_error
    # unknown_error

    # 1. connected (tested in test_diagnostics_success)
    # 2. configuration_error (tested in test_configuration_validation_checks)

    # 3. service_unreachable
    exc = Exception("connection refused")
    status, _ = ConnectionDiagnosticsService._classify_error("postgresql", exc)
    assert status == "service_unreachable"

    # 4. authentication_failed
    exc = Exception("28P01: password authentication failed")
    status, _ = ConnectionDiagnosticsService._classify_error("postgresql", exc)
    assert status == "authentication_failed"

    # 5. database_missing
    exc = Exception("3D000: database does not exist")
    status, _ = ConnectionDiagnosticsService._classify_error("postgresql", exc)
    assert status == "database_missing"

    # 6. timeout
    exc = TimeoutError("timed out")
    status, _ = ConnectionDiagnosticsService._classify_error("postgresql", exc)
    assert status == "timeout"

    # 7. unknown_error
    exc = Exception("something completely random")
    status, _ = ConnectionDiagnosticsService._classify_error("postgresql", exc)
    assert status == "unknown_error"
