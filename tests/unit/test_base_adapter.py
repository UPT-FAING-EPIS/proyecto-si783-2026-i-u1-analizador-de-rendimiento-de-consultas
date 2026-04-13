"""Tests unitarios para BaseAdapter y modelos asociados."""

from typing import Any

import pytest
from pydantic import ValidationError

from query_analyzer.adapters import (
    BaseAdapter,
    ConnectionConfig,
    ConnectionError,
    QueryAnalysisReport,
    Recommendation,
    Warning,
)

# ============================================================================
# MOCK ADAPTER
# ============================================================================


class MockAdapter(BaseAdapter):
    """Mock adapter que implementa todos los métodos abstractos para testing."""

    def connect(self) -> None:
        """Simula conexión establecida."""
        self._is_connected = True
        self._connection = {"type": "mock", "engine": self._config.engine}

    def disconnect(self) -> None:
        """Simula desconexión."""
        self._is_connected = False
        self._connection = None

    def test_connection(self) -> bool:
        """Retorna el estado de conexión."""
        return self._is_connected

    def execute_explain(self, query: str) -> QueryAnalysisReport:
        """Simula análisis de query."""
        return QueryAnalysisReport(
            engine=self._config.engine,
            query=query,
            score=85,
            execution_time_ms=123.45,
            warnings=[
                Warning(
                    severity="medium",
                    message="No índice en column X",
                    node_type="Seq Scan",
                    affected_object="column X",
                )
            ],
            recommendations=[
                Recommendation(
                    priority=3,
                    title="Crear índice en column X",
                    description="Un índice en column X mejorará performance",
                    affected_object="column X",
                )
            ],
            raw_plan={"type": "mock_plan", "rows": 1000},
            metrics={"rows": 1000, "cost": 100.5},
        )

    def get_slow_queries(self, threshold_ms: int = 1000) -> list[dict[str, Any]]:
        """Simula obtención de queries lentas."""
        return [
            {"query": "SELECT * FROM users WHERE...", "execution_time_ms": 5000},
            {"query": "SELECT * FROM orders WHERE...", "execution_time_ms": 3500},
        ]

    def get_metrics(self) -> dict[str, Any]:
        """Simula obtención de métricas."""
        return {
            "active_connections": 42,
            "queries_per_second": 150,
            "cache_hit_ratio": 0.95,
        }

    def get_engine_info(self) -> dict[str, Any]:
        """Simula obtención de información del motor."""
        return {
            "version": "5.7.35" if self._config.engine == "mysql" else "14.2",
            "engine": self._config.engine,
            "max_connections": 100,
        }


# ============================================================================
# TESTS: BaseAdapter - No se puede instanciar directamente
# ============================================================================


def test_cannot_instantiate_base_adapter() -> None:
    """Verifica que BaseAdapter no se puede instanciar directamente."""
    config = ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="test",
        username="user",
        password="pass",
    )

    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        BaseAdapter(config)  # type: ignore


# ============================================================================
# TESTS: Adapter incompleto lanza TypeError
# ============================================================================


def test_incomplete_adapter_raises_typeerror() -> None:
    """Verifica que un adapter sin implementar todos los métodos lanza TypeError."""

    class IncompleteAdapter(BaseAdapter):
        """Adapter que solo implementa algunos métodos."""

        def connect(self) -> None:
            pass

        def disconnect(self) -> None:
            pass

        # Faltan: test_connection, execute_explain, get_slow_queries,
        # get_metrics, get_engine_info

    config = ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="test",
        username="user",
        password="pass",
    )

    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IncompleteAdapter(config)  # type: ignore[abstract]


# ============================================================================
# TESTS: ConnectionConfig - Validación válida
# ============================================================================


def test_connection_config_valid_mysql() -> None:
    """Verifica que ConnectionConfig acepta datos válidos para MySQL."""
    config = ConnectionConfig(
        engine="mysql",
        host="localhost",
        port=3306,
        database="myapp",
        username="admin",
        password="secret123",
    )

    assert config.engine == "mysql"
    assert config.host == "localhost"
    assert config.port == 3306
    assert config.database == "myapp"
    assert config.username == "admin"
    assert config.password == "secret123"
    assert config.extra == {}


def test_connection_config_valid_postgresql() -> None:
    """Verifica que ConnectionConfig acepta datos válidos para PostgreSQL."""
    config = ConnectionConfig(
        engine="postgresql",
        host="db.example.com",
        port=5432,
        database="production",
        username="dbuser",
        password="dbpass",
    )

    assert config.engine == "postgresql"
    assert config.host == "db.example.com"
    assert config.port == 5432


