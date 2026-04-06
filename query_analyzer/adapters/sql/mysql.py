"""MySQL adapter for Query Analyzer with EXPLAIN parsing and metrics collection."""

import logging
import re
import time
from typing import Any

import pymysql

from query_analyzer.adapters.base import BaseAdapter
from query_analyzer.adapters.exceptions import QueryAnalysisError
from query_analyzer.adapters.models import ConnectionConfig, QueryAnalysisReport
from query_analyzer.adapters.registry import AdapterRegistry

from .mysql_metrics import MySQLMetricsHelper
from .mysql_parser import MySQLExplainParser

logger = logging.getLogger(__name__)


@AdapterRegistry.register("mysql")
class MySQLAdapter(BaseAdapter):
    """MySQL database adapter for query analysis and performance metrics.

    Provides EXPLAIN parsing, query metrics, slow query tracking, and MySQL-specific
    diagnostics for query optimization.
    """

    def __init__(self, config: ConnectionConfig) -> None:
        """Initialize MySQL adapter with connection configuration.

        Args:
            config: Connection configuration including host, port, database, credentials
        """
        super().__init__(config)
        self.connection: Any = None
        self.parser = MySQLExplainParser()

    def connect(self) -> None:
        """Establish connection to MySQL database.

        Raises:
            QueryAnalysisError: If connection fails
        """
        try:
            self.connection = pymysql.connect(
                host=self._config.host,
                port=self._config.port,
                user=self._config.username,
                password=self._config.password,
                database=self._config.database,
                charset="utf8mb4",
                autocommit=True,
            )
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = 'slow_queries_log' LIMIT 1"
            )
            if not cursor.fetchone():
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS slow_queries_log (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        query_text LONGTEXT NOT NULL,
                        execution_time_ms DECIMAL(10, 2) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            cursor.close()
        except pymysql.Error as e:
            raise QueryAnalysisError(f"Failed to connect to MySQL: {e}") from e

    def disconnect(self) -> None:
        """Close connection to MySQL database."""
        if self.connection:
            self.connection.close()
            self.connection = None

    def test_connection(self) -> bool:
        """Test if connection to MySQL is valid.

        Returns:
            True if connection is valid, False otherwise (strategy: fail-safe).

        Note:
            Errores en test de conexión retornan False en lugar de propagar
            excepciones, permitiendo detección segura de desconexión.
        """
        try:
            if not self.connection:
                return False
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception as e:
            logger.debug(f"Connection test failed: {e}")
            return False

    def is_connected(self) -> bool:
        """Check if currently connected to MySQL database.

        Returns:
            True if connected and connection is valid, False otherwise
        """
        return self.connection is not None and self.test_connection()

    def get_connection(self) -> Any:
        """Get active MySQL database connection.

        Returns:
            Connection object

        Raises:
            QueryAnalysisError: If not connected
        """
        if not self.is_connected():
            raise QueryAnalysisError("Not connected to database")
        return self.connection

    def _is_ddl_statement(self, query: str) -> bool:
        query_clean = re.sub(r"^\s*--.*?\n", "", query, flags=re.MULTILINE)
        query_clean = re.sub(r"^\s*/\*.*?\*/", "", query_clean, flags=re.DOTALL)
        query_clean = query_clean.strip()

        ddl_keywords = ["CREATE", "ALTER", "DROP", "TRUNCATE"]
        for keyword in ddl_keywords:
            if re.match(rf"^\s*{keyword}\b", query_clean, re.IGNORECASE):
                return True
        return False

    def _format_explain_output(self, result: str) -> str:
        return result.strip()

    def _get_query_metrics(self) -> dict[str, Any]:
        return {
            "tables_in_db": MySQLMetricsHelper.get_table_count(self.connection),
            "indexes_in_db": MySQLMetricsHelper.get_index_count(self.connection),
        }

    def execute_explain(self, query: str) -> QueryAnalysisReport:
        """Execute EXPLAIN analysis on SQL query.

        Args:
            query: SQL query to analyze

        Returns:
            QueryAnalysisReport with execution plan and metrics

        Raises:
            QueryAnalysisError: If query is DDL or analysis fails
        """
        if not self.is_connected():
            raise QueryAnalysisError("Not connected to database")

        if self._is_ddl_statement(query):
            raise QueryAnalysisError(
                "DDL statements (CREATE, ALTER, DROP, TRUNCATE) are not supported for analysis"
            )

        try:
            cursor = self.get_connection().cursor()

            start_time = time.time()

            explain_query = f"EXPLAIN FORMAT=JSON {query}"
            cursor.execute(explain_query)

            result = cursor.fetchone()
            explain_json = result[0] if result else "{}"

            execution_time_ms = (time.time() - start_time) * 1000

            parsed_plan = self.parser.parse(explain_json)

            warnings = self.parser.identify_warnings(parsed_plan)
            recommendations = self.parser.generate_recommendations(warnings)

            score = self.parser.calculate_score(parsed_plan, warnings)

            metrics = self._get_query_metrics()

            report = QueryAnalysisReport(
                engine="mysql",
                query=query,
                score=score,
                execution_time_ms=max(0.1, execution_time_ms),
                warnings=warnings,
                recommendations=recommendations,
                raw_plan=parsed_plan,
                metrics=metrics,
            )

            cursor.close()
            return report

        except pymysql.Error as e:
            raise QueryAnalysisError(f"MySQL error during explain: {e}") from e
        except Exception as e:
            raise QueryAnalysisError(f"Error analyzing query: {e}") from e

    def get_slow_queries(self, threshold_ms: int = 1000) -> list[dict[str, Any]]:
        """Get list of slow queries exceeding threshold.

        Args:
            threshold_ms: Time threshold in milliseconds (default: 1000ms)

        Returns:
            List of slow query records
        """
        if not self.is_connected():
            return []

        return MySQLMetricsHelper.get_slow_queries(self.connection, threshold_ms)

    def get_metrics(self) -> dict[str, Any]:
        """Get MySQL server and database metrics.

        Returns:
            Dictionary containing metrics like table count, database size, etc.
            Returns empty dict if metrics retrieval fails (strategy: fail-safe).

        Note:
            Errores en consultas de métricas retornan dict vacío en lugar de
            propagar excepciones, permitiendo análisis parcial.
        """
        if not self.is_connected():
            return {}

        try:
            return {
                "tables": MySQLMetricsHelper.get_table_count(self.connection),
                "indexes": MySQLMetricsHelper.get_index_count(self.connection),
                "database_size_bytes": MySQLMetricsHelper.get_database_size(self.connection),
                "slow_queries_count": len(MySQLMetricsHelper.get_slow_queries(self.connection)),
            }
        except Exception as e:
            logger.debug(f"Failed to get metrics: {e}")
            return {}

    def get_engine_info(self) -> dict[str, Any]:
        """Get MySQL version and engine information.

        Returns:
            Dictionary with version and engine details.
            Returns partial dict if retrieval fails (strategy: fail-safe).

        Note:
            Errores en consultas retornan dict parcial en lugar de propagar
            excepciones, permitiendo análisis parcial.
        """
        if not self.is_connected():
            return {}

        try:
            version = MySQLMetricsHelper.get_engine_version(self.connection)
            pragmas = MySQLMetricsHelper.get_pragmas(self.connection)

            return {
                "engine": "mysql",
                "version": version,
                "max_connections": pragmas.get("max_connections", "N/A"),
                "max_allowed_packet": pragmas.get("max_allowed_packet", "N/A"),
                "query_cache_size": pragmas.get("query_cache_size", "N/A"),
            }
        except Exception as e:
            logger.debug(f"Failed to get engine info: {e}")
            return {"engine": "mysql", "version": "unknown"}
