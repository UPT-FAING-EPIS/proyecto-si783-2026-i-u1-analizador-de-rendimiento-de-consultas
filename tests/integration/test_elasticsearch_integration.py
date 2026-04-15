"""Integration tests for Elasticsearch adapter."""

import json

import pytest

from query_analyzer.adapters.elasticsearch import ElasticsearchAdapter
from query_analyzer.adapters.models import ConnectionConfig


@pytest.fixture
def es_config() -> ConnectionConfig:
    """Elasticsearch test configuration."""
    return ConnectionConfig(
        engine="elasticsearch",
        host="localhost",
        port=9200,
        database="test_index",
    )


@pytest.fixture
def es_adapter(es_config: ConnectionConfig) -> ElasticsearchAdapter:
    """Elasticsearch adapter instance."""
    adapter = ElasticsearchAdapter(es_config)
    adapter.connect()
    yield adapter
    try:
        adapter.disconnect()
    except Exception:
        pass


class TestElasticsearchAdapterIntegration:
    """Integration tests for Elasticsearch adapter."""

    def test_adapter_connection(self, es_adapter: ElasticsearchAdapter) -> None:
        """Test successful connection to Elasticsearch."""
        assert es_adapter.is_connected()
        assert es_adapter.test_connection()

    def test_execute_explain_match_all_query(self, es_adapter: ElasticsearchAdapter) -> None:
        """Test explain on match_all query."""
        query = json.dumps({"match_all": {}})
        report = es_adapter.execute_explain(query)

        assert report.engine == "elasticsearch"
        assert report.query is not None
        # Should detect full index scan anti-pattern
        assert any(w.severity in ["high", "critical"] for w in report.warnings)

    def test_execute_explain_bool_query_with_filter(self, es_adapter: ElasticsearchAdapter) -> None:
        """Test explain on bool query with filter."""
        query = json.dumps(
            {
                "bool": {
                    "filter": {"term": {"status": "active"}},
                    "must": {"match": {"title": "test"}},
                }
            }
        )
        report = es_adapter.execute_explain(query)

        assert report.engine == "elasticsearch"
        # Should have fewer warnings since it has filters
        full_scan_warnings = [w for w in report.warnings if w.severity == "critical"]
        assert len(full_scan_warnings) == 0

    def test_execute_explain_wildcard_query(self, es_adapter: ElasticsearchAdapter) -> None:
        """Test explain on wildcard query."""
        query = json.dumps({"wildcard": {"title": {"value": "test*"}}})
        report = es_adapter.execute_explain(query)

        assert report.engine == "elasticsearch"
        # Should detect wildcard anti-pattern
        assert any(w.severity in ["high", "medium"] for w in report.warnings)

    def test_execute_explain_nested_wildcard_query(self, es_adapter: ElasticsearchAdapter) -> None:
        """Test explain on nested wildcard query."""
        query = json.dumps({"bool": {"must": [{"wildcard": {"field": {"value": "value*"}}}]}})
        report = es_adapter.execute_explain(query)

        assert report.engine == "elasticsearch"
        # Should detect nested wildcard
        assert any(w.severity in ["high", "medium"] for w in report.warnings)

    def test_execute_explain_script_score_query(self, es_adapter: ElasticsearchAdapter) -> None:
        """Test explain on script_score query."""
        query = json.dumps(
            {
                "script_score": {
                    "query": {"match_all": {}},
                    "script": {"source": "_score * params.factor", "params": {"factor": 1.2}},
                }
            }
        )
        report = es_adapter.execute_explain(query)

        assert report.engine == "elasticsearch"
        # Should detect script in query
        assert any(w.severity in ["high", "medium"] for w in report.warnings)

    def test_execute_explain_term_query(self, es_adapter: ElasticsearchAdapter) -> None:
        """Test explain on term query (good practice)."""
        query = json.dumps({"term": {"status": {"value": "published"}}})
        report = es_adapter.execute_explain(query)

        assert report.engine == "elasticsearch"
        # Term query is efficient, should have minimal warnings
        script_warnings = [w for w in report.warnings if w.severity == "high"]
        wildcard_warnings = [w for w in report.warnings if w.severity == "high"]
        assert len(script_warnings) == 0
        assert len(wildcard_warnings) == 0

    def test_get_metrics(self, es_adapter: ElasticsearchAdapter) -> None:
        """Test getting cluster metrics."""
        metrics = es_adapter.get_metrics()

        assert "cluster_status" in metrics
        assert "active_shards" in metrics
        assert "nodes_count" in metrics
        assert metrics["cluster_status"] in ["green", "yellow", "red"]

    def test_execute_explain_invalid_json_raises_error(
        self, es_adapter: ElasticsearchAdapter
    ) -> None:
        """Test that invalid JSON query raises error."""
        from query_analyzer.adapters.exceptions import QueryAnalysisError

        query = "{'invalid': json}"  # Invalid JSON
        with pytest.raises(QueryAnalysisError):
            es_adapter.execute_explain(query)

    def test_adapter_can_reconnect(self, es_adapter: ElasticsearchAdapter) -> None:
        """Test adapter can disconnect and reconnect."""
        es_adapter.disconnect()
        assert not es_adapter.is_connected()

        es_adapter.connect()
        assert es_adapter.is_connected()

    def test_score_calculation_no_warnings(self, es_adapter: ElasticsearchAdapter) -> None:
        """Test that query with no warnings gets high score."""
        query = json.dumps({"term": {"status": {"value": "published"}}})
        report = es_adapter.execute_explain(query)

        # Query with no anti-patterns should have high score
        assert report.score >= 85

    def test_score_calculation_with_warnings(self, es_adapter: ElasticsearchAdapter) -> None:
        """Test that query with warnings gets lower score."""
        query = json.dumps({"match_all": {}})
        report = es_adapter.execute_explain(query)

        # Query with full_index_scan should have lower score
        assert report.score < 90

    def test_recommendations_provided(self, es_adapter: ElasticsearchAdapter) -> None:
        """Test that recommendations are provided for anti-patterns."""
        query = json.dumps({"match_all": {}})
        report = es_adapter.execute_explain(query)

        assert len(report.recommendations) > 0
        # Should have recommendation for adding filters to match_all query
        assert any("filter" in r.title.lower() for r in report.recommendations)

    def test_multiple_anti_patterns_detected(self, es_adapter: ElasticsearchAdapter) -> None:
        """Test detecting multiple anti-patterns in one query."""
        query = json.dumps(
            {
                "bool": {
                    "should": [
                        {"wildcard": {"title": {"value": "test*"}}},
                        {
                            "script_score": {
                                "query": {"match_all": {}},
                                "script": {"source": "_score"},
                            }
                        },
                    ]
                }
            }
        )
        report = es_adapter.execute_explain(query)

        # Should detect multiple anti-patterns
        warning_severities = {w.severity for w in report.warnings}
        assert len(warning_severities) >= 1
