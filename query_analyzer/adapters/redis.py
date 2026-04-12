"""Redis database adapter using redis-py."""

import logging
from typing import Any

import redis

from query_analyzer.adapters.base import BaseAdapter
from query_analyzer.adapters.exceptions import ConnectionError as AdapterConnectionError
from query_analyzer.adapters.exceptions import QueryAnalysisError
from query_analyzer.adapters.models import ConnectionConfig, QueryAnalysisReport
from query_analyzer.adapters.registry import AdapterRegistry

from .redis_parser import RedisParser

logger = logging.getLogger(__name__)


@AdapterRegistry.register("redis")
class RedisAdapter(BaseAdapter):
    """Redis adapter using redis-py driver.

    Implements BaseAdapter methods for Redis, including SLOWLOG analysis,
    dangerous command detection, and metrics collection. Redis doesn't have
    a native query plan like SQL databases, so analysis focuses on:

    1. SLOWLOG entries (commands that exceeded execution threshold)
    2. Command pattern detection (O(N) operations on large structures)
    3. Runtime metrics (memory, connections, keyspace statistics)

    Attributes:
        _client: redis.Redis connection instance
        _connection_pool: Redis connection pool
        _is_cluster: Whether Redis is in cluster mode
        _redis_version: Redis server version
    """

    def __init__(self, config: ConnectionConfig) -> None:
        """Initialize Redis adapter.

        Args:
            config: Connection configuration with host, port, database

        Raises:
            ConnectionConfigError: If config is invalid
        """
        super().__init__(config)
        self._client: redis.Redis | None = None
        self._connection_pool: redis.ConnectionPool | None = None
        self._is_cluster: bool = False
        self._redis_version: str = ""
        self.parser = RedisParser()

    def connect(self) -> None:
        """Establish connection to Redis with UTF-8 decoding enabled.

        CRITICAL: Uses decode_responses=True to ensure all strings are
        decoded automatically, preventing bytes handling issues in SLOWLOG
        parsing and command regex matching.

        Raises:
            ConnectionError: If connection fails
        """
        if not self._config.host or not self._config.port:
            raise AdapterConnectionError("Redis host and port are required")

        try:
            # CRITICAL: decode_responses=True ensures UTF-8 automatic decoding
            # Build kwargs without ssl parameter for redis-py 7.0+
            pool_kwargs = {
                "host": self._config.host,
                "port": self._config.port,
                "db": int(self._config.database) if self._config.database else 0,
                "password": self._config.password,
                "decode_responses": True,  # Automatic UTF-8 decoding
                "socket_timeout": 5,
                "socket_keepalive": True,
            }

            self._connection_pool = redis.ConnectionPool(**pool_kwargs)  # type: ignore[arg-type]
            self._client = redis.Redis(connection_pool=self._connection_pool)

            # Test connection
            self._client.ping()
            self._is_connected = True

            # Get version for logging
            info = self._client.info("server")
            self._redis_version = info.get("redis_version", "unknown")

            logger.info(
                f"Connected to Redis {self._config.host}:{self._config.port} "
                f"(v{self._redis_version})"
            )

        except (redis.ConnectionError, redis.TimeoutError) as e:
            self._is_connected = False
            self._connection_pool = None
            self._client = None
            raise AdapterConnectionError(f"Failed to connect to Redis: {e}") from e

    def disconnect(self) -> None:
        """Close Redis connection and cleanup resources."""
        if self._connection_pool:
            try:
                self._connection_pool.disconnect()
                logger.info("Disconnected from Redis")
            except Exception as e:
                logger.warning(f"Error closing connection pool: {e}")
            finally:
                self._connection_pool = None
                self._client = None
                self._is_connected = False

    def test_connection(self) -> bool:
        """Test Redis connectivity with PING command (fail-safe).

        Returns:
            True if connection is valid, False otherwise (never raises)
        """
        try:
            if not self._is_connected or not self._client:
                return False

            return bool(self._client.ping())
        except Exception as e:
            logger.warning(f"Connection test failed: {e}")
            return False

    def get_engine_info(self) -> dict[str, Any]:
        """Get Redis version, cluster mode, and configuration (fail-safe).

        Returns:
            Dictionary with engine info:
                - version: Redis server version
                - cluster_enabled: Whether cluster mode is enabled
                - slowlog_threshold_microseconds: Current SLOWLOG threshold
                - slowlog_enabled: Whether SLOWLOG is active
        """
        try:
            if not self._is_connected or not self._client:
                return {}

            info = self._client.info("server")
            config = self._client.config_get("slowlog-log-slower-than")

            slowlog_threshold_us = int(config.get("slowlog-log-slower-than", 10000))
            slowlog_enabled = slowlog_threshold_us >= 0

            # Detect cluster mode
            self._is_cluster = info.get("cluster_enabled", False) == 1

            if self._is_cluster:
                logger.warning(
                    "Redis is in Cluster Mode. Analysis is node-level only. "
                    "Use Redis Cluster Monitor for full-cluster analysis."
                )

            # Warn if SLOWLOG is disabled
            if not slowlog_enabled:
                logger.warning(
                    "SLOWLOG is disabled (threshold < 0). "
                    "Recommend enabling with: CONFIG SET slowlog-log-slower-than 10000"
                )

            return {
                "version": info.get("redis_version", "unknown"),
                "cluster_enabled": self._is_cluster,
                "slowlog_threshold_microseconds": slowlog_threshold_us,
                "slowlog_enabled": slowlog_enabled,
                "uptime_seconds": info.get("uptime_in_seconds", 0),
                "process_id": info.get("process_id", 0),
            }

        except Exception as e:
            logger.warning(f"Failed to get engine info: {e}")
            return {}

    def execute_explain(self, query: str) -> QueryAnalysisReport:
        """Analyze Redis command via pattern detection (fail-fast).

        Since Redis has no native EXPLAIN, analysis consists of:
        1. Command pattern matching (detect O(N) operations)
        2. Plan normalization for documentation
        3. Scoring based on dangerous command detection

        Args:
            query: Redis command string to analyze (e.g., "KEYS *")

        Returns:
            QueryAnalysisReport with analysis results

        Raises:
            QueryAnalysisError: If analysis fails
        """
        try:
            if not self._is_connected:
                raise QueryAnalysisError("Not connected to Redis")

            # Validate command (basic sanity check)
            command = query.strip().upper().split()[0] if query.strip() else ""
            if not command:
                raise QueryAnalysisError("Empty command provided")

            # Detect dangerous patterns
            is_dangerous, reason, penalty = self.parser.detect_dangerous_command(query)

            # Normalize to standardized plan
            normalized_plan = self.parser.normalize_plan(query)

            # Generate warnings and recommendations based on dangerous detection
            warnings = []
            recommendations = []

            if is_dangerous:
                warnings.append(reason)

                # Add complexity-specific recommendations
                if "KEYS" in command:
                    recommendations.append("Use SCAN with cursor for pagination instead")
                elif "SMEMBERS" in command:
                    recommendations.append("Use SSCAN for large sets to avoid blocking")
                elif "HGETALL" in command:
                    recommendations.append(
                        "Use HSCAN for large hashes or retrieve specific fields only"
                    )
                elif "LRANGE" in command and "0" in query and "-1" in query:
                    recommendations.append("Add offset/limit parameters to LRANGE")
                elif "SORT" in command:
                    recommendations.append(
                        "Consider pre-sorting data on write or use SORT with LIMIT"
                    )
                elif "SINTER" in command or "SUNION" in command:
                    recommendations.append("Pre-compute and cache common intersections")
                elif "FLUSHDB" in command or "FLUSHALL" in command:
                    recommendations.append("Use with caution in production; consider selective DEL")

            # Calculate score: 100 is perfect, penalties for dangerous commands
            base_score = 100.0
            score = max(0.0, base_score + penalty)

            return QueryAnalysisReport(
                engine="redis",
                query=query,
                score=score,
                execution_time_ms=0,  # Unknown without real execution
                warnings=warnings,
                recommendations=recommendations,
                raw_plan=normalized_plan,
                metrics={
                    "is_dangerous_command": is_dangerous,
                    "danger_reason": reason if is_dangerous else None,
                    "command": command,
                    "normalized_plan": normalized_plan,
                    "complexity": normalized_plan.get("complexity", "Unknown"),
                },
            )

        except QueryAnalysisError:
            raise
        except Exception as e:
            raise QueryAnalysisError(f"Failed to analyze command: {e}") from e

    def get_slow_queries(self, threshold_ms: int = 100) -> list[dict[str, Any]]:
        """Extract slow queries from SLOWLOG (fail-safe).

        Args:
            threshold_ms: Millisecond threshold for filtering

        Returns:
            List of slow query entries or [] on error, each with:
                - id: SLOWLOG entry ID
                - timestamp: Unix timestamp
                - duration_ms: Execution duration in milliseconds
                - command: Full command string
                - client: Client address
                - client_addr: Client IP and port
        """
        try:
            if not self._is_connected or not self._client:
                return []

            # Get last 100 SLOWLOG entries
            slowlog_entries = self._client.slowlog_get(100)

            if not slowlog_entries:
                return []

            # Parse and filter entries
            parsed_queries = []
            for entry in slowlog_entries:
                parsed = self.parser.parse_slowlog_entry(entry)

                # Filter by threshold
                if parsed["duration_ms"] >= threshold_ms:
                    parsed_queries.append(parsed)

            return parsed_queries

        except Exception as e:
            logger.warning(f"Failed to retrieve slow queries: {e}")
            return []

    def get_metrics(self) -> dict[str, Any]:
        """Collect Redis metrics including memory, commands, and health (fail-safe).

        Returns:
            Dictionary with metrics or {} on error:
                - total_commands_processed: Cumulative commands executed
                - total_connections_received: Total client connections
                - used_memory_bytes: Current memory usage
                - used_memory_human: Human-readable memory
                - memory_fragmentation_ratio: Memory efficiency metric
                - total_keys: Total keys across all databases
                - databases: Per-database stats (keys, expires, avg_ttl_ms)
                - slowlog_config: SLOWLOG configuration details
        """
        try:
            if not self._is_connected or not self._client:
                return {}

            info_stats = self._client.info("stats")
            info_memory = self._client.info("memory")
            info_keyspace = self._client.info("keyspace")
            slowlog_config = self._client.config_get("slowlog-log-slower-than")

            # Parse SLOWLOG configuration
            slowlog_threshold_us = int(slowlog_config.get("slowlog-log-slower-than", 10000))
            slowlog_enabled = slowlog_threshold_us >= 0

            if not slowlog_enabled:
                logger.warning(
                    "SLOWLOG is disabled. Recommend: CONFIG SET slowlog-log-slower-than 10000"
                )

            # Calculate total keys
            total_keys = sum(
                int(db_info["keys"])
                for db_key, db_info in info_keyspace.items()
                if db_key.startswith("db")
            )

            return {
                "total_commands_processed": info_stats.get("total_commands_processed", 0),
                "total_connections_received": info_stats.get("total_connections_received", 0),
                "used_memory_bytes": info_memory.get("used_memory", 0),
                "used_memory_human": info_memory.get("used_memory_human", "0B"),
                "memory_fragmentation_ratio": float(
                    info_memory.get("mem_fragmentation_ratio", 1.0)
                ),
                "total_keys": total_keys,
                "databases": {
                    db_key: {
                        "keys": db_info.get("keys", 0),
                        "expires": db_info.get("expires", 0),
                        "avg_ttl_ms": db_info.get("avg_ttl", 0),
                    }
                    for db_key, db_info in info_keyspace.items()
                    if db_key.startswith("db")
                },
                "slowlog_config": {
                    "threshold_microseconds": slowlog_threshold_us,
                    "enabled": slowlog_enabled,
                },
            }

        except Exception as e:
            logger.warning(f"Failed to collect metrics: {e}")
            return {}

    def get_memory_hotspots(
        self, top_n: int = 100, max_keys_to_scan: int = 10000
    ) -> list[dict[str, Any]]:
        """Analyze memory usage per key via on-demand scanning (fail-safe).

        IMPORTANT: This scans the keyspace which is O(N) - call sparingly,
        especially on large databases. Only use after identifying problematic
        keys in SLOWLOG.

        Args:
            top_n: Number of top hotspots to return
            max_keys_to_scan: Maximum keys to evaluate (safety limit for large DBs)

        Returns:
            List of dicts with top memory consumers:
                - key: Key name
                - memory_bytes: Estimated memory usage
                - type: Redis data structure type (string, hash, list, etc.)
        """
        try:
            if not self._is_connected or not self._client:
                return []

            hotspots = []
            cursor = 0
            keys_scanned = 0

            while True:
                cursor, keys = self._client.scan(cursor, count=1000)

                for key in keys:
                    # Break if max keys scanned
                    if keys_scanned >= max_keys_to_scan:
                        break

                    try:
                        memory_bytes = self._client.memory_usage(key)
                        if memory_bytes:
                            key_str = key if isinstance(key, str) else key.decode("utf-8")
                            hotspots.append(
                                {
                                    "key": key_str,
                                    "memory_bytes": memory_bytes,
                                    "type": self._client.type(key),
                                }
                            )
                    except Exception as e:
                        logger.debug(f"Failed to get memory for key {key}: {e}")

                    keys_scanned += 1

                # Exit if cursor exhausted OR max keys reached
                if cursor == 0 or keys_scanned >= max_keys_to_scan:
                    break

            # Sort ALL sampled keys by memory and return top_n
            return sorted(hotspots, key=lambda x: x["memory_bytes"], reverse=True)[:top_n]

        except Exception as e:
            logger.warning(f"Failed to collect memory hotspots: {e}")
            return []
