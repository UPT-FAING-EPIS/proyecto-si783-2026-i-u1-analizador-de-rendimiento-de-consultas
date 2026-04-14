"""DynamoDB anti-pattern detector specialized for NoSQL queries.

Detects DynamoDB-specific anti-patterns:
1. Full Table Scan (Scan vs Query)
2. High RCU/WCU consumption
3. Query without partition key condition
4. Large result set without LIMIT
5. High scan/read ratio
6. Inefficient GSI usage
7. Missing projection expression

Architecture: Separate from SQL anti-pattern detector (core/anti_pattern_detector.py)
to avoid mixing SQL and NoSQL detection logic.
"""

from dataclasses import dataclass, field
from typing import Any

from query_analyzer.core.anti_pattern_detector import AntiPattern, DetectionResult, Severity


@dataclass
class DynamoDBDetectorConfig:
    """Configuration for DynamoDB anti-pattern detection."""

    high_rcu_threshold: int = 1000
    """RCU threshold for 'high consumption' alert"""

    high_scan_ratio_threshold: float = 2.0
    """ScannedCount / Count ratio threshold"""

    max_result_rows: int = 10_000
    """Maximum result rows before 'large result set' alert"""


@dataclass
class DynamoDBDetectionResult:
    """Result of DynamoDB anti-pattern analysis."""

    score: int
    """Score final 0-100"""

    anti_patterns: list[AntiPattern]
    """List of detected anti-patterns"""

    recommendations: list[str]
    """List of recommendations"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional analysis metadata"""


class DynamoDBScoringEngine:
    """Scoring engine specialized for DynamoDB (0-100).

    Each anti-pattern detected deducts points based on severity.
    Final score never goes below 0.

    Penalty scale:
    - Severity HIGH: -25 points
    - Severity MEDIUM: -15 points
    - Severity LOW: -5 points
    """

    PENALTIES = {
        Severity.HIGH: 25,
        Severity.MEDIUM: 15,
        Severity.LOW: 5,
    }

    @staticmethod
    def calculate_score(anti_patterns: list[AntiPattern]) -> int:
        """Calculate 0-100 score based on anti-patterns.

        Args:
            anti_patterns: List of detected anti-patterns

        Returns:
            Score from 0 to 100
        """
        score = 100
        for pattern in anti_patterns:
            penalty = DynamoDBScoringEngine.PENALTIES.get(pattern.severity, 5)
            score -= penalty

        return max(0, score)


