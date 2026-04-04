"""Tests unitarios para AdapterRegistry."""

import pytest
from typing import Any

from query_analyzer.adapters import (
    AdapterRegistry,
    BaseAdapter,
    ConnectionConfig,
    QueryAnalysisReport,
    UnsupportedEngineError,
)


# ============================================================================
# MOCK ADAPTERS PARA TESTING
# ============================================================================


class MockPostgreSQLAdapter(BaseAdapter):
    """Mock PostgreSQL adapter para testing."""

    def connect(self) -> None:
        self._is_connected = True
        self._connection = {"type": "postgresql"}

    def disconnect(self) -> None:
        self._is_connected = False
        self._connection = None

    def test_connection(self) -> bool:
        return self._is_connected

    def execute_explain(self, query: str) -> QueryAnalysisReport:
        return QueryAnalysisReport(
            engine="postgresql",
            query=query,
            score=80,
            execution_time_ms=100.0,
        )

    def get_slow_queries(self, threshold_ms: int = 1000) -> list[dict[str, Any]]:
        return []

    def get_metrics(self) -> dict[str, Any]:
        return {}

    def get_engine_info(self) -> dict[str, str]:
        return {"engine": "postgresql", "version": "16"}


class MockMySQLAdapter(BaseAdapter):
    """Mock MySQL adapter para testing."""

    def connect(self) -> None:
        self._is_connected = True
        self._connection = {"type": "mysql"}

    def disconnect(self) -> None:
        self._is_connected = False
        self._connection = None

    def test_connection(self) -> bool:
        return self._is_connected

    def execute_explain(self, query: str) -> QueryAnalysisReport:
        return QueryAnalysisReport(
            engine="mysql",
            query=query,
            score=75,
            execution_time_ms=150.0,
        )

    def get_slow_queries(self, threshold_ms: int = 1000) -> list[dict[str, Any]]:
        return []

    def get_metrics(self) -> dict[str, Any]:
        return {}

    def get_engine_info(self) -> dict[str, str]:
        return {"engine": "mysql", "version": "8"}


class InvalidAdapter:
    """Clase que NO hereda de BaseAdapter (para testing de validación)."""

    pass


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def clean_registry():
    """Limpia el registry antes de cada test."""
    AdapterRegistry._registry.clear()
    yield
    AdapterRegistry._registry.clear()


@pytest.fixture
def sample_config() -> ConnectionConfig:
    """Configuración de conexión válida para testing."""
    return ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="testdb",
        username="user",
        password="pass",
    )


# ============================================================================
# TESTS
# ============================================================================


class TestAdapterRegistryRegister:
    """Tests para el método register (decorador)."""

    def test_register_adapter_with_decorator(self, clean_registry):
        """Registrar adapter usando decorador @register."""

        @AdapterRegistry.register("postgresql")
        class TestAdapter(BaseAdapter):
            def connect(self) -> None:
                pass

            def disconnect(self) -> None:
                pass

            def test_connection(self) -> bool:
                return False

            def execute_explain(self, query: str) -> QueryAnalysisReport:
                return QueryAnalysisReport(engine="postgresql", query=query, score=0)

            def get_slow_queries(
                self, threshold_ms: int = 1000
            ) -> list[dict[str, Any]]:
                return []

            def get_metrics(self) -> dict[str, Any]:
                return {}

            def get_engine_info(self) -> dict[str, str]:
                return {}

        assert "postgresql" in AdapterRegistry._registry
        assert AdapterRegistry._registry["postgresql"] is TestAdapter

    def test_register_validates_inheritance(self, clean_registry):
        """Registrar clase que NO hereda de BaseAdapter lanza TypeError."""
        with pytest.raises(TypeError, match="debe heredar de BaseAdapter"):

            @AdapterRegistry.register("invalid")
            class NotAnAdapter:
                pass

    def test_register_case_insensitive(self, clean_registry, sample_config):
        """Register es case-insensitive (postgresql == POSTGRESQL)."""
        AdapterRegistry._registry["postgresql"] = MockPostgreSQLAdapter

        assert AdapterRegistry.is_registered("postgresql")
        assert AdapterRegistry.is_registered("PostgreSQL")
        assert AdapterRegistry.is_registered("POSTGRESQL")

    def test_register_overwrites_existing(self, clean_registry):
        """Re-registrar un motor sobrescribe la clase anterior."""
        AdapterRegistry._registry["test"] = MockPostgreSQLAdapter

        @AdapterRegistry.register("test")
        class NewAdapter(BaseAdapter):
            def connect(self) -> None:
                pass

            def disconnect(self) -> None:
                pass

            def test_connection(self) -> bool:
                return False

            def execute_explain(self, query: str) -> QueryAnalysisReport:
                return QueryAnalysisReport(engine="test", query=query, score=0)

            def get_slow_queries(
                self, threshold_ms: int = 1000
            ) -> list[dict[str, Any]]:
                return []

            def get_metrics(self) -> dict[str, Any]:
                return {}

            def get_engine_info(self) -> dict[str, str]:
                return {}

        assert AdapterRegistry._registry["test"] is NewAdapter


