"""SQL Server SHOWPLAN XML parser for EXPLAIN analysis."""

import xml.etree.ElementTree as ET
from typing import Any


class MSSQLExplainParser:
    """Parseador especializado para salidas SHOWPLAN_XML de SQL Server.

    Analiza el XML devuelto por SET SHOWPLAN_XML ON para extraer métricas,
    construir el árbol de ejecución y generar un plan normalizado compatible
    con AntiPatternDetector.
    """

    _SHOWPLAN_NS = "http://schemas.microsoft.com/sqlserver/2004/07/showplan"

    def __init__(self, seq_scan_threshold: int = 10000) -> None:
        """Initialize parser with configurable thresholds.

        Args:
            seq_scan_threshold: Row count threshold for table scan warnings
                (default: 10000)
        """
        self.seq_scan_threshold = seq_scan_threshold

    def parse(self, xml_string: str) -> dict[str, Any]:
        """Parse raw XML SHOWPLAN output into a structured metrics dict.

        Args:
            xml_string: Raw XML from SHOWPLAN_XML

        Returns:
            Dict with: execution_time_ms, total_cost, node_count,
            most_expensive_node, scan_nodes, join_nodes, all_nodes
        """
        root = ET.fromstring(xml_string)
        ns = {"sql": self._SHOWPLAN_NS}

        stmt_simple = root.find(".//sql:StmtSimple", ns)
        root_relop = None
        total_cost = 0.0
        if stmt_simple is not None:
            query_plan = stmt_simple.find("sql:QueryPlan", ns)
            if query_plan is not None:
                root_relop = query_plan.find("sql:RelOp", ns)
                if root_relop is not None:
                    total_cost = float(root_relop.get("EstimatedTotalSubtreeCost", 0.0))

        relops = [root_relop] if root_relop is not None else []
        all_nodes = self._collect_nodes(relops, root, ns)

        most_expensive = self._find_most_expensive(relops)

        scan_nodes = [
            n
            for n in all_nodes
            if n.get("node_type", "").lower()
            in ("table scan", "clustered index scan", "index scan")
        ]
        join_nodes = [
            n
            for n in all_nodes
            if "join" in n.get("node_type", "").lower()
            or n.get("node_type", "").lower() in ("hash match", "nested loops", "merge join")
        ]

        return {
            "execution_time_ms": 1.0,
            "total_cost": total_cost,
            "node_count": len(all_nodes),
            "most_expensive_node": most_expensive,
            "scan_nodes": scan_nodes,
            "join_nodes": join_nodes,
            "all_nodes": all_nodes,
        }

    def _collect_nodes(
        self,
        relops: list[ET.Element],
        root: ET.Element,
        ns: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Recursively extract all nodes from RelOp elements."""
        all_nodes: list[dict[str, Any]] = []

        for relop in relops:
            physical_op = relop.get("PhysicalOp", "Unknown")
            logical_op = relop.get("LogicalOp", "Unknown")
            estimate_rows = relop.get("EstimateRows")
            estimate_cost = relop.get("EstimatedTotalSubtreeCost")
            node_id = relop.get("NodeId")

            node: dict[str, Any] = {
                "node_type": physical_op,
                "logical_op": logical_op,
                "estimated_rows": int(float(estimate_rows)) if estimate_rows else 0,
                "estimated_cost": float(estimate_cost) if estimate_cost else 0.0,
                "node_id": int(node_id) if node_id else 0,
            }

            obj = relop.find(".//sql:Object", ns)
            if obj is not None:
                node["table_name"] = obj.get("Table", "unknown")
                node["schema"] = obj.get("Schema", "unknown")
                node["index_name"] = obj.get("Index", "") or None
                node["alias"] = obj.get("Alias", "")
            else:
                node["table_name"] = "unknown"

            predicate = relop.find(".//sql:Predicate/sql:ScalarOperator", ns)
            if predicate is not None:
                node["filter_condition"] = predicate.get("ScalarString", "")

            outputs = relop.findall(".//sql:ColumnReference", ns)
            output_columns = []
            for col in outputs:
                table = col.get("Table", "")
                column = col.get("Column", "")
                if column:
                    output_columns.append(f"{table}.{column}" if table else column)
            node["output_columns"] = output_columns

            children = relop.findall("sql:RelOp", ns)
            if children:
                child_nodes = self._collect_nodes(children, root, ns)
                node["children"] = child_nodes
                all_nodes.extend(child_nodes)

            all_nodes.append(node)

        return all_nodes

    def _find_most_expensive(self, relops: list[ET.Element]) -> dict[str, Any]:
        """Find the RelOp with highest EstimatedTotalSubtreeCost."""
        most_expensive: dict[str, Any] = {}
        max_cost = 0.0

        for relop in relops:
            cost_str = relop.get("EstimatedTotalSubtreeCost", "0.0")
            cost = float(cost_str)
            if cost > max_cost:
                max_cost = cost
                most_expensive = {
                    "type": relop.get("PhysicalOp", "Unknown"),
                    "cost": cost,
                    "logical_op": relop.get("LogicalOp", ""),
                    "estimated_rows": int(float(relop.get("EstimateRows", 0))),
                }

        return most_expensive

    def normalize_plan(self, raw_plan: dict[str, Any] | str) -> dict[str, Any]:
        """Convert SQL Server XML plan to normalized format for AntiPatternDetector.

        Args:
            raw_plan: Either a dict node from parse() or raw XML string

        Returns:
            Normalized plan dict with keys:
                node_type, table_name, estimated_rows, actual_rows,
                estimated_cost, index_used, filter_condition,
                extra_info, children
        """
        if isinstance(raw_plan, str):
            return self._normalize_from_xml(raw_plan)
        if not raw_plan:
            return {}
        return self._normalize_from_dict(raw_plan)

    def _normalize_from_xml(self, xml_string: str) -> dict[str, Any]:
        """Parse XML string into a normalized plan rooted at the outermost RelOp."""
        root = ET.fromstring(xml_string)
        ns = {"sql": self._SHOWPLAN_NS}

        stmt = root.find(".//sql:StmtSimple", ns)
        if stmt is None:
            return {}

        query_plan = stmt.find("sql:QueryPlan", ns)
        if query_plan is None:
            return {}

        relop = query_plan.find("sql:RelOp", ns)
        if relop is None:
            return {}

        return self._normalize_relop(relop, ns)

    def _normalize_from_dict(self, node: dict[str, Any]) -> dict[str, Any]:
        """Convert a dict node (from parse()) to normalized format."""
        node_type_map = self._get_node_type_mapping()
        raw_type = node.get("node_type", "Unknown")
        node_type = node_type_map.get(raw_type, raw_type)

        if raw_type.lower() in ("table scan", "clustered index scan"):
            node_type = "Seq Scan"

        children = []
        for child in node.get("children", []):
            children.append(self._normalize_from_dict(child))

        defined_values = node.get("defined_values", [])
        extra_info: list[str] = list(defined_values) if defined_values else []

        return {
            "node_type": node_type,
            "table_name": node.get("table_name", "unknown"),
            "actual_rows": None,
            "estimated_rows": node.get("estimated_rows"),
            "actual_time_ms": None,
            "estimated_cost": node.get("estimated_cost"),
            "index_used": node.get("index_name"),
            "filter_condition": node.get("filter_condition"),
            "extra_info": extra_info,
            "children": children,
        }

    def _normalize_relop(self, relop: ET.Element, ns: dict[str, str]) -> dict[str, Any]:
        """Recursively normalize an XML RelOp element."""
        physical_op = relop.get("PhysicalOp", "Unknown")
        logical_op = relop.get("LogicalOp", "Unknown")

        node_type_map = self._get_node_type_mapping()
        node_type = node_type_map.get(physical_op, physical_op)

        if physical_op.lower() in ("table scan", "clustered index scan"):
            node_type = "Seq Scan"

        estimate_rows = relop.get("EstimateRows")
        estimate_cost = relop.get("EstimatedTotalSubtreeCost")

        table_name = "unknown"
        index_used = None
        filter_condition = None

        obj = relop.find("sql:Object", ns)
        if obj is not None:
            table_name = obj.get("Table", "unknown")
            index_name_obj = obj.get("Index", "")
            if index_name_obj:
                index_used = index_name_obj

        predicate = relop.find(".//sql:Predicate/sql:ScalarOperator", ns)
        if predicate is not None:
            filter_condition = predicate.get("ScalarString", "")

        children = []
        for child_relop in relop.findall("sql:RelOp", ns):
            children.append(self._normalize_relop(child_relop, ns))

        return {
            "node_type": node_type,
            "table_name": table_name,
            "actual_rows": None,
            "estimated_rows": int(float(estimate_rows)) if estimate_rows else None,
            "actual_time_ms": None,
            "estimated_cost": float(estimate_cost) if estimate_cost else None,
            "index_used": index_used,
            "filter_condition": filter_condition,
            "extra_info": [f"LogicalOp: {logical_op}"],
            "children": children,
        }

    @staticmethod
    def _get_node_type_mapping() -> dict[str, str]:
        """Map SQL Server physical operator names to engine-agnostic types."""
        return {
            "Table Scan": "Seq Scan",
            "Clustered Index Scan": "Seq Scan",
            "Clustered Index Seek": "Index Seek",
            "Index Scan": "Index Scan",
            "Index Seek": "Index Seek",
            "RID Lookup": "Index Lookup",
            "Key Lookup": "Index Lookup",
            "Nested Loops": "Nested Loop",
            "Merge Join": "Merge Join",
            "Hash Match": "Hash Join",
            "Sort": "Sort",
            "Compute Scalar": "Compute Scalar",
            "Stream Aggregate": "Aggregate",
            "Hash Match Aggregate": "Aggregate",
            "Parallelism": "Parallelism",
            "Top": "Limit",
            "Filter": "Filter",
            "Bookmark Lookup": "Index Lookup",
        }
