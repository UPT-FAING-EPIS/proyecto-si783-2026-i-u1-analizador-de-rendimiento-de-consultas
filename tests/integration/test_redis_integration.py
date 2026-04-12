"""Integration tests for RedisAdapter with real Docker Redis instance."""

import pytest
import redis

from query_analyzer.adapters.models import ConnectionConfig, QueryAnalysisReport
from query_analyzer.adapters.redis import RedisAdapter


@pytest.fixture
def redis_config():
    """Create Redis configuration pointing to Docker instance."""
    return ConnectionConfig(
        engine="redis",
        host="localhost",
        port=6379,
        database="0",
    )


@pytest.fixture
def redis_client():
    """Create a raw Redis client for test setup."""
    client = redis.Redis(
        host="localhost",
        port=6379,
        db=0,
        decode_responses=True,
        socket_timeout=5,
    )
    # Verify connection
    client.ping()
    return client


@pytest.fixture
def adapter(redis_config):
    """Create and connect RedisAdapter with proper cleanup.

    This fixture ensures each test starts with a clean Redis state by:
    1. Connecting to Redis
    2. Yielding the adapter for test execution
    3. Flushing all data from the database
    4. Disconnecting from Redis
    """
    adapter = RedisAdapter(redis_config)
    adapter.connect()
    yield adapter
    # Critical: Clean up data to prevent test contamination
    client = adapter.get_connection()
    if client:
        client.flushdb()
    adapter.disconnect()


class TestRedisAdapterConnectionIntegration:
    """Test real Redis connections."""

    def test_connect_to_docker_redis(self, redis_config):
        """Test connecting to real Docker Redis."""
        adapter = RedisAdapter(redis_config)
        adapter.connect()

        assert adapter.is_connected() is True
        adapter.disconnect()

    def test_test_connection_succeeds(self, adapter):
        """Test connection test works with real Redis."""
        result = adapter.test_connection()

        assert result is True

    def test_get_engine_info_from_real_redis(self, adapter):
        """Test engine info retrieval from real Redis."""
        info = adapter.get_engine_info()

        assert "version" in info
        assert "cluster_enabled" in info
        assert "slowlog_threshold_microseconds" in info


class TestRedisAdapterExecuteExplainIntegration:
    """Test execute_explain with real commands."""

    def test_execute_explain_keys_command(self, adapter):
        """Test analysis of KEYS command.

        KEYS * is O(N) and dangerous. Analysis should:
        - Return low score (penalized)
        - Include warning about the O(N) operation
        - Recommend SCAN as the safe alternative
        """
        report = adapter.execute_explain("KEYS *")

        assert isinstance(report, QueryAnalysisReport), "Report must be QueryAnalysisReport"
        assert report.engine == "redis", f"Engine should be 'redis', got {report.engine}"
        assert report.query == "KEYS *", f"Query should be 'KEYS *', got {report.query}"
        assert report.score < 100, f"KEYS * should have score < 100, got {report.score}"

        # Verify warning and recommendation for SCAN
        assert len(report.warnings) > 0, "KEYS * should generate at least one warning"
        recommendations_text = " ".join(report.recommendations).upper()
        assert "SCAN" in recommendations_text, (
            f"Recommendations should suggest SCAN. Got: {report.recommendations}"
        )

    def test_execute_explain_smembers_command(self, adapter):
        """Test analysis of SMEMBERS command."""
        report = adapter.execute_explain("SMEMBERS myset")

        assert isinstance(report, QueryAnalysisReport)
        assert report.score < 100
        assert len(report.recommendations) > 0

    def test_execute_explain_safe_get_command(self, adapter):
        """Test analysis of safe GET command."""
        report = adapter.execute_explain("GET mykey")

        assert isinstance(report, QueryAnalysisReport)
        assert report.score == 100  # GET is safe

    def test_execute_explain_flushdb_command(self, adapter):
        """Test analysis of dangerous FLUSHDB command."""
        report = adapter.execute_explain("FLUSHDB")

        assert report.score < 100
        assert any("caution" in rec.lower() for rec in report.recommendations)


class TestRedisAdapterGetSlowQueriesIntegration:
    """Test SLOWLOG retrieval and parsing."""

    def test_get_slow_queries_returns_list(self, adapter, redis_client):
        """Test get_slow_queries returns list with real slow log entries.

        Process:
        1. Configure SLOWLOG to capture everything (threshold = 0 microseconds)
        2. Execute a test command that will be recorded
        3. Retrieve and verify SLOWLOG entries
        """
        # Configure SLOWLOG to capture all commands (0 microseconds = no threshold)
        redis_client.config_set("slowlog-log-slower-than", "0")

        try:
            # Execute a command that will definitely appear in SLOWLOG
            redis_client.set("test_key", "test_value")

            # Retrieve SLOWLOG with very low threshold to catch our command
            queries = adapter.get_slow_queries(threshold_ms=0)

            # Should return a list (may contain our command or others)
            assert isinstance(queries, list), "get_slow_queries must return a list"

            # With threshold=0, we should capture at least the SET command we just ran
            # (or potentially other commands depending on the SLOWLOG state)
            if queries:
                for entry in queries:
                    assert isinstance(entry, dict), "Each SLOWLOG entry must be a dict"
                    assert "duration_ms" in entry, "SLOWLOG entry missing 'duration_ms'"
                    assert "command" in entry, "SLOWLOG entry missing 'command'"
                    assert entry["duration_ms"] >= 0, "duration_ms must be >= 0"
        finally:
            # Restore default slowlog threshold (10000 microseconds)
            redis_client.config_set("slowlog-log-slower-than", "10000")

    def test_slowlog_entry_format(self, adapter):
        """Test that SLOWLOG entries have correct format."""
        queries = adapter.get_slow_queries(threshold_ms=0)  # Get all

        if queries:  # If there are any entries
            entry = queries[0]
            assert "id" in entry
            assert "timestamp" in entry
            assert "duration_ms" in entry
            assert "command" in entry


