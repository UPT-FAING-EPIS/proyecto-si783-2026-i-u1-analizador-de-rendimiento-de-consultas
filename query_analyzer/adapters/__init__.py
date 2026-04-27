"""Adapters module - Drivers por motor de base de datos."""

from typing import TYPE_CHECKING

from .base import BaseAdapter

try:
    from .elasticsearch import ElasticsearchAdapter
except ImportError:
    ElasticsearchAdapter = None  # type: ignore[assignment,misc]

if TYPE_CHECKING:
    from .elasticsearch import ElasticsearchAdapter as ElasticsearchAdapterType  # noqa: F401

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
from .redis import RedisAdapter
from .registry import AdapterRegistry

try:
    from .sql import MSSQLAdapter, MSSQLExplainParser, MSSQLMetricsHelper
except ImportError:
    MSSQLAdapter = None  # type: ignore[assignment,misc]
    MSSQLExplainParser = None  # type: ignore[assignment,misc]
    MSSQLMetricsHelper = None  # type: ignore[assignment,misc]

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
    # Cache Adapters
    "RedisAdapter",
    # SQL Server Adapters
    *(["MSSQLAdapter"] if MSSQLAdapter is not None else []),
    *(["MSSQLExplainParser"] if MSSQLExplainParser is not None else []),
    *(["MSSQLMetricsHelper"] if MSSQLMetricsHelper is not None else []),
    # Search Adapters
    *(["ElasticsearchAdapter"] if ElasticsearchAdapter is not None else []),
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
