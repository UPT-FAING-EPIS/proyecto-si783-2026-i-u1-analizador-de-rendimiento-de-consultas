"""Migration helpers for converting v1 data to v2 QueryAnalysisReport models.

This module provides utilities to convert legacy v1 reports (with string-based
warnings/recommendations) to v2 reports (with structured Warning/Recommendation
dataclasses).

Used by adapters during migration from v1 to v2 model.
"""

from typing import Any, Literal, cast

from query_analyzer.core.anti_pattern_detector import AntiPattern, DetectionResult, Severity

from .models import PlanNode, Recommendation, Warning


def antipattern_to_warning(antipattern: AntiPattern) -> Warning:
    """Convert AntiPattern to Warning dataclass.

    Maps Severity enum to literal severity strings used by Warning.

    Args:
        antipattern: AntiPattern from detector

    Returns:
        Warning with mapped severity and metadata
    """
    severity_map = {
        Severity.HIGH: "critical",
        Severity.MEDIUM: "high",
        Severity.LOW: "medium",
    }

    severity_str = severity_map.get(antipattern.severity, "low")
    severity: Literal["critical", "high", "medium", "low"] = cast(
        Literal["critical", "high", "medium", "low"], severity_str
    )

    affected_object = _resolve_affected_object(antipattern)

    return Warning(
        severity=severity,
        message=antipattern.description,
        node_type=antipattern.name,
        affected_object=affected_object,
        metadata={
            "column": antipattern.affected_column,
            **antipattern.metadata,
        },
    )


def _resolve_affected_object(antipattern: AntiPattern) -> str:
    """Resolve affected object name with safe fallbacks."""
    if antipattern.affected_table and antipattern.affected_table.lower() not in {"none", "unknown"}:
        return antipattern.affected_table

    metadata = antipattern.metadata or {}
    for key in ("table_name", "outer_table", "inner_table"):
        value = metadata.get(key)
        if isinstance(value, str) and value and value.lower() not in {"none", "unknown"}:
            return value

    return "unknown"


def detection_result_to_warnings_and_recommendations(
    detection_result: DetectionResult,
) -> tuple[list[Warning], list[Recommendation]]:
    """Convert DetectionResult to Warning and Recommendation lists.

    Args:
        detection_result: Result from AntiPatternDetector.analyze()

    Returns:
        Tuple of (warnings list, recommendations list)
    """
    warnings = [antipattern_to_warning(ap) for ap in detection_result.anti_patterns]

    recommendations = []
    for idx, rec_text in enumerate(detection_result.recommendations, start=1):
        priority = max(1, 10 - idx)
        rec = Recommendation(
            priority=priority,
            title=rec_text.split("\n")[0],
            description=rec_text,
            code_snippet=None,
            affected_object="",
            metadata={},
        )
        recommendations.append(rec)

    return warnings, recommendations


def build_plan_tree(raw_plan_dict: dict[str, Any], node_type: str = "root") -> PlanNode | None:
    """Build PlanNode tree from raw EXPLAIN plan dictionary.

    Handles generic plan structure that works across different SQL databases
    (PostgreSQL, MySQL, etc.) by extracting common fields.

    Args:
        raw_plan_dict: Raw EXPLAIN plan as dictionary
        node_type: Node type for the root (default: "root")

    Returns:
        PlanNode tree or None if plan is empty

    Raises:
        ValueError: If plan structure is invalid
    """
    if not raw_plan_dict:
        return None

    actual_node_type = (
        raw_plan_dict.get("Node Type")
        or raw_plan_dict.get("type")
        or raw_plan_dict.get("operation")
        or node_type
    )

    cost = raw_plan_dict.get("Total Cost") or raw_plan_dict.get("cost")
    estimated_rows = raw_plan_dict.get("Estimated Rows") or raw_plan_dict.get("estimated_rows")
    actual_rows = raw_plan_dict.get("Actual Rows") or raw_plan_dict.get("actual_rows")
    actual_time = (
        raw_plan_dict.get("Actual Total Time")
        or raw_plan_dict.get("actual_time_ms")
        or raw_plan_dict.get("Actual Time")
    )

    if isinstance(cost, (int, float)):
        cost = float(cost)
    if isinstance(estimated_rows, (int, float)):
        estimated_rows = int(estimated_rows)
    if isinstance(actual_rows, (int, float)):
        actual_rows = int(actual_rows)
    if isinstance(actual_time, (int, float)):
        actual_time_ms = float(actual_time)
    else:
        actual_time_ms = None

    children: list[PlanNode] = []
    plans = raw_plan_dict.get("Plans") or raw_plan_dict.get("children") or []
    for child_plan in plans:
        if isinstance(child_plan, dict):
            child_node = build_plan_tree(child_plan)
            if child_node:
                children.append(child_node)

    properties: dict[str, Any] = {}
    for key, value in raw_plan_dict.items():
        if key not in {
            "Node Type",
            "type",
            "operation",
            "Total Cost",
            "cost",
            "Estimated Rows",
            "estimated_rows",
            "Actual Rows",
            "actual_rows",
            "Actual Total Time",
            "actual_time_ms",
            "Actual Time",
            "Plans",
            "children",
        }:
            properties[key] = value

    return PlanNode(
        node_type=actual_node_type,
        cost=cost,
        estimated_rows=estimated_rows,
        actual_rows=actual_rows,
        actual_time_ms=actual_time_ms,
        children=children,
        properties=properties,
    )
