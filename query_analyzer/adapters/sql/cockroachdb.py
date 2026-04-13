"""CockroachDB database adapter using psycopg2 (wire protocol compatible).

CockroachDB implements PostgreSQL wire protocol, so we extend PostgreSQLAdapter
and use CockroachDBParser for CRDB-specific optimizations:
- EXPLAIN with intelligent fallback: DISTSQL → JSON → Text format
- CRDB-specific node types: Lookup Join, Zigzag Join, distributed execution
- CRDB-specific warnings: high lookup join count, distributed execution patterns
- Minimal metrics (no admin-only queries in v1)
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any, Literal, cast

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

from .cockroachdb_parser import CockroachDBParser
from .postgresql_metrics import PostgreSQLMetricsHelper

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
        # Use CockroachDB-specific parser instead of PostgreSQL parser
        self.parser = CockroachDBParser(
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
        """Execute EXPLAIN with intelligent fallback strategy.

        Attempts formats in this order (CRDB v23.2+):
        1. EXPLAIN (DISTSQL, ANALYZE, FORMAT JSON) — full distributed metrics
        2. EXPLAIN (ANALYZE, FORMAT JSON) — standard format, falls back for older versions
        3. EXPLAIN ANALYZE — text fallback if JSON fails

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
                original_error: str | None = None

                # Try DISTSQL format first (CockroachDB v22.1+)
                try:
                    explain_query = f"EXPLAIN (DISTSQL, ANALYZE, FORMAT JSON) {query}"
                    cursor.execute(explain_query)
                    result = cursor.fetchone()

                    if result:
                        # Parse JSON result
                        if isinstance(result[0], str):
                            explain_json = json.loads(result[0])[0]
                        else:
                            explain_json = result[0][0]
                        logger.debug("EXPLAIN DISTSQL JSON format succeeded")

                except Exception as e:
                    original_error = str(e)
                    logger.debug(f"DISTSQL EXPLAIN failed (expected for older versions): {e}")

                # Fallback: Try JSON format (standard PostgreSQL style)
                if not explain_json:
                    try:
                        # Rollback transaction to recover from previous error
                        self._connection.rollback()
                        explain_query = f"EXPLAIN (ANALYZE, FORMAT JSON) {query}"
                        cursor.execute(explain_query)
                        result = cursor.fetchone()

                        if result:
                            if isinstance(result[0], str):
                                explain_json = json.loads(result[0])[0]
                            else:
                                explain_json = result[0][0]
                            logger.debug("EXPLAIN JSON format succeeded")

                    except Exception as e:
                        if not original_error:
                            original_error = str(e)
                        logger.warning(f"JSON EXPLAIN failed: {e}, trying text fallback")

                # Fallback: Try text format
                if not explain_json:
                    try:
                        # Rollback transaction to recover from previous error
                        self._connection.rollback()
                        explain_query = f"EXPLAIN ANALYZE {query}"
                        cursor.execute(explain_query)
                        rows = cursor.fetchall()
                        explain_text = "\n".join([row[0] for row in rows])
                        logger.debug("EXPLAIN text fallback succeeded")
                    except Exception as e_text:
                        # Use original error if available, otherwise use final error
                        error_msg = original_error if original_error else str(e_text)
                        raise QueryAnalysisError(
                            f"All EXPLAIN formats failed: {error_msg}"
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

                # Normalize plan to engine-agnostic format for AntiPatternDetector
                normalized_plan = {}
                if explain_json:
                    root_plan = explain_json.get("Plan", {})
                    normalized_plan = self.parser.normalize_plan(root_plan)

                # Analyze with AntiPatternDetector for unified scoring
                detector = AntiPatternDetector()
                detection_result = detector.analyze(normalized_plan, query)

                # Convert v1 data (strings) to v2 models (Warning, Recommendation)
                warnings, recommendations = detection_result_to_warnings_and_recommendations(
                    detection_result
                )

                # If text fallback was used, extract CRDB-specific warnings from text
                if explain_text and not explain_json:
                    text_warnings = self._detect_crdb_specific_issues(explain_text, metrics)
                    # Import Warning here to avoid circular imports
                    from query_analyzer.adapters.models import Warning

                    for warning_msg in text_warnings:
                        # Parse severity from message (critical or high)
                        severity_str = "critical" if "CRITICAL" in warning_msg else "high"
                        severity: Literal["critical", "high", "medium", "low"] = cast(
                            Literal["critical", "high", "medium", "low"], severity_str
                        )
                        warnings.append(
                            Warning(
                                message=warning_msg,
                                severity=severity,
                                node_type="Seq Scan",
                                affected_object=None,
                                metadata={},
                            )
                        )

                # Build plan tree from raw EXPLAIN output
                plan_tree = None
                if explain_json:
                    root_plan = explain_json.get("Plan", {})
                    plan_tree = build_plan_tree(root_plan)

                # Build report (ensure raw_plan is None if text-only)
                raw_plan = explain_json if explain_json else None

                return QueryAnalysisReport(
                    engine="cockroachdb",
                    query=query,
                    score=detection_result.score,
                    execution_time_ms=metrics.get("execution_time_ms", 1.0),
                    warnings=warnings,
                    recommendations=recommendations,
                    plan_tree=plan_tree,
                    analyzed_at=datetime.now(UTC),
                    raw_plan=raw_plan,  # Only include JSON, not text fallback
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
            "execution_time_ms": 1.0,
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
