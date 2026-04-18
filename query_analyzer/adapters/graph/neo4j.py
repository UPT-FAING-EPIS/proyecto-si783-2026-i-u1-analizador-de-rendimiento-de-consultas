"""Neo4j database adapter using neo4j driver."""

import logging
import time
from datetime import UTC, datetime
from typing import Any

from neo4j import GraphDatabase, basic_auth
from neo4j.exceptions import (
    AuthError,
    ServiceUnavailable,
)

from query_analyzer.adapters.base import BaseAdapter
from query_analyzer.adapters.exceptions import (
    ConnectionError as AdapterConnectionError,
)
from query_analyzer.adapters.exceptions import QueryAnalysisError
from query_analyzer.adapters.migration_helpers import (
    detection_result_to_warnings_and_recommendations,
)
from query_analyzer.adapters.models import ConnectionConfig, PlanNode, QueryAnalysisReport
from query_analyzer.adapters.registry import AdapterRegistry
from query_analyzer.core.anti_pattern_detector import AntiPatternDetector

from .neo4j_metrics import Neo4jMetricsHelper
from .neo4j_parser import Neo4jExplainParser

logger = logging.getLogger(__name__)


@AdapterRegistry.register("neo4j")
class Neo4jAdapter(BaseAdapter):
    """Neo4j adapter using official neo4j driver.

    Implements all BaseAdapter methods for Neo4j, including PROFILE plan
    parsing and Cypher anti-pattern analysis.
    """

    def __init__(self, config: ConnectionConfig) -> None:
        """Initialize Neo4j adapter.

        Args:
            config: Connection configuration

        Raises:
            ConnectionConfigError: If config is invalid
        """
        super().__init__(config)
        self.parser = Neo4jExplainParser(
            expand_threshold=config.extra.get("expand_threshold", 1000)
        )
        self.metrics_helper = Neo4jMetricsHelper()
        self._driver: Any = None

    def connect(self) -> None:
        """Establish connection to Neo4j via Bolt.

        Raises:
            ConnectionError: If connection fails
        """
        try:
            host = self._config.host or "localhost"
            port = self._config.port or 7687
            database = self._config.database or "neo4j"

            uri = f"bolt://{host}:{port}"

            auth = None
            if self._config.username and self._config.password:
                auth = basic_auth(self._config.username, self._config.password)

            connection_timeout = self._config.extra.get("connection_timeout", 30)

            self._driver = GraphDatabase.driver(
                uri,
                auth=auth,
                connection_timeout=connection_timeout,
                max_connection_lifetime=3600,
            )

            with self._driver.session(database=database) as session:
                session.run("RETURN 1")

            self._is_connected = True
            self._connection = self._driver
            logger.info(f"Connected to Neo4j {host}:{port} (database: {database})")

        except (AuthError, ServiceUnavailable) as e:
            self._is_connected = False
            self._driver = None
            self._connection = None
            raise AdapterConnectionError(f"Failed to connect to Neo4j: {e}") from e
        except Exception as e:
            self._is_connected = False
            self._driver = None
            self._connection = None
            raise AdapterConnectionError(f"Unexpected error connecting to Neo4j: {e}") from e

    def disconnect(self) -> None:
        """Close Neo4j connection."""
        try:
            if self._driver:
                self._driver.close()
                logger.info("Disconnected from Neo4j")
        except Exception as e:
            logger.warning(f"Error closing connection: {e}")
        finally:
            self._driver = None
            self._connection = None
            self._is_connected = False

    def test_connection(self) -> bool:
        """Test Neo4j connection with simple query.

        Returns:
            True if connection is valid, False otherwise
        """
        try:
            if not self._is_connected or not self._driver:
                return False

            database = self._config.database or "neo4j"
            with self._driver.session(database=database) as session:
                session.run("RETURN 1")
                return True
        except Exception as e:
            logger.warning(f"Connection test failed: {e}")
            return False

    def execute_explain(self, query: str) -> QueryAnalysisReport:
        """Execute PROFILE on Cypher query and generate analysis report.

        Args:
            query: Cypher query to analyze (MATCH, WITH, CALL only)

        Returns:
            QueryAnalysisReport with analysis results (v2 model with Warning/Recommendation objects)

        Raises:
            QueryAnalysisError: If query analysis fails
        """
        if not self._is_connected or not self._driver:
            raise QueryAnalysisError("Not connected to database")

        query_upper = query.strip().upper()

        if any(query_upper.startswith(pattern) for pattern in ["CREATE", "DROP", "ALTER"]):
            raise QueryAnalysisError(
                "Cannot analyze DDL statements. Only MATCH, WITH, CALL queries are supported."
            )

        if query_upper.startswith("DELETE") and "MATCH" not in query_upper:
            raise QueryAnalysisError(
                "Cannot analyze DDL statements. Only MATCH, WITH, CALL queries are supported."
            )

        try:
            database = self._config.database or "neo4j"

            with self._driver.session(database=database) as session:
                profile_query = f"PROFILE {query}"

                start_time = time.time()
                result = session.run(profile_query)

                # Neo4j 5.26+ requires materializing results before PROFILE data is available
                # Iterate through all results to ensure they're fetched
                for _ in result:
                    pass

                summary = result.consume()
                execution_time_ms = (time.time() - start_time) * 1000

                profile_info = self._extract_profile_info(summary)

                # Parse metrics
                metrics = self.parser.parse(profile_info)
                metrics["execution_time_ms"] = execution_time_ms

                # Normalize plan for AntiPatternDetector
                plan_root = profile_info.get("profile", {}).get("plan", {})
                normalized_plan = self.parser.normalize_plan(plan_root)

                # Analyze with AntiPatternDetector
                detector = AntiPatternDetector()
                detection_result = detector.analyze(normalized_plan, query)

                # Convert to v2 models using migration helper
                warnings, recommendations = detection_result_to_warnings_and_recommendations(
                    detection_result
                )

                # Build PlanNode tree from Neo4j plan
                plan_tree = self._build_plan_tree_from_neo4j(plan_root)

                # Ensure execution_time_ms is valid
                if execution_time_ms <= 0:
                    execution_time_ms = 1.0

                # Build v2 report
                return QueryAnalysisReport(
                    engine="neo4j",
                    query=query,
                    score=detection_result.score,
                    execution_time_ms=execution_time_ms,
                    warnings=warnings,
                    recommendations=recommendations,
                    plan_tree=plan_tree,
                    analyzed_at=datetime.now(UTC),
                    raw_plan=profile_info,
                    metrics=metrics,
                )

        except QueryAnalysisError:
            raise
        except Exception as e:
            raise QueryAnalysisError(f"Failed to analyze query with PROFILE: {e}") from e

    def _build_plan_tree_from_neo4j(self, plan_root: dict[str, Any]) -> PlanNode | None:
        """Build PlanNode tree from Neo4j profile plan.

        Maps Neo4j operators (ProduceResults, NodeIndexSeek, AllNodesScan, etc.)
        to generic PlanNode structure.

        Args:
            plan_root: Root of Neo4j plan tree from PROFILE result

        Returns:
            PlanNode tree or None if plan is empty
        """
        if not plan_root:
            return None

        operator_type = plan_root.get("operatorType", "Unknown")
        rows = plan_root.get("rows", 0)
        db_hits = plan_root.get("dbHits", 0)

        # Extract operator-specific properties
        properties: dict[str, Any] = {}
        for key, value in plan_root.items():
            if key not in {"operatorType", "rows", "children"}:
                properties[key] = value

        # Add dbHits explicitly to properties
        properties["dbHits"] = db_hits

        # Recursively build children
        children: list[PlanNode] = []
        for child_plan in plan_root.get("children", []):
            if isinstance(child_plan, dict):
                child_node = self._build_plan_tree_from_neo4j(child_plan)
                if child_node:
                    children.append(child_node)

        return PlanNode(
            node_type=operator_type,
            cost=None,  # Neo4j doesn't provide cost estimates in PROFILE
            estimated_rows=None,  # Neo4j doesn't provide estimated rows
            actual_rows=rows,
            actual_time_ms=None,  # Neo4j PROFILE doesn't give per-operator time
            children=children,
            properties=properties,
        )

    def _extract_profile_info(self, summary: Any) -> dict[str, Any]:
        """Extract profile information from result summary.

        Extracts the PROFILE plan and stats from summary.profile.
        In Neo4j 5.26, summary.profile IS the root operator (flat structure with
        operatorType, rows, dbHits, children, args, etc.), not a wrapper dict.

        Args:
            summary: Result summary from Neo4j query

        Returns:
            Dict with profile structure matching parser expectations:
                {
                    "profile": {
                        "plan": {...nested tree with operatorType, rows, dbHits, children...},
                        "stats": {"rows": int, "time": int, "dbHits": int}
                    },
                    "notifications": []
                }
        """
        # Extract profile data from summary
        # In Neo4j 5.26, summary.profile IS the root operator dict (not nested under "plan")
        profile_data = summary.profile if hasattr(summary, "profile") else {}

        if not profile_data:
            return {
                "profile": {"plan": {}, "stats": {"rows": 0, "time": 0, "dbHits": 0}},
                "notifications": [],
            }

        # The root operator itself is the plan tree
        # Extract top-level metrics from the root operator
        plan = profile_data

        # Extract stats: these are also at the root level in Neo4j 5.26
        # Total execution time and row counts from root operator
        total_rows = int(profile_data.get("rows", 0))
        total_time = (
            int(profile_data.get("args", {}).get("Time", 0)) if profile_data.get("args") else 0
        )

        # Build standard structure matching parser expectations
        return {
            "profile": {
                "plan": plan,
                "stats": {
                    "rows": total_rows,
                    "time": total_time,
                    "dbHits": int(profile_data.get("dbHits", 0)),
                },
            },
            "notifications": [],
        }

    def get_slow_queries(self, threshold_ms: int = 1000) -> list[dict[str, Any]]:
        """Get slow queries (Neo4j doesn't have persistent slow query log).

        Returns empty list as Neo4j doesn't maintain a slow query log like
        PostgreSQL's pg_stat_statements. For production monitoring, users
        should configure Neo4j's query log or use Neo4j Aura insights.

        Args:
            threshold_ms: Threshold in milliseconds (unused)

        Returns:
            Empty list (Neo4j doesn't expose slow queries via driver)
        """
        logger.info(
            "Neo4j doesn't maintain a persistent slow query log. "
            "Enable query logging in neo4j.conf or use Neo4j Aura Insights."
        )
        return []

    def get_metrics(self) -> dict[str, Any]:
        """Get database metrics from Neo4j.

        Returns:
            Dict with connection, node, and relationship statistics
        """
        if not self._is_connected or not self._driver:
            return {}

        try:
            db_stats = self.metrics_helper.get_db_stats(self._driver)
            index_stats = self.metrics_helper.get_index_stats(self._driver)

            result = {
                **db_stats,
                **index_stats,
            }
            return result

        except Exception as e:
            logger.warning(f"Failed to retrieve metrics: {e}")
            return {}

    def get_engine_info(self) -> dict[str, Any]:
        """Get Neo4j version and configuration.

        Returns:
            Dict with version and configuration settings
        """
        if not self._is_connected or not self._driver:
            return {}

        try:
            server_info = self.metrics_helper.get_server_info(self._driver)

            return {
                "engine": "neo4j",
                **server_info,
            }

        except Exception as e:
            logger.warning(f"Failed to retrieve engine info: {e}")
            return {}
