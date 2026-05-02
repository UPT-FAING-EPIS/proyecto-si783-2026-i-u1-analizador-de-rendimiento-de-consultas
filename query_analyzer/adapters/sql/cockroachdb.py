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
                query_stripped = query.strip()
                query_upper = query_stripped.upper()

                # CRDB v26.1+ removed FORMAT JSON and ANALYZE option from EXPLAIN.
                # Use EXPLAIN ANALYZE (VERBOSE) for text output with full detail.
                if query_upper.startswith("EXPLAIN "):
                    explain_query = query_stripped
                else:
                    explain_query = f"EXPLAIN ANALYZE (VERBOSE) {query_stripped}"

                cursor.execute(explain_query)
                rows = cursor.fetchall()
                explain_text = "\n".join([row[0] for row in rows])

                # Parse text output into JSON-like structure for existing pipeline
                explain_json = self._parse_text_to_json_plan(explain_text)
                metrics = self.parser.parse(explain_json) if explain_json else self._parse_text_explain(explain_text)

                # Normalize plan for AntiPatternDetector
                normalized_plan = {}
                if explain_json:
                    root_plan = explain_json.get("Plan", {})
                    if root_plan:
                        normalized_plan = self.parser.normalize_plan(root_plan)

                # Analyze with AntiPatternDetector
                detector = AntiPatternDetector()
                detection_result = detector.analyze(normalized_plan, query)

                # Convert to v2 models
                warnings, recommendations = detection_result_to_warnings_and_recommendations(
                    detection_result
                )

                # Extract CRDB-specific warnings from text
                text_warnings = self._detect_crdb_specific_issues(explain_text, metrics)
                from query_analyzer.adapters.models import Warning

                for warning_msg in text_warnings:
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

                # Build plan tree
                plan_tree = None
                if explain_json:
                    root_plan = explain_json.get("Plan", {})
                    if root_plan:
                        plan_tree = build_plan_tree(root_plan)

                return QueryAnalysisReport(
                    engine="cockroachdb",
                    query=query,
                    score=detection_result.score,
                    execution_time_ms=metrics.get("execution_time_ms", 1.0),
                    warnings=warnings,
                    recommendations=recommendations,
                    plan_tree=plan_tree,
                    analyzed_at=datetime.now(UTC),
                    raw_plan=explain_json,
                    metrics=metrics,
                )

        except QueryAnalysisError:
            raise
        except Exception as e:
            self._connection.rollback()
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

    def _parse_text_to_json_plan(self, explain_text: str) -> dict[str, Any]:
        """Convert CRDB v26.1+ text EXPLAIN ANALYZE output to JSON-like dict.

        CRDB v26.1 removed FORMAT JSON support. This parser converts the
        structured text output back into a dict compatible with the existing
        PostgreSQLExplainParser pipeline.

        Args:
            explain_text: Text output from EXPLAIN ANALYZE (VERBOSE)

        Returns:
            Dict mimicking old JSON EXPLAIN format with Plan, Planning Time, etc.
        """
        import re

        lines = explain_text.split("\n")

        # Parse header metrics
        planning_time_ms = 0.0
        execution_time_ms = 1.0
        distribution = "local"
        vectorized = True
        header_done = False

        # Parse tree structure
        plan_nodes: list[dict[str, Any]] = []
        node_stack: list[dict[str, Any]] = []  # parent chain by indent
        current_node: dict[str, Any] | None = None
        current_attrs: dict[str, str] = {}

        # Regex patterns
        kv_re = re.compile(r'"\s*([^:]+):\s*(.+)"$')

        for line in lines:
            # Parse header line (key: value without quotes)
            if not header_done and ": " in line and not line.strip().startswith('"'):
                if line.strip().startswith("•") or line.strip().startswith("└"):
                    header_done = True
                    # Fall through to tree parsing
                else:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        if key == "planning time":
                            planning_time_ms = self._parse_time_to_ms(value)
                        elif key == "execution time":
                            execution_time_ms = self._parse_time_to_ms(value)
                        continue

            # Parse tree nodes
            stripped = line.strip()
            if not stripped:
                continue

            # Detect node header lines (start with • or tree char)
            if stripped.startswith("•") or stripped.startswith("└") or stripped.startswith("├"):
                # Save previous node
                if current_node is not None:
                    current_node.update(self._build_node_fields(current_attrs))
                    plan_nodes.append(current_node)

                # Determine indent level
                leading_spaces = len(line) - len(line.lstrip())
                indent_level = leading_spaces // 2 if leading_spaces > 0 else 0

                # Pop stack to correct depth
                while len(node_stack) > indent_level:
                    node_stack.pop()

                # Extract node type name
                node_name = re.sub(r"^[•└├│\s]+", "", stripped).strip()
                current_node = {
                    "Node Type": node_name,
                    "Plans": [],
                }
                current_attrs = {}

                # Link to parent
                if node_stack:
                    parent = node_stack[-1]
                    if "Plans" not in parent:
                        parent["Plans"] = []
                    parent["Plans"].append(current_node)

                node_stack.append(current_node)

            # Parse attribute lines (quoted key-value)
            elif stripped.startswith('"'):
                match = kv_re.match(stripped)
                if match and current_node is not None:
                    key = match.group(1).strip()
                    value = match.group(2).strip()
                    current_attrs[key] = value

        # Save last node
        if current_node is not None:
            current_node.update(self._build_node_fields(current_attrs))
            plan_nodes.append(current_node)

        # Build result
        root_plan = plan_nodes[0] if plan_nodes else {}

        return {
            "Plan": root_plan,
            "Planning Time": planning_time_ms,
            "Execution Time": execution_time_ms,
            "distribution": distribution,
            "vectorized": vectorized,
        }

    def _build_node_fields(self, attrs: dict[str, str]) -> dict[str, Any]:
        """Convert parsed text attributes to JSON plan node fields.

        Maps CRDB text attribute names to the field names expected by
        PostgreSQLExplainParser (which expects JSON format keys).
        """
        import re

        result: dict[str, Any] = {}

        # Map common attributes
        attr_map = {
            "actual row count": "Actual Rows",
            "estimated row count": "Plan Rows",
            "execution time": "Actual Total Time",
            "sql cpu time": "SQL CPU Time",
            "kv time": "KV Time",
            "kv rows decoded": "KV Rows Decoded",
            "sql nodes": "SQL Nodes",
            "kv nodes": "KV Nodes",
            "size": "Output Size",
            "spans": "Scan Span",
        }

        for text_key, json_key in attr_map.items():
            if text_key in attrs:
                value = attrs[text_key]
                # Extract numeric values
                if text_key in ("actual row count", "estimated row count", "kv rows decoded"):
                    try:
                        result[json_key] = int(re.sub(r"[,\s].*", "", value).replace(",", ""))
                    except ValueError:
                        result[json_key] = 0
                elif text_key in ("execution time", "sql cpu time", "kv time"):
                    result[json_key] = self._parse_time_to_ms(value)
                else:
                    result[json_key] = value

        # Parse table info: "table_name@index_name"
        if "table" in attrs:
            table_info = attrs["table"]
            if "@" in table_info:
                parts = table_info.split("@", 1)
                result["Relation Name"] = parts[0].strip()
                result["Index Name"] = parts[1].strip()
            else:
                result["Relation Name"] = table_info.strip()

        # Detect full scan
        if "spans" in attrs and "FULL SCAN" in attrs["spans"].upper():
            result["Node Type"] = "Seq Scan"

        # Extract scan cost if present
        if "estimated max memory allocated" in attrs:
            mem_str = attrs["estimated max memory allocated"]
            try:
                mem_val = re.sub(r"[^0-9.]", "", mem_str.split()[0])
                result["Estimated Cost"] = float(mem_val)
            except (ValueError, IndexError):
                pass

        return result

    @staticmethod
    def _parse_time_to_ms(time_str: str) -> float:
        """Parse CRDB time string like '57ms', '136µs', '1.5s' to milliseconds.

        Args:
            time_str: Time string from CRDB EXPLAIN output

        Returns:
            Time in milliseconds as float
        """
        import re

        time_str = time_str.strip()
        # Handle compound format like "57ms"
        match = re.match(r"([\d.]+)\s*(ms|µs|s|us|m|h)", time_str)
        if match:
            value = float(match.group(1))
            unit = match.group(2)
            if unit in ("µs", "us"):
                return value / 1000.0
            elif unit == "ms":
                return value
            elif unit == "s":
                return value * 1000.0
            elif unit == "m":
                return value * 60000.0
            elif unit == "h":
                return value * 3600000.0
        # Plain number
        try:
            return float(re.sub(r"[^0-9.]", "", time_str))
        except ValueError:
            return 0.0

    def _parse_text_explain(self, explain_text: str) -> dict[str, Any]:
        """Parse text-format EXPLAIN output into metrics dict.

        Extracts real metrics from CRDB v26.1 text output.

        Args:
            explain_text: Text-format EXPLAIN output

        Returns:
            Dictionary with metrics structure
        """
        import re

        lines = explain_text.split("\n")
        planning_time_ms = 0.0
        execution_time_ms = 1.0
        distribution = "local"
        node_count = 0
        scan_nodes: list[dict[str, Any]] = []
        join_nodes: list[dict[str, Any]] = []
        all_nodes: list[dict[str, Any]] = []
        actual_rows_total = 0
        plan_rows_total = 0

        for line in lines:
            stripped = line.strip()
            if ":" in stripped and not stripped.startswith('"'):
                parts = stripped.split(":", 1)
                key = parts[0].strip()
                value = parts[1].strip()
                if key == "planning time":
                    planning_time_ms = self._parse_time_to_ms(value)
                elif key == "execution time":
                    execution_time_ms = self._parse_time_to_ms(value)
                elif key == "distribution":
                    distribution = value

        # Count nodes and extract row info
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("•") or stripped.startswith("└") or stripped.startswith("├"):
                node_count += 1
            if '"  actual row count:' in stripped:
                match = re.search(r"actual row count:\s*([\d,]+)", stripped)
                if match:
                    rows = int(match.group(1).replace(",", ""))
                    actual_rows_total += rows

        return {
            "planning_time_ms": planning_time_ms,
            "execution_time_ms": execution_time_ms,
            "total_cost": 0.0,
            "actual_rows_total": actual_rows_total,
            "plan_rows_total": plan_rows_total,
            "node_count": node_count,
            "most_expensive_node": None,
            "buffer_stats": {},
            "scan_nodes": scan_nodes,
            "join_nodes": join_nodes,
            "all_nodes": all_nodes,
            "distribution": distribution,
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
