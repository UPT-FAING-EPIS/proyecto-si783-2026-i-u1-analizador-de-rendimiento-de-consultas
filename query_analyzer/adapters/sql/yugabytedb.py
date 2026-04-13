"""YugabyteDB database adapter using psycopg2 (wire protocol compatible).

YugabyteDB implements PostgreSQL wire protocol, so we extend PostgreSQLAdapter
with YugabyteDB-specific defaults:
- Default port: 5433 (vs PostgreSQL 5432)
- Uses standard PostgreSQL EXPLAIN format (no DISTSQL)
- Distribution is implicit (DocDB layer, not visible in plans)

For MVP (v1), this is a straightforward extension. Future enhancements:
- Tablet-level metrics via yb_local_tablets() and yb_tablet_servers()
- Colocation detection
- Cross-region warning detection
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

import psycopg2
from psycopg2 import OperationalError

from query_analyzer.adapters.base import BaseAdapter
from query_analyzer.adapters.exceptions import (
    ConnectionError as AdapterConnectionError,
)
from query_analyzer.adapters.exceptions import QueryAnalysisError
from query_analyzer.adapters.migration_helpers import (
    build_plan_tree,
    detection_result_to_warnings_and_recommendations,
)
from query_analyzer.adapters.models import ConnectionConfig, QueryAnalysisReport
from query_analyzer.adapters.registry import AdapterRegistry
from query_analyzer.core.anti_pattern_detector import AntiPatternDetector

from .postgresql_metrics import PostgreSQLMetricsHelper
from .yugabytedb_parser import YugabyteDBParser

logger = logging.getLogger(__name__)


@AdapterRegistry.register("yugabytedb")
class YugabyteDBAdapter(BaseAdapter):
    """YugabyteDB adapter using psycopg2 driver.

    Extends BaseAdapter with YugabyteDB-specific handling:
    - Default port: 5433 (override PostgreSQL default 5432)
    - Standard PostgreSQL EXPLAIN format (no DISTSQL, no special node types)
    - YugabyteDB-specific parser for future enhancements

    Uses YugabyteDBParser for EXPLAIN analysis.
    """

    def __init__(self, config: ConnectionConfig) -> None:
        """Initialize YugabyteDB adapter.

        Args:
            config: Connection configuration

        Raises:
            ConnectionConfigError: If config is invalid
        """
        super().__init__(config)
        # Use YugabyteDB-specific parser (currently minimal override of PostgreSQL parser)
        self.parser = YugabyteDBParser(
            seq_scan_threshold=config.extra.get("seq_scan_threshold", 10000)
        )
        self.metrics_helper = PostgreSQLMetricsHelper()

    def connect(self) -> None:
        """Establish connection to YugabyteDB using psycopg2.

        Raises:
            ConnectionError: If connection fails
        """
        try:
            # Use custom port if provided in config, otherwise default to 5433
            port = self._config.port if self._config.port != 5432 else 5433

            self._connection = psycopg2.connect(
                host=self._config.host,
                port=port,
                database=self._config.database,
                user=self._config.username,
                password=self._config.password,
                connect_timeout=self._config.extra.get("connection_timeout", 10),
            )
            self._is_connected = True
            logger.info(f"Connected to YugabyteDB {self._config.host}:{port}")
        except OperationalError as e:
            self._is_connected = False
            self._connection = None
            raise AdapterConnectionError(f"Failed to connect to YugabyteDB: {e}") from e

    def disconnect(self) -> None:
        """Close YugabyteDB connection."""
        if self._connection:
            try:
                self._connection.close()
                logger.info("Disconnected from YugabyteDB")
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
            finally:
                self._connection = None
                self._is_connected = False

    def test_connection(self) -> bool:
        """Test YugabyteDB connection with simple query.

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
                execution_time = metrics.get("execution_time_ms", 1.0)

                # Normalize plan to engine-agnostic format for AntiPatternDetector
                root_plan = explain_json.get("Plan", {})
                normalized_plan = self.parser.normalize_plan(root_plan)

                # Analyze with AntiPatternDetector for unified scoring
                detector = AntiPatternDetector()
                detection_result = detector.analyze(normalized_plan, query)

                # Convert v1 data (strings) to v2 models (Warning, Recommendation)
                warnings, recommendations = detection_result_to_warnings_and_recommendations(
                    detection_result
                )

                # Build plan tree from raw EXPLAIN output
                plan_tree = build_plan_tree(root_plan)

                # Create report
                report = QueryAnalysisReport(
                    query=query,
                    engine="yugabytedb",
                    score=detection_result.score,
                    execution_time_ms=execution_time,
                    warnings=warnings,
                    recommendations=recommendations,
                    plan_tree=plan_tree,
                    analyzed_at=datetime.now(UTC),
                    raw_plan=explain_json,
                    metrics=metrics,
                )

                logger.info(
                    f"Query analysis complete (YugabyteDB): "
                    f"score={detection_result.score}, exec_time={execution_time}ms, "
                    f"nodes={metrics['node_count']}"
                )

                return report

        except json.JSONDecodeError as e:
            raise QueryAnalysisError(f"Invalid EXPLAIN JSON format: {e}") from e
        except Exception as e:
            logger.error(f"Query analysis failed: {e}")
            raise QueryAnalysisError(f"Failed to analyze query: {e}") from e

    def get_slow_queries(self, threshold_ms: int = 1000) -> list[dict[str, Any]]:
        """Get slow queries from YugabyteDB.

        YugabyteDB provides query metrics through system tables similar to PostgreSQL.
        For MVP, returns empty list (enhancement for v1.1).

        Args:
            threshold_ms: Threshold in milliseconds (default: 1000)

        Returns:
            Empty list (future enhancement)
        """
        if not self._is_connected:
            return []

        logger.debug("get_slow_queries: not yet implemented for YugabyteDB MVP")
        return []

    def get_metrics(self) -> dict[str, Any]:
        """Get YugabyteDB metrics.

        Returns basic connection metrics. Full tablet-level metrics
        will be added in v1.1.

        Returns:
            Dict with basic metrics, or empty dict if not connected
        """
        if not self._is_connected:
            return {}

        try:
            with self._connection.cursor() as cursor:
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0]

                return {
                    "version": version,
                    "engine": "yugabytedb",
                    "connection_status": "connected",
                }

        except Exception as e:
            logger.warning(f"Failed to retrieve metrics: {e}")
            return {}

    def get_engine_info(self) -> dict[str, Any]:
        """Get YugabyteDB version and configuration.

        Returns:
            Dict with version and engine information
        """
        if not self._is_connected:
            return {}

        try:
            with self._connection.cursor() as cursor:
                # Get version
                cursor.execute("SELECT version()")
                version_string = cursor.fetchone()[0]

                return {
                    "version": version_string,
                    "engine": "yugabytedb",
                    "protocol": "PostgreSQL-compatible",
                }

        except Exception as e:
            logger.warning(f"Failed to retrieve engine info: {e}")
            return {}
