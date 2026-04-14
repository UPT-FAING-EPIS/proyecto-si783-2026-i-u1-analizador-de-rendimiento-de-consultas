"""Parse Cassandra TRACING output and analyze query execution.

Cassandra has no native EXPLAIN statement, so analysis is based on:
1. TRACING ON - captures event timeline from coordinator and replicas
2. Schema analysis - partition/clustering key detection
3. system.size_estimates - partition size estimation
"""

import logging
from typing import Any

from ..models import PlanNode

logger = logging.getLogger(__name__)


class CassandraExplainParser:
    """Parse Cassandra trace events and build analysis."""

    @staticmethod
    def parse(
        trace_events: list,
        query: str,
        keyspace: str,
        table_name: str,
        schema: dict[str, Any],
        allow_filtering: bool,
    ) -> dict[str, Any]:
        """Parse Cassandra trace events and extract metrics.

        Args:
            trace_events: List of trace events from query trace
            query: Original CQL query
            keyspace: Keyspace name
            table_name: Table name being queried
            schema: Table schema with partition/clustering keys
            allow_filtering: Whether query uses ALLOW FILTERING

        Returns:
            Normalized dict with query analysis metrics:
            {
                "query_type": "select" | "other",
                "table": str,
                "keyspace": str,
                "execution_time_ms": float,
                "trace_events": [...],
                "partition_keys": [...],
                "clustering_keys": [...],
                "allow_filtering": bool,
                "coordinator": str,
                "replicas_touched": int,
                "stages": [...],
                "has_filter_without_key": bool,
            }
        """
        partition_keys = schema.get("partition_keys", [])
        clustering_keys = schema.get("clustering_keys", [])

        # Analyze trace events
        coordinator = ""
        replicas_touched = set()
        stages = []
        total_time_ms = 0.0

        if trace_events:
            for event in trace_events:
                source = str(event.source) if hasattr(event, "source") else ""
                activity = str(event.activity) if hasattr(event, "activity") else ""
                source_elapsed = event.source_elapsed if hasattr(event, "source_elapsed") else 0

                if not coordinator and source:
                    coordinator = source

                if source and source != coordinator:
                    replicas_touched.add(source)

                if activity:
                    stages.append(
                        {
                            "source": source,
                            "activity": activity,
                            "elapsed_us": source_elapsed,
                        }
                    )

                # Accumulate total time
                if source_elapsed:
                    total_time_ms = max(total_time_ms, source_elapsed / 1000.0)

        # Detect if query filters on non-partition-key columns
        has_filter_without_key = CassandraExplainParser._detect_filter_without_key(
            query, partition_keys
        )

        return {
            "query_type": "select" if query.strip().upper().startswith("SELECT") else "other",
            "table": table_name,
            "keyspace": keyspace,
            "execution_time_ms": total_time_ms,
            "trace_events": trace_events,
            "partition_keys": partition_keys,
            "clustering_keys": clustering_keys,
            "allow_filtering": allow_filtering,
            "coordinator": coordinator,
            "replicas_touched": len(replicas_touched),
            "stages": stages,
            "has_filter_without_key": has_filter_without_key,
        }

    @staticmethod
    def build_plan_tree(
        trace_events: list,
        table_name: str,
        keyspace: str,
    ) -> PlanNode | None:
        """Build hierarchical PlanNode tree from trace events.

        Simple structure: coordinator node with replica nodes as children.

        Args:
            trace_events: List of trace events
            table_name: Table being queried
            keyspace: Keyspace name

        Returns:
            PlanNode tree or None if no events
        """
        if not trace_events:
            return None

        try:
            # Group events by source
            coordinator = None
            events_by_source: dict[str, list] = {}

            for event in trace_events:
                source = str(event.source) if hasattr(event, "source") else "unknown"
                if not coordinator:
                    coordinator = source

                if source not in events_by_source:
                    events_by_source[source] = []
                events_by_source[source].append(event)

            if not coordinator:
                return None

            # Build coordinator node
            coordinator_events = events_by_source.get(coordinator, [])
            coordinator_node = PlanNode(
                node_type="Coordinator",
                cost=0.0,
                estimated_rows=0,
                actual_rows=len(coordinator_events),
                actual_time_ms=0.0,
                properties={
                    "coordinator": coordinator,
                    "table": table_name,
                    "keyspace": keyspace,
                },
                children=[],
            )

            # Build replica nodes as children
            for source, events in events_by_source.items():
                if source == coordinator:
                    continue  # Skip coordinator, already root

                replica_node = PlanNode(
                    node_type="Replica",
                    cost=0.0,
                    estimated_rows=0,
                    actual_rows=len(events),
                    actual_time_ms=0.0,
                    properties={
                        "source": source,
                        "events": len(events),
                        "table": table_name,
                    },
                    children=[],
                )
                coordinator_node.children.append(replica_node)

            return coordinator_node

        except Exception as e:
            logger.warning(f"Failed to build plan tree: {e}")
            return None

    @staticmethod
    def _detect_filter_without_key(query: str, partition_keys: list[str]) -> bool:
        """Detect if query filters on non-partition-key columns.

        Simple heuristic: Check if WHERE clause exists but doesn't mention
        any partition key columns.

        Args:
            query: CQL query
            partition_keys: List of partition key column names

        Returns:
            True if query has WHERE but no partition key filtering
        """
        if not partition_keys:
            return False

        query_upper = query.upper()

        # Check if query has WHERE clause
        if "WHERE" not in query_upper:
            return False

        # Extract WHERE clause
        where_match = query_upper.find("WHERE")
        if where_match == -1:
            return False

        where_clause = query_upper[where_match:]

        # Check if any partition key is mentioned in WHERE
        for pk in partition_keys:
            if pk.upper() in where_clause:
                return False  # Found partition key, so not a full cluster scan

        # WHERE exists but no partition key mentioned
        return True
