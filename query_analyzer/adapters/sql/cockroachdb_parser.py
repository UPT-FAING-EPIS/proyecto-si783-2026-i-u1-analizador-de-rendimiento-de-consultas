"""CockroachDB EXPLAIN parser with support for CRDB-specific node types.

CockroachDB implements the PostgreSQL wire protocol, so EXPLAIN output format
is mostly compatible. However, CockroachDB has some unique node types:
- Lookup Join: Similar to Nested Loop but with index lookups
- Zigzag Join: Optimization for multi-index scans
- Distributed/Remote nodes: Indicate distributed execution (single-node mode may still use them)

This parser extends PostgreSQLExplainParser to:
1. Detect and categorize CockroachDB-specific join types
2. Track lookup join count (warning if > 5)
3. Identify distributed execution patterns
4. Add CockroachDB-specific warnings
"""

from typing import Any

from .postgresql_parser import PostgreSQLExplainParser


class CockroachDBParser(PostgreSQLExplainParser):
    """Parser para planes EXPLAIN de CockroachDB con nodos específicos.

    Extiende PostgreSQLExplainParser para manejar:
    - Lookup Join (búsquedas indexadas similares a Nested Loop)
    - Zigzag Join (optimización para múltiples índices)
    - Nodos distribuidos (Distributed, Remote, Local)
    - Métricas específicas de CockroachDB

    Atributos:
        seq_scan_threshold: Número de filas para considerar un Seq Scan problemático
        lookup_join_warn_threshold: Número máximo de Lookup Joins antes de advertencia
    """

    def __init__(self, seq_scan_threshold: int = 10000) -> None:
        """Initialize CockroachDB parser.

        Args:
            seq_scan_threshold: Row count threshold for Seq Scan warnings (default: 10000)
        """
        super().__init__(seq_scan_threshold)
        # CockroachDB-specific thresholds
        self.lookup_join_warn_threshold = 5
        self.network_latency_warn_threshold_ms = 50

    def parse(self, explain_json: dict[str, Any]) -> dict[str, Any]:
        """Parse EXPLAIN output and extract all metrics including CRDB-specific ones.

        Args:
            explain_json: Complete EXPLAIN (ANALYZE, FORMAT JSON) output

        Returns:
            Dictionary with standard metrics plus CockroachDB-specific fields:
                - is_distributed: Whether plan uses distributed execution
                - lookup_join_count: Number of Lookup Join nodes
                - zigzag_join_count: Number of Zigzag Join nodes
                - has_remote_execution: Whether plan contains Remote nodes
        """
        # Get base metrics from PostgreSQL parser
        base_metrics = super().parse(explain_json)

        # Extract CockroachDB-specific metrics
        plan = explain_json.get("Plan", {})
        all_nodes = base_metrics.get("all_nodes", [])

        # Detect distribution patterns
        is_distributed = self._is_distributed_plan(plan, all_nodes)
        lookup_join_count = self._count_node_type(all_nodes, "Lookup Join")
        zigzag_join_count = self._count_node_type(all_nodes, "Zigzag Join")
        has_remote_execution = any("Remote" in node.get("Node Type", "") for node in all_nodes)

        # Add CRDB-specific metrics
        base_metrics.update(
            {
                "is_distributed": is_distributed,
                "lookup_join_count": lookup_join_count,
                "zigzag_join_count": zigzag_join_count,
                "has_remote_execution": has_remote_execution,
            }
        )

        return base_metrics

    def _is_distributed_plan(self, plan: dict[str, Any], all_nodes: list[dict[str, Any]]) -> bool:
        """Check if plan indicates distributed execution.

        Args:
            plan: Root plan node
            all_nodes: Flat list of all nodes

        Returns:
            True if plan uses distributed execution
        """
        # Check for Distributed or Remote nodes
        for node in all_nodes:
            node_type = node.get("Node Type", "")
            if "Distributed" in node_type or "Remote" in node_type:
                return True
        return False

    def _count_node_type(self, all_nodes: list[dict[str, Any]], node_type_name: str) -> int:
        """Count occurrences of a specific node type.

        Args:
            all_nodes: List of all plan nodes
            node_type_name: Name to search for (e.g., "Lookup Join")

        Returns:
            Count of matching nodes
        """
        return sum(1 for node in all_nodes if node_type_name in node.get("Node Type", ""))

    def identify_warnings(
        self, metrics: dict[str, Any], all_nodes: list[dict[str, Any]]
    ) -> list[str]:
        """Generate warnings based on plan analysis, including CRDB-specific checks.

        Args:
            metrics: Parsed metrics dictionary
            all_nodes: Flat list of all plan nodes

        Returns:
            List of warning strings (base + CRDB-specific)
        """
        # Get base warnings from PostgreSQL parser
        warnings = super().identify_warnings(metrics, all_nodes)

        # CockroachDB-specific warning: Many lookup joins
        lookup_join_count = metrics.get("lookup_join_count", 0)
        if lookup_join_count > self.lookup_join_warn_threshold:
            warnings.append(
                f"Alto número de Lookup Joins detectado ({lookup_join_count}) - "
                f"considera colocar tablas o usar Hash Join distribuido"
            )

        # CockroachDB-specific warning: Distributed execution (informational)
        if metrics.get("is_distributed"):
            warnings.append(
                "Ejecución distribuida detectada - verifica latencia de red entre nodos"
            )

        return warnings

    def generate_recommendations(self, metrics: dict[str, Any], warnings: list[str]) -> list[str]:
        """Generate recommendations based on metrics and warnings.

        Args:
            metrics: Parsed metrics dictionary
            warnings: List of identified warnings

        Returns:
            List of recommendation strings (base + CRDB-specific)
        """
        # Get base recommendations from PostgreSQL parser
        recommendations = super().generate_recommendations(metrics, warnings)

        # CockroachDB-specific recommendations
        if "Lookup Joins" in str(warnings):
            recommendations.append(
                "Consider using PARTITION BY or geographic colocation to reduce lookup joins"
            )

        if metrics.get("is_distributed"):
            recommendations.append(
                "Verify inter-node latency and consider query fragmentation optimization"
            )

        if metrics.get("has_remote_execution"):
            recommendations.append(
                "Plan contains remote execution - ensure adequate network bandwidth and latency"
            )

        return recommendations

    def calculate_score(self, metrics: dict[str, Any], warnings: list[str]) -> int:
        """Calculate optimization score (0-100) with CRDB-specific penalties.

        Applies additional deductions for:
        - High lookup join count (additional -10)
        - Distributed execution with many nodes (additional -5 if is_distributed)

        Args:
            metrics: Parsed metrics dictionary
            warnings: List of identified warnings

        Returns:
            Optimization score from 0 to 100
        """
        # Start with base score from PostgreSQL parser
        base_score = super().calculate_score(metrics, warnings)

        # Apply CRDB-specific deductions
        score = base_score

        # Deduction for high lookup join count
        lookup_join_count = metrics.get("lookup_join_count", 0)
        if lookup_join_count > self.lookup_join_warn_threshold:
            score -= min(10, lookup_join_count - self.lookup_join_warn_threshold)

        # Deduction for distributed execution (network overhead)
        if metrics.get("is_distributed") and metrics.get("has_remote_execution"):
            score -= 5

        # Ensure score stays in valid range
        return max(0, min(100, score))

    def normalize_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Normalize CockroachDB plan node to engine-agnostic format.

        Args:
            plan: Single CockroachDB plan node

        Returns:
            Normalized node with engine-agnostic fields
        """
        # Start with base normalization from PostgreSQL parser
        normalized = super().normalize_plan(plan)

        # Map CockroachDB-specific node types to normalized form
        node_type = plan.get("Node Type", "")

        if "Lookup Join" in node_type:
            normalized["node_type"] = "Lookup Join"
            if "extra_info" not in normalized:
                normalized["extra_info"] = []
            normalized["extra_info"].append("CockroachDB-specific join type (index lookup)")

        elif "Zigzag Join" in node_type:
            normalized["node_type"] = "Zigzag Join"
            if "extra_info" not in normalized:
                normalized["extra_info"] = []
            normalized["extra_info"].append("CockroachDB-specific optimization (multi-index scan)")

        elif "Distributed" in node_type:
            if "extra_info" not in normalized:
                normalized["extra_info"] = []
            normalized["extra_info"].append("Distributed execution across multiple nodes")

        elif "Remote" in node_type:
            if "extra_info" not in normalized:
                normalized["extra_info"] = []
            normalized["extra_info"].append("Remote execution on different node")

        return normalized
