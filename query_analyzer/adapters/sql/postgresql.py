"""PostgreSQL database adapter using psycopg2."""

import json
import logging
from typing import Any

import psycopg2
from psycopg2 import OperationalError

from query_analyzer.adapters.base import BaseAdapter
from query_analyzer.adapters.exceptions import (
    ConnectionError as AdapterConnectionError,
)
from query_analyzer.adapters.exceptions import QueryAnalysisError
from query_analyzer.adapters.models import ConnectionConfig, QueryAnalysisReport
from query_analyzer.adapters.registry import AdapterRegistry
from query_analyzer.core.anti_pattern_detector import AntiPatternDetector

from .postgresql_metrics import PostgreSQLMetricsHelper
from .postgresql_parser import PostgreSQLExplainParser

logger = logging.getLogger(__name__)


@AdapterRegistry.register("postgresql")
class PostgreSQLAdapter(BaseAdapter):
    """PostgreSQL adapter using psycopg2 driver.

    Implements all BaseAdapter methods for PostgreSQL, including intelligent
    EXPLAIN plan parsing and analysis.
    """

    def __init__(self, config: ConnectionConfig) -> None:
        """Initialize PostgreSQL adapter.

        Args:
            config: Connection configuration

        Raises:
            ConnectionConfigError: If config is invalid
        """
        super().__init__(config)
        self.parser = PostgreSQLExplainParser(
            seq_scan_threshold=config.extra.get("seq_scan_threshold", 10000)
        )
        self.metrics_helper = PostgreSQLMetricsHelper()

    def connect(self) -> None:
        """Establish connection to PostgreSQL.

        Raises:
            ConnectionError: If connection fails
        """
        try:
            self._connection = psycopg2.connect(
                host=self._config.host,
                port=self._config.port,
                database=self._config.database,
                user=self._config.username,
                password=self._config.password,
                connect_timeout=self._config.extra.get("connection_timeout", 10),
            )
            self._is_connected = True
            logger.info(f"Connected to PostgreSQL {self._config.host}:{self._config.port}")
        except OperationalError as e:
            self._is_connected = False
            self._connection = None
            raise AdapterConnectionError(f"Failed to connect to PostgreSQL: {e}") from e

    def disconnect(self) -> None:
        """Close PostgreSQL connection."""
        if self._connection:
            try:
                self._connection.close()
                logger.info("Disconnected from PostgreSQL")
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
            finally:
                self._connection = None
                self._is_connected = False

    def test_connection(self) -> bool:
        """Test PostgreSQL connection with simple query.

        Returns:
            True if connection is valid, False otherwise
        """
        try:
            if not self._is_connected:
                return False

            with self._connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return True
        except Exception as e:
            logger.warning(f"Connection test failed: {e}")
            return False

    def execute_explain(self, query: str) -> QueryAnalysisReport:
        """Execute EXPLAIN ANALYZE and generate analysis report.

        Args:
            query: SQL query to analyze (SELECT/INSERT/UPDATE/DELETE)

        Returns:
            QueryAnalysisReport with analysis results

        Raises:
            QueryAnalysisError: If query analysis fails
        """
        if not self._is_connected:
            raise QueryAnalysisError("Not connected to database")

        # Validate query is not DDL
        query_upper = query.strip().upper()
        if any(query_upper.startswith(ddl) for ddl in ["CREATE", "ALTER", "DROP", "TRUNCATE"]):
            raise QueryAnalysisError(
                "Cannot analyze DDL statements. Only SELECT, INSERT, UPDATE, DELETE are supported."
            )

        try:
            with self._connection.cursor() as cursor:
                # Execute EXPLAIN with ANALYZE, BUFFERS, VERBOSE, FORMAT JSON
                explain_query = f"EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON) {query}"
                cursor.execute(explain_query)
                result = cursor.fetchone()

                if not result:
                    raise QueryAnalysisError("EXPLAIN returned no results")

                # Parse JSON result
                # psycopg2 with FORMAT JSON returns result[0] as a Python list (already parsed)
                # Extract the first element which contains the plan
                if isinstance(result[0], str):
                    # If it's a string, parse it
                    explain_json = json.loads(result[0])[0]
                else:
                    # If it's already a list (psycopg2 parsed it), just use first element
                    explain_json = result[0][0]

                # Parse plan and extract metrics
                metrics = self.parser.parse(explain_json)
                execution_time = metrics.get("execution_time_ms", 0.0)

                # Normalize plan to engine-agnostic format for AntiPatternDetector
                root_plan = explain_json.get("Plan", {})
                normalized_plan = self.parser.normalize_plan(root_plan)

                # Analyze with AntiPatternDetector for unified scoring
                detector = AntiPatternDetector()
                detection_result = detector.analyze(normalized_plan, query)

                # Use detector's score and recommendations (single source of truth)
                # Convert anti-pattern descriptions to warnings
                warnings = [ap.description for ap in detection_result.anti_patterns]
                recommendations = detection_result.recommendations
                score = detection_result.score

                # Build report
                return QueryAnalysisReport(
                    engine="postgresql",
                    query=query,
                    score=score,
                    execution_time_ms=execution_time,
                    warnings=warnings,
                    recommendations=recommendations,
                    raw_plan=explain_json,
                    metrics=metrics,
                )

        except QueryAnalysisError:
            raise
        except Exception as e:
            raise QueryAnalysisError(f"Failed to analyze query with EXPLAIN: {e}") from e

    def get_slow_queries(self, threshold_ms: int = 1000) -> list[dict[str, Any]]:
        """Get slow queries from pg_stat_statements.

        Gracefully handles case where pg_stat_statements is not installed.

        Args:
            threshold_ms: Threshold in milliseconds (default: 1000)

        Returns:
            List of dicts with query timing information, or empty list if
            pg_stat_statements is not available
        """
        if not self._is_connected:
            return []

        try:
            # Check if pg_stat_statements is available
            if not self.metrics_helper.check_pg_stat_statements_available(self._connection):
                logger.warning(
                    "pg_stat_statements extension not installed. "
                    "Install with: CREATE EXTENSION pg_stat_statements"
                )
                return []

            # Get slow queries
            queries = self.metrics_helper.get_slow_queries_from_pg_stat_statements(
                self._connection, threshold_ms=threshold_ms, limit=100
            )
            return queries

        except Exception as e:
            logger.warning(f"Failed to retrieve slow queries: {e}")
            return []

    def get_metrics(self) -> dict[str, Any]:
        """Get database metrics from pg_stat_database.

        Returns:
            Dict with connection, transaction, and tuple statistics
        """
        if not self._is_connected:
            return {}

        try:
            db_stats = self.metrics_helper.get_db_stats(self._connection)
            cache_ratio = self.metrics_helper.get_cache_hit_ratio(self._connection)

            result = {
                **db_stats,
                "cache_hit_ratio": cache_ratio if cache_ratio >= 0 else None,
            }
            return result

        except Exception as e:
            logger.warning(f"Failed to retrieve metrics: {e}")
            return {}

    def get_engine_info(self) -> dict[str, Any]:
        """Get PostgreSQL version and configuration.

        Returns:
            Dict with version and configuration settings
        """
        if not self._is_connected:
            return {}

        try:
            with self._connection.cursor() as cursor:
                # Get version
                cursor.execute("SELECT version()")
                version_string = cursor.fetchone()[0]

                # Get settings
                settings = self.metrics_helper.get_settings(
                    self._connection,
                    [
                        "max_connections",
                        "shared_buffers",
                        "effective_cache_size",
                        "work_mem",
                    ],
                )

                return {
                    "version": version_string,
                    "engine": "postgresql",
                    **settings,
                }

        except Exception as e:
            logger.warning(f"Failed to retrieve engine info: {e}")
            return {}
