"""CockroachDB database adapter using psycopg2 (wire protocol compatible).

CockroachDB implements PostgreSQL wire protocol, so we extend PostgreSQLAdapter
and override key methods for CRDB-specific behavior:
- EXPLAIN with JSON format (with text fallback for older versions)
- CRDB-specific warnings (full scans, cross-region scans)
- Minimal metrics (no admin-only queries in v1)
"""

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

from .postgresql_metrics import PostgreSQLMetricsHelper
from .postgresql_parser import PostgreSQLExplainParser

logger = logging.getLogger(__name__)


@AdapterRegistry.register("cockroachdb")
class CockroachDBAdapter(BaseAdapter):
    """CockroachDB adapter using psycopg2 driver.

    Extends BaseAdapter with CockroachDB-specific EXPLAIN handling:
    - Primary: EXPLAIN (ANALYZE, FORMAT JSON)
    - Fallback: EXPLAIN ANALYZE (text)
    - CRDB-specific warnings: full scans, cross-region scans

    Uses PostgreSQLExplainParser directly (JSON format compatible via wire protocol).
    """

    def __init__(self, config: ConnectionConfig) -> None:
        """Initialize CockroachDB adapter.

        Args:
            config: Connection configuration

        Raises:
            ConnectionConfigError: If config is invalid
        """
        super().__init__(config)
        # Reuse PostgreSQL parser (YAGNI — create subclass if tests fail)
        self.parser = PostgreSQLExplainParser(
            seq_scan_threshold=config.extra.get("seq_scan_threshold", 10000)
        )
        self.metrics_helper = PostgreSQLMetricsHelper()

    def connect(self) -> None:
        """Establish connection to CockroachDB using psycopg2.

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
            logger.info(f"Connected to CockroachDB {self._config.host}:{self._config.port}")
        except OperationalError as e:
            self._is_connected = False
            self._connection = None
            raise AdapterConnectionError(f"Failed to connect to CockroachDB: {e}") from e

    def disconnect(self) -> None:
        """Close CockroachDB connection."""
        if self._connection:
            try:
                self._connection.close()
                logger.info("Disconnected from CockroachDB")
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
            finally:
                self._connection = None
                self._is_connected = False

    def test_connection(self) -> bool:
        """Test CockroachDB connection with simple query.

        Returns:
            True if connection is valid, False otherwise (strategy: fail-safe).

        Note:
            Errores en test de conexión retornan False en lugar de propagar
            excepciones, permitiendo detección segura de desconexión.
        """
        try:
            if not self._is_connected:
                return False

            with self._connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return True
        except Exception as e:
            logger.debug(f"Connection test failed: {e}")
            return False

    def execute_explain(self, query: str) -> QueryAnalysisReport:
        """Execute EXPLAIN with JSON primary, text fallback.

        Attempts EXPLAIN (ANALYZE, FORMAT JSON) first (CockroachDB v22.1+).
        Falls back to EXPLAIN ANALYZE (text) if JSON fails.

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
                explain_json = None
                explain_text = None

                # Try JSON format first (CockroachDB v22.1+)
                try:
                    explain_query = f"EXPLAIN (ANALYZE, FORMAT JSON) {query}"
                    cursor.execute(explain_query)
                    result = cursor.fetchone()

                    if not result:
                        raise QueryAnalysisError("EXPLAIN returned no results")

                    # Parse JSON result
                    if isinstance(result[0], str):
                        explain_json = json.loads(result[0])[0]
                    else:
                        explain_json = result[0][0]

                    logger.debug("EXPLAIN JSON format succeeded")

                except Exception as e:
                    logger.warning(f"JSON EXPLAIN failed: {e}, trying text fallback")

                    # Fallback to text format
                    try:
                        explain_query = f"EXPLAIN ANALYZE {query}"
                        cursor.execute(explain_query)
                        rows = cursor.fetchall()
                        explain_text = "\n".join([row[0] for row in rows])
                        logger.debug("EXPLAIN text fallback succeeded")
                    except Exception as e_text:
                        raise QueryAnalysisError(
                            f"Both JSON and text EXPLAIN failed: {e_text}"
                        ) from e_text

                # Parse plan
                if explain_json:
                    metrics = self.parser.parse(explain_json)
                else:
                    # Text parsing — create minimal metrics dict
                    if explain_text is None:
                        raise QueryAnalysisError(
                            "No EXPLAIN output available (neither JSON nor text)"
                        )
                    metrics = self._parse_text_explain(explain_text)

                # Get CRDB-specific warnings
                plan_text = explain_text or json.dumps(explain_json)
                crdb_warnings = self._detect_crdb_specific_issues(plan_text, metrics)

                # Get base warnings from parser
                base_warnings = self.parser.identify_warnings(metrics, metrics["all_nodes"])

                # Merge warnings (CRDB + base)
                all_warnings = crdb_warnings + base_warnings

                # Generate recommendations
                recommendations = self.parser.generate_recommendations(metrics, all_warnings)

                # Calculate optimization score
                score = self.parser.calculate_score(metrics, all_warnings)

                # Build report
                return QueryAnalysisReport(
                    engine="cockroachdb",
                    query=query,
                    score=score,
                    execution_time_ms=metrics.get("execution_time_ms", 0.0),
                    warnings=all_warnings,
                    recommendations=recommendations,
                    raw_plan=explain_json,  # Only include JSON, not text fallback
                    metrics=metrics,
                )

        except QueryAnalysisError:
            raise
        except Exception as e:
            raise QueryAnalysisError(f"Failed to analyze query with EXPLAIN: {e}") from e

    def _detect_crdb_specific_issues(self, plan_text: str, metrics: dict[str, Any]) -> list[str]:
        """Detect CockroachDB-specific anti-patterns from EXPLAIN output.

        Checks for:
        - Cross-region full scans (CRITICAL)
        - Full table scans (HIGH)

        Args:
            plan_text: EXPLAIN output as text
            metrics: Parsed metrics dict (for future use)

        Returns:
            List of warning strings (may be empty)
        """
        warnings = []
        plan_lower = plan_text.lower()

        # Detect cross-region full scan (CRITICAL)
        if "full scan" in plan_lower and "region" in plan_lower:
            warnings.append(
                "CRITICAL: Full scan across multiple regions detected — high latency risk"
            )
        # Detect full scan (HIGH) — only if not already caught by cross-region
        elif "full scan" in plan_lower:
            warnings.append("Full table scan detected — consider creating an index")

        return warnings

    def _parse_text_explain(self, explain_text: str) -> dict[str, Any]:
        """Parse text-format EXPLAIN output into minimal metrics dict.

        For v1, returns basic structure to avoid breaking parser.
        Real metrics extraction from text happens in v2 if needed.

        Args:
            explain_text: Text-format EXPLAIN output

        Returns:
            Dictionary with minimal metrics structure
        """
        return {
            "planning_time_ms": 0.0,
            "execution_time_ms": 0.0,
            "total_cost": 0.0,
            "actual_rows_total": 0,
            "plan_rows_total": 0,
            "node_count": 0,
            "most_expensive_node": None,
            "buffer_stats": {},
            "scan_nodes": [],
            "join_nodes": [],
            "all_nodes": [],
        }

    def get_slow_queries(self, threshold_ms: int = 1000) -> list[dict[str, Any]]:
        """Get slow queries from CockroachDB.

        CockroachDB doesn't expose pg_stat_statements equivalent in v1.
        Planned for v2 using system.statement_stats table.

        Args:
            threshold_ms: Threshold in milliseconds (default: 1000)

        Returns:
            Empty list (not implemented in v1)
        """
        logger.warning(
            "get_slow_queries() not supported for CockroachDB in v1. "
            "Planned for v2 with system.statement_stats table."
        )
        return []

    def get_metrics(self) -> dict[str, Any]:
        """Get minimal metrics from CockroachDB.

        Only non-admin queries in v1. Node count and replication factor
        require admin privileges — deferred to v2.

        Returns:
            Dict with engine info and version (if available)
        """
        if not self._is_connected:
            return {"engine": "cockroachdb"}

        try:
            with self._connection.cursor() as cursor:
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0]
                return {
                    "engine": "cockroachdb",
                    "version": version,
                }
        except Exception as e:
            logger.warning(f"CockroachDB metrics unavailable: {e}")
            return {"engine": "cockroachdb"}

    def get_engine_info(self) -> dict[str, Any]:
        """Get CockroachDB version and basic info.

        Returns:
            Dict with version and engine name
        """
        if not self._is_connected:
            return {}

        try:
            with self._connection.cursor() as cursor:
                cursor.execute("SELECT version()")
                version_string = cursor.fetchone()[0]

                return {
                    "version": version_string,
                    "engine": "cockroachdb",
                }

        except Exception as e:
            logger.warning(f"Failed to retrieve engine info: {e}")
            return {}
