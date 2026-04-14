"""DynamoDB database adapter for query performance analysis.

Uses boto3 to connect to DynamoDB (AWS or local DynamoDB-Local).
Analyzes Query and Scan operations based on metrics and anti-patterns.

Architecture:
- Metrics-driven analysis (no query optimizer)
- Anti-patterns detected via DynamoDBAntiPatternDetector
- Results converted to v2 QueryAnalysisReport models
"""

import logging
from datetime import UTC, datetime
from typing import Any, cast

from query_analyzer.adapters.base import BaseAdapter
from query_analyzer.adapters.models import ConnectionConfig, QueryAnalysisReport
from query_analyzer.adapters.registry import AdapterRegistry
from query_analyzer.core.dynamodb_anti_pattern_detector import (
    DynamoDBAntiPatternDetector,
)

logger = logging.getLogger(__name__)


@AdapterRegistry.register("dynamodb")
class DynamoDBAdapter(BaseAdapter):
    """DynamoDB adapter for query performance analysis.

    Supports Query and Scan operations, analyzes consumed capacity,
    and detects anti-patterns specific to DynamoDB.
    """

    def __init__(self, config: ConnectionConfig) -> None:
        """Initialize DynamoDB adapter.

        Args:
            config: ConnectionConfig with DynamoDB connection details
        """
        super().__init__(config)
        self._dynamodb_client: Any = None
        self._parser: Any = None

    @property
    def parser(self) -> Any:
        """Get the parser instance (public accessor for tests).

        Returns:
            DynamoDBParser instance
        """
        return self._parser

    def connect(self) -> None:
        """Initialize boto3 DynamoDB client.

        Raises:
            ConnectionError: If connection fails or credentials are invalid
        """
        try:
            import boto3

            from query_analyzer.adapters.nosql.dynamodb_parser import DynamoDBParser

            self._parser = DynamoDBParser()

            # Configure boto3 client
            region = self._config.host or "us-east-1"

            # Check if using DynamoDB Local
            if region.startswith("http://") or region.startswith("https://"):
                # Local DynamoDB endpoint
                self._dynamodb_client = boto3.client(
                    "dynamodb",
                    endpoint_url=region,
                    region_name="us-east-1",
                    aws_access_key_id=self._config.username or "local",
                    aws_secret_access_key=self._config.password or "local",
                )
            else:
                # AWS region
                self._dynamodb_client = boto3.client(
                    "dynamodb",
                    region_name=region,
                )

            # Test connection
            if not self.test_connection():
                raise ConnectionError("DynamoDB health check failed")

            self._is_connected = True
            logger.info(f"Connected to DynamoDB region: {region}")

        except Exception as e:
            self._is_connected = False
            self._dynamodb_client = None
            raise ConnectionError(f"Failed to connect to DynamoDB: {e}") from e

    def disconnect(self) -> None:
        """Close DynamoDB connection.

        DynamoDB clients don't have explicit close method in boto3,
        but we mark as disconnected for cleanup.
        """
        self._is_connected = False
        self._dynamodb_client = None
        logger.info("Disconnected from DynamoDB")

    def test_connection(self) -> bool:
        """Test connection with DescribeTable call.

        Returns:
            True if connection is valid, False otherwise
        """
        if not self._dynamodb_client:
            return False

        try:
            # Try to describe a table (any table name for test)
            # In real usage, we'd use the actual table from the query
            # For now, just check if client can make an API call
            self._dynamodb_client.list_tables()
            logger.debug("DynamoDB connection test successful")
            return True
        except Exception as e:
            logger.debug(f"DynamoDB connection test failed: {e}")
            return False

    def execute_explain(self, query: str) -> QueryAnalysisReport:
        """Analyze DynamoDB query (Query or Scan operation).

        Args:
            query: JSON string representing DynamoDB Query or Scan

        Returns:
            QueryAnalysisReport with analysis results

        Raises:
            QueryAnalysisError: If analysis fails or not connected
        """
        import time

        from query_analyzer.adapters.exceptions import QueryAnalysisError
        from query_analyzer.adapters.migration_helpers import (
            detection_result_to_warnings_and_recommendations,
        )

        if not self._is_connected or not self._dynamodb_client:
            raise QueryAnalysisError("Not connected to DynamoDB")

        if not self._parser:
            raise QueryAnalysisError("Parser not initialized")

        try:
            # Parse query
            query_dict = self._parser.parse_query_string(query)
            table_name = self._parser.extract_table_name(query_dict)

            logger.debug(f"Analyzing query on table: {table_name}")

            # Inject ReturnConsumedCapacity to capture metrics
            query_dict["ReturnConsumedCapacity"] = "TOTAL"

            # Execute query and measure timing
            start_time = time.perf_counter()
            response = self._execute_query(query_dict)
            end_time = time.perf_counter()
            execution_time_ms = (end_time - start_time) * 1000

            logger.debug(f"Query executed in {execution_time_ms:.2f}ms")

            # Extract metrics from response
            metrics = self._parser.extract_consumed_capacity(response)

            # Analyze with DynamoDBAntiPatternDetector
            detector = DynamoDBAntiPatternDetector()
            detection_result = detector.analyze(query_dict, response)

            # Convert to v2 models
            warnings, recommendations = detection_result_to_warnings_and_recommendations(
                detection_result
            )

            # Build report
            report = QueryAnalysisReport(
                engine="dynamodb",
                query=query,
                score=detection_result.score,
                warnings=warnings,
                recommendations=recommendations,
                execution_time_ms=max(execution_time_ms, 0.1),  # Ensure > 0
                raw_plan=query_dict,
                metrics={
                    "consumed_read_capacity": metrics["read_capacity_units"],
                    "item_count": metrics["item_count"],
                    "scanned_count": metrics["scanned_count"],
                },
                plan_tree=None,  # DynamoDB doesn't have a tree plan
                analyzed_at=datetime.now(UTC),
            )

            logger.info(f"Analysis complete: {table_name} (score={report.score})")
            return report

        except QueryAnalysisError:
            raise
        except Exception as e:
            logger.error(f"Query analysis failed: {e}", exc_info=True)
            raise QueryAnalysisError(f"DynamoDB query analysis failed: {e}") from e

    def _execute_query(self, query_dict: dict[str, Any]) -> dict[str, Any]:
        """Execute DynamoDB Query or Scan operation.

        Supports both Query (with KeyConditionExpression) and Scan operations.
        Handles errors gracefully and logs execution details.

        Args:
            query_dict: Parsed DynamoDB operation parameters

        Returns:
            Response from boto3 Query/Scan operation

        Raises:
            RuntimeError: If execution fails
        """
        if not self._dynamodb_client:
            raise RuntimeError("DynamoDB client not initialized")

        # Determine operation type
        operation_type = self._parser.extract_operation_type(query_dict)

        try:
            logger.debug(
                f"Executing DynamoDB {operation_type} on table "
                f"{query_dict.get('TableName', 'unknown')}"
            )

            # Execute appropriate operation
            if operation_type == "Query":
                response = self._dynamodb_client.query(**query_dict)
            else:  # Scan
                response = self._dynamodb_client.scan(**query_dict)

            # Log response metrics
            if "ConsumedCapacity" in response:
                cc = response["ConsumedCapacity"]
                logger.debug(
                    f"Operation consumed: "
                    f"Read={cc.get('CapacityUnits', 0)} RCU, "
                    f"Items={response.get('Count', 0)}, "
                    f"Scanned={response.get('ScannedCount', 0)}"
                )

            return cast(dict[str, Any], response)

        except self._dynamodb_client.exceptions.ResourceNotFoundException as e:
            logger.error(f"Table not found: {e}")
            raise RuntimeError(f"DynamoDB table not found: {e}") from e
        except self._dynamodb_client.exceptions.ValidationException as e:
            logger.error(f"Query validation error: {e}")
            raise RuntimeError(f"DynamoDB validation error: {e}") from e
        except Exception as e:
            logger.error(f"Failed to execute {operation_type}: {e}", exc_info=True)
            raise RuntimeError(f"DynamoDB {operation_type} failed: {e}") from e

    def get_slow_queries(self, threshold_ms: int = 100) -> list[dict]:
        """Return empty list (DynamoDB has no slow query logs in Phase 1).

        Phase 2 (future): Could use CloudWatch Logs + Insights

        Args:
            threshold_ms: Unused in Phase 1

        Returns:
            Empty list
        """
        return []

    def get_metrics(self) -> dict[str, Any]:
        """Return empty dict (CloudWatch integration is Phase 2).

        Phase 1: No persistent metrics
        Phase 2: Could query CloudWatch for table metrics

        Returns:
            Empty dictionary
        """
        return {}

    def get_engine_info(self) -> dict[str, Any]:
        """Return DynamoDB version and account info.

        Returns:
            Dictionary with engine metadata
        """
        region = self._config.host or "us-east-1"
        return {
            "engine": "dynamodb",
            "region": region,
            "service": "AWS DynamoDB",
            "api_version": "2012-08-17",
        }
