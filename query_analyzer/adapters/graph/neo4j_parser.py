"""Neo4j PROFILE plan parser and analyzer."""

from typing import Any


class Neo4jExplainParser:
    """Parser for Neo4j PROFILE output.

    Analyzes execution plans returned by PROFILE command, extracts metrics
    (db_hits, rows, execution time), and normalizes to engine-agnostic format
    for AntiPatternDetector.

    Attributes:
        expand_threshold: Expand node threshold for detecting unbounded expansion
    """

    def __init__(self, expand_threshold: int = 1000) -> None:
        """Initialize parser with configurable thresholds.

        Args:
            expand_threshold: Expand node rows threshold (default: 1000)
        """
        self.expand_threshold = expand_threshold

    def parse(self, profile_result: dict[str, Any]) -> dict[str, Any]:
        """Parse PROFILE output and extract all metrics.

        Args:
            profile_result: Complete PROFILE output dict with 'profile' key

        Returns:
            Dictionary with:
                - execution_time_ms: Total execution time
                - planning_time_ms: Planning time
                - total_db_hits: Aggregate db_hits across all nodes
                - total_rows: Total rows returned
                - node_count: Number of nodes in plan tree
                - plan_nodes: All nodes in flat list
                - scan_nodes: NodeByLabelScan, NodeIndexScan, etc.
                - expand_nodes: Expand(All), Expand nodes
                - filter_nodes: Filter nodes
                - join_nodes: CartesianProduct, etc.
                - most_expensive_node: Node with highest db_hits
                - all_nodes: All nodes for AntiPatternDetector
        """
        # Extract profile statistics
        profile_data = profile_result.get("profile", {})
        stats = profile_data.get("stats", {})

        # Basic metrics
        execution_time_ms = float(stats.get("time", 0)) / 1000.0  # Convert from ms to ms
        planning_time_ms = 0.0  # Neo4j doesn't separate planning time in PROFILE

        # Get plan root node
        plan_root = profile_data.get("plan", {})

        # Collect all nodes via recursive traversal
        all_nodes: list[dict[str, Any]] = []
        self._traverse_plan_tree(plan_root, all_nodes)

        # Aggregate metrics
        total_db_hits = sum(int(node.get("dbHits", 0)) for node in all_nodes)
        total_rows = int(stats.get("rows", 0))

        # Categorize nodes by type
        scan_nodes = [
            n
            for n in all_nodes
            if n.get("operatorType", "").endswith("Scan")
            and "Index" not in n.get("operatorType", "")
        ]
        expand_nodes = [n for n in all_nodes if "Expand" in n.get("operatorType", "")]
        filter_nodes = [n for n in all_nodes if n.get("operatorType") == "Filter"]
        join_nodes = [
            n
            for n in all_nodes
            if "CartesianProduct" in n.get("operatorType", "")
            or "Join" in n.get("operatorType", "")
        ]

        # Find most expensive node
        most_expensive = self._find_most_expensive_node(all_nodes)

        return {
            "execution_time_ms": execution_time_ms,
            "planning_time_ms": planning_time_ms,
            "total_db_hits": total_db_hits,
            "total_rows": total_rows,
            "node_count": len(all_nodes),
            "plan_nodes": all_nodes,
            "scan_nodes": scan_nodes,
            "expand_nodes": expand_nodes,
            "filter_nodes": filter_nodes,
            "join_nodes": join_nodes,
            "most_expensive_node": most_expensive,
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

        # Add current node
        all_nodes.append(node)

        # Traverse children
        children = node.get("children", [])
        for child in children:
            self._traverse_plan_tree(child, all_nodes, depth + 1)

    def _find_most_expensive_node(self, all_nodes: list[dict[str, Any]]) -> dict[str, Any]:
        """Find the node with highest db_hits.

        Args:
            all_nodes: List of all nodes in plan

        Returns:
            Node with highest db_hits, or empty dict if no nodes
        """
        if not all_nodes:
            return {}

        return max(all_nodes, key=lambda n: int(n.get("dbHits", 0)))

    def normalize_plan(self, plan_root: dict[str, Any]) -> dict[str, Any]:
        """Convert Neo4j plan to engine-agnostic format.

        Transforms Neo4j-specific operator types and metrics to a normalized
        structure that AntiPatternDetector understands.

        Args:
            plan_root: Root node of Neo4j PROFILE plan

        Returns:
            Normalized plan node structure for AntiPatternDetector
        """
        if not plan_root:
            return {}

        node_type = plan_root.get("operatorType", "Unknown")
        arguments = plan_root.get("arguments", {})

        # Normalize node type
        normalized_type = self._normalize_operator_type(node_type)

        # Extract metrics
        db_hits = int(plan_root.get("dbHits", 0))
        rows = int(plan_root.get("rows", 0))
        estimated_rows = int(arguments.get("EstimatedRows", 0))

        # Determine if index is used
        index_used = "Index" in node_type

        # Get filter info
        filter_expr = arguments.get("filter", None) or arguments.get("Condition", None)

        # Normalize children
        children = plan_root.get("children", [])
        normalized_children = [self.normalize_plan(child) for child in children if child]

        return {
            "node_type": normalized_type,
            "estimated_rows": estimated_rows,
            "actual_rows": rows,
            "db_hits": db_hits,
            "children": normalized_children,
            "index_used": index_used,
            "filter": filter_expr,
            "original_operator": node_type,
            "arguments": arguments,
        }

    def _normalize_operator_type(self, operator_type: str) -> str:
        """Map Neo4j operator types to normalized types.

        Args:
            operator_type: Neo4j operator type string

        Returns:
            Normalized operator type
        """
        # Scan operators
        if operator_type == "NodeByLabelScan":
            return "NodeByLabelScan"
        if "NodeIndexScan" in operator_type or "NodeIndexSeek" in operator_type:
            return "NodeIndexScan"
        if operator_type == "AllNodesScan":
            return "AllNodesScan"

        # Expand operators
        if "Expand" in operator_type:
            return "Expand"

        # Join operators
        if operator_type == "CartesianProduct":
            return "CartesianProduct"

        # Other
        if operator_type == "Filter":
            return "Filter"
        if operator_type == "ProduceResults":
            return "ProduceResults"

        return operator_type

    def detect_anti_patterns_cypher(self, plan_root: dict[str, Any]) -> list[dict[str, Any]]:
        """Detect anti-patterns specific to Cypher in the plan tree.

        Args:
            plan_root: Root node of Neo4j PROFILE plan

        Returns:
            List of detected anti-patterns with details
        """
        anti_patterns: list[dict[str, Any]] = []
        all_nodes: list[dict[str, Any]] = []

        # Collect all nodes
        self._traverse_plan_tree(plan_root, all_nodes)

        # 1. Detect AllNodesScan
        for node in all_nodes:
            if node.get("operatorType") == "AllNodesScan":
                anti_patterns.append(
                    {
                        "type": "AllNodesScan",
                        "severity": "HIGH",
                        "node": node,
                        "message": "Query scans all nodes without label filter",
                    }
                )

        # 2. Detect CartesianProduct
        for node in all_nodes:
            if node.get("operatorType") == "CartesianProduct":
                anti_patterns.append(
                    {
                        "type": "CartesianProduct",
                        "severity": "HIGH",
                        "node": node,
                        "message": "Cartesian product detected - likely disconnected patterns in MATCH",
                    }
                )

        # 3. Detect NodeByLabelScan without index on filtered property
        for node in all_nodes:
            if node.get("operatorType") == "NodeByLabelScan":
                # Check if next node is a Filter
                if self._has_filter_child(node):
                    anti_patterns.append(
                        {
                            "type": "LabelScanWithFilter",
                            "severity": "MEDIUM",
                            "node": node,
                            "message": "Label scan followed by filter - consider creating index",
                        }
                    )

        # 4. Detect Expand without limit on high-degree nodes
        for node in all_nodes:
            if "Expand" in node.get("operatorType", ""):
                rows = int(node.get("rows", 0))
                if rows > self.expand_threshold and rows > 0:
                    anti_patterns.append(
                        {
                            "type": "UnboundedExpand",
                            "severity": "MEDIUM",
                            "node": node,
                            "message": f"Expand without limit returns {rows} rows",
                        }
                    )

        # 5. Detect Filter after Expand (inefficient)
        for node in all_nodes:
            if "Expand" in node.get("operatorType", ""):
                if self._has_filter_child(node):
                    anti_patterns.append(
                        {
                            "type": "FilterAfterExpand",
                            "severity": "LOW",
                            "node": node,
                            "message": "Filter applied after Expand - move filter before Expand if possible",
                        }
                    )

        return anti_patterns

    def _has_filter_child(self, node: dict[str, Any]) -> bool:
        """Check if node has Filter in its children.

        Args:
            node: Plan node

        Returns:
            True if Filter is found in children
        """
        children = node.get("children", [])
        for child in children:
            if child.get("operatorType") == "Filter":
                return True
        return False
