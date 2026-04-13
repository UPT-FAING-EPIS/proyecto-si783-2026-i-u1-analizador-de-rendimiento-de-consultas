"""SQLite Database Adapter.

Provides query analysis for SQLite databases using EXPLAIN QUERY PLAN.
Supports both in-memory and file-based databases.
"""

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from query_analyzer.adapters.base import BaseAdapter
from query_analyzer.adapters.exceptions import (
    ConnectionError as AdapterConnectionError,
)
from query_analyzer.adapters.exceptions import (
    DisconnectionError,
    QueryAnalysisError,
)
from query_analyzer.adapters.migration_helpers import (
    build_plan_tree,
    detection_result_to_warnings_and_recommendations,
)
from query_analyzer.adapters.models import ConnectionConfig, QueryAnalysisReport
from query_analyzer.adapters.registry import AdapterRegistry
from query_analyzer.core.anti_pattern_detector import AntiPatternDetector

from .sqlite_metrics import SQLiteMetricsHelper
from .sqlite_parser import SQLiteExplainParser

logger = logging.getLogger(__name__)


@AdapterRegistry.register("sqlite")
class SQLiteAdapter(BaseAdapter):
    """SQLite adapter for query analysis using EXPLAIN QUERY PLAN.

    Supports:
    - File-based databases (relative and absolute paths)
    - In-memory databases (:memory:)
    - Analysis of SELECT, INSERT, UPDATE, DELETE statements
    - Rejection of DDL statements (CREATE, ALTER, DROP, TRUNCATE)
    """

    def __init__(self, config: ConnectionConfig):
        """Initialize SQLite adapter.

        Args:
            config: ConnectionConfig with database path in config.database
                   Example: ConnectionConfig(
                       engine="sqlite",
                       host="localhost",  # Unused for SQLite
                       port=0,  # Unused for SQLite
                       database="path/to/database.db",
                       username="",  # Unused
                       password=""  # Unused
                   )
        """
        super().__init__(config)
        self.parser = SQLiteExplainParser()
        self.metrics = SQLiteMetricsHelper()

    def connect(self) -> None:
        """Establish connection to SQLite database.

        Creates database file if it doesn't exist (unless :memory:).

        Raises:
            AdapterConnectionError: If connection fails
        """
        try:
            db_path = self._config.database

            if db_path == ":memory:":
                self._connection = sqlite3.connect(":memory:")
            else:
                path = Path(db_path)

                if path.parent != Path("."):
                    path.parent.mkdir(parents=True, exist_ok=True)

                self._connection = sqlite3.connect(str(path))

            self._connection.execute("PRAGMA foreign_keys = ON")

            self._is_connected = True
        except sqlite3.Error as e:
            raise AdapterConnectionError(
                f"Failed to connect to SQLite database '{self._config.database}': {e}"
            ) from e
        except Exception as e:
            raise AdapterConnectionError(f"Unexpected error connecting to SQLite: {e}") from e

    def disconnect(self) -> None:
        """Close database connection.

        Raises:
            DisconnectionError: If disconnection fails
        """
        try:
            if self._connection:
                self._connection.close()
                self._connection = None
            self._is_connected = False
        except sqlite3.Error as e:
            raise DisconnectionError(f"Failed to disconnect from SQLite: {e}") from e

    def test_connection(self) -> bool:
        """Test if connection is valid.

        Returns:
            True if connection is working, False otherwise.

        Note:
            Errores en test de conexión retornan False en lugar de propagar
            excepciones, permitiendo detección segura de desconexión.
        """
        if not self.is_connected():
            return False

        try:
            cursor = self.get_connection().cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            return True
        except Exception:
            return False

    def execute_explain(self, query: str) -> QueryAnalysisReport:
        """Analyze query using EXPLAIN QUERY PLAN.

        Args:
            query: SQL query to analyze (SELECT, INSERT, UPDATE, DELETE)

        Returns:
            QueryAnalysisReport with analysis results

        Raises:
            QueryAnalysisError: If query is invalid or analysis fails
        """
        if not self.is_connected():
            raise QueryAnalysisError("Not connected to database")

        if self._is_ddl_statement(query):
            raise QueryAnalysisError(
                "DDL statements (CREATE, ALTER, DROP, TRUNCATE) are not supported for analysis"
            )

        try:
            cursor = self.get_connection().cursor()

            explain_query = f"EXPLAIN QUERY PLAN {query}"
            cursor.execute(explain_query)

            rows = cursor.fetchall()
            explain_text = self._format_explain_output(rows)

            parsed_plan = self.parser.parse(explain_text)

            # Normalize plan to engine-agnostic format for AntiPatternDetector
            # SQLite parse() returns dict with nodes list, normalize each top-level node
            # For simplicity, we normalize the first node (SQLite usually has single root)
            normalized_plan = {}
            if parsed_plan.get("nodes"):
                # Build normalized plan from SQLite nodes
                # SQLite's structure is different - we need to construct a normalized tree
                normalized_plan = self._build_normalized_plan_from_nodes(
                    parsed_plan.get("nodes", [])
                )

            # Analyze with AntiPatternDetector for unified scoring
            detector = AntiPatternDetector()
            detection_result = detector.analyze(normalized_plan, query)

            # Convert v1 data (strings) to v2 models (Warning, Recommendation)
            warnings, recommendations = detection_result_to_warnings_and_recommendations(
                detection_result
            )

            # Build plan tree from parsed plan
            plan_tree = build_plan_tree(parsed_plan)

            metrics = self._get_query_metrics()

            report = QueryAnalysisReport(
                engine="sqlite",
                query=query,
                score=detection_result.score,
                execution_time_ms=1.0,
                warnings=warnings,
                recommendations=recommendations,
                plan_tree=plan_tree,
                analyzed_at=datetime.now(UTC),
                raw_plan=parsed_plan,
                metrics=metrics,
            )

            return report

        except sqlite3.Error as e:
            raise QueryAnalysisError(f"SQLite error during explain: {e}") from e
        except Exception as e:
            raise QueryAnalysisError(f"Error analyzing query: {e}") from e

    def get_slow_queries(self, threshold_ms: int = 1000) -> list[dict[str, Any]]:
        """Get slow queries (not supported in SQLite).

        SQLite doesn't have a native slow query log. This method returns
        an empty list as per design decision.

        Args:
            threshold_ms: Unused (kept for interface compatibility)

        Returns:
            Empty list (SQLite doesn't support slow query logs)
        """
        return []

    def get_metrics(self) -> dict[str, Any]:
        """Get database metrics.

        Returns:
            Dict with: tables, indexes, page_size, page_count, total_size_mb, cache_config.
            Returns empty dict if metrics retrieval fails (strategy: fail-safe).

        Note:
            Errores en consultas de métricas retornan dict vacío en lugar de
            propagar excepciones, permitiendo análisis parcial.
        """
        if not self.is_connected():
            return {}

        try:
            conn = self.get_connection()

            table_count = self.metrics.get_table_count(conn)
            index_count = self.metrics.get_index_count(conn)

            page_stats = self.metrics.get_page_stats(conn)

            cache_settings = self.metrics.get_cache_settings(conn)

            db_path = self._config.database
            file_size = self.metrics.get_database_size(conn, db_path)

            return {
                "tables": table_count,
                "indexes": index_count,
                "page_size_bytes": page_stats.get("page_size", 0),
                "page_count": page_stats.get("page_count", 0),
                "total_size_bytes": file_size
                if file_size > 0
                else page_stats.get("total_size_bytes", 0),
                "cache_size_pages": cache_settings.get("cache_size_pages", 0),
                "cache_size_bytes": cache_settings.get("cache_size_bytes", 0),
            }
        except Exception as e:
            logger.debug(f"Failed to get metrics: {e}")
            return {}

        try:
            conn = self.get_connection()

            table_count = self.metrics.get_table_count(conn)
            index_count = self.metrics.get_index_count(conn)

            page_stats = self.metrics.get_page_stats(conn)

            cache_settings = self.metrics.get_cache_settings(conn)

            db_path = self._config.database
            file_size = self.metrics.get_database_size(conn, db_path)

            return {
                "tables": table_count,
                "indexes": index_count,
                "page_size_bytes": page_stats.get("page_size", 0),
                "page_count": page_stats.get("page_count", 0),
                "total_size_bytes": file_size
                if file_size > 0
                else page_stats.get("total_size_bytes", 0),
                "cache_size_pages": cache_settings.get("cache_size_pages", 0),
                "cache_size_bytes": cache_settings.get("cache_size_bytes", 0),
            }
        except Exception as e:
            import logging

            logging.getLogger(__name__).debug(f"Failed to get metrics: {e}")
            return {}

    def get_engine_info(self) -> dict[str, Any]:
        """Get SQLite engine information.

        Returns:
            Dict with: version, engine, database_path, max_connections.
            Returns empty dict if retrieval fails (strategy: fail-safe).

        Note:
            Errores en consultas retornan dict vacío en lugar de propagar
            excepciones, permitiendo análisis parcial.
        """
        if not self.is_connected():
            return {}

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT sqlite_version()")
            version = cursor.fetchone()[0]

            return {
                "version": version,
                "engine": "sqlite",
                "database_path": str(self._config.database),
                "max_connections": 1,
            }
        except Exception as e:
            logger.debug(f"Failed to get engine info: {e}")
            return {}

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT sqlite_version()")
            version = cursor.fetchone()[0]

            return {
                "version": version,
                "engine": "sqlite",
                "database_path": str(self._config.database),
                "max_connections": 1,
            }
        except Exception as e:
            import logging

            logging.getLogger(__name__).debug(f"Failed to get engine info: {e}")
            return {}

    def _is_ddl_statement(self, query: str) -> bool:
        """Check if query is a DDL statement.

        Args:
            query: SQL query string

        Returns:
            True if DDL (CREATE, ALTER, DROP, TRUNCATE), False otherwise
        """
        clean_query = query.strip()

        lines = [
            line.split("--")[0].strip()
            for line in clean_query.split("\n")
            if line.strip() and not line.strip().startswith("--")
        ]

        if not lines:
            return False

        first_word = lines[0].split()[0].upper()

        return first_word in {"CREATE", "ALTER", "DROP", "TRUNCATE"}

    def _format_explain_output(self, rows: list[tuple]) -> str:
        """Format EXPLAIN results into tab-separated text.

        SQLite's cursor.fetchall() returns tuples. Convert to formatted string.

        Args:
            rows: List of tuples from EXPLAIN QUERY PLAN

        Returns:
            Tab-separated string with header and data rows
        """
        if not rows:
            return ""

        lines = ["id\tparent\tnotused\tdetail"]

        for row in rows:
            line = "\t".join(str(val) for val in row)
            lines.append(line)

        return "\n".join(lines)

    def _get_query_metrics(self) -> dict[str, Any]:
        """Get basic metrics for a query analysis.

        Returns:
            Dict with query-related metrics
        """
        if not self.is_connected():
            return {}

        try:
            conn = self.get_connection()
            pragmas = self.metrics.get_pragmas(conn)
            cache = self.metrics.get_cache_settings(conn)

            return {
                "journal_mode": pragmas.get("journal_mode"),
                "foreign_keys_enabled": pragmas.get("foreign_keys") == 1,
                "query_only_mode": pragmas.get("query_only") == 1,
                "cache_size_bytes": cache.get("cache_size_bytes", 0),
            }
        except Exception:
            return {}

    def _build_normalized_plan_from_nodes(self, nodes: list[dict[str, Any]]) -> dict[str, Any]:
        """Build a normalized plan from SQLite EXPLAIN QUERY PLAN nodes.

        SQLite returns a flat list of nodes. This converts them to a tree structure
        compatible with AntiPatternDetector.

        Args:
            nodes: List of parsed nodes from SQLiteParser

        Returns:
            Normalized plan dict with standard fields
        """
        if not nodes:
            return {}

        # Find root nodes (parent == 0 or no parent in list)
        root_nodes = [node for node in nodes if node.get("parent") == 0]

        if not root_nodes:
            # If no clear root, use first node
            root_nodes = [nodes[0]]

        # Convert first root node to normalized format
        root = root_nodes[0]

        # Determine node type based on SQLite operation
        detail = root.get("detail", "")
        is_full_scan = root.get("is_full_scan", False)
        node_type = "Seq Scan" if is_full_scan else "Index Scan"

        # Build children from nodes with this node as parent
        children = []
        for node in nodes:
            if node.get("parent") == root.get("id"):
                child_normalized = self._build_normalized_plan_from_nodes([node])
                if child_normalized:
                    children.append(child_normalized)

        return {
            "node_type": node_type,
            "table_name": root.get("table"),
            "actual_rows": None,  # SQLite EXPLAIN doesn't provide actual rows
            "estimated_rows": None,  # SQLite EXPLAIN doesn't provide estimates
            "actual_time_ms": None,
            "estimated_cost": None,
            "index_used": root.get("index"),
            "filter_condition": None,
            "extra_info": [detail] if detail else [],
            "buffers": None,
            "children": children,
        }
