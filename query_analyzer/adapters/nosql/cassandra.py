"""Cassandra adapter for query performance analysis.

Uses cassandra-driver to connect to Cassandra clusters.
Analyzes query performance using TRACING and schema analysis.

Key features:
- TRACING ON to capture event timeline
- ALLOW FILTERING detection (critical anti-pattern)
- Full cluster scan detection
- Partition key analysis via system.schema_*
- Size estimation via system.size_estimates

Note: cassandra-driver requires explicit installation on Python 3.14
due to Windows build issues. Install with: pip install cassandra-driver==3.29.3
"""

import logging
import re
from datetime import UTC, datetime
from typing import Any

from ..base import BaseAdapter
from ..exceptions import ConnectionError as AdapterConnectionError
from ..exceptions import QueryAnalysisError
from ..models import ConnectionConfig, QueryAnalysisReport, Recommendation, Warning
from ..registry import AdapterRegistry
from .cassandra_parser import CassandraExplainParser

logger = logging.getLogger(__name__)

# Import cassandra-driver (optional)
try:
    from cassandra.cluster import Cluster, NoHostAvailable
    from cassandra.protocol import InvalidRequest

    HAS_CASSANDRA = True
except ImportError:
    Cluster = None
    NoHostAvailable = None
    InvalidRequest = None
    HAS_CASSANDRA = False