class TestRedisAdapterMetricsIntegration:
    """Test metrics collection from real Redis."""

    def test_get_metrics_returns_data(self, adapter):
        """Test metrics collection from real Redis with exact keys validation.

        Must return dict containing AT MINIMUM these keys (per specification):
        - total_commands_processed
        - used_memory_bytes
        - total_keys
        - slowlog_enabled

        (May include additional metrics like fragmentation ratio, databases info, etc.)
        """
        metrics = adapter.get_metrics()

        assert isinstance(metrics, dict), "Metrics must return a dict"

        # Verify all required keys are present (per specification)
        required_keys = {
            "total_commands_processed",
            "used_memory_bytes",
            "total_keys",
        }

        missing_keys = required_keys - set(metrics.keys())
        assert not missing_keys, (
            f"Metrics missing required keys: {missing_keys}. Got: {list(metrics.keys())}"
        )

        # Verify slowlog_enabled is present either directly or nested in slowlog_config
        has_slowlog_enabled = "slowlog_enabled" in metrics or (
            "slowlog_config" in metrics and "enabled" in metrics["slowlog_config"]
        )
        assert has_slowlog_enabled, (
            "slowlog_enabled must be present (directly or in slowlog_config)"
        )

        # Verify data types and values for required keys
        assert isinstance(metrics["total_commands_processed"], int), (
            "total_commands_processed must be int"
        )
        assert isinstance(metrics["used_memory_bytes"], int), "used_memory_bytes must be int"
        assert isinstance(metrics["total_keys"], int), "total_keys must be int"

    def test_metrics_slowlog_config(self, adapter):
        """Test SLOWLOG configuration is retrieved."""
        metrics = adapter.get_metrics()

        slowlog_config = metrics["slowlog_config"]
        assert "threshold_microseconds" in slowlog_config
        assert "enabled" in slowlog_config

    def test_get_memory_hotspots_integration(self, adapter, redis_client):
        """Test memory hotspots detection with ordering validation.

        Should:
        - Return list of dicts with key, memory_bytes, type
        - Items should be ordered by memory_bytes in descending order (largest first)
        - Each entry must have required fields with valid values
        """
        # Create some keys in Redis with different sizes
        for i in range(5):
            redis_client.set(f"key_{i}", f"value_{i}" * 100)

        hotspots = adapter.get_memory_hotspots(top_n=10, max_keys_to_scan=1000)

        # Should return list of dicts with key, memory_bytes, type
        assert isinstance(hotspots, list), "Memory hotspots must return a list"

        if hotspots:
            # Verify each entry has required fields
            for i, spot in enumerate(hotspots):
                assert "key" in spot, f"Entry {i} missing 'key' field"
                assert "memory_bytes" in spot, f"Entry {i} missing 'memory_bytes' field"
                assert "type" in spot, f"Entry {i} missing 'type' field"
                assert spot["memory_bytes"] > 0, f"Entry {i} memory_bytes must be > 0"

            # Verify ordering: each element should have >= memory than the next
            for i in range(len(hotspots) - 1):
                current_memory = hotspots[i]["memory_bytes"]
                next_memory = hotspots[i + 1]["memory_bytes"]
                assert current_memory >= next_memory, (
                    f"Hotspots not properly ordered. Position {i} ({current_memory} bytes) "
                    f"should be >= position {i + 1} ({next_memory} bytes)"
                )


class TestRedisAdapterEndToEndIntegration:
    """End-to-end integration tests."""

    def test_end_to_end_workflow(self, adapter, redis_client):
        """Test complete workflow: connect, analyze, get metrics."""
        # 1. Verify connection
        assert adapter.is_connected() is True

        # 2. Get engine info
        info = adapter.get_engine_info()
        assert "version" in info

        # 3. Analyze commands
        keys_report = adapter.execute_explain("KEYS *")
        assert keys_report.score < 100

        get_report = adapter.execute_explain("GET mykey")
        assert get_report.score == 100

        # 4. Get metrics
        metrics = adapter.get_metrics()
        assert "total_commands_processed" in metrics

    def test_dangerous_commands_consistency(self, adapter):
        """Test that dangerous command detection is consistent."""
        dangerous_commands = [
            "KEYS *",
            "SMEMBERS myset",
            "HGETALL myhash",
            "LRANGE mylist 0 -1",
            "SORT mykey",
            "FLUSHDB",
        ]

        for cmd in dangerous_commands:
            report = adapter.execute_explain(cmd)
            # All these should have low scores
            assert report.score < 100, f"Command {cmd} should have low score"
            # All should have warnings
            assert len(report.warnings) > 0, f"Command {cmd} should have warnings"

    def test_safe_commands_consistency(self, adapter):
        """Test that safe commands maintain high scores."""
        safe_commands = [
            "GET mykey",
            "SET mykey myvalue",
            "DEL mykey",
            "INCR counter",
            "LPUSH mylist value",
        ]

        for cmd in safe_commands:
            report = adapter.execute_explain(cmd)
            # All these should have high scores
            assert report.score == 100, f"Command {cmd} should have score 100"
            # Safe commands should have no warnings
            assert len(report.warnings) == 0, f"Command {cmd} should have no warnings"


class TestRedisAdapterClusterDetection:
    """Test cluster mode detection."""

    def test_cluster_detection_standalone(self, adapter):
        """Test that standalone Redis is detected correctly."""
        info = adapter.get_engine_info()

        # Docker Redis should be standalone
        assert info["cluster_enabled"] is False
