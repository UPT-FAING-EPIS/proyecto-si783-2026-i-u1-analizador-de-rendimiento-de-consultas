"""Tests for the Query Analyzer MCP server."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from query_analyzer.adapters.models import ConnectionConfig, QueryAnalysisReport
from query_analyzer.mcp_server import analyze_query_with_profile


def test_analyze_query_uses_explicit_profile() -> None:
    """The MCP tool resolves an explicit profile and returns report data."""
    connection_config = ConnectionConfig(engine="sqlite", database=":memory:")
    config_manager = MagicMock()
    config_manager.get_connection_config.return_value = connection_config
    adapter = MagicMock()
    adapter.__enter__.return_value = adapter
    adapter.execute_explain.return_value = QueryAnalysisReport(
        engine="sqlite",
        query="SELECT 1",
        execution_time_ms=1.5,
        plan_summary="SCAN CONSTANT ROW",
        raw_plan={"detail": "constant"},
        metrics={"node_count": 1},
        analyzed_at=datetime(2026, 6, 15, tzinfo=UTC),
    )

    with (
        patch("query_analyzer.mcp_server.ConfigManager", return_value=config_manager),
        patch("query_analyzer.mcp_server.AdapterRegistry.create", return_value=adapter) as create,
    ):
        result = analyze_query_with_profile("SELECT 1", profile="local")

    assert result == {
        "success": True,
        "profile": "local",
        "engine": "sqlite",
        "query": "SELECT 1",
        "execution_time_ms": 1.5,
        "plan_summary": "SCAN CONSTANT ROW",
        "metrics": {"node_count": 1},
        "raw_plan": {"detail": "constant"},
        "analyzed_at": "2026-06-15T00:00:00Z",
        "error": None,
    }
    config_manager.get_connection_config.assert_called_once_with("local")
    create.assert_called_once_with("sqlite", connection_config)
    adapter.execute_explain.assert_called_once_with("SELECT 1")


def test_analyze_query_uses_default_profile_when_omitted() -> None:
    """The MCP tool falls back to Query Analyzer's default profile."""
    connection_config = ConnectionConfig(engine="sqlite", database=":memory:")
    app_config = MagicMock(default_profile="default-sqlite")
    config_manager = MagicMock()
    config_manager.load_config.return_value = app_config
    config_manager.get_connection_config.return_value = connection_config
    adapter = MagicMock()
    adapter.__enter__.return_value = adapter
    adapter.execute_explain.return_value = QueryAnalysisReport(
        engine="sqlite",
        query="SELECT 1",
        execution_time_ms=1.0,
    )

    with (
        patch("query_analyzer.mcp_server.ConfigManager", return_value=config_manager),
        patch("query_analyzer.mcp_server.AdapterRegistry.create", return_value=adapter),
    ):
        result = analyze_query_with_profile("SELECT 1")

    assert result["success"] is True
    assert result["profile"] == "default-sqlite"
    config_manager.get_connection_config.assert_called_once_with("default-sqlite")


def test_analyze_query_returns_error_without_profile() -> None:
    """The MCP tool reports a useful error when no profile can be resolved."""
    config_manager = MagicMock()
    config_manager.load_config.return_value = MagicMock(default_profile=None)

    with patch("query_analyzer.mcp_server.ConfigManager", return_value=config_manager):
        result = analyze_query_with_profile("SELECT 1")

    assert result["success"] is False
    assert "No profile provided" in result["error"]


def test_analyze_query_rejects_empty_query() -> None:
    """The MCP tool rejects blank input before touching configuration."""
    result = analyze_query_with_profile("   ")

    assert result == {
        "success": False,
        "engine": "",
        "query": "   ",
        "error": "Query cannot be empty.",
    }