@AdapterRegistry.register("cassandra")
class CassandraAdapter(BaseAdapter):
    """Adapter for Cassandra query performance analysis.

    Supports SELECT queries with tracing and anti-pattern detection.
    Analyzes queries for ALLOW FILTERING, full cluster scans, and partition
    key usage.
    """

    def __init__(self, config: ConnectionConfig) -> None:
        """Initialize Cassandra adapter.

        Args:
            config: ConnectionConfig with Cassandra connection details
                - host: Contact point IP or hostname (e.g., "127.0.0.1")
                - port: Cassandra port (default 9042)
                - database: Keyspace name
                - username: Optional auth username
                - password: Optional auth password
                - extra: Protocol version, SSL config, etc.
        """
        super().__init__(config)
        self._cluster: Cluster | None = None
        self._session: Any = None
        self._parser = CassandraExplainParser()
        self._schema_cache: dict[str, Any] = {}

    def connect(self) -> None:
        """Establish connection to Cassandra cluster.

        Raises:
            ConnectionError: If cluster connection fails or auth invalid
        """
        if Cluster is None:
            raise AdapterConnectionError(
                "cassandra-driver is not installed. "
                "Install with: pip install cassandra-driver==3.29.3"
            )

        try:
            contact_points = [self._config.host or "localhost"]
            port = self._config.port or 9042

            # Build cluster with optional auth
            if self._config.username and self._config.password:
                from cassandra.auth import PlainTextAuthProvider

                auth_provider = PlainTextAuthProvider(
                    username=self._config.username,
                    password=self._config.password,
                )
            else:
                auth_provider = None

            # Get protocol version from extra config
            protocol_version = self._config.extra.get("protocol_version", 3)

            # Create cluster
            self._cluster = Cluster(
                contact_points=contact_points,
                port=port,
                auth_provider=auth_provider,
                protocol_version=protocol_version,
                connect_timeout=5.0,
            )

            # Connect
            self._session = self._cluster.connect()
            self._is_connected = True

            # Set keyspace if provided
            if self._config.database:
                self._session.set_keyspace(self._config.database)

            logger.info(
                f"Connected to Cassandra cluster at {contact_points}:{port} "
                f"keyspace={self._config.database}"
            )

        except Exception as e:
            # Handle both cassandra-driver exceptions and generic exceptions
            exc_name = type(e).__name__
            if exc_name == "NoHostAvailable":
                raise AdapterConnectionError(
                    f"Failed to connect to Cassandra cluster at "
                    f"{self._config.host}:{self._config.port}: {e}"
                ) from e
            elif exc_name == "InvalidRequest":
                raise AdapterConnectionError(f"Invalid authentication or keyspace: {e}") from e
            else:
                raise AdapterConnectionError(
                    f"Unexpected error connecting to Cassandra: {e}"
                ) from e

    def disconnect(self) -> None:
        """Close Cassandra connection.

        Raises:
            DisconnectionError: If disconnection fails
        """
        try:
            if self._session:
                self._session.shutdown()
            if self._cluster:
                self._cluster.shutdown()
            self._is_connected = False
            logger.info("Disconnected from Cassandra cluster")
        except Exception as e:
            logger.warning(f"Error disconnecting from Cassandra: {e}")
            self._is_connected = False

    def test_connection(self) -> bool:
        """Test connection with lightweight query.

        Returns:
            True if connection valid, False otherwise.
        """
        try:
            if self._session is None:
                return False
            # Query system table to verify connection
            result = self._session.execute("SELECT * FROM system.peers LIMIT 1")
            return result is not None
        except Exception as e:
            logger.warning(f"Connection test failed: {e}")
            return False

    def execute_explain(self, query: str) -> QueryAnalysisReport:
        """Analyze Cassandra query performance.

        Executes query with TRACING to capture event timeline.
        Parses trace, detects anti-patterns, generates recommendations.

        Args:
            query: CQL SELECT query (e.g., "SELECT * FROM users WHERE id=1")

        Returns:
            QueryAnalysisReport with score, warnings, recommendations, plan

        Raises:
            QueryAnalysisError: If query execution or analysis fails
        """
        if not self._is_connected:
            raise QueryAnalysisError("Not connected to Cassandra cluster")

        try:
            # Validate query is SELECT
            query_upper = query.strip().upper()
            if not query_upper.startswith("SELECT"):
                raise QueryAnalysisError("Only SELECT queries are supported for analysis")

            # Extract table name for schema lookups
            table_name = self._extract_table_name(query)
            if not table_name:
                raise QueryAnalysisError("Could not extract table name from query")

            # Load schema for this table if not cached
            if table_name not in self._schema_cache:
                self._load_table_schema(table_name)

            # Execute query with tracing
            logger.info(f"Executing query with tracing: {query[:100]}...")
            statement = self._session.prepare(query)
            statement.trace = True
            result_set = self._session.execute(statement)

            # Extract trace events
            trace = result_set.get_query_trace()
            if not trace:
                raise QueryAnalysisError("Query tracing failed or returned no trace")

            trace_events = trace.events

            # Parse trace and analyze
            execution_time_ms = trace.duration / 1000.0  # Convert microseconds to ms

            # Detect ALLOW FILTERING in query text (critical anti-pattern)
            has_allow_filtering = "ALLOW FILTERING" in query_upper

            # Parse normalized plan
            parsed = self._parser.parse(
                trace_events=trace_events,
                query=query,
                keyspace=self._config.database or "",
                table_name=table_name,
                schema=self._schema_cache.get(table_name, {}),
                allow_filtering=has_allow_filtering,
            )

            # Run anti-pattern detection
            from query_analyzer.core.cassandra_anti_pattern_detector import (
                CassandraAntiPatternDetector,
            )

            detector = CassandraAntiPatternDetector()
            detection_result = detector.analyze(
                parsed_query=parsed,
                query=query,
                table_schema=self._schema_cache.get(table_name, {}),
            )

            # Convert to warnings and recommendations
            warnings: list[Warning] = []
            for ap in detection_result.anti_patterns:
                severity_map = {
                    "critical": "critical",
                    "high": "high",
                    "medium": "medium",
                    "low": "low",
                }
                warning = Warning(
                    severity=severity_map.get(ap.severity, "low"),  # type: ignore
                    message=ap.message,
                    node_type=ap.name,
                    affected_object=table_name,
                    metadata={"penalty": ap.penalty},
                )
                warnings.append(warning)

            recommendations: list[Recommendation] = []
            for idx, rec_text in enumerate(detection_result.recommendations, start=1):
                priority = max(1, 10 - idx)
                rec = Recommendation(
                    priority=priority,
                    title=rec_text.split("\n")[0][:50],
                    description=rec_text,
                    code_snippet=None,
                    affected_object=table_name,
                    metadata={},
                )
                recommendations.append(rec)

            # Build plan tree
            plan_tree = self._parser.build_plan_tree(
                trace_events=trace_events,
                table_name=table_name,
                keyspace=self._config.database or "",
            )

            # Create report
            report = QueryAnalysisReport(
                engine="cassandra",
                query=query,
                score=detection_result.score,
                execution_time_ms=execution_time_ms,
                warnings=warnings,
                recommendations=recommendations,
                plan_tree=plan_tree,
                analyzed_at=datetime.now(UTC),
                raw_plan={
                    "trace_events": [
                        {
                            "event_id": str(e.event_id),
                            "timestamp": e.timestamp,
                            "source": str(e.source),
                            "thread_id": e.thread_id,
                            "activity": e.activity,
                            "source_elapsed": e.source_elapsed,
                        }
                        for e in (trace_events[:10] if trace_events else [])
                    ],
                    "duration_us": trace.duration,
                    "client": str(trace.client),
                    "coordinator": str(trace.coordinator),
                },
                metrics={
                    "execution_time_ms": execution_time_ms,
                    "trace_events_count": len(trace_events) if trace_events else 0,
                    "allow_filtering": has_allow_filtering,
                    "table": table_name,
                    "keyspace": self._config.database or "",
                },
            )

            return report

        except QueryAnalysisError:
            raise
        except Exception as e:
            raise QueryAnalysisError(f"Query analysis failed: {e}") from e

    def get_slow_queries(self, threshold_ms: int = 1000) -> list[dict[str, Any]]:
        """Get slow queries from cluster.

        Cassandra doesn't have a built-in slow query log like MySQL/PostgreSQL.
        This implementation is a placeholder that returns empty list.

        Args:
            threshold_ms: Threshold in milliseconds (unused for Cassandra)

        Returns:
            Empty list (Cassandra has no slow query log)
        """
        # Cassandra has no native slow query log
        # Applications need to implement their own query logging/metrics
        logger.info(
            "Cassandra adapter: get_slow_queries not supported. "
            "Use application-level metrics or CassandraDriver metrics."
        )
        return []

    def get_metrics(self) -> dict[str, Any]:
        """Get cluster-level metrics from system tables.

        Returns:
            Dict with cluster info, node count, schema stats, etc.
        """
        if not self._is_connected:
            raise QueryAnalysisError("Not connected to Cassandra cluster")

        try:
            metrics = {}

            # Cluster info
            cluster_name_row = self._session.execute("SELECT cluster_name FROM system.local")
            if cluster_name_row:
                metrics["cluster_name"] = cluster_name_row[0].cluster_name

            # Node count (peers + local)
            peers_result = self._session.execute("SELECT COUNT(*) as count FROM system.peers")
            peer_count = peers_result[0].count if peers_result else 0
            metrics["node_count"] = peer_count + 1  # +1 for local node

            # Size estimates
            try:
                size_estimates = self._session.execute(
                    "SELECT keyspace_name, table_name, range_start, range_end, "
                    "mean_partition_size, partitions_count "
                    "FROM system.size_estimates LIMIT 100"
                )
                metrics["size_estimates_count"] = len(size_estimates) if size_estimates else 0
            except Exception:
                metrics["size_estimates_count"] = 0

            return metrics

        except Exception as e:
            logger.warning(f"Failed to get metrics: {e}")
            return {}

    def get_engine_info(self) -> dict[str, Any]:
        """Get Cassandra version and configuration info.

        Returns:
            Dict with version, release_version, etc.
        """
        if not self._is_connected:
            raise QueryAnalysisError("Not connected to Cassandra cluster")

        try:
            result = self._session.execute("SELECT * FROM system.local")
            if result:
                row = result[0]
                return {
                    "cluster_name": getattr(row, "cluster_name", "unknown"),
                    "release_version": getattr(row, "release_version", "unknown"),
                    "schema_version": getattr(row, "schema_version", "unknown"),
                    "cql_version": getattr(row, "cql_version", "unknown"),
                }
            return {}
        except Exception as e:
            logger.warning(f"Failed to get engine info: {e}")
            return {}

    def _extract_table_name(self, query: str) -> str | None:
        """Extract table name from SELECT query.

        Simple regex-based extraction. Handles:
        - SELECT ... FROM table_name
        - SELECT ... FROM keyspace.table_name

        Args:
            query: CQL SELECT query

        Returns:
            Table name or None if not found
        """
        # Match: FROM [keyspace.]table_name
        match = re.search(r"\bFROM\s+(?:(\w+)\.)?(\w+)", query, re.IGNORECASE)
        if match:
            # Return table name (group 2); ignore keyspace (group 1)
            return match.group(2)
        return None

    def _load_table_schema(self, table_name: str) -> None:
        """Load and cache table schema (partition/clustering keys, columns).

        Queries system.schema_columns to get column info.

        Args:
            table_name: Name of table to load
        """
        try:
            keyspace = self._config.database or "system"

            # Query schema columns
            columns_query = (
                "SELECT column_name, kind, clustering_order "
                "FROM system_schema.columns "
                "WHERE keyspace_name = ? AND table_name = ?"
            )
            columns_result = self._session.execute(columns_query, [keyspace, table_name])

            schema: dict[str, Any] = {
                "partition_keys": [],
                "clustering_keys": [],
                "columns": [],
            }

            for row in columns_result:
                col_name = row.column_name
                kind = row.kind  # "partition_key", "clustering", "static", "regular"

                schema["columns"].append(
                    {
                        "name": col_name,
                        "kind": kind,
                        "clustering_order": getattr(row, "clustering_order", None),
                    }
                )

                if kind == "partition_key":
                    schema["partition_keys"].append(col_name)
                elif kind == "clustering":
                    schema["clustering_keys"].append(col_name)

            self._schema_cache[table_name] = schema
            logger.debug(f"Loaded schema for table {table_name}: {schema}")

        except Exception as e:
            logger.warning(f"Failed to load schema for table {table_name}: {e}")
            self._schema_cache[table_name] = {
                "partition_keys": [],
                "clustering_keys": [],
                "columns": [],
            }
