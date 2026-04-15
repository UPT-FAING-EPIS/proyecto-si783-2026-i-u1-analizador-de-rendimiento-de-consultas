"""Elasticsearch adapter for query performance analysis."""

import json
import logging
from datetime import UTC, datetime
from typing import Any, cast

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError as ESConnectionError
from elasticsearch.exceptions import NotFoundError

from query_analyzer.adapters.base import BaseAdapter
from query_analyzer.adapters.exceptions import ConnectionError as AdapterConnectionError
from query_analyzer.adapters.exceptions import QueryAnalysisError
from query_analyzer.adapters.models import (
    ConnectionConfig,
    QueryAnalysisReport,
    Recommendation,
    Warning,
)
from query_analyzer.adapters.registry import AdapterRegistry

from .elasticsearch_parser import ElasticsearchParser

logger = logging.getLogger(__name__)


@AdapterRegistry.register("elasticsearch")
class ElasticsearchAdapter(BaseAdapter):
    """Adapter for Elasticsearch query performance analysis.

    Supports: Query DSL queries with _profile API for detailed execution metrics.
    Uses elasticsearch-py 8.x client for connection and API interactions.

    The adapter analyzes queries using Elasticsearch's _profile API which provides:
    - Query execution timing
    - Collector timing
    - Document scoring information
    - Per-shard breakdown

    Attributes:
        _client: Elasticsearch client instance
        _parser: ElasticsearchParser instance
    """

    def __init__(self, config: ConnectionConfig) -> None:
        """Initialize Elasticsearch adapter.

        Args:
            config: Connection configuration
        """
        super().__init__(config)
        self._client: Elasticsearch | None = None
        self._parser = ElasticsearchParser()

    def connect(self) -> None:
        """Establish connection to Elasticsearch.

        Raises:
            ConnectionError: If connection fails
        """
        try:
            # Build connection parameters
            host = self._config.host or "localhost"
            port = self._config.port or 9200
            scheme = "http"  # Use http by default; can be https with auth

            # Build URL
            url = f"{scheme}://{host}:{port}"

            # Create client with timeout settings
            self._client = Elasticsearch(
                [url],
                request_timeout=10,
                max_retries=3,
                retry_on_timeout=True,
            )

            # Test connection via cluster health check
            info = self._client.info()
            logger.info(f"Connected to Elasticsearch {info.get('version', {}).get('number')}")

            self._is_connected = True

        except ESConnectionError as e:
            raise AdapterConnectionError(
                f"Failed to connect to Elasticsearch at {host}:{port}: {e}"
            ) from e
        except Exception as e:
            raise AdapterConnectionError(
                f"Unexpected error connecting to Elasticsearch: {e}"
            ) from e

    def disconnect(self) -> None:
        """Close connection to Elasticsearch.

        Raises:
            ConnectionError: If disconnection fails
        """
        try:
            if self._client:
                self._client.close()
                self._is_connected = False
        except Exception as e:
            raise AdapterConnectionError(f"Error disconnecting from Elasticsearch: {e}") from e

    def test_connection(self) -> bool:
        """Test Elasticsearch connection.

        Returns:
            True if connection is valid, False otherwise
        """
        try:
            if not self._client:
                return False
            self._client.info()
            return True
        except Exception:
            return False

    def execute_explain(self, query: str) -> QueryAnalysisReport:
        """Analyze query using Elasticsearch _profile API.

        Args:
            query: JSON string representing Elasticsearch query DSL

        Returns:
            QueryAnalysisReport with metrics and anti-pattern analysis

        Raises:
            QueryAnalysisError: If query execution or analysis fails
        """
        if not self._is_connected:
            raise QueryAnalysisError("No connection to Elasticsearch")

        try:
            # Parse query string
            query_dict = self._parser.parse_query_string(query)

            # Use a test index or create temporary one for analysis
            # For now, we'll use _search with a dummy index to get profile
            index_name = "_all"  # Search across all indices

            # Execute search with profile enabled
            # Type: ignore because self._client is checked to be not None via _is_connected
            response = self._client.search(  # type: ignore[union-attr]
                index=index_name,
                body={"query": query_dict, "profile": True},
                size=10,
            )

            # Parse profile response
            parsed_profile = self._parser.parse_profile(cast(dict[str, Any], response))

            # Detect anti-patterns
            warnings, recommendations = self._detect_anti_patterns(query_dict, parsed_profile)

            # Calculate optimization score (0-100)
            score = self._calculate_score(warnings, parsed_profile)

            # Ensure execution_time_ms is at least 0.1 (can't be 0)
            execution_time = max(0.1, parsed_profile["metrics"]["execution_time_ms"])

            # Build report
            report = QueryAnalysisReport(
                query=query,
                engine="elasticsearch",
                execution_time_ms=execution_time,
                score=score,
                warnings=warnings,
                recommendations=recommendations,
                metrics={
                    "took": parsed_profile["metrics"]["took"],
                    "query_type": parsed_profile["metrics"]["query_type"],
                    "has_filter": parsed_profile["has_filter"],
                    "timed_out": parsed_profile["metrics"]["timed_out"],
                },
                analyzed_at=datetime.now(UTC),
            )

            return report

        except json.JSONDecodeError as e:
            raise QueryAnalysisError(f"Invalid JSON query: {e}") from e
        except NotFoundError as e:
            # If index doesn't exist, still return analysis based on query structure
            logger.warning(f"Index not found during profile, analyzing query structure only: {e}")
            return self._analyze_query_structure_only(query_dict)
        except Exception as e:
            raise QueryAnalysisError(f"Error executing query profile: {e}") from e

    def _analyze_query_structure_only(self, query_dict: dict[str, Any]) -> QueryAnalysisReport:
        """Analyze query structure when no real execution is possible.

        Args:
            query_dict: Parsed query dictionary

        Returns:
            QueryAnalysisReport based on query structure analysis
        """
        warnings, recommendations = self._detect_anti_patterns(query_dict, {})

        score = self._calculate_score(warnings, {})

        report = QueryAnalysisReport(
            query=json.dumps(query_dict),
            engine="elasticsearch",
            execution_time_ms=0.1,  # Minimum positive value
            score=score,
            warnings=warnings,
            recommendations=recommendations,
            metrics={
                "query_type": self._parser._detect_query_type(query_dict),
                "has_filter": self._parser._has_filter(query_dict),
                "analysis_mode": "structure_only",
            },
            analyzed_at=datetime.now(UTC),
        )

        return report

    def _detect_anti_patterns(
        self, query_dict: dict[str, Any], parsed_profile: dict[str, Any]
    ) -> tuple[list[Warning], list[Recommendation]]:
        """Detect anti-patterns in query.

        Args:
            query_dict: Parsed query dictionary
            parsed_profile: Parsed profile response

        Returns:
            Tuple of (warnings list, recommendations list)
        """
        warnings: list[Warning] = []
        recommendations: list[Recommendation] = []

        # Anti-pattern 1: MatchAllQuery without filters
        query_type = self._parser._detect_query_type(query_dict)
        has_filter = self._parser._has_filter(query_dict)

        if query_type == "match_all" and not has_filter:
            warnings.append(
                Warning(
                    severity="high",
                    message="Query matches all documents - no filters applied",
                )
            )
            recommendations.append(
                Recommendation(
                    title="Add Query Filters",
                    description="Add filters or constraints to limit the result set",
                    priority=2,
                )
            )

        # Anti-pattern 2: WildcardQuery
        if self._parser.has_wildcard_query(query_dict):
            warnings.append(
                Warning(
                    severity="high",
                    message="Query contains wildcard patterns which are expensive to execute",
                )
            )
            recommendations.append(
                Recommendation(
                    title="Replace Wildcard Queries",
                    description="Use n-gram analyzers or keyword queries instead of wildcards",
                    priority=3,
                )
            )

        # Anti-pattern 3: Script queries
        if self._parser.has_script_query(query_dict):
            warnings.append(
                Warning(
                    severity="medium",
                    message="Query contains scripts which are expensive to execute",
                )
            )
            recommendations.append(
                Recommendation(
                    title="Optimize Scripts",
                    description="Use stored scripts or precompute values instead of inline scripts",
                    priority=4,
                )
            )

        return warnings, recommendations

    def _calculate_score(self, warnings: list[Warning], parsed_profile: dict[str, Any]) -> int:
        """Calculate optimization score (0-100).

        Args:
            warnings: List of detected warnings
            parsed_profile: Parsed profile data

        Returns:
            Score from 0-100
        """
        score = 100

        # Deduct points for each warning
        for warning in warnings:
            if warning.severity == "critical":
                score -= 30
            elif warning.severity == "high":
                score -= 15
            elif warning.severity == "medium":
                score -= 10
            else:  # low
                score -= 5

        # Check execution time if available
        if parsed_profile and "metrics" in parsed_profile:
            exec_time = parsed_profile["metrics"].get("execution_time_ms", 0)
            if exec_time > 1000:
                score -= 20
            elif exec_time > 100:
                score -= 10

        return max(0, min(100, score))

    def get_slow_queries(self, threshold_ms: int = 100) -> list[dict[str, Any]]:
        """Get slow queries from Elasticsearch slow log.

        Searches for slow log entries in .logs-* indices if available.

        Args:
            threshold_ms: Threshold in milliseconds (default: 100)

        Returns:
            List of slow query dictionaries

        Raises:
            QueryAnalysisError: If query fails
        """
        if not self._is_connected:
            raise QueryAnalysisError("No connection to Elasticsearch")

        try:
            # Try to search slow logs
            # Elasticsearch slow logs are typically stored in .logs-* indices
            slow_log_pattern = ".logs-*-*"

            response = self._client.search(  # type: ignore[union-attr]
                index=slow_log_pattern,
                body={
                    "query": {
                        "range": {
                            "service_time": {
                                "gte": threshold_ms,
                            }
                        }
                    },
                    "size": 100,
                    "sort": [{"@timestamp": {"order": "desc"}}],
                },
            )

            slow_queries = []
            for hit in response.get("hits", {}).get("hits", []):
                source = hit.get("_source", {})
                slow_queries.append(
                    {
                        "query": source.get("statement", "N/A"),
                        "execution_time_ms": source.get("service_time", threshold_ms),
                        "timestamp": source.get("@timestamp"),
                        "index": source.get("index"),
                    }
                )

            return slow_queries

        except NotFoundError:
            logger.warning("No slow log indices found")
            return []
        except Exception as e:
            raise QueryAnalysisError(f"Error fetching slow queries: {e}") from e

    def get_metrics(self) -> dict[str, Any]:
        """Get Elasticsearch cluster metrics.

        Returns:
            Dictionary with cluster health and node information

        Raises:
            QueryAnalysisError: If query fails
        """
        if not self._is_connected:
            raise QueryAnalysisError("No connection to Elasticsearch")

        try:
            health = self._client.cluster.health()  # type: ignore[union-attr]
            stats = self._client.cluster.stats()  # type: ignore[union-attr]

            return {
                "cluster_status": health.get("status"),
                "active_shards": health.get("active_shards"),
                "nodes_count": stats.get("nodes", {}).get("count", {}).get("total", 0),
                "indices_count": health.get("number_of_indices"),
                "timed_out": health.get("timed_out"),
            }

        except Exception as e:
            raise QueryAnalysisError(f"Error fetching metrics: {e}") from e

    def get_engine_info(self) -> dict[str, Any]:
        """Get Elasticsearch engine information.

        Returns:
            Dictionary with Elasticsearch version and configuration

        Raises:
            QueryAnalysisError: If connection fails
        """
        if not self._is_connected:
            raise QueryAnalysisError("No connection to Elasticsearch")

        try:
            info = self._client.info()  # type: ignore[union-attr]
            version = info.get("version", {})

            return {
                "engine": "elasticsearch",
                "version": version.get("number", "unknown"),
                "build_hash": version.get("build_hash", "unknown"),
                "lucene_version": version.get("lucene_version", "unknown"),
            }

        except Exception as e:
            raise QueryAnalysisError(f"Error fetching engine info: {e}") from e
