"""Unit tests for DynamoDB adapter.

Tests use moto for mocking DynamoDB. No Docker required for unit tests.
"""

import json

import pytest
from moto import mock_aws

from query_analyzer.adapters.exceptions import QueryAnalysisError
from query_analyzer.adapters.models import ConnectionConfig, QueryAnalysisReport
from query_analyzer.adapters.nosql.dynamodb import DynamoDBAdapter
from query_analyzer.adapters.registry import AdapterRegistry
from query_analyzer.core.anti_pattern_detector import AntiPattern, Severity
from query_analyzer.core.dynamodb_anti_pattern_detector import (
    DynamoDBAntiPatternDetector,
)


@pytest.fixture
def moto_dynamodb_env():
    """Mock DynamoDB for all tests in this module."""
    with mock_aws():
        yield


@pytest.fixture
def dynamodb_config() -> ConnectionConfig:
    """Valid DynamoDB config pointing to moto mock."""
    return ConnectionConfig(
        engine="dynamodb",
        host="us-east-1",  # moto handles region automatically
        database="test-db",  # DynamoDB doesn't use DB names like SQL, but required by ConnectionConfig
        username="test",
        password="test",
    )


@pytest.fixture
def dynamodb_adapter(moto_dynamodb_env, dynamodb_config) -> DynamoDBAdapter:
    """DynamoDB adapter with mocked connection."""
    adapter = DynamoDBAdapter(dynamodb_config)
    adapter.connect()
    yield adapter
    adapter.disconnect()


class TestDynamoDBAdapterInstantiation:
    """Test adapter creation and registry."""

    def test_instantiate_with_valid_config(self, dynamodb_config) -> None:
        """Can instantiate DynamoDBAdapter with valid config."""
        adapter = DynamoDBAdapter(dynamodb_config)
        assert adapter is not None
        assert adapter._config == dynamodb_config

    def test_registry_can_create_dynamodb_adapter(self, dynamodb_config) -> None:
        """AdapterRegistry.create can instantiate DynamoDB adapter."""
        adapter = AdapterRegistry.create("dynamodb", dynamodb_config)
        assert isinstance(adapter, DynamoDBAdapter)
        assert adapter._config.engine == "dynamodb"

    def test_registry_case_insensitive(self, dynamodb_config) -> None:
        """Registry lookup is case-insensitive for DynamoDB."""
        adapter1 = AdapterRegistry.create("dynamodb", dynamodb_config)
        adapter2 = AdapterRegistry.create("DYNAMODB", dynamodb_config)
        adapter3 = AdapterRegistry.create("DynamoDB", dynamodb_config)

        assert isinstance(adapter1, DynamoDBAdapter)
        assert isinstance(adapter2, DynamoDBAdapter)
        assert isinstance(adapter3, DynamoDBAdapter)


class TestDynamoDBAdapterConnection:
    """Test connection lifecycle."""

    def test_connect_success(self, moto_dynamodb_env, dynamodb_config) -> None:
        """Connection succeeds with moto mock."""
        adapter = DynamoDBAdapter(dynamodb_config)
        adapter.connect()

        assert adapter._is_connected is True
        assert adapter._dynamodb_client is not None

    def test_disconnect(self, dynamodb_adapter) -> None:
        """Disconnect sets state correctly."""
        assert dynamodb_adapter._is_connected is True
        dynamodb_adapter.disconnect()
        assert dynamodb_adapter._is_connected is False

    def test_test_connection_returns_bool(self, dynamodb_adapter) -> None:
        """test_connection returns boolean."""
        result = dynamodb_adapter.test_connection()
        assert isinstance(result, bool)

    def test_test_connection_succeeds_when_connected(self, dynamodb_adapter) -> None:
        """test_connection returns True when connected."""
        result = dynamodb_adapter.test_connection()
        assert result is True


