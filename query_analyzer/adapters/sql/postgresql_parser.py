"""PostgreSQL EXPLAIN plan parser and analyzer."""

from typing import Any


class PostgreSQLExplainParser:
    """Parser for PostgreSQL EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) output.

    Recursively traverses the plan tree, extracts metrics, calculates warnings,
    and computes an optimization score (0-100) based on plan structure and
    execution time.
    """

    def __init__(self, seq_scan_threshold: int = 10000) -> None:
        """Initialize parser with configurable thresholds.

        Args:
            seq_scan_threshold: Table row count threshold for Seq Scan warning
                (default: 10000)
        """
        self.seq_scan_threshold = seq_scan_threshold

    def parse(self, explain_json: dict[str, Any]) -> dict[str, Any]:
        """Parse EXPLAIN output and extract all metrics.

        Args:
            explain_json: Complete EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) output

        Returns:
            Dictionary with:
                - planning_time_ms: Planning time
                - execution_time_ms: Total execution time
                - total_cost: Estimated total cost
                - actual_rows_total: Total actual rows returned
                - plan_rows_total: Total estimated rows
                - node_count: Number of nodes in plan tree
                - most_expensive_node: Node with highest Total Cost
                - buffer_stats: Shared hit/read statistics
                - scan_nodes: All Seq/Index scan nodes
                - join_nodes: All join operation nodes
                - all_nodes: Flat list of all nodes
        """
        plan = explain_json.get("Plan", {})

        # Collect all nodes via recursive traversal
        all_nodes: list[dict[str, Any]] = []
        self._traverse_plan_tree(plan, all_nodes)

        # Extract basic metrics
        planning_time_ms = float(explain_json.get("Planning Time", 0.0))
        execution_time_ms = float(explain_json.get("Execution Time", 0.0))

        # Aggregate metrics across all nodes
        total_cost = float(plan.get("Total Cost", 0.0))
        actual_rows_total = self._sum_actual_rows(all_nodes)
        plan_rows_total = self._sum_plan_rows(all_nodes)

        # Find most expensive node
        most_expensive = self._find_most_expensive_node(all_nodes)

        # Buffer statistics
        buffer_stats = self._aggregate_buffer_stats(all_nodes)

        # Categorize nodes by type
        scan_nodes = [n for n in all_nodes if "Scan" in n.get("Node Type", "")]
        join_nodes = [
            n
            for n in all_nodes
            if any(j in n.get("Node Type", "") for j in ["Join", "Hash"])
        ]

        return {
            "planning_time_ms": planning_time_ms,
            "execution_time_ms": execution_time_ms,
            "total_cost": total_cost,
            "actual_rows_total": actual_rows_total,
            "plan_rows_total": plan_rows_total,
            "node_count": len(all_nodes),
            "most_expensive_node": most_expensive,
            "buffer_stats": buffer_stats,
            "scan_nodes": scan_nodes,
            "join_nodes": join_nodes,
            "all_nodes": all_nodes,
        }

    def _traverse_plan_tree(
        self, node: dict[str, Any], all_nodes: list[dict[str, Any]], depth: int = 0
    ) -> None:
        """Recursively traverse plan tree, collecting all nodes.

        Args:
            node: Current plan node
            all_nodes: Accumulator list for all nodes
            depth: Current tree depth (for debugging)
        """
        if not node:
            return

        # Add current node to list with depth info
        node_copy = dict(node)
        node_copy["_depth"] = depth
        all_nodes.append(node_copy)

        # Recursively process child plans
        sub_plans = node.get("Plans", [])
        for sub_plan in sub_plans:
            self._traverse_plan_tree(sub_plan, all_nodes, depth + 1)

    def _sum_actual_rows(self, nodes: list[dict[str, Any]]) -> int:
        """Sum actual rows across all leaf nodes (nodes without children)."""
        # Count actual rows from nodes that don't have Plans array
        # (leaf nodes in the tree)
        total = 0
        for node in nodes:
            if "Plans" not in node or not node["Plans"]:
                total += int(node.get("Actual Rows", 0))
        return total

    def _sum_plan_rows(self, nodes: list[dict[str, Any]]) -> int:
        """Sum plan rows across all leaf nodes."""
        total = 0
        for node in nodes:
            if "Plans" not in node or not node["Plans"]:
                total += int(node.get("Plan Rows", 0))
        return total

    def _find_most_expensive_node(self, nodes: list[dict[str, Any]]) -> dict[str, Any]:
        """Find node with highest Total Cost.

        Returns dict with node info including cost and actual time.
        """
        if not nodes:
            return {}

        most_expensive = max(nodes, key=lambda n: float(n.get("Total Cost", 0)))

        return {
            "type": most_expensive.get("Node Type", "Unknown"),
            "cost": float(most_expensive.get("Total Cost", 0)),
            "actual_time": float(most_expensive.get("Actual Total Time", 0)),
            "actual_rows": int(most_expensive.get("Actual Rows", 0)),
            "plan_rows": int(most_expensive.get("Plan Rows", 0)),
        }

    def _aggregate_buffer_stats(self, nodes: list[dict[str, Any]]) -> dict[str, Any]:
        """Aggregate buffer hit/read statistics across all nodes.

        Returns:
            Dict with shared_hit_total, shared_read_total, and cache_miss_rate
        """
        shared_hit = 0
        shared_read = 0

        for node in nodes:
            buffers = node.get("Buffers", {})
            if isinstance(buffers, dict):
                shared_hit += int(buffers.get("Shared Hit", 0))
                shared_read += int(buffers.get("Shared Read", 0))

        total_accesses = shared_hit + shared_read
        cache_miss_rate = 0.0
        if total_accesses > 0:
            cache_miss_rate = shared_read / total_accesses

        return {
            "shared_hit_total": shared_hit,
            "shared_read_total": shared_read,
            "total_accesses": total_accesses,
            "cache_miss_rate": cache_miss_rate,
        }

    def _calculate_row_divergence(self, plan_rows: int, actual_rows: int) -> float:
        """Calculate row estimate divergence: |actual - plan| / plan.

        Returns:
            Float in [0, inf). 0 = perfect estimate, 1.0 = 100% divergence, etc.
        """
        if plan_rows == 0:
            return float("inf") if actual_rows > 0 else 0.0
        return abs(actual_rows - plan_rows) / plan_rows

    def identify_warnings(
        self, metrics: dict[str, Any], all_nodes: list[dict[str, Any]]
    ) -> list[str]:
        """Generate warnings based on plan analysis.

        Returns:
            List of warning strings
        """
        warnings: list[str] = []

        # Warning 1: Row divergence > 20%
        divergent_nodes = []
        for node in all_nodes:
            plan_rows = int(node.get("Plan Rows", 0))
            actual_rows = int(node.get("Actual Rows", 0))
            divergence = self._calculate_row_divergence(plan_rows, actual_rows)

            if divergence > 0.2:
                divergent_nodes.append(
                    (
                        node.get("Node Type", "Unknown"),
                        plan_rows,
                        actual_rows,
                        divergence,
                    )
                )

        if divergent_nodes:
            node_type, plan_rows, actual_rows, divergence = divergent_nodes[0]
            warnings.append(
                f"Estimación de filas inexacta en {node_type}: "
                f"esperaba {plan_rows}, obtuve {actual_rows} "
                f"({divergence:.0%} divergencia)"
            )

        # Warning 2: Sequential scans on large tables
        for node in all_nodes:
            if node.get("Node Type") == "Seq Scan":
                # Try to get table row estimate from Plan Rows
                plan_rows = int(node.get("Plan Rows", 0))
                if plan_rows >= self.seq_scan_threshold:
                    relation = node.get("Relation Name", "unknown")
                    warnings.append(
                        f"Búsqueda secuencial en tabla {relation} "
                        f"({plan_rows} filas) - considere agregar un índice"
                    )

        # Warning 3: Nested loops with high iterations
        for node in all_nodes:
            if node.get("Node Type") == "Nested Loop":
                actual_rows = int(node.get("Actual Rows", 0))
                if actual_rows > 1000:
                    warnings.append(
                        f"Nested Loop con {actual_rows} iteraciones - "
                        f"puede ser muy costoso"
                    )

        # Warning 4: Poor cache hit rate
        buffer_stats = metrics.get("buffer_stats", {})
        cache_miss_rate = buffer_stats.get("cache_miss_rate", 0.0)
        if cache_miss_rate > 0.1:
            warnings.append(
                f"Tasa de fallos de caché alta ({cache_miss_rate:.1%}) - "
                f"considere aumentar shared_buffers"
            )

        return warnings

    def generate_recommendations(
        self, metrics: dict[str, Any], warnings: list[str]
    ) -> list[str]:
        """Generate optimization recommendations based on analysis.

        Returns:
            List of recommendation strings
        """
        recommendations: list[str] = []

        # Recommendation for sequential scans
        if any("Búsqueda secuencial" in w for w in warnings):
            recommendations.append(
                "Crear un índice en la(s) columna(s) utilizada(s) en la condición WHERE"
            )

        # Recommendation for nested loops
        if any("Nested Loop" in w for w in warnings):
            recommendations.append(
                "Considere agregar índices en las columnas de JOIN para mejorar "
                "la eficiencia del Nested Loop"
            )

        # Recommendation for cache issues
        if any("caché" in w for w in warnings):
            recommendations.append(
                "Aumentar shared_buffers en postgresql.conf o usar índices "
                "para reducir accesos a disco"
            )

        # Recommendation for planning time
        planning_time = metrics.get("planning_time_ms", 0.0)
        if planning_time > 5.0:
            recommendations.append(
                "Simplificar la consulta o actualizar estadísticas con ANALYZE"
            )

        return recommendations

    def calculate_score(self, metrics: dict[str, Any], warnings: list[str]) -> int:
        """Calculate optimization score (0-100).

        Factors:
        - Execution time penalty: -30 max
        - Row estimate accuracy: -20 max
        - Sequential scans: -25 max
        - Nested loop efficiency: -15 max
        - Cache hit rate: -10 max
        - Planning time: ±5
        - Multiple scans: -10 max

        Args:
            metrics: Dict from parse()
            warnings: List from identify_warnings()

        Returns:
            Score (0-100) where 100 is optimal
        """
        base_score = 100
        deductions = 0

        # EXECUTION TIME PENALTY (max -30)
        actual_time = metrics.get("execution_time_ms", 0.0)
        if actual_time > 1000:
            deductions += 30
        elif actual_time > 500:
            deductions += 20
        elif actual_time > 100:
            deductions += 10
        elif actual_time > 50:
            deductions += 5

        # ROW ACCURACY PENALTY (max -20)
        # Count nodes with >20% divergence
        all_nodes = metrics.get("all_nodes", [])
        divergent_count = 0
        for node in all_nodes:
            plan_rows = int(node.get("Plan Rows", 0))
            actual_rows = int(node.get("Actual Rows", 0))
            divergence = self._calculate_row_divergence(plan_rows, actual_rows)
            if divergence > 0.2:
                divergent_count += 1

        deductions += min(20, divergent_count * 5)

        # SEQUENTIAL SCAN PENALTY (max -25)
        seq_scans_large = 0
        for node in all_nodes:
            if node.get("Node Type") == "Seq Scan":
                plan_rows = int(node.get("Plan Rows", 0))
                if plan_rows >= self.seq_scan_threshold:
                    seq_scans_large += 1
                elif plan_rows > 1000:
                    deductions += 5

        deductions += min(25, seq_scans_large * 20)

        # NESTED LOOP PENALTY (max -15)
        for node in all_nodes:
            if node.get("Node Type") == "Nested Loop":
                actual_rows = int(node.get("Actual Rows", 0))
                if actual_rows > 1000:
                    deductions += 15
                elif actual_rows > 100:
                    deductions += 5

        # BUFFER CACHE PENALTY (max -10)
        buffer_stats = metrics.get("buffer_stats", {})
        cache_miss_rate = buffer_stats.get("cache_miss_rate", 0.0)
        if cache_miss_rate > 0.1:
            deductions += 10

        # PLANNING TIME PENALTY/BONUS (±5)
        planning_time = metrics.get("planning_time_ms", 0.0)
        if planning_time > 5.0:
            deductions += 5
        elif planning_time < 0.1:
            deductions -= 2  # Bonus

        # MULTIPLE SCAN PENALTY (max -10)
        scan_count = len([n for n in all_nodes if "Scan" in n.get("Node Type", "")])
        if scan_count > 3:
            deductions += 10

        # Calculate final score
        final_score = max(0, min(100, base_score - deductions))
        return int(final_score)
