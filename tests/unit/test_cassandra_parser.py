"""Unit tests for Cassandra parser."""

from unittest.mock import Mock

import pytest

from query_analyzer.adapters.nosql.cassandra_parser import CassandraExplainParser

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_trace_events() -> list:
    """Create mock trace events."""
    event1 = Mock()
    event1.source = "127.0.0.1"
    event1.activity = "Parsing SELECT statement"
    event1.source_elapsed = 100

    event2 = Mock()
    event2.source = "127.0.0.2"
    event2.activity = "Executing read"
    event2.source_elapsed = 200

    event3 = Mock()
    event3.source = "127.0.0.3"
    event3.activity = "Read remote"
    event3.source_elapsed = 150

    return [event1, event2, event3]


@pytest.fixture
def sample_schema() -> dict:
    """Sample table schema."""
    return {
        "partition_keys": ["user_id"],
        "clustering_keys": ["created_at"],
        "columns": [
            {"name": "user_id", "kind": "partition_key"},
            {"name": "created_at", "kind": "clustering"},
            {"name": "email", "kind": "regular"},
            {"name": "name", "kind": "regular"},
        ],
    }


# ============================================================================
# PARSE TESTS
# ============================================================================


class TestCassandraExplainParserParse:
    """Test trace event parsing."""

    def test_parse_basic_query(self, mock_trace_events: list, sample_schema: dict) -> None:
        """Test basic query parsing."""
        parsed = CassandraExplainParser.parse(
            trace_events=mock_trace_events,
            query="SELECT * FROM users WHERE user_id = 1",
            keyspace="test_ks",
            table_name="users",
            schema=sample_schema,
            allow_filtering=False,
        )

        assert parsed["query_type"] == "select"
        assert parsed["table"] == "users"
        assert parsed["keyspace"] == "test_ks"
        assert parsed["allow_filtering"] is False
        assert parsed["coordinator"] == "127.0.0.1"
        assert parsed["replicas_touched"] == 2
        assert len(parsed["stages"]) > 0

    def test_parse_with_allow_filtering(self, mock_trace_events: list, sample_schema: dict) -> None:
        """Test parsing with ALLOW FILTERING flag."""
        parsed = CassandraExplainParser.parse(
            trace_events=mock_trace_events,
            query="SELECT * FROM users WHERE email = 'test@example.com' ALLOW FILTERING",
            keyspace="test_ks",
            table_name="users",
            schema=sample_schema,
            allow_filtering=True,
        )

        assert parsed["allow_filtering"] is True

    def test_parse_empty_trace_events(self, sample_schema: dict) -> None:
        """Test parsing with no trace events."""
        parsed = CassandraExplainParser.parse(
            trace_events=[],
            query="SELECT * FROM users WHERE user_id = 1",
            keyspace="test_ks",
            table_name="users",
            schema=sample_schema,
            allow_filtering=False,
        )

        assert parsed["execution_time_ms"] == 0.0
        assert parsed["coordinator"] == ""
        assert parsed["replicas_touched"] == 0

    def test_parse_filter_without_key_detection(
        self, mock_trace_events: list, sample_schema: dict
    ) -> None:
        """Test detection of filtering without partition key."""
        # Query filters on email (not partition key)
        parsed = CassandraExplainParser.parse(
            trace_events=mock_trace_events,
            query="SELECT * FROM users WHERE email = 'test@example.com'",
            keyspace="test_ks",
            table_name="users",
            schema=sample_schema,
            allow_filtering=False,
        )

        assert parsed["has_filter_without_key"] is True

    def test_parse_filter_with_key_not_detected(
        self, mock_trace_events: list, sample_schema: dict
    ) -> None:
        """Test that filtering with partition key is not flagged."""
        parsed = CassandraExplainParser.parse(
            trace_events=mock_trace_events,
            query="SELECT * FROM users WHERE user_id = 1",
            keyspace="test_ks",
            table_name="users",
            schema=sample_schema,
            allow_filtering=False,
        )

        assert parsed["has_filter_without_key"] is False

    def test_parse_no_where_clause(self, mock_trace_events: list, sample_schema: dict) -> None:
        """Test query with no WHERE clause."""
        parsed = CassandraExplainParser.parse(
            trace_events=mock_trace_events,
            query="SELECT * FROM users",
            keyspace="test_ks",
            table_name="users",
            schema=sample_schema,
            allow_filtering=False,
        )

        assert parsed["has_filter_without_key"] is False  # No WHERE = not "filter without key"

    def test_parse_multiple_replicas(self, sample_schema: dict) -> None:
        """Test counting multiple replicas touched."""
        # Create events from multiple nodes
        events = []
        for i in range(5):
            event = Mock()
            event.source = f"127.0.0.{i + 1}"
            event.activity = f"Activity {i}"
            event.source_elapsed = 100 * (i + 1)
            events.append(event)

        parsed = CassandraExplainParser.parse(
            trace_events=events,
            query="SELECT * FROM users WHERE user_id = 1",
            keyspace="test_ks",
            table_name="users",
            schema=sample_schema,
            allow_filtering=False,
        )

        # First node is coordinator, others are replicas
        assert parsed["replicas_touched"] == 4


