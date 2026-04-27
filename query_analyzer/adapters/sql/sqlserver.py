"""MSSQL (SQL Server) database adapter using pymssql."""

import logging
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any

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

from .sqlserver_metrics import MSSQLMetricsHelper
from .sqlserver_parser import MSSQLExplainParser

logger = logging.getLogger(__name__)

try:
    import pymssql
    _PYMSSQL_AVAILABLE = True
except ImportError:
    pymssql = None  # type: ignore
    _PYMSSQL_AVAILABLE = False


@AdapterRegistry.register("mssql")
class MSSQLAdapter(BaseAdapter):
    """SQL Server adapter using pymssql driver.

    Implements all BaseAdapter methods for Microsoft SQL Server,
    using SET SHOWPLAN_XML ON for EXPLAIN analysis and DMV queries
    for metrics and slow query detection.
    """

    def __init__(self, config: ConnectionConfig) -> None:
        """Initialize SQL Server adapter.

        Args:
            config: Connection configuration
        """
        super().__init__(config)
        self._connection: Any = None
        self.parser = MSSQLExplainParser(
            seq_scan_threshold=config.extra.get("seq_scan_threshold", 10000)
        )
        self.metrics_helper = MSSQLMetricsHelper()

    def _check_driver(self) -> None:
        """Verify pymssql is installed.

        Raises:
            AdapterConnectionError: If pymssql is not available
        """
        if not _PYMSSQL_AVAILABLE:
            raise AdapterConnectionError(
                "pymssql is not installed. Install it with: pip install pymssql"
            )

    def connect(self) -> None:
        """Establish connection to SQL Server using pymssql.

        Raises:
            AdapterConnectionError: If connection fails
        """
        self._check_driver()

        try:
            self._connection = pymssql.connect(
                server=self._config.host or "localhost",
                port=str(self._config.port or 1433),
                database=self._config.database,
                user=self._config.username,
                password=self._config.password or "",
                timeout=self._config.extra.get("connection_timeout", 10),
                login_timeout=self._config.extra.get("login_timeout", 10),
            )
            self._is_connected = True
            logger.info(
                f"Connected to SQL Server {self._config.host}:{self._config.port}"
            )
        except pymssql.OperationalError as e:
            self._is_connected = False
            self._connection = None
            raise AdapterConnectionError(
                f"Failed to connect to SQL Server: {e}"
            ) from e

    def disconnect(self) -> None:
        """Close SQL Server connection."""
        if self._connection:
            try:
                self._connection.close()
                logger.info("Disconnected from SQL Server")
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
            finally:
                self._connection = None
                self._is_connected = False

    def test_connection(self) -> bool:
        """Test connection with SELECT 1.

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
            logger.debug(f"Connection test failed: {e}")
            return False

    def execute_explain(self, query: str) -> QueryAnalysisReport:
        """Execute SHOWPLAN_XML analysis on SQL query.

        Uses SET SHOWPLAN_XML ON to obtain the execution plan as XML
        without actually executing the query.

        Args:
            query: SQL query to analyze (SELECT/INSERT/UPDATE/DELETE)

        Returns:
            QueryAnalysisReport with analysis results

        Raises:
            QueryAnalysisError: If query is DDL or analysis fails
        """
        if not self._is_connected:
            raise QueryAnalysisError("Not connected to database")

        query_upper = query.strip().upper()
        if any(
            query_upper.startswith(ddl)
            for ddl in ["CREATE", "ALTER", "DROP", "TRUNCATE"]
        ):
            raise QueryAnalysisError(
                "Cannot analyze DDL statements. "
                "Only SELECT, INSERT, UPDATE, DELETE are supported."
            )

        try:
            with self._connection.cursor() as cursor:
                query_stripped = query.strip()

                cursor.execute("SET SHOWPLAN_XML ON")
                cursor.execute(query_stripped)
                result = cursor.fetchone()
                cursor.execute("SET SHOWPLAN_XML OFF")

                if not result or not result[0]:
                    raise QueryAnalysisError(
                        "SHOWPLAN_XML returned no results"
                    )

                raw_xml = result[0]
                if isinstance(raw_xml, bytes):
                    raw_xml = raw_xml.decode("utf-16-le")

                metrics = self.parser.parse(raw_xml)
                normalized_plan = self.parser.normalize_plan(raw_xml)

                detector = AntiPatternDetector()
                detection_result = detector.analyze(normalized_plan, query)

                warnings, recommendations = (
                    detection_result_to_warnings_and_recommendations(
                        detection_result
                    )
                )

                plan_dict = self._xml_to_plan_dict(raw_xml)
                plan_tree = build_plan_tree(plan_dict)

                return QueryAnalysisReport(
                    engine="mssql",
                    query=query,
                    score=detection_result.score,
                    execution_time_ms=1.0,
                    warnings=warnings,
                    recommendations=recommendations,
                    plan_tree=plan_tree,
                    analyzed_at=datetime.now(UTC),
                    raw_plan={"xml": raw_xml, **metrics},
                    metrics=metrics,
                )

        except QueryAnalysisError:
            raise
        except Exception as e:
            try:
                with self._connection.cursor() as c:
                    c.execute("SET SHOWPLAN_XML OFF")
            except Exception:
                pass
            self._connection.rollback()
            raise QueryAnalysisError(
                f"Failed to analyze query: {e}"
            ) from e

    def _xml_to_plan_dict(self, xml_string: str) -> dict[str, Any]:
        """Convert raw SHOWPLAN XML to a dict compatible with build_plan_tree().

        build_plan_tree() expects keys like 'Node Type', 'Total Cost',
        'Estimated Rows', 'Plans' (children).

        Args:
            xml_string: Raw XML from SHOWPLAN_XML

        Returns:
            Dict compatible with build_plan_tree
        """
        try:
            root = ET.fromstring(xml_string)
            ns = {"sql": MSSQLExplainParser._SHOWPLAN_NS}
            stmt = root.find(".//sql:StmtSimple", ns)
            if stmt is None:
                return {}
            query_plan = stmt.find("sql:QueryPlan", ns)
            if query_plan is None:
                return {}
            relop = query_plan.find("sql:RelOp", ns)
            if relop is None:
                return {}
            return self._relop_to_dict(relop, ns)
        except Exception as e:
            logger.debug(f"Failed to convert XML to plan dict: {e}")
            return {}

    def _relop_to_dict(
        self, relop: ET.Element, ns: dict[str, str]
    ) -> dict[str, Any]:
        """Recursively convert RelOp element to dict for build_plan_tree."""
        physical_op = relop.get("PhysicalOp", "Unknown")

        node_type_map = {
            "Table Scan": "Seq Scan",
            "Clustered Index Scan": "Seq Scan",
            "Clustered Index Seek": "Index Seek",
            "Index Scan": "Index Scan",
            "Index Seek": "Index Seek",
        }
        node_type = node_type_map.get(physical_op, physical_op)

        estimate_rows = relop.get("EstimateRows")
        total_cost = relop.get("EstimatedTotalSubtreeCost")

        result: dict[str, Any] = {
            "Node Type": node_type,
            "Estimated Rows": (
                int(float(estimate_rows)) if estimate_rows else 0
            ),
            "Total Cost": float(total_cost) if total_cost else 0.0,
        }

        obj = relop.find("sql:Object", ns)
        if obj is not None:
            result["Relation Name"] = obj.get("Table", "unknown")
            index_name = obj.get("Index")
            if index_name:
                result["Index Name"] = index_name

        result["Plans"] = []
        for child in relop.findall("sql:RelOp", ns):
            result["Plans"].append(self._relop_to_dict(child, ns))

        return result

    def get_slow_queries(
        self, threshold_ms: int = 1000
    ) -> list[dict[str, Any]]:
        """Get slow queries from sys.dm_exec_query_stats.

        Args:
            threshold_ms: Threshold in milliseconds (default: 1000)

        Returns:
            List of dicts with query timing information (empty list on failure)
        """
        if not self._is_connected:
            return []

        try:
            return self.metrics_helper.get_slow_queries_from_dmv(
                self._connection, threshold_ms=threshold_ms
            )
        except Exception as e:
            logger.warning(f"Failed to retrieve slow queries: {e}")
            return []

    def get_metrics(self) -> dict[str, Any]:
        """Get SQL Server performance metrics from DMVs.

        Returns:
            Dict with connection and performance metrics (empty on failure)
        """
        if not self._is_connected:
            return {}

        try:
            db_stats = self.metrics_helper.get_db_stats(self._connection)
            settings = self.metrics_helper.get_settings(self._connection)

            return {
                **db_stats,
                **settings,
            }
        except Exception as e:
            logger.warning(f"Failed to retrieve metrics: {e}")
            return {}

    def get_engine_info(self) -> dict[str, Any]:
        """Get SQL Server version and edition info.

        Returns:
            Dict with version, edition, and engine name
        """
        if not self._is_connected:
            return {}

        try:
            version = self.metrics_helper.get_version(self._connection)
            product_version = self.metrics_helper.get_product_version(
                self._connection
            )
            edition = self.metrics_helper.get_edition(self._connection)

            return {
                "version": version,
                "product_version": product_version,
                "edition": edition,
                "engine": "mssql",
            }
        except Exception as e:
            logger.warning(f"Failed to retrieve engine info: {e}")
            return {}
