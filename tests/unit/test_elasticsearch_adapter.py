"""Unit tests for Elasticsearch adapter."""

from unittest.mock import MagicMock, patch

import pytest

from query_analyzer.adapters.elasticsearch import ElasticsearchAdapter
from query_analyzer.adapters.elasticsearch_parser import ElasticsearchParser
from query_analyzer.adapters.exceptions import ConnectionError, QueryAnalysisError
from query_analyzer.adapters.models import ConnectionConfig


class TestElasticsearchParser:
    """Test ElasticsearchParser methods."""

    def test_parse_query_string_valid_json(self) -> None:
        """Test parsing valid JSON query string."""
        query_str = '{"query": {"match_all": {}}}'
        result = ElasticsearchParser.parse_query_string(query_str)
        assert result == {"query": {"match_all": {}}}

    def test_parse_query_string_invalid_json(self) -> None:
        """Test parsing invalid JSON raises ValueError."""
        query_str = '{"invalid": json}'
        with pytest.raises(ValueError, match="Invalid JSON"):
            ElasticsearchParser.parse_query_string(query_str)

    def test_detect_query_type_match_all(self) -> None:
        """Test detecting match_all query type."""
        query = {"match_all": {}}
        result = ElasticsearchParser._detect_query_type(query)
        assert result == "match_all"

    def test_detect_query_type_bool(self) -> None:
        """Test detecting bool query type."""
        query = {"bool": {"must": [{"term": {"status": "published"}}]}}
        result = ElasticsearchParser._detect_query_type(query)
        assert result == "bool"

    def test_detect_query_type_wildcard(self) -> None:
        """Test detecting wildcard query type."""
        query = {"wildcard": {"title": {"value": "test*"}}}
        result = ElasticsearchParser._detect_query_type(query)
        assert result == "wildcard"

    def test_detect_query_type_script(self) -> None:
        """Test detecting script query type."""
        query = {"script_score": {"query": {"match_all": {}}}}
        result = ElasticsearchParser._detect_query_type(query)
        assert result == "script_score"

    def test_has_filter_bool_with_filter(self) -> None:
        """Test that bool query with filter is detected."""
        query = {"bool": {"filter": {"term": {"status": "active"}}}}
        result = ElasticsearchParser._has_filter(query)
        assert result is True

    def test_has_filter_bool_without_filter(self) -> None:
        """Test that bool query without filter is detected."""
        query = {"bool": {}}
        result = ElasticsearchParser._has_filter(query)
        assert result is False

    def test_has_filter_match_all_no_filter(self) -> None:
        """Test that match_all without filters is detected."""
        query = {"match_all": {}}
        result = ElasticsearchParser._has_filter(query)
        assert result is False

    def test_has_filter_other_query_has_filter(self) -> None:
        """Test that non-match_all queries have implicit filters."""
        query = {"term": {"status": "active"}}
        result = ElasticsearchParser._has_filter(query)
        assert result is True

    def test_has_wildcard_query_detects_wildcard(self) -> None:
        """Test detecting wildcard in query structure."""
        query = {"query": {"wildcard": {"title": {"value": "test*"}}}}
        result = ElasticsearchParser.has_wildcard_query(query)
        assert result is True

    def test_has_wildcard_query_nested(self) -> None:
        """Test detecting nested wildcard queries."""
        query = {"bool": {"must": [{"wildcard": {"field": {"value": "value*"}}}]}}
        result = ElasticsearchParser.has_wildcard_query(query)
        assert result is True

    def test_has_wildcard_query_no_wildcard(self) -> None:
        """Test no wildcard in query."""
        query = {"bool": {"must": [{"term": {"status": "active"}}]}}
        result = ElasticsearchParser.has_wildcard_query(query)
        assert result is False

    def test_has_script_query_detects_script(self) -> None:
        """Test detecting script in query."""
        query = {"script_score": {"query": {"match_all": {}}}}
        result = ElasticsearchParser.has_script_query(query)
        assert result is True

    def test_has_script_query_no_script(self) -> None:
        """Test no script in query."""
        query = {"match_all": {}}
        result = ElasticsearchParser.has_script_query(query)
        assert result is False

    def test_parse_profile_empty_response(self) -> None:
        """Test parsing empty profile response."""
        response = {"profile": {}, "took": 1}
        result = ElasticsearchParser.parse_profile(response)
        assert result["metrics"]["execution_time_ms"] == 0.0
        assert result["metrics"]["took"] == 1
        assert result["stages"] == []

    def test_estimate_documents_examined(self) -> None:
        """Test estimating documents examined."""
        response = {"hits": {"total": {"value": 100}}}
        result = ElasticsearchParser.estimate_documents_examined(response)
        assert result == 100


