"""Unit tests for Cassandra anti-pattern detector."""

import pytest

from query_analyzer.core.cassandra_anti_pattern_detector import (
    CassandraAntiPatternDetector,
)

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def detector() -> CassandraAntiPatternDetector:
    """Create detector instance."""
    return CassandraAntiPatternDetector()


@pytest.fixture
def sample_parsed_query() -> dict:
    """Sample parsed query from parser."""
    return {
        "query_type": "select",
        "table": "users",
        "keyspace": "test_ks",
        "execution_time_ms": 50.0,
        "partition_keys": ["user_id"],
        "clustering_keys": ["created_at"],
        "allow_filtering": False,
        "coordinator": "127.0.0.1",
        "replicas_touched": 1,
        "stages": [],
        "has_filter_without_key": False,
    }


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
        ],
    }


# ============================================================================
# ALLOW FILTERING TESTS
# ============================================================================


class TestAllowFilteringDetection:
    """Test ALLOW FILTERING detection."""

    def test_allow_filtering_detected(
        self,
        detector: CassandraAntiPatternDetector,
        sample_parsed_query: dict,
        sample_schema: dict,
    ) -> None:
        """Test that ALLOW FILTERING is detected as critical anti-pattern."""
        sample_parsed_query["allow_filtering"] = True

        result = detector.analyze(
            parsed_query=sample_parsed_query,
            query="SELECT * FROM users WHERE email = 'test' ALLOW FILTERING",
            table_schema=sample_schema,
        )

        assert result.score < 100
        assert any(ap.name == "ALLOW FILTERING" for ap in result.anti_patterns)
        ap = next(ap for ap in result.anti_patterns if ap.name == "ALLOW FILTERING")
        assert ap.severity == "critical"

    def test_allow_filtering_recommendation(
        self,
        detector: CassandraAntiPatternDetector,
        sample_parsed_query: dict,
        sample_schema: dict,
    ) -> None:
        """Test that ALLOW FILTERING generates appropriate recommendation."""
        sample_parsed_query["allow_filtering"] = True

        result = detector.analyze(
            parsed_query=sample_parsed_query,
            query="SELECT * FROM users WHERE email = 'test' ALLOW FILTERING",
            table_schema=sample_schema,
        )

        assert len(result.recommendations) > 0
        assert any("ALLOW FILTERING" in rec for rec in result.recommendations)


# ============================================================================
# FULL CLUSTER SCAN TESTS
# ============================================================================


class TestFullClusterScanDetection:
    """Test full cluster scan detection."""

    def test_full_cluster_scan_detected(
        self,
        detector: CassandraAntiPatternDetector,
        sample_parsed_query: dict,
        sample_schema: dict,
    ) -> None:
        """Test that queries without partition key are detected."""
        sample_parsed_query["has_filter_without_key"] = True

        result = detector.analyze(
            parsed_query=sample_parsed_query,
            query="SELECT * FROM users WHERE email = 'test'",
            table_schema=sample_schema,
        )

        assert result.score < 100
        assert any(ap.name == "Full Cluster Scan" for ap in result.anti_patterns)
        ap = next(ap for ap in result.anti_patterns if ap.name == "Full Cluster Scan")
        assert ap.severity == "critical"

    def test_full_cluster_scan_penalty(
        self,
        detector: CassandraAntiPatternDetector,
        sample_parsed_query: dict,
        sample_schema: dict,
    ) -> None:
        """Test score penalty for full cluster scan."""
        sample_parsed_query["has_filter_without_key"] = True

        result = detector.analyze(
            parsed_query=sample_parsed_query,
            query="SELECT * FROM users WHERE email = 'test' LIMIT 100",
            table_schema=sample_schema,
        )

        # Should lose critical penalty points
        assert result.score == 100 - detector.PENALTY_CRITICAL


# ============================================================================
# WIDE QUERY TESTS
# ============================================================================


class TestWideDistributedQuery:
    """Test detection of queries touching many replicas."""

    def test_wide_query_detected(
        self,
        detector: CassandraAntiPatternDetector,
        sample_parsed_query: dict,
        sample_schema: dict,
    ) -> None:
        """Test that queries touching many replicas are flagged."""
        sample_parsed_query["replicas_touched"] = 10

        result = detector.analyze(
            parsed_query=sample_parsed_query,
            query="SELECT * FROM users WHERE user_id = 1",
            table_schema=sample_schema,
        )

        assert any(ap.name == "Wide Distributed Query" for ap in result.anti_patterns)

    def test_wide_query_threshold(
        self,
        detector: CassandraAntiPatternDetector,
        sample_parsed_query: dict,
        sample_schema: dict,
    ) -> None:
        """Test that queries with <= 5 replicas are not flagged."""
        sample_parsed_query["replicas_touched"] = 5

        result = detector.analyze(
            parsed_query=sample_parsed_query,
            query="SELECT * FROM users WHERE user_id = 1",
            table_schema=sample_schema,
        )

        assert not any(ap.name == "Wide Distributed Query" for ap in result.anti_patterns)


# ============================================================================
# UNFILTERED QUERY TESTS
# ============================================================================


