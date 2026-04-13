"""InfluxDB 2.x database adapter using influxdb-client."""

import logging
import time
from typing import Any

from query_analyzer.adapters.base import BaseAdapter
from query_analyzer.adapters.exceptions import (
    ConnectionError as AdapterConnectionError,
)
from query_analyzer.adapters.exceptions import QueryAnalysisError
from query_analyzer.adapters.models import ConnectionConfig, QueryAnalysisReport
from query_analyzer.adapters.registry import AdapterRegistry
from query_analyzer.core.anti_pattern_detector import AntiPatternDetector

from .influxdb_parser import InfluxDBFluxParser

logger = logging.getLogger(__name__)


@AdapterRegistry.register("influxdb")
class InfluxDBAdapter(BaseAdapter):
    """InfluxDB 2.x adapter using influxdb-client library.

    Implements all BaseAdapter methods for InfluxDB 2.x with Flux query analysis
    and performance profiling. Flux is InfluxDB's functional query language using
    pipe-based syntax (|>).

    Key features:
    - Token-based authentication (InfluxDB 2.x only)
    - Flux query validation and parsing
    - Automatic detection of unbounded queries (no time filter)
    - Performance scoring (0-100 scale)
    - Actionable recommendations for optimization

    Attributes:
        parser: InfluxDBFluxParser instance for query analysis
        _query_api: InfluxDB QueryApi instance (lazy initialized)
    """

    def __init__(self, config: ConnectionConfig) -> None:
        """Initialize InfluxDB adapter.

        Args:
            config: Connection configuration with host, port, token (in password field)

        Raises:
            ConnectionConfigError: If config is invalid
        """
        super().__init__(config)
        self.parser = InfluxDBFluxParser()
        self._query_api: Any = None
        self._org_id: str | None = None  # Store org ID for query_raw() calls

    def connect(self) -> None:
        """Establish connection to InfluxDB 2.x using token authentication.

        InfluxDB 2.x requires an API token (not username/password).
        Token should be provided in config.password field.
        Organization can be specified in config.extra["org"].

        Raises:
            ConnectionError: If connection fails or health check fails
        """
        try:
            from influxdb_client import InfluxDBClient

            # Extract configuration
            host = self._config.host or "localhost"
            port = self._config.port or 8086
            token = self._config.password or "invalid_token"  # API token for InfluxDB 2.x
            org = self._config.extra.get("org", "")  # Organization (optional)
            timeout = self._config.extra.get("connection_timeout", 10)

            logger.debug(f"Connect: org={org!r}, extra={self._config.extra}")

            # Build connection URL
            url = f"http://{host}:{port}"

            # Create InfluxDB client
            self._connection = InfluxDBClient(url=url, token=token, org=org, timeout=timeout)

            # Verify connectivity with health check
            health = self._connection.health()
            if health.status != "pass":
                raise AdapterConnectionError(f"InfluxDB health check failed: {health.message}")

            # Fetch and store org ID for query_raw() calls
            # If org is empty or not provided, try to find the first available org
            if org:
                self._org_id = org  # Default to org name if we can't fetch ID
                try:
                    orgs_api = self._connection.organizations_api()
                    orgs = orgs_api.find_organizations()
                    # Find org by name
                    for org_obj in orgs:
                        if org_obj.name == org:
                            self._org_id = org_obj.id
                            break
                except Exception as e:
                    # Check if this is an authentication error (401)
                    error_str = str(e).lower()
                    if "401" in error_str or "unauthorized" in error_str:
                        raise AdapterConnectionError(
                            f"Authentication failed: Invalid token or insufficient permissions: {e}"
                        ) from e
                    logger.warning(f"Failed to fetch org ID, using org name: {e}")
            else:
                # If no org specified, try to find the default or first org
                try:
                    orgs_api = self._connection.organizations_api()
                    orgs = orgs_api.find_organizations()
                    if orgs:
                        self._org_id = orgs[0].id  # Use first available org
                        logger.debug(f"Using first org: {orgs[0].name}")
                except Exception as e:
                    # Check if this is an authentication error (401)
                    error_str = str(e).lower()
                    if "401" in error_str or "unauthorized" in error_str:
                        raise AdapterConnectionError(
                            f"Authentication failed: Invalid token or insufficient permissions: {e}"
                        ) from e
                    logger.warning(f"Failed to fetch default org: {e}")

            # Get query API for later use
            self._query_api = self._connection.query_api()
            self._is_connected = True
            logger.info(f"Connected to InfluxDB {host}:{port}")

        except AdapterConnectionError:
            raise
        except Exception as e:
            self._is_connected = False
            self._connection = None
            self._query_api = None
            raise AdapterConnectionError(f"Failed to connect to InfluxDB: {e}") from e

    def disconnect(self) -> None:
        """Close InfluxDB connection.

        Gracefully handles errors during disconnection to ensure cleanup
        even if the connection is already broken.
        """
        if self._connection:
            try:
                self._connection.close()
                logger.info("Disconnected from InfluxDB")
            except Exception as e:
                logger.warning(f"Error closing InfluxDB connection: {e}")
            finally:
                self._connection = None
                self._query_api = None
                self._org_id = None
                self._is_connected = False

    def test_connection(self) -> bool:
        """Test InfluxDB connection with health check.

        Performs a lightweight health check to verify the connection is valid.
        Returns False instead of raising exceptions for fail-safe behavior.

        Returns:
            True if connection is valid, False otherwise
        """
        try:
            if not self._is_connected or not self._connection:
                return False

            health = self._connection.health()
            result = health.status == "pass"
            return bool(result)
        except Exception as e:
            logger.warning(f"Connection test failed: {e}")
            return False

    def execute_explain(self, query: str) -> QueryAnalysisReport:
        """Execute Flux query and generate analysis report.

        6-Step Pipeline:
        1. VALIDATION     → Check connection, validate Flux syntax
        2. EXECUTION      → Run query via InfluxDB API
        3. PARSING        → Parse Flux structure using regex patterns
        4. NORMALIZATION  → Convert to engine-agnostic plan format
        5. ANTI-PATTERN   → Detect patterns and calculate score (0-100)
        6. REPORTING      → Build QueryAnalysisReport with recommendations

        Args:
            query: Flux query to analyze (not DDL statements)

        Returns:
            QueryAnalysisReport with score, warnings, and recommendations

        Raises:
            QueryAnalysisError: If query analysis fails or connection not active
        """
        # STEP 1: VALIDATION
        if not self._is_connected:
            raise QueryAnalysisError("Not connected to InfluxDB")

        query_clean = query.strip()
        if not query_clean:
            raise QueryAnalysisError("Empty query provided")

        query_upper = query_clean.upper()
        invalid_keywords = ["IMPORT", "BUILTIN", "DELETE BUCKET", "CREATE"]
        if any(query_upper.startswith(kw) for kw in invalid_keywords):
            raise QueryAnalysisError(
                "Cannot analyze DDL/administrative statements. "
                "Only Flux queries (SELECT-like: from, filter, range, etc.) are supported."
            )

        try:
            # STEP 2: EXECUTION (with timing)
            # Try to execute the query to get runtime metrics
            start_time = time.time()
            logger.debug(f"Query with org={self._org_id}")
            result_str = ""
            execution_time_ms = 0.0
            metrics: dict[str, Any] = {"records_returned": 0, "measurements_scanned": 1}

            try:
                result = self._query_api.query_raw(org=self._org_id or "", query=query)
                execution_time_ms = (time.time() - start_time) * 1000

                # Convert HTTPResponse to string
                if hasattr(result, "data"):
                    result_str = result.data.decode("utf-8")
                else:
                    result_str = str(result)

                # Extract metrics from CSV response
                metrics = self._extract_metrics_from_response(result_str)
                metrics["execution_time_ms"] = execution_time_ms
            except Exception as exec_error:
                # Query execution failed - this is expected for unbounded queries
                # We can still perform static analysis on the query
                execution_time_ms = (time.time() - start_time) * 1000
                metrics["execution_time_ms"] = execution_time_ms
                logger.debug(
                    f"Query execution failed (expected for problematic queries): {exec_error}"
                )
                # Continue with static analysis

            # STEP 3: PARSING
            parsed = self.parser.parse_query(query)

            # STEP 4: NORMALIZATION
            normalized_plan = self.parser.normalize_plan(parsed)

            # STEP 5: ANTI-PATTERN DETECTION
            detector = AntiPatternDetector()
            detection_result = detector.analyze_influxdb_patterns(normalized_plan, query)

            # Convert anti-patterns to warnings
            warnings = [ap.description for ap in detection_result.anti_patterns]
            recommendations = detection_result.recommendations
            score = detection_result.score

            # STEP 6: REPORT BUILDING
            return QueryAnalysisReport(
                engine="influxdb",
                query=query,
                score=score,
                execution_time_ms=execution_time_ms,
                warnings=warnings,
                recommendations=recommendations,
                raw_plan=normalized_plan,
                metrics=metrics,
            )

        except QueryAnalysisError:
            raise
        except Exception as e:
            raise QueryAnalysisError(f"Failed to analyze Flux query: {e}") from e

    def _extract_metrics_from_response(self, response: str) -> dict[str, Any]:
        """Extract metrics from InfluxDB CSV response.

        Parses CSV response to count records and extract measurement info.
        Gracefully handles empty or malformed responses.

        Args:
            response: CSV response from query_api.query_raw()

        Returns:
            Dict with records_returned and measurements_scanned
        """
        try:
            lines = response.strip().split("\n")
            # Exclude header row
            record_count = max(0, len(lines) - 1)

            return {
                "records_returned": record_count,
                "measurements_scanned": 1,  # Typically one per query
            }
        except Exception as e:
            logger.warning(f"Failed to extract metrics from response: {e}")
            return {"records_returned": 0, "measurements_scanned": 1}

    def get_slow_queries(self, threshold_ms: int = 1000) -> list[dict[str, Any]]:
        """Get slow queries from InfluxDB.

        Note: InfluxDB 2.x does not have a traditional slow query log like SQL
        databases. Query execution history is available through task execution logs,
        but not through a direct slow query interface.

        Returns empty list as graceful fallback for API compatibility.

        Args:
            threshold_ms: Threshold in milliseconds (ignored for InfluxDB)

        Returns:
            Empty list (InfluxDB 2.x lacks slow query logs)
        """
        if not self._is_connected:
            return []

        try:
            # InfluxDB 2.x doesn't have traditional slow query logs
            # Task execution history could be queried here but requires
            # additional permissions and context
            logger.debug("InfluxDB 2.x does not provide slow query logs")
            return []
        except Exception as e:
            logger.warning(f"Failed to retrieve slow queries: {e}")
            return []

    def get_metrics(self) -> dict[str, Any]:
        """Get InfluxDB server metrics and health status.

        Returns health check information and any available statistics.
        Gracefully handles errors to ensure this call never raises exceptions.

        Returns:
            Dict with status, message, and other available metrics
        """
        if not self._is_connected:
            return {}

        try:
            health = self._connection.health()
            metrics = {
                "status": health.status,
                "message": health.message,
            }

            # Include additional fields if available
            if hasattr(health, "checks"):
                metrics["checks"] = health.checks
            if hasattr(health, "version"):
                metrics["version"] = health.version

            return metrics
        except Exception as e:
            logger.warning(f"Failed to retrieve metrics: {e}")
            return {}

    def get_engine_info(self) -> dict[str, Any]:
        """Get InfluxDB version and configuration information.

        Returns version, commit hash, and other engine-specific details.
        Gracefully handles errors to ensure this call never raises exceptions.

        Returns:
            Dict with engine, version, commit, and other config details
        """
        if not self._is_connected:
            return {}

        try:
            health = self._connection.health()
            engine_info = {
                "engine": "influxdb",
                "version": getattr(health, "version", "unknown"),
                "commit": getattr(health, "commit", "unknown"),
                "status": health.status,
            }
            return engine_info
        except Exception as e:
            logger.warning(f"Failed to retrieve engine info: {e}")
            return {}
