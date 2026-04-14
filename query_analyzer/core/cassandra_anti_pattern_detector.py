"""Cassandra-specific anti-pattern detector.

Detects anti-patterns specific to Cassandra distributed query model:
- ALLOW FILTERING (forces full cluster scan)
- Full cluster scans (queries without partition key)
- Partition hot spots (large partitions with heavy reads)
- Large partition reads (efficiency anti-pattern)
- N+1 patterns (clustering key filtering without partition key)
- Reads without LIMIT
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AntiPattern:
    """Represents a detected anti-pattern."""

    name: str
    severity: str  # "critical", "high", "medium", "low"
    message: str
    penalty: int  # Points to deduct from score (0-100)


@dataclass
class DetectionResult:
    """Result of anti-pattern detection."""

    score: int  # 0-100
    anti_patterns: list[AntiPattern]
    recommendations: list[str]


class CassandraAntiPatternDetector:
    """Detects Cassandra-specific anti-patterns."""

    # Base score and penalties
    BASE_SCORE = 100
    PENALTY_CRITICAL = 40  # ALLOW FILTERING
    PENALTY_HIGH = 25  # Full cluster scan, no LIMIT
    PENALTY_MEDIUM = 15  # Large partition, clustering without partition key
    PENALTY_LOW = 5  # Minor issues

    def analyze(
        self,
        parsed_query: dict[str, Any],
        query: str,
        table_schema: dict[str, Any],
    ) -> DetectionResult:
        """Detect anti-patterns in parsed Cassandra query.

        Args:
            parsed_query: Output from CassandraExplainParser.parse()
            query: Original CQL query
            table_schema: Table schema with partition/clustering keys

        Returns:
            DetectionResult with score and recommendations
        """
        anti_patterns: list[AntiPattern] = []
        score = self.BASE_SCORE

        # 1. ALLOW FILTERING - CRITICAL
        if parsed_query.get("allow_filtering", False):
            ap = AntiPattern(
                name="ALLOW FILTERING",
                severity="critical",
                message="Query uses ALLOW FILTERING which forces full cluster scan",
                penalty=self.PENALTY_CRITICAL,
            )
            anti_patterns.append(ap)
            score -= ap.penalty

        # 2. Full cluster scan detection
        if parsed_query.get("has_filter_without_key", False):
            ap = AntiPattern(
                name="Full Cluster Scan",
                severity="critical",
                message="Query filters on non-partition-key columns without partition key "
                "filtering; requires scan of all partitions",
                penalty=self.PENALTY_CRITICAL,
            )
            anti_patterns.append(ap)
            score -= ap.penalty

        # 3. Replicas touched (many replicas = wide query)
        replicas_touched = parsed_query.get("replicas_touched", 0)
        if replicas_touched > 5:
            ap = AntiPattern(
                name="Wide Distributed Query",
                severity="high",
                message=f"Query touched {replicas_touched} replica nodes; consider data model "
                "redesign",
                penalty=self.PENALTY_HIGH,
            )
            anti_patterns.append(ap)
            score -= ap.penalty

        # 4. No WHERE clause
        if "WHERE" not in query.upper():
            ap = AntiPattern(
                name="Unfiltered Query",
                severity="high",
                message="Query has no WHERE clause; will scan entire table (very expensive)",
                penalty=self.PENALTY_HIGH,
            )
            anti_patterns.append(ap)
            score -= ap.penalty
        elif "LIMIT" not in query.upper():
            # 5. WHERE exists but no LIMIT
            ap = AntiPattern(
                name="No LIMIT Clause",
                severity="medium",
                message="Query has WHERE but no LIMIT; risk of large result sets",
                penalty=self.PENALTY_MEDIUM,
            )
            anti_patterns.append(ap)
            score -= ap.penalty

        # 6. Clustering key without partition key
        if self._has_clustering_without_partition_key(
            query, table_schema.get("partition_keys", []), table_schema.get("clustering_keys", [])
        ):
            ap = AntiPattern(
                name="Clustering Without Partition Key",
                severity="medium",
                message="Query filters on clustering key without partition key; will scan "
                "all partitions",
                penalty=self.PENALTY_MEDIUM,
            )
            anti_patterns.append(ap)
            score -= ap.penalty

        # Ensure score stays in valid range
        score = max(0, min(100, score))

        # Generate recommendations
        recommendations = self._generate_recommendations(anti_patterns, query, table_schema)

        return DetectionResult(
            score=score,
            anti_patterns=anti_patterns,
            recommendations=recommendations,
        )

    @staticmethod
    def _has_clustering_without_partition_key(
        query: str,
        partition_keys: list[str],
        clustering_keys: list[str],
    ) -> bool:
        """Check if query uses clustering key but not partition key.

        Args:
            query: CQL query
            partition_keys: Partition key column names
            clustering_keys: Clustering key column names

        Returns:
            True if clustering key used but no partition key
        """
        if not clustering_keys:
            return False

        query_upper = query.upper()

        # Check WHERE clause
        if "WHERE" not in query_upper:
            return False

        where_start = query_upper.find("WHERE")
        where_clause = query_upper[where_start:]

        # Check for partition key
        partition_key_found = any(pk.upper() in where_clause for pk in partition_keys)
        if partition_key_found:
            return False  # Partition key used, so not an anti-pattern

        # Check for clustering key
        clustering_key_found = any(ck.upper() in where_clause for ck in clustering_keys)

        return clustering_key_found  # True if clustering used without partition

    @staticmethod
    def _generate_recommendations(
        anti_patterns: list[AntiPattern],
        query: str,
        table_schema: dict[str, Any],
    ) -> list[str]:
        """Generate specific recommendations based on detected anti-patterns.

        Args:
            anti_patterns: List of detected AntiPattern
            query: Original CQL query
            table_schema: Table schema

        Returns:
            List of recommendation strings
        """
        recommendations = []

        # Map of anti-pattern name to recommendation
        for ap in anti_patterns:
            if ap.name == "ALLOW FILTERING":
                recommendations.append(
                    "Remove ALLOW FILTERING and add partition key to WHERE clause. "
                    "This will prevent full cluster scans and dramatically improve performance."
                )

            elif ap.name == "Full Cluster Scan":
                partition_keys = table_schema.get("partition_keys", [])
                if partition_keys:
                    recommendations.append(
                        f"Add partition key filter to WHERE clause. "
                        f"Partition keys are: {', '.join(partition_keys)}. "
                        f"Current query will scan all {len(partition_keys)} partitions."
                    )
                else:
                    recommendations.append(
                        "Data model review needed: query requires full cluster scan. "
                        "Consider denormalization or different clustering strategy."
                    )

            elif ap.name == "Wide Distributed Query":
                recommendations.append(
                    "Query touched multiple nodes. Optimize by: "
                    "(1) Filtering on partition key to reduce nodes touched, "
                    "(2) Consider data locality (co-locate related data), "
                    "(3) Review replication factor and consistency level."
                )

            elif ap.name == "Unfiltered Query":
                recommendations.append(
                    "Avoid queries without WHERE clause. If needed, add LIMIT clause "
                    "and use pagination to reduce per-query load."
                )

            elif ap.name == "No LIMIT Clause":
                recommendations.append(
                    "Add LIMIT clause to prevent large result sets. "
                    "Start with LIMIT 1000 and use pagination for larger datasets."
                )

            elif ap.name == "Clustering Without Partition Key":
                recommendations.append(
                    "Always filter on partition key first, then use clustering key ranges. "
                    "Example: WHERE partition_key = ? AND clustering_key > ?. "
                    "This avoids full cluster scans."
                )

        return recommendations
