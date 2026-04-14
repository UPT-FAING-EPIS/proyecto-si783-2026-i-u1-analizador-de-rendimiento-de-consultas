"""Adapters module - Drivers por motor de base de datos."""

from .base import BaseAdapter
from .exceptions import (
    AdapterError,
    ConnectionConfigError,
    ConnectionError,
    DisconnectionError,
    QueryAnalysisError,
    UnsupportedEngineError,
)
from .graph import Neo4jAdapter
from .models import (
    ConnectionConfig,
    PlanNode,
    QueryAnalysisReport,
    Recommendation,
    Warning,
)
from .nosql import CassandraAdapter, DynamoDBAdapter, MongoDBAdapter
from .registry import AdapterRegistry
from .sql import (
    CockroachDBAdapter,
    CockroachDBMetricsHelper,
    MySQLAdapter,
    PostgreSQLAdapter,
    PostgreSQLExplainParser,
    PostgreSQLMetricsHelper,
    YugabyteDBAdapter,
    YugabyteDBParser,
)
from .timeseries import InfluxDBAdapter

__all__ = [
    # Models
    "ConnectionConfig",
    "PlanNode",
    "QueryAnalysisReport",
    "Warning",
    "Recommendation",
    # Base
    "BaseAdapter",
    # Registry
    "AdapterRegistry",
    # SQL Adapters
    "CockroachDBAdapter",
    "CockroachDBMetricsHelper",
    "MySQLAdapter",
    "PostgreSQLAdapter",
    "PostgreSQLExplainParser",
    "PostgreSQLMetricsHelper",
    "YugabyteDBAdapter",
    "YugabyteDBParser",
    # NoSQL Adapters
    "CassandraAdapter",
    "DynamoDBAdapter",
    "MongoDBAdapter",
    # TimeSeries Adapters
    "InfluxDBAdapter",
    # Graph Adapters
    "Neo4jAdapter",
    # Exceptions
    "AdapterError",
    "ConnectionError",
    "ConnectionConfigError",
    "QueryAnalysisError",
    "DisconnectionError",
    "UnsupportedEngineError",
]
