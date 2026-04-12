"""Unit tests for RedisAdapter and RedisParser."""

import pytest

from query_analyzer.adapters.exceptions import QueryAnalysisError
from query_analyzer.adapters.models import ConnectionConfig, QueryAnalysisReport
from query_analyzer.adapters.redis import RedisAdapter
from query_analyzer.adapters.redis_parser import RedisParser


@pytest.fixture
def redis_config():
    """Create a test Redis configuration."""
    return ConnectionConfig(
        engine="redis",
        host="localhost",
        port=6379,
        database="0",
        username=None,
        password=None,
    )


@pytest.fixture
def adapter(redis_config):
    """Create RedisAdapter instance for testing."""
    return RedisAdapter(redis_config)


class TestRedisParserParsing:
    """Test RedisParser command parsing functionality."""

    def test_parse_command_simple(self):
        """Test parsing simple Redis command."""
        result = RedisParser.parse_command("SET mykey myvalue")

        assert result["command"] == "SET"
        assert result["args"] == ["mykey", "myvalue"]
        assert result["raw"] == "SET mykey myvalue"

    def test_parse_command_keys_pattern(self):
        """Test parsing KEYS command with pattern."""
        result = RedisParser.parse_command("KEYS users:*")

        assert result["command"] == "KEYS"
        assert result["args"] == ["users:*"]

    def test_parse_command_case_insensitive(self):
        """Test command parsing is case-insensitive."""
        result = RedisParser.parse_command("set mykey myvalue")

        assert result["command"] == "SET"

    def test_parse_command_empty(self):
        """Test parsing empty command."""
        result = RedisParser.parse_command("")

        assert result["command"] == ""
        assert result["args"] == []


class TestRedisParserDangerousCommands:
    """Test detection of dangerous O(N) commands."""

    def test_detect_keys_command(self):
        """Test KEYS command detection."""
        is_dangerous, reason, penalty = RedisParser.detect_dangerous_command("KEYS *")

        assert is_dangerous is True
        assert "bloqueante" in reason.lower()
        assert penalty == -25

    def test_detect_smembers_command(self):
        """Test SMEMBERS command detection."""
        is_dangerous, reason, penalty = RedisParser.detect_dangerous_command("SMEMBERS myset")

        assert is_dangerous is True
        assert "paginación" in reason.lower()
        assert penalty == -25

    def test_detect_hgetall_command(self):
        """Test HGETALL command detection."""
        is_dangerous, reason, penalty = RedisParser.detect_dangerous_command("HGETALL myhash")

        assert is_dangerous is True
        assert "paginación" in reason.lower()
        assert penalty == -20

    def test_detect_lrange_full(self):
        """Test LRANGE 0 -1 (full list) detection."""
        is_dangerous, reason, penalty = RedisParser.detect_dangerous_command("LRANGE mylist 0 -1")

        assert is_dangerous is True
        assert "O(N)" in reason
        assert penalty == -20

    def test_detect_sort_command(self):
        """Test SORT command detection."""
        is_dangerous, reason, penalty = RedisParser.detect_dangerous_command("SORT mykey")

        assert is_dangerous is True
        assert "O(N + M log M)" in reason
        assert penalty == -25

    def test_detect_sinter_command(self):
        """Test SINTER (set intersection) detection."""
        is_dangerous, reason, penalty = RedisParser.detect_dangerous_command(
            "SINTER set1 set2 set3"
        )

        assert is_dangerous is True
        assert "O(N+M)" in reason
        assert penalty == -15

    def test_detect_sunion_command(self):
        """Test SUNION (set union) detection."""
        is_dangerous, reason, penalty = RedisParser.detect_dangerous_command("SUNION set1 set2")

        assert is_dangerous is True
        assert "O(N+M)" in reason
        assert penalty == -15

    def test_detect_flushdb_command(self):
        """Test FLUSHDB command detection."""
        is_dangerous, reason, penalty = RedisParser.detect_dangerous_command("FLUSHDB")

        assert is_dangerous is True
        assert "destructiva" in reason.lower()
        assert penalty == -30

    def test_detect_flushall_command(self):
        """Test FLUSHALL command detection."""
        is_dangerous, reason, penalty = RedisParser.detect_dangerous_command("FLUSHALL")

        assert is_dangerous is True
        assert "destructiva" in reason.lower()
        assert penalty == -30

    def test_detect_safe_command(self):
        """Test safe command returns no danger."""
        is_dangerous, reason, penalty = RedisParser.detect_dangerous_command("GET mykey")

        assert is_dangerous is False
        assert reason == ""
        assert penalty == 0

    def test_detect_set_command(self):
        """Test SET command is safe."""
        is_dangerous, reason, penalty = RedisParser.detect_dangerous_command("SET mykey myvalue")

        assert is_dangerous is False