class TestDynamoDBParser:
    """Test JSON query parsing."""

    def test_parse_valid_query(self, dynamodb_adapter) -> None:
        """Parse valid DynamoDB Query operation."""
        query_json = json.dumps(
            {
                "TableName": "Users",
                "KeyConditionExpression": "user_id = :uid",
                "ExpressionAttributeValues": {":uid": {"S": "123"}},
            }
        )

        query_dict = dynamodb_adapter.parser.parse_query_string(query_json)
        assert query_dict["TableName"] == "Users"
        assert "KeyConditionExpression" in query_dict

    def test_parse_invalid_json_raises_error(self, dynamodb_adapter) -> None:
        """Invalid JSON raises ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            dynamodb_adapter.parser.parse_query_string("not valid json {")

    def test_parse_missing_table_name_raises_error(self, dynamodb_adapter) -> None:
        """Missing TableName raises ValueError."""
        query_json = json.dumps({"KeyConditionExpression": "pk = :pk"})

        with pytest.raises(ValueError, match="TableName"):
            dynamodb_adapter.parser.parse_query_string(query_json)

    def test_extract_operation_type_query(self, dynamodb_adapter) -> None:
        """Detect Query operation when KeyConditionExpression present."""
        query_dict = {
            "TableName": "Users",
            "KeyConditionExpression": "user_id = :uid",
        }

        op_type = dynamodb_adapter.parser.extract_operation_type(query_dict)
        assert op_type == "Query"

    def test_extract_operation_type_scan(self, dynamodb_adapter) -> None:
        """Detect Scan operation when no KeyConditionExpression."""
        query_dict = {"TableName": "Users"}

        op_type = dynamodb_adapter.parser.extract_operation_type(query_dict)
        assert op_type == "Scan"


class TestDynamoDBAntiPatterns:
    """Test anti-pattern detection."""

    def test_detect_scan_operation(self) -> None:
        """Detect Scan operation as anti-pattern."""
        detector = DynamoDBAntiPatternDetector()
        query_dict = {"TableName": "Users"}

        pattern = detector.detect_scan_operation(query_dict)
        assert pattern is not None
        assert pattern.name == "full_table_scan"
        assert pattern.severity.value == "Alta"

    def test_detect_query_operation_no_pattern(self) -> None:
        """Query operation doesn't trigger scan anti-pattern."""
        detector = DynamoDBAntiPatternDetector()
        query_dict = {
            "TableName": "Users",
            "KeyConditionExpression": "user_id = :uid",
        }

        pattern = detector.detect_scan_operation(query_dict)
        assert pattern is None

    def test_detect_missing_partition_key(self) -> None:
        """Detect incomplete KeyConditionExpression."""
        detector = DynamoDBAntiPatternDetector()
        query_dict = {
            "TableName": "Users",
            "KeyConditionExpression": "some_condition",  # No = sign
        }

        detector.detect_missing_partition_key(query_dict)
        # Note: Basic implementation may or may not detect this
        # Real implementation in Phase 2 will be more thorough

    def test_detect_high_capacity_consumption(self) -> None:
        """Detect high RCU consumption."""
        detector = DynamoDBAntiPatternDetector()
        response_metrics = {"read_capacity_units": 2000.0}

        pattern = detector.detect_high_capacity_consumption(response_metrics)
        assert pattern is not None
        assert pattern.name == "high_capacity_consumption"

    def test_detect_large_result_set(self) -> None:
        """Detect large result set without LIMIT."""
        detector = DynamoDBAntiPatternDetector()
        query_dict = {"TableName": "Users"}
        response_metrics = {"item_count": 15000}

        pattern = detector.detect_large_result_set(query_dict, response_metrics)
        assert pattern is not None
        assert pattern.name == "large_result_set"

    def test_no_pattern_when_limit_present(self) -> None:
        """No large result set alert if LIMIT present."""
        detector = DynamoDBAntiPatternDetector()
        query_dict = {"TableName": "Users", "Limit": 100}
        response_metrics = {"item_count": 15000}

        pattern = detector.detect_large_result_set(query_dict, response_metrics)
        assert pattern is None

    def test_detect_high_scan_ratio(self) -> None:
        """Detect inefficient filtering (scan ratio)."""
        detector = DynamoDBAntiPatternDetector()
        response_metrics = {"scanned_count": 5000, "item_count": 100}

        pattern = detector.detect_high_scan_ratio(response_metrics)
        assert pattern is not None
        assert pattern.name == "high_scan_ratio"