def test_connection_config_with_extra_params() -> None:
    """Verifica que ConnectionConfig acepta parámetros extra."""
    config = ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="test",
        username="user",
        password="pass",
        extra={"sslmode": "require", "connect_timeout": 10},
    )

    assert config.extra == {"sslmode": "require", "connect_timeout": 10}


def test_connection_config_strips_whitespace() -> None:
    """Verifica que ConnectionConfig elimina espacios en blanco."""
    config = ConnectionConfig(
        engine="postgresql",
        host="  localhost  ",
        port=5432,
        database="  test  ",
        username="  user  ",
        password="  pass  ",
    )

    assert config.host == "localhost"
    assert config.database == "test"
    assert config.username == "user"
    assert config.password == "pass"


# ============================================================================
# TESTS: ConnectionConfig - Validación inválida
# ============================================================================


def test_connection_config_invalid_engine() -> None:
    """Verifica que rechaza motores no soportados."""
    with pytest.raises(ValidationError) as exc_info:
        ConnectionConfig(
            engine="oracle",
            host="localhost",
            port=1521,
            database="test",
            username="user",
            password="pass",
        )

    assert "Motor no soportado" in str(exc_info.value)


def test_connection_config_engine_case_insensitive() -> None:
    """Verifica que el engine es case-insensitive."""
    config = ConnectionConfig(
        engine="PostgreSQL",
        host="localhost",
        port=5432,
        database="test",
        username="user",
        password="pass",
    )

    assert config.engine == "postgresql"


def test_connection_config_invalid_port_negative() -> None:
    """Verifica que rechaza puertos negativos."""
    with pytest.raises(ValidationError) as exc_info:
        ConnectionConfig(
            engine="postgresql",
            host="localhost",
            port=-1,
            database="test",
            username="user",
            password="pass",
        )

    assert "Puerto debe estar entre 1 y 65535" in str(exc_info.value)


def test_connection_config_invalid_port_zero() -> None:
    """Verifica que rechaza puerto 0."""
    with pytest.raises(ValidationError) as exc_info:
        ConnectionConfig(
            engine="postgresql",
            host="localhost",
            port=0,
            database="test",
            username="user",
            password="pass",
        )

    assert "Puerto debe estar entre 1 y 65535" in str(exc_info.value)


def test_connection_config_invalid_port_too_high() -> None:
    """Verifica que rechaza puertos > 65535."""
    with pytest.raises(ValidationError) as exc_info:
        ConnectionConfig(
            engine="postgresql",
            host="localhost",
            port=99999,
            database="test",
            username="user",
            password="pass",
        )

    assert "Puerto debe estar entre 1 y 65535" in str(exc_info.value)


def test_connection_config_empty_host() -> None:
    """Verifica que rechaza host vacío."""
    with pytest.raises(ValidationError) as exc_info:
        ConnectionConfig(
            engine="postgresql",
            host="",
            port=5432,
            database="test",
            username="user",
            password="pass",
        )

    assert "no puede estar vacío" in str(exc_info.value)


def test_connection_config_empty_database() -> None:
    """Verifica que rechaza database vacío."""
    with pytest.raises(ValidationError) as exc_info:
        ConnectionConfig(
            engine="postgresql",
            host="localhost",
            port=5432,
            database="",
            username="user",
            password="pass",
        )

    assert "no puede estar vacío" in str(exc_info.value)


def test_connection_config_empty_username() -> None:
    """Verifica que rechaza username vacío."""
    with pytest.raises(ValidationError) as exc_info:
        ConnectionConfig(
            engine="postgresql",
            host="localhost",
            port=5432,
            database="test",
            username="",
            password="pass",
        )

    assert "no puede estar vacío" in str(exc_info.value)


def test_connection_config_empty_password() -> None:
    """Verifica que rechaza password vacío."""
    with pytest.raises(ValidationError) as exc_info:
        ConnectionConfig(
            engine="postgresql",
            host="localhost",
            port=5432,
            database="test",
            username="user",
            password="",
        )

    assert "no puede estar vacío" in str(exc_info.value)


# ============================================================================
# TESTS: QueryAnalysisReport - Validación válida
# ============================================================================