class TestUnfilteredQuery:
    """Test detection of queries without WHERE clause."""

    def test_unfiltered_query_detected(
        self,
        detector: CassandraAntiPatternDetector,
        sample_parsed_query: dict,
        sample_schema: dict,
    ) -> None:
        """Test that unfiltered queries are detected."""
        result = detector.analyze(
            parsed_query=sample_parsed_query,
            query="SELECT * FROM users",
            table_schema=sample_schema,
        )

        assert any(ap.name == "Unfiltered Query" for ap in result.anti_patterns)

    def test_filtered_query_not_flagged(
        self,
        detector: CassandraAntiPatternDetector,
        sample_parsed_query: dict,
        sample_schema: dict,
    ) -> None:
        """Test that queries with WHERE are not flagged as unfiltered."""
        result = detector.analyze(
            parsed_query=sample_parsed_query,
            query="SELECT * FROM users WHERE user_id = 1",
            table_schema=sample_schema,
        )

        assert not any(ap.name == "Unfiltered Query" for ap in result.anti_patterns)


# ============================================================================
# NO LIMIT CLAUSE TESTS
# ============================================================================


class TestNoLimitClause:
    """Test detection of queries without LIMIT."""

    def test_no_limit_with_where_detected(
        self,
        detector: CassandraAntiPatternDetector,
        sample_parsed_query: dict,
        sample_schema: dict,
    ) -> None:
        """Test that queries with WHERE but no LIMIT are flagged."""
        result = detector.analyze(
            parsed_query=sample_parsed_query,
            query="SELECT * FROM users WHERE email = 'test'",
            table_schema=sample_schema,
        )

        # Note: This query also triggers "Full Cluster Scan" due to email filter
        assert any(ap.name == "No LIMIT Clause" for ap in result.anti_patterns)

    def test_with_limit_not_flagged(
        self,
        detector: CassandraAntiPatternDetector,
        sample_parsed_query: dict,
        sample_schema: dict,
    ) -> None:
        """Test that queries with LIMIT are not flagged."""
        result = detector.analyze(
            parsed_query=sample_parsed_query,
            query="SELECT * FROM users WHERE user_id = 1 LIMIT 100",
            table_schema=sample_schema,
        )

        assert not any(ap.name == "No LIMIT Clause" for ap in result.anti_patterns)


# ============================================================================
# CLUSTERING WITHOUT PARTITION KEY TESTS
# ============================================================================


class TestClusteringWithoutPartitionKey:
    """Test detection of clustering key without partition key."""

    def test_clustering_without_partition_key_detected(
        self,
        detector: CassandraAntiPatternDetector,
        sample_parsed_query: dict,
        sample_schema: dict,
    ) -> None:
        """Test that queries using clustering without partition key are flagged."""
        result = detector.analyze(
            parsed_query=sample_parsed_query,
            query="SELECT * FROM users WHERE created_at > '2024-01-01'",
            table_schema=sample_schema,
        )

        assert any(ap.name == "Clustering Without Partition Key" for ap in result.anti_patterns)

    def test_clustering_with_partition_key_not_flagged(
        self,
        detector: CassandraAntiPatternDetector,
        sample_parsed_query: dict,
        sample_schema: dict,
    ) -> None:
        """Test that clustering key with partition key is not flagged."""
        result = detector.analyze(
            parsed_query=sample_parsed_query,
            query="SELECT * FROM users WHERE user_id = 1 AND created_at > '2024-01-01'",
            table_schema=sample_schema,
        )

        assert not any(ap.name == "Clustering Without Partition Key" for ap in result.anti_patterns)


# ============================================================================
# SCORING TESTS
# ============================================================================


class TestScoringCalculation:
    """Test score calculation."""

    def test_base_score(
        self,
        detector: CassandraAntiPatternDetector,
        sample_parsed_query: dict,
        sample_schema: dict,
    ) -> None:
        """Test that optimal query gets base score."""
        result = detector.analyze(
            parsed_query=sample_parsed_query,
            query="SELECT * FROM users WHERE user_id = 1 LIMIT 100",
            table_schema=sample_schema,
        )

        assert result.score == 100

    def test_multiple_penalties_stack(
        self,
        detector: CassandraAntiPatternDetector,
        sample_parsed_query: dict,
        sample_schema: dict,
    ) -> None:
        """Test that multiple anti-patterns stack their penalties."""
        sample_parsed_query["allow_filtering"] = True
        sample_parsed_query["has_filter_without_key"] = True

        result = detector.analyze(
            parsed_query=sample_parsed_query,
            query="SELECT * FROM users WHERE email = 'test' ALLOW FILTERING LIMIT 100",
            table_schema=sample_schema,
        )

        # Both penalties should apply
        expected_score = 100 - detector.PENALTY_CRITICAL - detector.PENALTY_CRITICAL
        assert result.score == max(0, expected_score)

    def test_score_minimum_zero(
        self,
        detector: CassandraAntiPatternDetector,
        sample_parsed_query: dict,
        sample_schema: dict,
    ) -> None:
        """Test that score never goes below 0."""
        sample_parsed_query["allow_filtering"] = True
        sample_parsed_query["has_filter_without_key"] = True
        sample_parsed_query["replicas_touched"] = 10

        result = detector.analyze(
            parsed_query=sample_parsed_query,
            query="SELECT * FROM users",
            table_schema=sample_schema,
        )

        assert result.score >= 0
        assert result.score <= 100
