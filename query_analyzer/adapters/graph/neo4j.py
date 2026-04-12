"""Neo4j database adapter using neo4j driver."""

import logging
import time
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
from query_analyzer.adapters.models import ConnectionConfig, QueryAnalysisReport
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

            # Build connection URI
            uri = f"bolt://{host}:{port}"

            # Create driver with authentication
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

            # Test connection
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
            QueryAnalysisReport with analysis results

        Raises:
            QueryAnalysisError: If query analysis fails
        """
        if not self._is_connected or not self._driver:
            raise QueryAnalysisError("Not connected to database")

        # Validate query is not DDL
        query_upper = query.strip().upper()

        # Reject CREATE, DROP, ALTER (these are DDL)
        if any(query_upper.startswith(pattern) for pattern in ["CREATE", "DROP", "ALTER"]):
            raise QueryAnalysisError(
                "Cannot analyze DDL statements. Only MATCH, WITH, CALL queries are supported."
            )

        # Reject DELETE that isn't part of a pattern (DELETE without MATCH)
        if query_upper.startswith("DELETE") and "MATCH" not in query_upper:
            raise QueryAnalysisError(
                "Cannot analyze DDL statements. Only MATCH, WITH, CALL queries are supported."
            )

        try:
            database = self._config.database or "neo4j"

            with self._driver.session(database=database) as session:
                # Wrap with PROFILE
                profile_query = f"PROFILE {query}"

                # Execute PROFILE query
                start_time = time.time()
                result = session.run(profile_query)

                # Get result and consume it to populate profile data
                summary = result.consume()
                execution_time_ms = (time.time() - start_time) * 1000

                # Extract profile info from summary
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

                # Use detector's score and recommendations
                warnings = [ap.description for ap in detection_result.anti_patterns]
                recommendations = detection_result.recommendations
                score = detection_result.score

                # Build report
                return QueryAnalysisReport(
                    engine="neo4j",
                    query=query,
                    score=score,
                    execution_time_ms=execution_time_ms,
                    warnings=warnings,
                    recommendations=recommendations,
                    raw_plan=profile_info,
                    metrics=metrics,
                )

        except QueryAnalysisError:
            raise
        except Exception as e:
            raise QueryAnalysisError(f"Failed to analyze query with PROFILE: {e}") from e

    def _extract_profile_info(self, summary: Any) -> dict[str, Any]:
        """Extract profile information from result summary.

        Extracts the PROFILE plan and stats directly from summary.profile,
        which contains the nested plan tree (with children) and aggregated
        metrics (rows, time, dbHits).

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
        # Extract profile data from summary (contains plan tree and stats)
        profile_data = summary.profile if hasattr(summary, "profile") else {}

        # Extract plan (nested tree structure)
        plan = profile_data.get("plan", {}) if profile_data else {}

        # Extract stats (aggregated metrics)
        stats = profile_data.get("stats", {}) if profile_data else {}

        # Build standard structure matching parser expectations
        return {
            "profile": {
                "plan": plan,
                "stats": {
                    "rows": int(stats.get("rows", 0)) if stats else 0,
                    "time": int(stats.get("time", 0)) if stats else 0,
                    "dbHits": int(stats.get("dbHits", 0)) if stats else 0,
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