class TestAdapterRegistryCreate:
    """Tests para el método create (factory)."""

    def test_create_adapter_success(self, clean_registry, sample_config):
        """Crear adapter existente retorna instancia correcta."""
        AdapterRegistry._registry["postgresql"] = MockPostgreSQLAdapter

        adapter = AdapterRegistry.create("postgresql", sample_config)

        assert isinstance(adapter, MockPostgreSQLAdapter)
        assert adapter._config == sample_config

    def test_create_adapter_case_insensitive(self, clean_registry, sample_config):
        """Create es case-insensitive."""
        AdapterRegistry._registry["postgresql"] = MockPostgreSQLAdapter

        adapter1 = AdapterRegistry.create("postgresql", sample_config)
        adapter2 = AdapterRegistry.create("PostgreSQL", sample_config)
        adapter3 = AdapterRegistry.create("POSTGRESQL", sample_config)

        assert isinstance(adapter1, MockPostgreSQLAdapter)
        assert isinstance(adapter2, MockPostgreSQLAdapter)
        assert isinstance(adapter3, MockPostgreSQLAdapter)

    def test_create_adapter_unsupported_engine(self, clean_registry, sample_config):
        """Create lanza UnsupportedEngineError si motor no existe."""
        with pytest.raises(UnsupportedEngineError):
            AdapterRegistry.create("nonexistent", sample_config)

    def test_create_passes_config_correctly(self, clean_registry, sample_config):
        """Create pasa la config correctamente al adapter."""
        AdapterRegistry._registry["postgresql"] = MockPostgreSQLAdapter

        adapter = AdapterRegistry.create("postgresql", sample_config)

        assert adapter._config.engine == "postgresql"
        assert adapter._config.host == "localhost"
        assert adapter._config.port == 5432
        assert adapter._config.database == "testdb"

    def test_create_multiple_adapters_different_configs(self, clean_registry):
        """Create múltiples adapters con diferentes configs."""
        AdapterRegistry._registry["postgresql"] = MockPostgreSQLAdapter
        AdapterRegistry._registry["mysql"] = MockMySQLAdapter

        config_pg = ConnectionConfig(
            engine="postgresql",
            host="pg-host",
            port=5432,
            database="pg_db",
            username="pg_user",
            password="pg_pass",
        )
        config_mysql = ConnectionConfig(
            engine="mysql",
            host="mysql-host",
            port=3306,
            database="mysql_db",
            username="mysql_user",
            password="mysql_pass",
        )

        adapter_pg = AdapterRegistry.create("postgresql", config_pg)
        adapter_mysql = AdapterRegistry.create("mysql", config_mysql)

        assert isinstance(adapter_pg, MockPostgreSQLAdapter)
        assert isinstance(adapter_mysql, MockMySQLAdapter)
        assert adapter_pg._config.host == "pg-host"
        assert adapter_mysql._config.host == "mysql-host"


class TestAdapterRegistryErrors:
    """Tests para manejo de errores."""

    def test_unsupported_engine_error_includes_available(
        self, clean_registry, sample_config
    ):
        """UnsupportedEngineError incluye lista de motores disponibles."""
        AdapterRegistry._registry["postgresql"] = MockPostgreSQLAdapter
        AdapterRegistry._registry["mysql"] = MockMySQLAdapter

        with pytest.raises(UnsupportedEngineError) as exc_info:
            AdapterRegistry.create("oracle", sample_config)

        error = exc_info.value
        assert error.engine_name == "oracle"
        assert "mysql" in error.available_engines
        assert "postgresql" in error.available_engines
        assert "oracle" not in error.available_engines

    def test_unsupported_engine_error_message_format(
        self, clean_registry, sample_config
    ):
        """Mensaje de error es descriptivo."""
        AdapterRegistry._registry["postgresql"] = MockPostgreSQLAdapter

        with pytest.raises(UnsupportedEngineError) as exc_info:
            AdapterRegistry.create("unknown", sample_config)

        error_msg = str(exc_info.value)
        assert "unknown" in error_msg
        assert "no soportado" in error_msg or "not supported" in error_msg
        assert "postgresql" in error_msg

    def test_unsupported_engine_error_empty_available(
        self, clean_registry, sample_config
    ):
        """Error con lista vacía de disponibles."""
        with pytest.raises(UnsupportedEngineError) as exc_info:
            AdapterRegistry.create("any", sample_config)

        error_msg = str(exc_info.value)
        assert "any" in error_msg
        assert "Disponibles" in error_msg or "Available" in error_msg