def test_query_analysis_report_valid() -> None:
    """Verifica que QueryAnalysisReport acepta datos válidos."""
    report = QueryAnalysisReport(
        engine="postgresql",
        query="SELECT * FROM users WHERE id = 1",
        score=90,
        execution_time_ms=45.5,
        warnings=[
            Warning(
                severity="low",
                message="No índice en id",
                affected_object="id",
            )
        ],
        recommendations=[
            Recommendation(
                priority=5,
                title="Crear índice",
                description="Crear un índice en la columna id",
                affected_object="id",
            )
        ],
        raw_plan={"plan": "scan"},
        metrics={"rows": 100},
    )

    assert report.engine == "postgresql"
    assert report.query == "SELECT * FROM users WHERE id = 1"
    assert report.score == 90
    assert report.execution_time_ms == 45.5


def test_query_analysis_report_min_score() -> None:
    """Verifica que score mínimo (0) es válido."""
    report = QueryAnalysisReport(
        engine="mysql",
        query="SELECT 1",
        score=0,
        execution_time_ms=1.0,
        raw_plan={},
        metrics={},
    )

    assert report.score == 0


def test_query_analysis_report_max_score() -> None:
    """Verifica que score máximo (100) es válido."""
    report = QueryAnalysisReport(
        engine="mysql",
        query="SELECT 1",
        score=100,
        execution_time_ms=1.0,
        raw_plan={},
        metrics={},
    )

    assert report.score == 100


def test_query_analysis_report_default_lists_and_dicts() -> None:
    """Verifica que warnings, recommendations y metrics tienen defaults."""
    report = QueryAnalysisReport(
        engine="postgresql",
        query="SELECT 1",
        score=50,
        execution_time_ms=10.5,
        raw_plan={},
    )

    assert report.warnings == []
    assert report.recommendations == []
    assert report.metrics == {}


# ============================================================================
# TESTS: QueryAnalysisReport - Validación inválida
# ============================================================================


def test_query_analysis_report_invalid_score_negative() -> None:
    """Verifica que rechaza score < 0."""
    with pytest.raises(ValidationError) as exc_info:
        QueryAnalysisReport(
            engine="postgresql",
            query="SELECT 1",
            score=-1,
            execution_time_ms=10.0,
            raw_plan={},
        )

    assert "Score debe estar entre 0 y 100" in str(exc_info.value)


def test_query_analysis_report_invalid_score_too_high() -> None:
    """Verifica que rechaza score > 100."""
    with pytest.raises(ValidationError) as exc_info:
        QueryAnalysisReport(
            engine="postgresql",
            query="SELECT 1",
            score=101,
            execution_time_ms=10.0,
            raw_plan={},
        )

    assert "Score debe estar entre 0 y 100" in str(exc_info.value)


def test_query_analysis_report_invalid_execution_time_zero() -> None:
    """Verifica que rechaza execution_time_ms = 0."""
    with pytest.raises(ValidationError) as exc_info:
        QueryAnalysisReport(
            engine="postgresql",
            query="SELECT 1",
            score=50,
            execution_time_ms=0.0,
            raw_plan={},
        )

    assert "debe ser mayor a 0" in str(exc_info.value)


def test_query_analysis_report_invalid_execution_time_negative() -> None:
    """Verifica que rechaza execution_time_ms < 0."""
    with pytest.raises(ValidationError) as exc_info:
        QueryAnalysisReport(
            engine="postgresql",
            query="SELECT 1",
            score=50,
            execution_time_ms=-10.5,
            raw_plan={},
        )

    assert "debe ser mayor a 0" in str(exc_info.value)


def test_query_analysis_report_invalid_engine() -> None:
    """Verifica que rechaza motores no soportados."""
    with pytest.raises(ValidationError) as exc_info:
        QueryAnalysisReport(
            engine="oracle",
            query="SELECT 1",
            score=50,
            execution_time_ms=10.0,
            raw_plan={},
        )

    assert "Motor no soportado" in str(exc_info.value)


# ============================================================================
# TESTS: Mock Adapter - Instanciación correcta
# ============================================================================


def test_mock_adapter_instantiation() -> None:
    """Verifica que un adapter completo se instancia correctamente."""
    config = ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="test",
        username="user",
        password="pass",
    )

    adapter = MockAdapter(config)

    assert adapter is not None
    assert adapter._config == config
    assert not adapter.is_connected()


# ============================================================================
# TESTS: Context Manager
# ============================================================================