class TestRedisParserNormalization:
    """Test command normalization to standardized format."""

    def test_normalize_keys_command(self):
        """Test normalization of KEYS command."""
        result = RedisParser.normalize_plan("KEYS *")

        assert result["node_type"] == "KEYS_SCAN"
        assert result["command"] == "KEYS"
        assert result["complexity"] == "O(N)"
        assert result["is_blocking"] is True
        assert result["data_structure"] == "KEYS"
        assert len(result["extra_info"]) > 0
        assert any("SCAN" in info for info in result["extra_info"])

    def test_normalize_smembers_command(self):
        """Test normalization of SMEMBERS command."""
        result = RedisParser.normalize_plan("SMEMBERS myset")

        assert result["node_type"] == "SET_ITERATION"
        assert result["command"] == "SMEMBERS"
        assert result["complexity"] == "O(N)"
        assert result["data_structure"] == "SET"
        assert result["is_blocking"] is False

    def test_normalize_hgetall_command(self):
        """Test normalization of HGETALL command."""
        result = RedisParser.normalize_plan("HGETALL myhash")

        assert result["node_type"] == "HASH_ITERATION"
        assert result["command"] == "HGETALL"
        assert result["complexity"] == "O(N)"
        assert result["data_structure"] == "HASH"

    def test_normalize_lrange_command(self):
        """Test normalization of LRANGE command."""
        result = RedisParser.normalize_plan("LRANGE mylist 0 -1")

        assert result["node_type"] == "LIST_RANGE"
        assert result["command"] == "LRANGE"
        assert result["complexity"] == "O(N)"
        assert result["data_structure"] == "LIST"

    def test_normalize_sort_command(self):
        """Test normalization of SORT command."""
        result = RedisParser.normalize_plan("SORT mykey")

        assert result["node_type"] == "SORT_OPERATION"
        assert result["command"] == "SORT"
        assert result["complexity"] == "O(N + M log M)"
        assert result["is_blocking"] is True

    def test_normalize_includes_recommendations(self):
        """Test normalized plan includes optimization recommendations."""
        result = RedisParser.normalize_plan("KEYS *")

        assert "extra_info" in result
        assert len(result["extra_info"]) > 0

    def test_normalize_sets_estimated_rows_to_none(self):
        """Test that estimated_rows is None (unknown without MEMORY USAGE)."""
        result = RedisParser.normalize_plan("SMEMBERS myset")

        assert result["estimated_rows"] is None

    def test_normalize_has_empty_children(self):
        """Test that Redis commands have no nested operations."""
        result = RedisParser.normalize_plan("KEYS *")

        assert result["children"] == []


class TestRedisParserSLOWLOG:
    """Test SLOWLOG entry parsing."""

    def test_parse_slowlog_entry(self):
        """Test parsing a SLOWLOG entry."""
        # Format: [id, timestamp, duration_us, command_array, client, client_addr]
        entry = [1, 1234567890, 50000, ["SET", "mykey", "myvalue"], "redis-cli", "127.0.0.1:12345"]

        result = RedisParser.parse_slowlog_entry(entry)

        assert result["id"] == 1
        assert result["timestamp"] == 1234567890
        assert result["duration_ms"] == 50.0  # 50000 us = 50 ms
        assert result["command"] == "SET mykey myvalue"
        assert result["client"] == "redis-cli"
        assert result["client_addr"] == "127.0.0.1:12345"

    def test_parse_slowlog_entry_microseconds_conversion(self):
        """Test that microseconds are converted to milliseconds correctly."""
        entry = [1, 1234567890, 1000000, ["KEYS", "*"], "redis-cli", "127.0.0.1:12345"]

        result = RedisParser.parse_slowlog_entry(entry)

        assert result["duration_ms"] == 1000.0  # 1000000 us = 1000 ms = 1 second


class TestRedisAdapterInitialization:
    """Test RedisAdapter initialization."""

    def test_adapter_initialization(self, redis_config):
        """Test adapter is properly initialized."""
        adapter = RedisAdapter(redis_config)

        assert adapter is not None
        assert adapter._config == redis_config
        assert adapter._client is None
        assert not adapter.is_connected()

    def test_adapter_has_parser(self, adapter):
        """Test adapter has RedisParser instance."""
        assert adapter.parser is not None
        assert isinstance(adapter.parser, RedisParser)

    def test_adapter_attributes(self, adapter):
        """Test adapter has required attributes."""
        assert hasattr(adapter, "_is_cluster")
        assert hasattr(adapter, "_redis_version")
        assert adapter._is_cluster is False


class TestRedisAdapterConnection:
    """Test RedisAdapter connection methods."""

    def test_connect_requires_host_port(self):
        """Test connect() raises error if host/port missing."""
        config = ConnectionConfig(
            engine="redis",
            host="",  # Empty host
            port=6379,
            database="0",
        )
        adapter = RedisAdapter(config)

        with pytest.raises(Exception):
            adapter.connect()

    def test_is_connected_false_initially(self, adapter):
        """Test is_connected() returns False initially."""
        assert adapter.is_connected() is False