class TestAdapterRegistryList:
    """Tests para list_engines."""

    def test_list_engines_empty(self, clean_registry):
        """List retorna lista vacía al inicio."""
        engines = AdapterRegistry.list_engines()
        assert engines == []

    def test_list_engines_after_registration(self, clean_registry):
        """List retorna motores registrados en orden alfabético."""
        AdapterRegistry._registry["postgresql"] = MockPostgreSQLAdapter
        AdapterRegistry._registry["mysql"] = MockMySQLAdapter

        engines = AdapterRegistry.list_engines()

        assert engines == ["mysql", "postgresql"]

    def test_list_engines_sorted(self, clean_registry):
        """List retorna motores en orden alfabético."""
        AdapterRegistry._registry["z_engine"] = MockPostgreSQLAdapter
        AdapterRegistry._registry["a_engine"] = MockMySQLAdapter
        AdapterRegistry._registry["m_engine"] = MockPostgreSQLAdapter

        engines = AdapterRegistry.list_engines()

        assert engines == ["a_engine", "m_engine", "z_engine"]

    def test_list_engines_lowercase(self, clean_registry):
        """List retorna nombres en lowercase."""
        AdapterRegistry._registry["postgresql"] = MockPostgreSQLAdapter

        engines = AdapterRegistry.list_engines()

        assert engines == ["postgresql"]
        assert all(e.islower() for e in engines)


class TestAdapterRegistryIsRegistered:
    """Tests para is_registered."""

    def test_is_registered_true(self, clean_registry):
        """is_registered retorna True si motor existe."""
        AdapterRegistry._registry["postgresql"] = MockPostgreSQLAdapter

        assert AdapterRegistry.is_registered("postgresql") is True

    def test_is_registered_false(self, clean_registry):
        """is_registered retorna False si motor no existe."""
        assert AdapterRegistry.is_registered("postgresql") is False

    def test_is_registered_case_insensitive(self, clean_registry):
        """is_registered es case-insensitive."""
        AdapterRegistry._registry["postgresql"] = MockPostgreSQLAdapter

        assert AdapterRegistry.is_registered("postgresql") is True
        assert AdapterRegistry.is_registered("PostgreSQL") is True
        assert AdapterRegistry.is_registered("POSTGRESQL") is True
        assert AdapterRegistry.is_registered("PostgresQL") is True

    def test_is_registered_multiple_engines(self, clean_registry):
        """is_registered con múltiples motores registrados."""
        AdapterRegistry._registry["postgresql"] = MockPostgreSQLAdapter
        AdapterRegistry._registry["mysql"] = MockMySQLAdapter

        assert AdapterRegistry.is_registered("postgresql") is True
        assert AdapterRegistry.is_registered("mysql") is True
        assert AdapterRegistry.is_registered("mongodb") is False


class TestAdapterRegistryIntegration:
    """Tests de integración."""

    def test_full_workflow_register_and_create(self, clean_registry, sample_config):
        """Flujo completo: registrar, listar y crear."""

        @AdapterRegistry.register("postgresql")
        class PGAdapter(BaseAdapter):
            def connect(self) -> None:
                pass

            def disconnect(self) -> None:
                pass

            def test_connection(self) -> bool:
                return False

            def execute_explain(self, query: str) -> QueryAnalysisReport:
                return QueryAnalysisReport(engine="postgresql", query=query, score=0)

            def get_slow_queries(
                self, threshold_ms: int = 1000
            ) -> list[dict[str, Any]]:
                return []

            def get_metrics(self) -> dict[str, Any]:
                return {}

            def get_engine_info(self) -> dict[str, str]:
                return {}

        assert AdapterRegistry.is_registered("postgresql")
        assert "postgresql" in AdapterRegistry.list_engines()

        adapter = AdapterRegistry.create("postgresql", sample_config)
        assert isinstance(adapter, PGAdapter)

    def test_adapter_functionality_after_creation(self, clean_registry, sample_config):
        """Adapter creado funciona correctamente."""
        AdapterRegistry._registry["postgresql"] = MockPostgreSQLAdapter

        adapter = AdapterRegistry.create("postgresql", sample_config)

        assert not adapter.is_connected()
        adapter.connect()
        assert adapter.is_connected()
        adapter.disconnect()
        assert not adapter.is_connected()

    def test_context_manager_with_created_adapter(self, clean_registry, sample_config):
        """Adapter creado funciona como context manager."""
        AdapterRegistry._registry["postgresql"] = MockPostgreSQLAdapter

        adapter = AdapterRegistry.create("postgresql", sample_config)

        assert not adapter.is_connected()
        with adapter:
            assert adapter.is_connected()
        assert not adapter.is_connected()
