"""Clase abstracta base para todos los adapters de bases de datos."""

from abc import ABC, abstractmethod
from typing import Any

from .exceptions import ConnectionError
from .models import ConnectionConfig, QueryAnalysisReport


class BaseAdapter(ABC):
    """
    Contrato abstracto para adapters de bases de datos.

    Define la interfaz que todos los drivers deben implementar.
    El motor de análisis usa este contrato sin importar la BD específica.

    Esta clase es abstracta y no puede ser instanciada directamente.
    Todos los subclasses deben implementar los 6 métodos abstractos.

    Attributes:
        _config: Configuración de la conexión
        _is_connected: Estado actual de la conexión
        _connection: Objeto de conexión nativo (específico del motor)
    """

    def __init__(self, config: ConnectionConfig) -> None:
        """
        Inicializa el adapter con la configuración de conexión.

        Args:
            config: Configuración con detalles de conexión

        Raises:
            ConnectionConfigError: Si la configuración es inválida
        """
        self._config = config
        self._is_connected = False
        self._connection: Any = None

    def __enter__(self) -> "BaseAdapter":
        """
        Contexto manager: conecta al entrar.

        Returns:
            Retorna self para permitir uso en with

        Raises:
            ConnectionError: Si falla la conexión
        """
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Contexto manager: desconecta al salir.

        Asegura que la conexión se cierre correctamente aunque
        ocurra una excepción dentro del bloque with.

        Args:
            exc_type: Tipo de excepción (si la hay)
            exc_val: Valor de la excepción (si la hay)
            exc_tb: Traceback de la excepción (si la hay)
        """
        self.disconnect()

    def is_connected(self) -> bool:
        """
        Verifica si el adapter está conectado.

        Returns:
            True si hay conexión activa, False en caso contrario
        """
        return self._is_connected

    def get_connection(self) -> Any:
        """
        Obtiene el objeto de conexión nativa.

        Retorna el objeto específico del motor (psycopg2 connection,
        mysql.connector.MySQLConnection, etc.).

        Returns:
            Objeto de conexión del motor

        Raises:
            ConnectionError: Si no hay conexión activa
        """
        if not self._is_connected:
            raise ConnectionError("No hay conexión activa con la base de datos")
        return self._connection

    @abstractmethod
    def connect(self) -> None:
        """
        Establece la conexión a la base de datos.

        Debe ser implementado por cada adapter específico.
        Al completar, debe asignar _is_connected = True y _connection a
        un objeto válido del motor.

        Raises:
            ConnectionError: Si falla la conexión
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Cierra la conexión a la base de datos.

        Debe ser implementado por cada adapter específico.
        Debe asignar _is_connected = False y _connection = None.

        Raises:
            DisconnectionError: Si falla el cierre
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Prueba la conexión sin ejecutar cambios.

        Intenta una operación simple (como SELECT 1 o PING) para
        verificar que la conexión sea válida.

        Returns:
            True si la conexión es válida, False en caso contrario
        """
        pass

    @abstractmethod
    def execute_explain(self, query: str) -> QueryAnalysisReport:
        """
        Ejecuta EXPLAIN PLAN en la query y retorna un análisis detallado.

        Debe:
        1. Validar que la query sea SQL válida
        2. Ejecutar EXPLAIN (o equivalente del motor)
        3. Parsear el plan de ejecución
        4. Calcular score de optimización (0-100)
        5. Generar warnings y recomendaciones
        6. Retornar QueryAnalysisReport completo

        Args:
            query: Consulta SQL a analizar (SELECT, INSERT, UPDATE, DELETE)

        Returns:
            QueryAnalysisReport con análisis completo incluyendo plan,
            score, warnings y recomendaciones

        Raises:
            QueryAnalysisError: Si falla la ejecución o parseo
        """
        pass

    @abstractmethod
    def get_slow_queries(self, threshold_ms: int = 1000) -> list[dict[str, Any]]:
        """
        Obtiene queries que superan el threshold de tiempo de ejecución.

        Accede a los logs de slow queries del motor (si está disponible)
        y retorna aquellas que tomaron más de threshold_ms milisegundos.

        Cada diccionario debe contener al menos:
        - query: La consulta SQL
        - execution_time_ms: Tiempo de ejecución
        - timestamp: Cuándo se ejecutó (opcional)

        Args:
            threshold_ms: Umbral de tiempo en milisegundos (default: 1000)

        Returns:
            Lista de diccionarios con queries lentas

        Raises:
            QueryAnalysisError: Si falla la consulta de logs
        """
        pass

    @abstractmethod
    def get_metrics(self) -> dict[str, Any]:
        """
        Obtiene métricas generales del motor.

        Métricas típicas por motor:
        - PostgreSQL: active connections, tps, cache hit ratio
        - MySQL: connections, questions/sec, slow queries count
        - Ambos: uptime, database size

        Returns:
            Diccionario con métricas clave del motor
            Estructura: {"metric_name": value, ...}

        Raises:
            QueryAnalysisError: Si falla la obtención de métricas
        """
        pass

    @abstractmethod
    def get_engine_info(self) -> dict[str, Any]:
        """
        Obtiene información del motor (versión, configuración, etc.).

        Retorna información estática sobre el motor:
        - version: Versión del servidor
        - engine: Nombre del motor (mysql, postgresql)
        - datadir: Ubicación de datos
        - max_connections: Límite de conexiones
        - Otros parámetros relevantes del motor

        Returns:
            Diccionario con información del motor
            Estructura: {"param_name": value, ...}

        Raises:
            QueryAnalysisError: Si falla la obtención de información
        """
        pass