class TestElasticsearchAdapter:
    """Test ElasticsearchAdapter methods."""

    @pytest.fixture
    def config(self) -> ConnectionConfig:
        """Create test configuration."""
        return ConnectionConfig(
            engine="elasticsearch",
            host="localhost",
            port=9200,
            database="test",
        )

    @pytest.fixture
    def adapter(self, config: ConnectionConfig) -> ElasticsearchAdapter:
        """Create adapter instance."""
        return ElasticsearchAdapter(config)

    def test_adapter_initialization(self, adapter: ElasticsearchAdapter) -> None:
        """Test adapter initialization."""
        assert adapter._config.engine == "elasticsearch"
        assert adapter._config.host == "localhost"
        assert adapter._config.port == 9200
        assert adapter._is_connected is False

    @patch("query_analyzer.adapters.elasticsearch.Elasticsearch")
    def test_connect_success(self, mock_es_class: MagicMock, adapter: ElasticsearchAdapter) -> None:
        """Test successful connection."""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "8.14.0"}}
        mock_es_class.return_value = mock_client

        adapter.connect()

        assert adapter._is_connected is True
        assert adapter._client is not None

    @patch("query_analyzer.adapters.elasticsearch.Elasticsearch")
    def test_connect_failure(self, mock_es_class: MagicMock, adapter: ElasticsearchAdapter) -> None:
        """Test connection failure."""
        from elasticsearch.exceptions import ConnectionError as ESConnectionError

        mock_es_class.side_effect = ESConnectionError("Connection failed")

        with pytest.raises(ConnectionError):
            adapter.connect()

    @patch("query_analyzer.adapters.elasticsearch.Elasticsearch")
    def test_disconnect_success(
        self, mock_es_class: MagicMock, adapter: ElasticsearchAdapter
    ) -> None:
        """Test successful disconnection."""
        mock_client = MagicMock()
        mock_es_class.return_value = mock_client
        adapter.connect()

        adapter.disconnect()

        assert adapter._is_connected is False
        mock_client.close.assert_called_once()

    @patch("query_analyzer.adapters.elasticsearch.Elasticsearch")
    def test_test_connection_success(
        self, mock_es_class: MagicMock, adapter: ElasticsearchAdapter
    ) -> None:
        """Test connection test."""
        mock_client = MagicMock()
        mock_client.info.return_value = {}
        mock_es_class.return_value = mock_client
        adapter.connect()

        result = adapter.test_connection()

        assert result is True

    def test_test_connection_no_client(self, adapter: ElasticsearchAdapter) -> None:
        """Test connection test without client."""
        result = adapter.test_connection()
        assert result is False

    @patch("query_analyzer.adapters.elasticsearch.Elasticsearch")
    def test_execute_explain_match_all_no_filter(
        self, mock_es_class: MagicMock, adapter: ElasticsearchAdapter
    ) -> None:
        """Test executing explain on match_all query without filter."""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "8.14.0"}}
        mock_client.search.return_value = {
            "profile": {},
            "took": 1,
            "hits": {"total": {"value": 1000}},
            "query": {"match_all": {}},
        }
        mock_es_class.return_value = mock_client
        adapter.connect()

        query_str = '{"match_all": {}}'
        report = adapter.execute_explain(query_str)

        assert report.engine == "elasticsearch"
        assert len(report.warnings) > 0
        assert any(w.severity in ["high", "critical"] for w in report.warnings)

    @patch("query_analyzer.adapters.elasticsearch.Elasticsearch")
    def test_execute_explain_with_wildcard(
        self, mock_es_class: MagicMock, adapter: ElasticsearchAdapter
    ) -> None:
        """Test executing explain on query with wildcard."""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "8.14.0"}}
        mock_client.search.return_value = {
            "profile": {},
            "took": 1,
            "hits": {"total": {"value": 100}},
        }
        mock_es_class.return_value = mock_client
        adapter.connect()

        query_str = '{"wildcard": {"title": {"value": "test*"}}}'
        report = adapter.execute_explain(query_str)

        assert len(report.warnings) > 0
        assert any(w.severity in ["high", "medium"] for w in report.warnings)

    @patch("query_analyzer.adapters.elasticsearch.Elasticsearch")
    def test_execute_explain_with_script(
        self, mock_es_class: MagicMock, adapter: ElasticsearchAdapter
    ) -> None:
        """Test executing explain on query with script."""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "8.14.0"}}
        mock_client.search.return_value = {
            "profile": {},
            "took": 1,
            "hits": {"total": {"value": 50}},
        }
        mock_es_class.return_value = mock_client
        adapter.connect()

        query_str = '{"script_score": {"query": {"match_all": {}}}}'
        report = adapter.execute_explain(query_str)

        assert len(report.warnings) > 0
        assert any(w.severity in ["high", "medium"] for w in report.warnings)

    @patch("query_analyzer.adapters.elasticsearch.Elasticsearch")
    def test_execute_explain_invalid_json(
        self, mock_es_class: MagicMock, adapter: ElasticsearchAdapter
    ) -> None:
        """Test executing explain with invalid JSON."""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "8.14.0"}}
        mock_es_class.return_value = mock_client
        adapter.connect()

        query_str = '{"invalid": json}'
        with pytest.raises(QueryAnalysisError):
            adapter.execute_explain(query_str)

    def test_execute_explain_not_connected(self, adapter: ElasticsearchAdapter) -> None:
        """Test executing explain without connection."""
        query_str = '{"match_all": {}}'
        with pytest.raises(QueryAnalysisError, match="No connection"):
            adapter.execute_explain(query_str)

    @patch("query_analyzer.adapters.elasticsearch.Elasticsearch")
    def test_get_slow_queries_not_connected(
        self, mock_es_class: MagicMock, adapter: ElasticsearchAdapter
    ) -> None:
        """Test get_slow_queries without connection."""
        with pytest.raises(QueryAnalysisError, match="No connection"):
            adapter.get_slow_queries()

    @patch("query_analyzer.adapters.elasticsearch.Elasticsearch")
    def test_get_metrics_success(
        self, mock_es_class: MagicMock, adapter: ElasticsearchAdapter
    ) -> None:
        """Test getting metrics."""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "8.14.0"}}
        mock_client.cluster.health.return_value = {
            "status": "green",
            "active_shards": 5,
            "number_of_indices": 10,
            "timed_out": False,
        }
        mock_client.cluster.stats.return_value = {"nodes": {"count": {"total": 3}}}
        mock_es_class.return_value = mock_client
        adapter.connect()

        metrics = adapter.get_metrics()

        assert metrics["cluster_status"] == "green"
        assert metrics["active_shards"] == 5
        assert metrics["nodes_count"] == 3