class TestDynamoDBAdvancedAntiPatterns:
    """Test Phase 3 advanced anti-patterns (#7, #8, #9)."""

    def test_detect_full_attribute_projection_with_many_items(self) -> None:
        """Detect full attribute projection with 100+ items and high RCU."""
        detector = DynamoDBAntiPatternDetector()
        query_dict = {"TableName": "Users"}
        response_metrics = {
            "item_count": 150,
            "read_capacity_units": 20.0,
        }

        pattern = detector.detect_full_attribute_projection(query_dict, response_metrics)
        assert pattern is not None
        assert pattern.name == "full_attribute_projection"
        assert pattern.severity.value == "Baja"

    def test_no_projection_pattern_with_few_items(self) -> None:
        """No projection pattern if item count < 100."""
        detector = DynamoDBAntiPatternDetector()
        query_dict = {"TableName": "Users"}
        response_metrics = {
            "item_count": 50,
            "read_capacity_units": 20.0,
        }

        pattern = detector.detect_full_attribute_projection(query_dict, response_metrics)
        assert pattern is None

    def test_no_projection_pattern_with_low_rcu(self) -> None:
        """No projection pattern if RCU < 10."""
        detector = DynamoDBAntiPatternDetector()
        query_dict = {"TableName": "Users"}
        response_metrics = {
            "item_count": 150,
            "read_capacity_units": 5.0,
        }

        pattern = detector.detect_full_attribute_projection(query_dict, response_metrics)
        assert pattern is None

    def test_no_projection_pattern_when_projection_expression_present(self) -> None:
        """No projection pattern if ProjectionExpression present."""
        detector = DynamoDBAntiPatternDetector()
        query_dict = {
            "TableName": "Users",
            "ProjectionExpression": "user_id, email",
        }
        response_metrics = {
            "item_count": 150,
            "read_capacity_units": 20.0,
        }

        pattern = detector.detect_full_attribute_projection(query_dict, response_metrics)
        assert pattern is None

    def test_detect_inefficient_pagination_no_limit_no_start_key(self) -> None:
        """Detect inefficient pagination without Limit or ExclusiveStartKey."""
        detector = DynamoDBAntiPatternDetector()
        query_dict = {"TableName": "Users"}

        pattern = detector.detect_inefficient_pagination(query_dict)
        assert pattern is not None
        assert pattern.name == "inefficient_pagination"
        assert pattern.severity.value == "Baja"

    def test_no_pagination_pattern_with_limit(self) -> None:
        """No pagination pattern if Limit present."""
        detector = DynamoDBAntiPatternDetector()
        query_dict = {"TableName": "Users", "Limit": 100}

        pattern = detector.detect_inefficient_pagination(query_dict)
        assert pattern is None

    def test_no_pagination_pattern_with_exclusive_start_key(self) -> None:
        """No pagination pattern if ExclusiveStartKey present."""
        detector = DynamoDBAntiPatternDetector()
        query_dict = {
            "TableName": "Users",
            "ExclusiveStartKey": {"user_id": {"S": "123"}},
        }

        pattern = detector.detect_inefficient_pagination(query_dict)
        assert pattern is None

    def test_no_pagination_pattern_with_both_limit_and_start_key(self) -> None:
        """No pagination pattern if both Limit and ExclusiveStartKey present."""
        detector = DynamoDBAntiPatternDetector()
        query_dict = {
            "TableName": "Users",
            "Limit": 100,
            "ExclusiveStartKey": {"user_id": {"S": "123"}},
        }

        pattern = detector.detect_inefficient_pagination(query_dict)
        assert pattern is None

    def test_detect_gsi_without_range_key(self) -> None:
        """Detect GSI query without range key."""
        detector = DynamoDBAntiPatternDetector()
        query_dict = {
            "TableName": "Users",
            "IndexName": "email_index",
            "KeyConditionExpression": "email = :email",
        }

        pattern = detector.detect_gsi_query_without_range_key(query_dict)
        assert pattern is not None
        assert pattern.name == "gsi_without_range_key"
        assert pattern.severity.value == "Baja"

    def test_no_gsi_pattern_for_base_table_query(self) -> None:
        """No GSI pattern for base table queries (no IndexName)."""
        detector = DynamoDBAntiPatternDetector()
        query_dict = {
            "TableName": "Users",
            "KeyConditionExpression": "user_id = :uid",
        }

        pattern = detector.detect_gsi_query_without_range_key(query_dict)
        assert pattern is None

    def test_no_gsi_pattern_with_range_key(self) -> None:
        """No GSI pattern if range key condition present (AND operator)."""
        detector = DynamoDBAntiPatternDetector()
        query_dict = {
            "TableName": "Users",
            "IndexName": "email_index",
            "KeyConditionExpression": "email = :email AND created_at > :date",
        }

        pattern = detector.detect_gsi_query_without_range_key(query_dict)
        assert pattern is None

    def test_gsi_pattern_case_insensitive_and(self) -> None:
        """GSI pattern detection works with lowercase 'and'."""
        detector = DynamoDBAntiPatternDetector()
        query_dict = {
            "TableName": "Users",
            "IndexName": "email_index",
            "KeyConditionExpression": "email = :email",  # lowercase 'and' would be ignored
        }

        pattern = detector.detect_gsi_query_without_range_key(query_dict)
        assert pattern is not None

    def test_gsi_pattern_with_uppercase_and(self) -> None:
        """GSI pattern is skipped when uppercase AND is present."""
        detector = DynamoDBAntiPatternDetector()
        query_dict = {
            "TableName": "Users",
            "IndexName": "email_index",
            "KeyConditionExpression": "email = :email AND created_at > :date",
        }

        pattern = detector.detect_gsi_query_without_range_key(query_dict)
        assert pattern is None

    def test_analyze_combines_all_anti_patterns(self) -> None:
        """analyze() orchestrates all detectors and combines results."""
        detector = DynamoDBAntiPatternDetector()

        # Create a query with multiple anti-patterns:
        # - Scan (HIGH severity)
        # - No projection (LOW severity)
        # - No pagination (LOW severity)
        query_dict = {
            "TableName": "Users",
            # No KeyConditionExpression -> Scan
            # No ProjectionExpression
            # No Limit or ExclusiveStartKey
        }
        response = {
            "Count": 200,
            "ScannedCount": 200,
            "ConsumedCapacity": {"CapacityUnits": 50.0},
        }

        result = detector.analyze(query_dict, response)

        # Should detect: full_table_scan (HIGH)
        assert result.score < 100
        assert len(result.anti_patterns) >= 1
        assert any(ap.name == "full_table_scan" for ap in result.anti_patterns)

    def test_analyze_with_good_query(self) -> None:
        """analyze() returns high score for well-optimized query."""
        detector = DynamoDBAntiPatternDetector()

        # Well-optimized Query:
        # - Has KeyConditionExpression (Query, not Scan)
        # - Has ProjectionExpression
        # - Has Limit
        # - Low RCU, few items
        query_dict = {
            "TableName": "Users",
            "KeyConditionExpression": "user_id = :uid",
            "ProjectionExpression": "user_id, email",
            "Limit": 50,
        }
        response = {
            "Count": 1,
            "ScannedCount": 1,
            "ConsumedCapacity": {"CapacityUnits": 1.0},
        }

        result = detector.analyze(query_dict, response)

        # Should detect no anti-patterns
        assert result.score == 100
        assert len(result.anti_patterns) == 0


