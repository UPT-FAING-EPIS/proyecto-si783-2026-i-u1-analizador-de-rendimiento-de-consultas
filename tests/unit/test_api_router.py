"""Tests for Query Analyzer API routes."""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from query_analyzer.adapters.models import QueryAnalysisReport
from query_analyzer.api.app import app


@dataclass
class StubAIResult:
    """Small AI result shape matching the core analyzer contract."""

    summary: str
    observations: list[str]
    recommendations: list[str]
    suggested_query: str | None = None
    raw_response: str | None = None


def test_explain_includes_optional_ai_analysis() -> None:
    """EXPLAIN includes AI analysis when explicitly requested."""
    adapter = MagicMock()
    adapter.__enter__.return_value = adapter
    adapter.execute_explain.return_value = QueryAnalysisReport(
        engine="sqlite",
        query="SELECT 1",
        execution_time_ms=1.0,
        plan_summary="SCAN CONSTANT ROW",
        raw_plan={"Plan": {"Node Type": "Result"}},
        metrics={"node_count": 1},
    )
    analyzer = MagicMock()
    analyzer.available = True
    analyzer.analyze.return_value = StubAIResult(
        summary="La consulta es simple y eficiente.",
        observations=["No requiere lectura de tablas."],
        recommendations=["No se requieren cambios."],
    )

    with (
        patch("query_analyzer.api.router.AdapterRegistry.create", return_value=adapter),
        patch("query_analyzer.api.router.AIAnalyzer", return_value=analyzer),
    ):
        response = TestClient(app).post(
            "/api/v1/analyzer/explain",
            json={
                "connection": {"engine": "sqlite", "database": ":memory:"},
                "query": "SELECT 1",
                "include_ai": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["ai_analysis"] == {
        "summary": "La consulta es simple y eficiente.",
        "observations": ["No requiere lectura de tablas."],
        "recommendations": ["No se requieren cambios."],
        "suggested_query": None,
        "raw_response": None,
    }
    analyzer.analyze.assert_called_once_with(
        plan_json={"Plan": {"Node Type": "Result"}},
        query="SELECT 1",
        engine="sqlite",
    )


def test_explain_still_succeeds_when_optional_ai_fails() -> None:
    """AI errors should not turn a successful EXPLAIN into a failed response."""
    adapter = MagicMock()
    adapter.__enter__.return_value = adapter
    adapter.execute_explain.return_value = QueryAnalysisReport(
        engine="sqlite",
        query="SELECT 1",
        execution_time_ms=1.0,
        plan_summary="SCAN CONSTANT ROW",
    )
    analyzer = MagicMock()
    analyzer.available = True
    analyzer.analyze.side_effect = RuntimeError("AI provider unavailable")

    with (
        patch("query_analyzer.api.router.AdapterRegistry.create", return_value=adapter),
        patch("query_analyzer.api.router.AIAnalyzer", return_value=analyzer),
    ):
        response = TestClient(app).post(
            "/api/v1/analyzer/explain",
            json={
                "connection": {"engine": "sqlite", "database": ":memory:"},
                "query": "SELECT 1",
                "include_ai": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["ai_analysis"] is None


def test_explain_does_not_call_ai_by_default() -> None:
    """EXPLAIN returns factual data immediately unless include_ai is requested."""
    adapter = MagicMock()
    adapter.__enter__.return_value = adapter
    adapter.execute_explain.return_value = QueryAnalysisReport(
        engine="sqlite",
        query="SELECT 1",
        execution_time_ms=1.0,
        plan_summary="SCAN CONSTANT ROW",
    )

    with (
        patch("query_analyzer.api.router.AdapterRegistry.create", return_value=adapter),
        patch("query_analyzer.api.router.AIAnalyzer") as analyzer,
    ):
        response = TestClient(app).post(
            "/api/v1/analyzer/explain",
            json={
                "connection": {"engine": "sqlite", "database": ":memory:"},
                "query": "SELECT 1",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["ai_analysis"] is None
    analyzer.assert_not_called()


def test_ai_endpoint_uses_environment_configuration_when_ai_config_is_omitted() -> None:
    """The async AI endpoint can use QA_AI_* from the API process environment."""
    analyzer = MagicMock()
    analyzer.available = True
    analyzer.analyze.return_value = StubAIResult(
        summary="Plan eficiente.",
        observations=[],
        recommendations=[],
    )

    with patch("query_analyzer.api.router.AIAnalyzer", return_value=analyzer) as analyzer_cls:
        response = TestClient(app).post(
            "/api/v1/analyzer/ai",
            json={
                "plan_json": {"Plan": {"Node Type": "Result"}},
                "query": "SELECT 1",
                "engine": "sqlite",
            },
        )

    assert response.status_code == 200
    assert response.json()["summary"] == "Plan eficiente."
    analyzer_cls.assert_called_once_with()