class DynamoDBAntiPatternDetector:
    """Detect anti-patterns specific to DynamoDB queries."""

    def __init__(self, config: DynamoDBDetectorConfig | None = None) -> None:
        """Initialize detector with configuration.

        Args:
            config: DynamoDBDetectorConfig (uses defaults if None)
        """
        self.config = config or DynamoDBDetectorConfig()

    def detect_scan_operation(self, query_dict: dict[str, Any]) -> AntiPattern | None:
        """Detect if operation is a Scan (inefficient vs Query).

        Anti-pattern #1: Full Table Scan
        Scan reads all items, Query reads only matching partition key items.

        Args:
            query_dict: Parsed DynamoDB operation

        Returns:
            AntiPattern if Scan detected, None otherwise
        """
        if "KeyConditionExpression" not in query_dict:
            return AntiPattern(
                name="full_table_scan",
                severity=Severity.HIGH,
                description=(
                    "Operation uses Scan instead of Query. "
                    "Scan reads all items in table, Query reads only matching partition key. "
                    "Use Query with KeyConditionExpression for better performance."
                ),
                affected_table=query_dict.get("TableName"),
                metadata={
                    "operation_type": "Scan",
                    "recommendation": "Use Query with KeyConditionExpression on partition key",
                },
            )
        return None

    def detect_missing_partition_key(self, query_dict: dict[str, Any]) -> AntiPattern | None:
        """Detect if Query lacks partition key condition.

        Anti-pattern #3: Query without partition key condition
        Valid Query requires: partition_key = value in KeyConditionExpression

        Args:
            query_dict: Parsed DynamoDB operation

        Returns:
            AntiPattern if partition key missing, None otherwise
        """
        if "KeyConditionExpression" in query_dict:
            key_expr = query_dict["KeyConditionExpression"]

            # Basic check: if expression seems incomplete or only has sort key
            # TODO: Full parsing of KeyConditionExpression syntax
            # For now, simple heuristics
            if isinstance(key_expr, str):
                # If expression only mentions a secondary index sort key
                # This is simplified - real implementation would parse more thoroughly
                if "=" not in key_expr:
                    return AntiPattern(
                        name="missing_partition_key",
                        severity=Severity.HIGH,
                        description=(
                            "Query KeyConditionExpression appears incomplete. "
                            "Partition key condition is required. "
                            "Example: pk = :pk AND sk = :sk"
                        ),
                        affected_table=query_dict.get("TableName"),
                        metadata={
                            "operation_type": "Query",
                            "key_expression": key_expr,
                        },
                    )

        return None

    def detect_high_capacity_consumption(
        self, response_metrics: dict[str, Any]
    ) -> AntiPattern | None:
        """Detect if query consumed excessive read capacity units.

        Anti-pattern #2: High RCU/WCU consumption
        Threshold: configurable, default 1000 RCU per request

        Args:
            response_metrics: Metrics from DynamoDB response

        Returns:
            AntiPattern if high consumption, None otherwise
        """
        read_capacity = response_metrics.get("read_capacity_units", 0)

        if read_capacity > self.config.high_rcu_threshold:
            return AntiPattern(
                name="high_capacity_consumption",
                severity=Severity.MEDIUM,
                description=(
                    f"Query consumed {read_capacity:.1f} RCU. "
                    f"This exceeds the threshold of {self.config.high_rcu_threshold} RCU. "
                    "Consider optimizing with indexes or reducing result size."
                ),
                metadata={
                    "read_capacity_units": read_capacity,
                    "threshold": self.config.high_rcu_threshold,
                },
            )

        return None

    def detect_large_result_set(
        self, query_dict: dict[str, Any], response_metrics: dict[str, Any]
    ) -> AntiPattern | None:
        """Detect if query returns many items without LIMIT.

        Anti-pattern #4: Large result set without LIMIT
        Check: response.Count > threshold AND no Limit in query

        Args:
            query_dict: Parsed DynamoDB operation
            response_metrics: Metrics from DynamoDB response

        Returns:
            AntiPattern if large result set detected, None otherwise
        """
        item_count = response_metrics.get("item_count", 0)
        has_limit = "Limit" in query_dict

        if item_count > self.config.max_result_rows and not has_limit:
            return AntiPattern(
                name="large_result_set",
                severity=Severity.MEDIUM,
                description=(
                    f"Query returned {item_count} items without LIMIT. "
                    f"This exceeds the threshold of {self.config.max_result_rows} items. "
                    "Add LIMIT to paginate results and reduce RCU consumption."
                ),
                affected_table=query_dict.get("TableName"),
                metadata={
                    "item_count": item_count,
                    "threshold": self.config.max_result_rows,
                    "has_limit": has_limit,
                },
            )

        return None

    def detect_high_scan_ratio(self, response_metrics: dict[str, Any]) -> AntiPattern | None:
        """Detect inefficient filtering (ScannedCount >> Count).

        Anti-pattern #6: High scan/read ratio
        Example: Scan 10K items but return only 100 (ratio 100x)
        Suggests: Move filter to KeyConditionExpression or use better index

        Args:
            response_metrics: Metrics from DynamoDB response

        Returns:
            AntiPattern if high ratio detected, None otherwise
        """
        scanned_count = response_metrics.get("scanned_count", 0)
        item_count = response_metrics.get("item_count", 0)

        # Avoid division by zero
        if item_count == 0 and scanned_count > 0:
            scan_ratio = float("inf")
        elif item_count > 0:
            scan_ratio = scanned_count / item_count
        else:
            scan_ratio = 0

        if scan_ratio > self.config.high_scan_ratio_threshold:
            return AntiPattern(
                name="high_scan_ratio",
                severity=Severity.MEDIUM,
                description=(
                    f"Query scanned {scanned_count} items but returned only {item_count}. "
                    f"Scan/read ratio is {scan_ratio:.2f}x (threshold: {self.config.high_scan_ratio_threshold}x). "
                    "Move FilterExpression conditions to KeyConditionExpression or create a better GSI."
                ),
                metadata={
                    "scanned_count": scanned_count,
                    "item_count": item_count,
                    "scan_ratio": scan_ratio,
                    "threshold": self.config.high_scan_ratio_threshold,
                },
            )

        return None

    def detect_full_attribute_projection(
        self, query_dict: dict[str, Any], response_metrics: dict[str, Any]
    ) -> AntiPattern | None:
        """Detect unnecessary full attribute projection (no ProjectionExpression).

        Anti-pattern #7: Missing ProjectionExpression
        Without projection, DynamoDB returns all attributes, consuming more RCU.
        If returning many items with many attributes, RCU waste is significant.

        Args:
            query_dict: Parsed DynamoDB operation
            response_metrics: Metrics from DynamoDB response

        Returns:
            AntiPattern if full projection detected and inefficient, None otherwise
        """
        has_projection = "ProjectionExpression" in query_dict
        item_count = response_metrics.get("item_count", 0)
        read_capacity = response_metrics.get("read_capacity_units", 0)

        # Only flag if: many items returned + no projection + reasonable RCU
        # Heuristic: 100+ items with no projection + RCU > 10 suggests inefficiency
        if not has_projection and item_count >= 100 and read_capacity >= 10:
            return AntiPattern(
                name="full_attribute_projection",
                severity=Severity.LOW,
                description=(
                    f"Query returns {item_count} items without ProjectionExpression. "
                    "Consumed {read_capacity:.1f} RCU for full attribute set. "
                    "Use ProjectionExpression to request only needed attributes and reduce RCU."
                ),
                affected_table=query_dict.get("TableName"),
                metadata={
                    "item_count": item_count,
                    "read_capacity_units": read_capacity,
                    "has_projection": has_projection,
                },
            )

        return None

    def detect_inefficient_pagination(self, query_dict: dict[str, Any]) -> AntiPattern | None:
        """Detect missing or inefficient pagination (LastEvaluatedKey not used).

        Anti-pattern #8: No pagination limit or inefficient pagination
        If query returns many items, pagination is critical to manage RCU.

        Args:
            query_dict: Parsed DynamoDB operation

        Returns:
            AntiPattern if inefficient pagination detected, None otherwise
        """
        has_limit = "Limit" in query_dict
        has_exclusive_start_key = "ExclusiveStartKey" in query_dict

        # Flag if: no pagination control at all
        if not has_limit and not has_exclusive_start_key:
            return AntiPattern(
                name="inefficient_pagination",
                severity=Severity.LOW,
                description=(
                    "Query lacks pagination (no Limit or ExclusiveStartKey). "
                    "Without pagination, queries fetch unbounded results consuming excess RCU. "
                    "Use Limit to paginate and ExclusiveStartKey for subsequent requests."
                ),
                affected_table=query_dict.get("TableName"),
                metadata={
                    "has_limit": has_limit,
                    "has_exclusive_start_key": has_exclusive_start_key,
                },
            )

        return None

    def detect_gsi_query_without_range_key(self, query_dict: dict[str, Any]) -> AntiPattern | None:
        """Detect GSI query without range key (causes additional scan overhead).

        Anti-pattern #9: GSI query only on partition key without range key
        GSI queries without range key require full partition scan vs index range scan.

        Args:
            query_dict: Parsed DynamoDB operation

        Returns:
            AntiPattern if inefficient GSI query detected, None otherwise
        """
        # Check for IndexName (indicates GSI query)
        index_name = query_dict.get("IndexName")
        if not index_name:
            return None  # Not a GSI query

        # Check KeyConditionExpression for range key (usually has AND for range)
        key_expr = query_dict.get("KeyConditionExpression", "")
        if isinstance(key_expr, str):
            # Heuristic: if no AND or only one condition, likely no range key
            has_range_condition = " AND " in key_expr or " and " in key_expr

            if not has_range_condition:
                return AntiPattern(
                    name="gsi_without_range_key",
                    severity=Severity.LOW,
                    description=(
                        f"Query on GSI '{index_name}' lacks range key in KeyConditionExpression. "
                        "GSI queries without range keys require scanning the full partition. "
                        "Add range key condition if available to reduce scanned items."
                    ),
                    metadata={
                        "index_name": index_name,
                        "key_expression": key_expr,
                        "has_range_condition": has_range_condition,
                    },
                )

        return None

    def analyze(self, query_dict: dict[str, Any], response: dict[str, Any]) -> DetectionResult:
        """Orchestrate detection of DynamoDB anti-patterns.

        Detects Phase 1 anti-patterns (#1, #3, #2, #4, #6).
        Detects Phase 3 anti-patterns (#7, #8, #9).

        Args:
            query_dict: Parsed DynamoDB Query or Scan operation
            response: Response from DynamoDB (with ReturnConsumedCapacity)

        Returns:
            DetectionResult with score, anti-patterns, and recommendations
        """
        anti_patterns: list[AntiPattern] = []
        response_metrics = {
            "read_capacity_units": response.get("ConsumedCapacity", {}).get("CapacityUnits", 0),
            "item_count": response.get("Count", 0),
            "scanned_count": response.get("ScannedCount", 0),
        }

        # Phase 1: Detect critical anti-patterns
        pattern = self.detect_scan_operation(query_dict)
        if pattern:
            anti_patterns.append(pattern)

        pattern = self.detect_missing_partition_key(query_dict)
        if pattern:
            anti_patterns.append(pattern)

        # Phase 1: Detect medium-severity anti-patterns
        pattern = self.detect_high_capacity_consumption(response_metrics)
        if pattern:
            anti_patterns.append(pattern)

        pattern = self.detect_large_result_set(query_dict, response_metrics)
        if pattern:
            anti_patterns.append(pattern)

        pattern = self.detect_high_scan_ratio(response_metrics)
        if pattern:
            anti_patterns.append(pattern)

        # Phase 3: Detect advanced low-severity anti-patterns
        pattern = self.detect_full_attribute_projection(query_dict, response_metrics)
        if pattern:
            anti_patterns.append(pattern)

        pattern = self.detect_inefficient_pagination(query_dict)
        if pattern:
            anti_patterns.append(pattern)

        pattern = self.detect_gsi_query_without_range_key(query_dict)
        if pattern:
            anti_patterns.append(pattern)

        # Calculate score
        score = DynamoDBScoringEngine.calculate_score(anti_patterns)

        # Generate recommendations (stub for now)
        recommendations = [f"{ap.description}" for ap in anti_patterns]

        return DetectionResult(
            score=score, anti_patterns=anti_patterns, recommendations=recommendations
        )