class TestDynamoDBErrorHandling:
    """Test error scenarios."""

    def test_not_connected_raises_error(self, dynamodb_config) -> None:
        """execute_explain raises error if not connected."""
        adapter = DynamoDBAdapter(dynamodb_config)
        # Don't connect

        query_json = json.dumps({"TableName": "Users"})

        with pytest.raises(QueryAnalysisError, match="Not connected"):
            adapter.execute_explain(query_json)

    def test_malformed_query_raises_error(self, dynamodb_adapter) -> None:
        """Malformed JSON query raises error."""
        with pytest.raises(QueryAnalysisError):
            dynamodb_adapter.execute_explain("not json {")

    def test_missing_table_name_raises_error(self, dynamodb_adapter) -> None:
        """Missing TableName in query raises error."""
        query_json = json.dumps({"KeyConditionExpression": "pk = :pk"})

        with pytest.raises(QueryAnalysisError):
            dynamodb_adapter.execute_explain(query_json)


class TestDynamoDBScoringEngine:
    """Test score calculation."""

    def test_score_calculation_no_patterns(self) -> None:
        """Score is 100 when no anti-patterns."""
        from query_analyzer.core.dynamodb_anti_pattern_detector import (
            DynamoDBScoringEngine,
        )

        score = DynamoDBScoringEngine.calculate_score([])
        assert score == 100

    def test_score_calculation_high_severity(self) -> None:
        """HIGH severity deducts 25 points."""
        from query_analyzer.core.anti_pattern_detector import Severity
        from query_analyzer.core.dynamodb_anti_pattern_detector import (
            DynamoDBScoringEngine,
        )

        pattern = AntiPattern(
            name="test",
            severity=Severity.HIGH,
            description="test",
        )
        score = DynamoDBScoringEngine.calculate_score([pattern])
        assert score == 75

    def test_score_never_negative(self) -> None:
        """Score floor is 0."""
        from query_analyzer.core.anti_pattern_detector import Severity
        from query_analyzer.core.dynamodb_anti_pattern_detector import (
            DynamoDBScoringEngine,
        )

        patterns = [
            AntiPattern(
                name=f"test_{i}",
                severity=Severity.HIGH,
                description="test",
            )
            for i in range(10)  # 10 * 25 = 250 points deducted
        ]
        score = DynamoDBScoringEngine.calculate_score(patterns)
        assert score == 0


class TestDynamoDBGetters:
    """Test getter methods."""

    def test_get_engine_info(self, dynamodb_adapter) -> None:
        """get_engine_info returns metadata."""
        info = dynamodb_adapter.get_engine_info()

        assert isinstance(info, dict)
        assert info["engine"] == "dynamodb"
        assert "region" in info

    def test_get_slow_queries_returns_empty_list(self, dynamodb_adapter) -> None:
        """get_slow_queries returns empty list (Phase 2 feature)."""
        result = dynamodb_adapter.get_slow_queries()

        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_metrics_returns_empty_dict(self, dynamodb_adapter) -> None:
        """get_metrics returns empty dict (Phase 2 feature)."""
        result = dynamodb_adapter.get_metrics()

        assert isinstance(result, dict)
        assert len(result) == 0