# ============================================================================
# PLAN TREE BUILDING TESTS
# ============================================================================


class TestBuildPlanTree:
    """Test plan tree construction."""

    def test_build_plan_tree_basic(self, mock_trace_events: list) -> None:
        """Test basic plan tree building."""
        tree = CassandraExplainParser.build_plan_tree(
            trace_events=mock_trace_events,
            table_name="users",
            keyspace="test_ks",
        )

        assert tree is not None
        assert tree.node_type == "Coordinator"
        assert tree.properties["table"] == "users"
        assert tree.properties["keyspace"] == "test_ks"
        assert len(tree.children) > 0

    def test_build_plan_tree_coordinator_and_replicas(self, mock_trace_events: list) -> None:
        """Test that coordinator is root and replicas are children."""
        tree = CassandraExplainParser.build_plan_tree(
            trace_events=mock_trace_events,
            table_name="users",
            keyspace="test_ks",
        )

        assert tree is not None
        # First source is coordinator
        assert tree.properties["coordinator"] == mock_trace_events[0].source
        # Other sources are children (replicas)
        assert len(tree.children) == len(set(e.source for e in mock_trace_events[1:]))

    def test_build_plan_tree_no_events(self) -> None:
        """Test plan tree building with no events."""
        tree = CassandraExplainParser.build_plan_tree(
            trace_events=[],
            table_name="users",
            keyspace="test_ks",
        )

        assert tree is None

    def test_build_plan_tree_single_node(self) -> None:
        """Test plan tree with single node (no replicas)."""
        event = Mock()
        event.source = "127.0.0.1"
        event.activity = "Read"
        event.source_elapsed = 100

        tree = CassandraExplainParser.build_plan_tree(
            trace_events=[event],
            table_name="users",
            keyspace="test_ks",
        )

        assert tree is not None
        assert tree.node_type == "Coordinator"
        # No children since there's only one node
        assert len(tree.children) == 0


# ============================================================================
# DETECT FILTER WITHOUT KEY TESTS
# ============================================================================


class TestDetectFilterWithoutKey:
    """Test detection of filters on non-partition-key columns."""

    def test_filter_on_partition_key(self) -> None:
        """Test that partition key filtering is not flagged."""
        result = CassandraExplainParser._detect_filter_without_key(
            query="SELECT * FROM users WHERE user_id = 1",
            partition_keys=["user_id"],
        )
        assert result is False

    def test_filter_on_non_partition_key(self) -> None:
        """Test that non-partition-key filtering is flagged."""
        result = CassandraExplainParser._detect_filter_without_key(
            query="SELECT * FROM users WHERE email = 'test@example.com'",
            partition_keys=["user_id"],
        )
        assert result is True

    def test_no_where_clause(self) -> None:
        """Test query with no WHERE clause."""
        result = CassandraExplainParser._detect_filter_without_key(
            query="SELECT * FROM users",
            partition_keys=["user_id"],
        )
        assert result is False

    def test_filter_on_multiple_columns(self) -> None:
        """Test filtering on multiple columns including partition key."""
        result = CassandraExplainParser._detect_filter_without_key(
            query="SELECT * FROM users WHERE user_id = 1 AND email = 'test@example.com'",
            partition_keys=["user_id"],
        )
        assert result is False  # Has partition key, so not flagged

    def test_case_insensitive_detection(self) -> None:
        """Test case-insensitive detection."""
        result = CassandraExplainParser._detect_filter_without_key(
            query="select * from users where USER_ID = 1",
            partition_keys=["user_id"],
        )
        assert result is False

    def test_clustering_key_without_partition_key(self) -> None:
        """Test clustering key filtering without partition key."""
        result = CassandraExplainParser._detect_filter_without_key(
            query="SELECT * FROM users WHERE created_at > '2024-01-01'",
            partition_keys=["user_id"],
        )
        # Clustering key without partition key should be flagged
        assert result is True

    def test_empty_partition_keys(self) -> None:
        """Test with empty partition keys list."""
        result = CassandraExplainParser._detect_filter_without_key(
            query="SELECT * FROM users WHERE email = 'test@example.com'",
            partition_keys=[],
        )
        assert result is False  # No partition keys to check