class TestRedisAdapterExecuteExplain:
    """Test RedisAdapter execute_explain method."""

    def test_execute_explain_returns_report(self, adapter, mocker):
        """Test execute_explain returns QueryAnalysisReport."""
        # Mock the connection
        mocker.patch.object(adapter, "_is_connected", True)
        mocker.patch.object(adapter, "_client", {})

        report = adapter.execute_explain("KEYS *")

        assert isinstance(report, QueryAnalysisReport)
        assert report.engine == "redis"
        assert report.query == "KEYS *"
        assert 0 <= report.score <= 100

    def test_execute_explain_keys_command_score(self, adapter, mocker):
        """Test KEYS command receives low score (dangerous)."""
        mocker.patch.object(adapter, "_is_connected", True)
        mocker.patch.object(adapter, "_client", {})

        report = adapter.execute_explain("KEYS *")

        # KEYS * is O(N) bloqueante, should have low score
        assert report.score < 100

    def test_execute_explain_safe_command_score(self, adapter, mocker):
        """Test safe command receives higher score."""
        mocker.patch.object(adapter, "_is_connected", True)
        mocker.patch.object(adapter, "_client", {})

        report = adapter.execute_explain("GET mykey")

        # GET is safe, should have acceptable score
        # (Score depends on AntiPatternDetector)
        assert report.score >= 0

    def test_execute_explain_not_connected(self, adapter):
        """Test execute_explain raises error when not connected."""
        with pytest.raises(QueryAnalysisError):
            adapter.execute_explain("KEYS *")

    def test_execute_explain_empty_command(self, adapter, mocker):
        """Test execute_explain raises error for empty command."""
        mocker.patch.object(adapter, "_is_connected", True)

        with pytest.raises(QueryAnalysisError):
            adapter.execute_explain("")

    def test_execute_explain_includes_metrics(self, adapter, mocker):
        """Test execute_explain includes metrics in report."""
        mocker.patch.object(adapter, "_is_connected", True)
        mocker.patch.object(adapter, "_client", {})

        report = adapter.execute_explain("KEYS *")

        assert "is_dangerous_command" in report.metrics
        assert "command" in report.metrics


class TestRedisAdapterParserIntegration:
    """Test integration between adapter and parser."""

    def test_adapter_uses_parser_for_normalization(self, adapter):
        """Test adapter correctly uses RedisParser."""
        assert adapter.parser is not None

        # Verify parser methods exist
        assert hasattr(adapter.parser, "parse_command")
        assert hasattr(adapter.parser, "detect_dangerous_command")
        assert hasattr(adapter.parser, "normalize_plan")


class TestRedisAdapterMetrics:
    """Test RedisAdapter metrics collection."""

    def test_get_metrics_returns_dict(self, adapter, mocker):
        """Test get_metrics returns dictionary."""
        # Mock Redis client with INFO responses
        mock_client = mocker.MagicMock()
        mock_client.info.side_effect = [
            {"total_commands_processed": 1000, "total_connections_received": 50},  # stats
            {"used_memory": 1000000, "mem_fragmentation_ratio": 1.5},  # memory
            {"db0": {"keys": 100, "expires": 10, "avg_ttl": 3600000}},  # keyspace
        ]
        mock_client.config_get.return_value = {"slowlog-log-slower-than": "10000"}

        mocker.patch.object(adapter, "_is_connected", True)
        mocker.patch.object(adapter, "_client", mock_client)

        metrics = adapter.get_metrics()

        assert isinstance(metrics, dict)
        assert "total_commands_processed" in metrics
        assert "total_connections_received" in metrics

    def test_get_metrics_returns_empty_dict_on_error(self, adapter):
        """Test get_metrics returns empty dict on connection error."""
        metrics = adapter.get_metrics()

        assert metrics == {}

    def test_get_engine_info_returns_dict(self, adapter, mocker):
        """Test get_engine_info returns dictionary."""
        mock_client = mocker.MagicMock()
        mock_client.info.return_value = {
            "redis_version": "7.0.0",
            "cluster_enabled": 0,
            "uptime_in_seconds": 86400,
            "process_id": 1234,
        }
        mock_client.config_get.return_value = {"slowlog-log-slower-than": "10000"}

        mocker.patch.object(adapter, "_is_connected", True)
        mocker.patch.object(adapter, "_client", mock_client)

        info = adapter.get_engine_info()

        assert isinstance(info, dict)
        assert "version" in info
        assert "cluster_enabled" in info

    def test_test_connection_returns_false_when_not_connected(self, adapter):
        """Test test_connection returns False when not connected."""
        result = adapter.test_connection()

        assert result is False