def test_context_manager_calls_connect_and_disconnect() -> None:
    """Verifica que __enter__ llama a connect() y __exit__ a disconnect()."""
    config = ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="test",
        username="user",
        password="pass",
    )

    adapter = MockAdapter(config)

    # Antes del with: no conectado
    assert not adapter.is_connected()

    with adapter:
        # Dentro del with: conectado (llamó a __enter__ -> connect())
        assert adapter.is_connected()
        assert adapter._connection is not None

    # Después del with: desconectado (llamó a __exit__ -> disconnect())
    assert not adapter.is_connected()
    assert adapter._connection is None


def test_context_manager_disconnects_even_on_exception() -> None:
    """Verifica que disconnect() se llama incluso si hay excepción."""
    config = ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="test",
        username="user",
        password="pass",
    )

    adapter = MockAdapter(config)

    try:
        with adapter:
            assert adapter.is_connected()
            raise ValueError("Error simulado")
    except ValueError:
        pass

    # Debe estar desconectado aunque ocurrió excepción
    assert not adapter.is_connected()


# ============================================================================
# TESTS: Métodos auxiliares
# ============================================================================


def test_is_connected_initial_state() -> None:
    """Verifica que is_connected() retorna False al inicio."""
    config = ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="test",
        username="user",
        password="pass",
    )

    adapter = MockAdapter(config)

    assert not adapter.is_connected()


def test_is_connected_after_connection() -> None:
    """Verifica que is_connected() retorna True después de conectar."""
    config = ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="test",
        username="user",
        password="pass",
    )

    adapter = MockAdapter(config)
    adapter.connect()

    assert adapter.is_connected()


def test_get_connection_without_connection_raises_error() -> None:
    """Verifica que get_connection() lanza ConnectionError sin conexión."""
    config = ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="test",
        username="user",
        password="pass",
    )

    adapter = MockAdapter(config)

    with pytest.raises(ConnectionError, match="No hay conexión activa"):
        adapter.get_connection()


def test_get_connection_with_active_connection() -> None:
    """Verifica que get_connection() retorna la conexión cuando está activa."""
    config = ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="test",
        username="user",
        password="pass",
    )

    adapter = MockAdapter(config)
    adapter.connect()

    conn = adapter.get_connection()

    assert conn is not None
    assert isinstance(conn, dict)
    assert conn["type"] == "mock"


# ============================================================================
# TESTS: Métodos implementados en MockAdapter
# ============================================================================


def test_mock_adapter_test_connection() -> None:
    """Verifica que test_connection() funciona correctamente."""
    config = ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="test",
        username="user",
        password="pass",
    )

    adapter = MockAdapter(config)

    assert not adapter.test_connection()

    adapter.connect()
    assert adapter.test_connection()


def test_mock_adapter_execute_explain() -> None:
    """Verifica que execute_explain() retorna QueryAnalysisReport válido."""
    config = ConnectionConfig(
        engine="mysql",
        host="localhost",
        port=3306,
        database="test",
        username="user",
        password="pass",
    )

    adapter = MockAdapter(config)

    report = adapter.execute_explain("SELECT * FROM users WHERE id = 1")

    assert report.engine == "mysql"
    assert report.query == "SELECT * FROM users WHERE id = 1"
    assert report.score == 85
    assert report.execution_time_ms == 123.45
    assert len(report.warnings) > 0
    assert len(report.recommendations) > 0


def test_mock_adapter_get_slow_queries() -> None:
    """Verifica que get_slow_queries() retorna lista de diccionarios."""
    config = ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="test",
        username="user",
        password="pass",
    )

    adapter = MockAdapter(config)

    slow_queries = adapter.get_slow_queries(threshold_ms=1000)

    assert isinstance(slow_queries, list)
    assert len(slow_queries) == 2
    assert all("query" in q and "execution_time_ms" in q for q in slow_queries)


def test_mock_adapter_get_metrics() -> None:
    """Verifica que get_metrics() retorna diccionario de métricas."""
    config = ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="test",
        username="user",
        password="pass",
    )

    adapter = MockAdapter(config)

    metrics = adapter.get_metrics()

    assert isinstance(metrics, dict)
    assert "active_connections" in metrics
    assert "queries_per_second" in metrics


def test_mock_adapter_get_engine_info() -> None:
    """Verifica que get_engine_info() retorna información del motor."""
    config = ConnectionConfig(
        engine="postgresql",
        host="localhost",
        port=5432,
        database="test",
        username="user",
        password="pass",
    )

    adapter = MockAdapter(config)

    info = adapter.get_engine_info()

    assert isinstance(info, dict)
    assert "version" in info
    assert "engine" in info
    assert info["engine"] == "postgresql"