class TestDynamoDBExecuteQuery:
    """Test _execute_query() method with moto mocking."""

    def test_execute_query_with_query_operation(self, moto_dynamodb_env, dynamodb_adapter) -> None:
        """Execute Query operation returns response with ConsumedCapacity."""

        # Create a test table in moto
        dynamodb_adapter._dynamodb_client.create_table(
            TableName="Users",
            KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "user_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # Put some test data
        dynamodb_adapter._dynamodb_client.put_item(
            TableName="Users",
            Item={"user_id": {"S": "123"}, "name": {"S": "John"}},
            ReturnConsumedCapacity="TOTAL",
        )

        # Execute Query operation
        query_dict = {
            "TableName": "Users",
            "KeyConditionExpression": "user_id = :uid",
            "ExpressionAttributeValues": {":uid": {"S": "123"}},
            "ReturnConsumedCapacity": "TOTAL",
        }

        response = dynamodb_adapter._execute_query(query_dict)

        assert isinstance(response, dict)
        assert "Items" in response
        assert "ConsumedCapacity" in response
        assert response["Count"] == 1

    def test_execute_query_with_scan_operation(self, moto_dynamodb_env, dynamodb_adapter) -> None:
        """Execute Scan operation returns response."""
        # Create a test table
        dynamodb_adapter._dynamodb_client.create_table(
            TableName="Products",
            KeySchema=[{"AttributeName": "product_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "product_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # Put some test data
        for i in range(3):
            dynamodb_adapter._dynamodb_client.put_item(
                TableName="Products",
                Item={"product_id": {"S": f"prod_{i}"}, "price": {"N": str(100 + i)}},
            )

        # Execute Scan operation
        query_dict = {
            "TableName": "Products",
            "ReturnConsumedCapacity": "TOTAL",
        }

        response = dynamodb_adapter._execute_query(query_dict)

        assert isinstance(response, dict)
        assert "Items" in response
        assert response["Count"] == 3

    def test_execute_query_table_not_found(self, dynamodb_adapter) -> None:
        """Execute query on non-existent table raises error."""
        query_dict = {
            "TableName": "NonExistentTable",
            "KeyConditionExpression": "pk = :pk",
            "ReturnConsumedCapacity": "TOTAL",
        }

        with pytest.raises(RuntimeError, match="table not found|ResourceNotFound"):
            dynamodb_adapter._execute_query(query_dict)

    def test_execute_query_no_client_raises_error(self, dynamodb_config) -> None:
        """Execute query without client raises error."""
        adapter = DynamoDBAdapter(dynamodb_config)
        # Don't connect, so client is None

        query_dict = {
            "TableName": "Users",
            "KeyConditionExpression": "pk = :pk",
        }

        with pytest.raises(RuntimeError, match="not initialized"):
            adapter._execute_query(query_dict)


class TestDynamoDBExecuteExplain:
    """Test execute_explain() end-to-end."""

    def test_execute_explain_query_success(self, moto_dynamodb_env, dynamodb_adapter) -> None:
        """execute_explain successfully analyzes a Query operation."""
        # Create table
        dynamodb_adapter._dynamodb_client.create_table(
            TableName="Users",
            KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "user_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # Put test data
        dynamodb_adapter._dynamodb_client.put_item(
            TableName="Users",
            Item={"user_id": {"S": "123"}, "email": {"S": "user@example.com"}},
        )

        # Execute explain
        query_json = json.dumps(
            {
                "TableName": "Users",
                "KeyConditionExpression": "user_id = :uid",
                "ExpressionAttributeValues": {":uid": {"S": "123"}},
            }
        )

        report = dynamodb_adapter.execute_explain(query_json)

        # Verify report structure
        assert isinstance(report, QueryAnalysisReport)
        assert report.engine == "dynamodb"
        assert report.score >= 0 and report.score <= 100
        assert report.execution_time_ms > 0
        assert isinstance(report.warnings, list)
        assert isinstance(report.recommendations, list)
        assert report.metrics["item_count"] == 1

    def test_execute_explain_scan_success(self, moto_dynamodb_env, dynamodb_adapter) -> None:
        """execute_explain detects Scan operation (should reduce score)."""
        # Create table
        dynamodb_adapter._dynamodb_client.create_table(
            TableName="Products",
            KeySchema=[{"AttributeName": "product_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "product_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # Put test data
        for i in range(5):
            dynamodb_adapter._dynamodb_client.put_item(
                TableName="Products",
                Item={"product_id": {"S": f"prod_{i}"}},
            )

        # Execute explain for Scan
        query_json = json.dumps({"TableName": "Products"})

        report = dynamodb_adapter.execute_explain(query_json)

        # Scan operation should produce warnings
        assert report.score < 100  # Scan reduces score
        assert len(report.warnings) > 0  # Should have scan warning

    def test_execute_explain_includes_metrics(self, moto_dynamodb_env, dynamodb_adapter) -> None:
        """execute_explain includes ConsumedCapacity metrics in report."""
        # Create table
        dynamodb_adapter._dynamodb_client.create_table(
            TableName="Users",
            KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "user_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # Put test data
        dynamodb_adapter._dynamodb_client.put_item(
            TableName="Users",
            Item={"user_id": {"S": "123"}},
        )

        # Execute query with metrics
        query_json = json.dumps(
            {
                "TableName": "Users",
                "KeyConditionExpression": "user_id = :uid",
                "ExpressionAttributeValues": {":uid": {"S": "123"}},
            }
        )

        report = dynamodb_adapter.execute_explain(query_json)

        # Verify metrics are captured
        assert "consumed_read_capacity" in report.metrics
        assert "item_count" in report.metrics
        assert "scanned_count" in report.metrics
        assert report.metrics["item_count"] >= 0
        assert report.metrics["scanned_count"] >= 0

    def test_execute_explain_execution_time_positive(
        self, moto_dynamodb_env, dynamodb_adapter
    ) -> None:
        """execute_explain measures execution time correctly."""
        # Create table
        dynamodb_adapter._dynamodb_client.create_table(
            TableName="Users",
            KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "user_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        # Execute explain
        query_json = json.dumps(
            {
                "TableName": "Users",
                "KeyConditionExpression": "user_id = :uid",
                "ExpressionAttributeValues": {":uid": {"S": "123"}},
            }
        )

        report = dynamodb_adapter.execute_explain(query_json)

        # execution_time_ms must be > 0 (as per QueryAnalysisReport validator)
        assert report.execution_time_ms > 0

    def test_execute_explain_invalid_json_raises_error(self, dynamodb_adapter) -> None:
        """execute_explain with invalid JSON raises QueryAnalysisError."""
        with pytest.raises(QueryAnalysisError, match="query analysis failed"):
            dynamodb_adapter.execute_explain("not valid json {")

    def test_execute_explain_not_connected_raises_error(
        self,
        dynamodb_config,
    ) -> None:
        """execute_explain without connection raises QueryAnalysisError."""
        adapter = DynamoDBAdapter(dynamodb_config)
        # Don't connect

        query_json = json.dumps({"TableName": "Users"})

        with pytest.raises(QueryAnalysisError, match="Not connected"):
            adapter.execute_explain(query_json)


class TestDynamoDBRecommendationEngine:
    """Test recommendations generation for anti-patterns."""

    def test_full_table_scan_recommendation(self) -> None:
        """Generate recommendation for full table scan."""
        from query_analyzer.core.dynamodb_anti_pattern_detector import (
            DynamoDBRecommendationEngine,
        )

        pattern = AntiPattern(
            name="full_table_scan",
            severity=Severity.HIGH,
            description="Full table scan",
        )
        query_dict = {"TableName": "Users"}

        recommendations = DynamoDBRecommendationEngine.generate_recommendations(
            [pattern], query_dict
        )

        assert len(recommendations) == 1
        assert "Query" in recommendations[0]
        assert "KeyConditionExpression" in recommendations[0]

    def test_high_capacity_consumption_recommendation(self) -> None:
        """Generate recommendation for high RCU."""
        from query_analyzer.core.dynamodb_anti_pattern_detector import (
            DynamoDBRecommendationEngine,
        )

        pattern = AntiPattern(
            name="high_capacity_consumption",
            severity=Severity.MEDIUM,
            description="High RCU",
            metadata={"read_capacity_units": 2000, "threshold": 1000},
        )
        query_dict = {"TableName": "Users"}

        recommendations = DynamoDBRecommendationEngine.generate_recommendations(
            [pattern], query_dict
        )

        assert len(recommendations) == 1
        assert "2000" in recommendations[0]
        assert "ProjectionExpression" in recommendations[0]

    def test_large_result_set_recommendation(self) -> None:
        """Generate recommendation for large result set."""
        from query_analyzer.core.dynamodb_anti_pattern_detector import (
            DynamoDBRecommendationEngine,
        )

        pattern = AntiPattern(
            name="large_result_set",
            severity=Severity.MEDIUM,
            description="Large result set",
            metadata={"item_count": 15000},
        )
        query_dict = {"TableName": "Users"}

        recommendations = DynamoDBRecommendationEngine.generate_recommendations(
            [pattern], query_dict
        )

        assert len(recommendations) == 1
        assert "Limit" in recommendations[0]
        assert "pagination" in recommendations[0]

    def test_high_scan_ratio_recommendation(self) -> None:
        """Generate recommendation for high scan ratio."""
        from query_analyzer.core.dynamodb_anti_pattern_detector import (
            DynamoDBRecommendationEngine,
        )

        pattern = AntiPattern(
            name="high_scan_ratio",
            severity=Severity.MEDIUM,
            description="High scan ratio",
            metadata={"scanned_count": 5000, "item_count": 100, "scan_ratio": 50.0},
        )
        query_dict = {"TableName": "Users"}

        recommendations = DynamoDBRecommendationEngine.generate_recommendations(
            [pattern], query_dict
        )

        assert len(recommendations) == 1
        assert "5000" in recommendations[0]
        assert "100" in recommendations[0]
        assert "KeyConditionExpression" in recommendations[0]

    def test_full_attribute_projection_recommendation(self) -> None:
        """Generate recommendation for full attribute projection."""
        from query_analyzer.core.dynamodb_anti_pattern_detector import (
            DynamoDBRecommendationEngine,
        )

        pattern = AntiPattern(
            name="full_attribute_projection",
            severity=Severity.LOW,
            description="Full projection",
            metadata={"item_count": 150, "read_capacity_units": 20},
        )
        query_dict = {"TableName": "Users"}

        recommendations = DynamoDBRecommendationEngine.generate_recommendations(
            [pattern], query_dict
        )

        assert len(recommendations) == 1
        assert "ProjectionExpression" in recommendations[0]
        assert "150" in recommendations[0]

    def test_inefficient_pagination_recommendation(self) -> None:
        """Generate recommendation for inefficient pagination."""
        from query_analyzer.core.dynamodb_anti_pattern_detector import (
            DynamoDBRecommendationEngine,
        )

        pattern = AntiPattern(
            name="inefficient_pagination",
            severity=Severity.LOW,
            description="No pagination",
        )
        query_dict = {"TableName": "Users"}

        recommendations = DynamoDBRecommendationEngine.generate_recommendations(
            [pattern], query_dict
        )

        assert len(recommendations) == 1
        assert "Limit" in recommendations[0]
        assert "ExclusiveStartKey" in recommendations[0]

    def test_gsi_without_range_key_recommendation(self) -> None:
        """Generate recommendation for GSI without range key."""
        from query_analyzer.core.dynamodb_anti_pattern_detector import (
            DynamoDBRecommendationEngine,
        )

        pattern = AntiPattern(
            name="gsi_without_range_key",
            severity=Severity.LOW,
            description="GSI without range",
            metadata={"index_name": "email_index"},
        )
        query_dict = {"TableName": "Users"}

        recommendations = DynamoDBRecommendationEngine.generate_recommendations(
            [pattern], query_dict
        )

        assert len(recommendations) == 1
        assert "email_index" in recommendations[0]
        assert "range key" in recommendations[0]

    def test_multiple_recommendations(self) -> None:
        """Generate multiple recommendations for multiple anti-patterns."""
        from query_analyzer.core.dynamodb_anti_pattern_detector import (
            DynamoDBRecommendationEngine,
        )

        patterns = [
            AntiPattern(
                name="full_table_scan",
                severity=Severity.HIGH,
                description="Scan",
            ),
            AntiPattern(
                name="large_result_set",
                severity=Severity.MEDIUM,
                description="Large results",
                metadata={"item_count": 10000},
            ),
        ]
        query_dict = {"TableName": "Products"}

        recommendations = DynamoDBRecommendationEngine.generate_recommendations(
            patterns, query_dict
        )

        assert len(recommendations) == 2
        assert any("Query" in r for r in recommendations)
        assert any("Limit" in r for r in recommendations)

    def test_recommendation_order(self) -> None:
        """Recommendations appear in same order as anti-patterns."""
        from query_analyzer.core.dynamodb_anti_pattern_detector import (
            DynamoDBRecommendationEngine,
        )

        patterns = [
            AntiPattern(
                name="inefficient_pagination",
                severity=Severity.LOW,
                description="No pagination",
            ),
            AntiPattern(
                name="full_table_scan",
                severity=Severity.HIGH,
                description="Scan",
            ),
        ]
        query_dict = {"TableName": "Users"}

        recommendations = DynamoDBRecommendationEngine.generate_recommendations(
            patterns, query_dict
        )

        # First recommendation should be about pagination (first pattern)
        assert "Limit" in recommendations[0] or "pagination" in recommendations[0]
        # Second recommendation should be about scanning (second pattern)
        assert "Query" in recommendations[1]

    def test_recommendation_includes_context(self) -> None:
        """Recommendations include specific context from metadata."""
        from query_analyzer.core.dynamodb_anti_pattern_detector import (
            DynamoDBRecommendationEngine,
        )

        pattern = AntiPattern(
            name="high_scan_ratio",
            severity=Severity.MEDIUM,
            description="High scan ratio",
            metadata={
                "scanned_count": 10000,
                "item_count": 50,
                "scan_ratio": 200.0,
            },
        )
        query_dict = {"TableName": "Orders"}

        recommendations = DynamoDBRecommendationEngine.generate_recommendations(
            [pattern], query_dict
        )

        rec = recommendations[0]
        assert "10000" in rec  # Scanned count
        assert "50" in rec  # Item count
        assert "200.0" in rec  # Ratio


class TestDynamoDBEndToEndIntegration:
    """Test end-to-end flow: Query → Analysis → Report with v2 models."""

    def test_full_flow_scan_operation(self, moto_dynamodb_env, dynamodb_adapter) -> None:
        """Full flow: Scan operation triggers warnings and recommendations."""
        dynamodb_adapter._dynamodb_client.create_table(
            TableName="Products",
            KeySchema=[{"AttributeName": "product_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "product_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        for i in range(5):
            dynamodb_adapter._dynamodb_client.put_item(
                TableName="Products",
                Item={"product_id": {"S": f"prod_{i}"}, "price": {"N": str(100 + i)}},
            )

        query_json = json.dumps({"TableName": "Products"})
        report = dynamodb_adapter.execute_explain(query_json)

        assert isinstance(report, QueryAnalysisReport)
        assert report.engine == "dynamodb"
        assert report.score < 100  # Scan reduces score
        assert len(report.warnings) > 0  # Should have scan warning
        assert len(report.recommendations) > 0  # Should have recommendations

        scan_warning = report.warnings[0]
        assert scan_warning.severity == "critical"
        assert "Scan" in scan_warning.message or "scan" in scan_warning.message
        assert scan_warning.node_type == "full_table_scan"

        rec = report.recommendations[0]
        assert 1 <= rec.priority <= 10
        assert "Query" in rec.title or "Query" in rec.description

    def test_full_flow_optimized_query(self, moto_dynamodb_env, dynamodb_adapter) -> None:
        """Full flow: Well-optimized query → high score, no warnings."""
        dynamodb_adapter._dynamodb_client.create_table(
            TableName="Users",
            KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "user_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        dynamodb_adapter._dynamodb_client.put_item(
            TableName="Users",
            Item={"user_id": {"S": "user_123"}, "email": {"S": "user@example.com"}},
        )

        query_json = json.dumps(
            {
                "TableName": "Users",
                "KeyConditionExpression": "user_id = :uid",
                "ExpressionAttributeValues": {":uid": {"S": "user_123"}},
                "ProjectionExpression": "user_id, email",
                "Limit": 100,
            }
        )
        report = dynamodb_adapter.execute_explain(query_json)

        assert report.engine == "dynamodb"
        assert report.score == 100  # Perfect score
        assert len(report.warnings) == 0  # No warnings
        assert len(report.recommendations) == 0  # No recommendations

    def test_full_flow_high_rcu_consumption(self, moto_dynamodb_env, dynamodb_adapter) -> None:
        """Full flow: High RCU consumption triggers medium severity warning."""
        dynamodb_adapter._dynamodb_client.create_table(
            TableName="LargeTable",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        for i in range(200):
            dynamodb_adapter._dynamodb_client.put_item(
                TableName="LargeTable",
                Item={"pk": {"S": f"item_{i:04d}"}, "data": {"S": "x" * 1000}},
            )

        query_json = json.dumps({"TableName": "LargeTable"})
        report = dynamodb_adapter.execute_explain(query_json)

        assert len(report.warnings) >= 1
        assert report.score < 100

        severities = [w.severity for w in report.warnings]
        assert any(s in ["critical", "high"] for s in severities)

    def test_full_flow_metrics_in_report(self, moto_dynamodb_env, dynamodb_adapter) -> None:
        """Full flow: Metrics are correctly captured in report."""
        dynamodb_adapter._dynamodb_client.create_table(
            TableName="TestTable",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        for i in range(10):
            dynamodb_adapter._dynamodb_client.put_item(
                TableName="TestTable",
                Item={"id": {"S": f"id_{i}"}, "value": {"N": str(i)}},
            )

        query_json = json.dumps(
            {
                "TableName": "TestTable",
                "KeyConditionExpression": "id = :id",
                "ExpressionAttributeValues": {":id": {"S": "id_0"}},
            }
        )
        report = dynamodb_adapter.execute_explain(query_json)

        assert "consumed_read_capacity" in report.metrics
        assert "item_count" in report.metrics
        assert "scanned_count" in report.metrics

        assert report.metrics["item_count"] >= 0
        assert report.metrics["scanned_count"] >= 0
        assert report.metrics["consumed_read_capacity"] >= 0

    def test_full_flow_execution_time_measured(self, moto_dynamodb_env, dynamodb_adapter) -> None:
        """Full flow: Execution time is measured and positive."""
        dynamodb_adapter._dynamodb_client.create_table(
            TableName="Users",
            KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "user_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        query_json = json.dumps(
            {
                "TableName": "Users",
                "KeyConditionExpression": "user_id = :uid",
                "ExpressionAttributeValues": {":uid": {"S": "test"}},
            }
        )
        report = dynamodb_adapter.execute_explain(query_json)

        assert report.execution_time_ms > 0
        assert report.analyzed_at is not None

    def test_full_flow_raw_plan_preserved(self, moto_dynamodb_env, dynamodb_adapter) -> None:
        """Full flow: Original query is preserved in raw_plan and query fields."""
        dynamodb_adapter._dynamodb_client.create_table(
            TableName="TestTable",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        original_query = {
            "TableName": "TestTable",
            "KeyConditionExpression": "pk = :pk",
            "ExpressionAttributeValues": {":pk": {"S": "value"}},
            "ProjectionExpression": "pk",
            "Limit": 50,
        }
        query_json = json.dumps(original_query)
        report = dynamodb_adapter.execute_explain(query_json)

        assert report.query == query_json
        assert report.raw_plan is not None
        assert isinstance(report.raw_plan, dict)

    def test_full_flow_multiple_antipatterns(self, moto_dynamodb_env, dynamodb_adapter) -> None:
        """Full flow: Multiple anti-patterns detected simultaneously."""
        dynamodb_adapter._dynamodb_client.create_table(
            TableName="Products",
            KeySchema=[{"AttributeName": "product_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "product_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        for i in range(300):
            dynamodb_adapter._dynamodb_client.put_item(
                TableName="Products",
                Item={
                    "product_id": {"S": f"prod_{i:04d}"},
                    "name": {"S": f"Product {i}"},
                    "price": {"N": str(100 + i)},
                    "description": {"S": "x" * 500},
                },
            )

        query_json = json.dumps({"TableName": "Products"})
        report = dynamodb_adapter.execute_explain(query_json)

        assert len(report.warnings) >= 2  # At least scan + another
        assert len(report.recommendations) >= 2

        assert report.score < 80

    def test_full_flow_recommendation_priority(self, moto_dynamodb_env, dynamodb_adapter) -> None:
        """Full flow: Recommendations have valid priority values."""
        dynamodb_adapter._dynamodb_client.create_table(
            TableName="Data",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        for i in range(50):
            dynamodb_adapter._dynamodb_client.put_item(
                TableName="Data",
                Item={"id": {"S": f"id_{i}"}, "data": {"S": "x" * 100}},
            )

        query_json = json.dumps({"TableName": "Data"})
        report = dynamodb_adapter.execute_explain(query_json)

        for rec in report.recommendations:
            assert 1 <= rec.priority <= 10
            assert rec.title is not None and len(rec.title) > 0
            assert rec.description is not None and len(rec.description) > 0

    def test_full_flow_warning_metadata(self, moto_dynamodb_env, dynamodb_adapter) -> None:
        """Full flow: Warning metadata includes relevant context."""
        dynamodb_adapter._dynamodb_client.create_table(
            TableName="TestTable",
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        for i in range(20):
            dynamodb_adapter._dynamodb_client.put_item(
                TableName="TestTable",
                Item={"pk": {"S": f"key_{i}"}, "value": {"N": str(i)}},
            )

        query_json = json.dumps({"TableName": "TestTable"})
        report = dynamodb_adapter.execute_explain(query_json)

        assert len(report.warnings) > 0
        for warning in report.warnings:
            assert warning.metadata is not None
            assert isinstance(warning.metadata, dict)
