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
from .models import ConnectionConfig, QueryAnalysisReport
from .nosql import MongoDBAdapter
from .registry import AdapterRegistry
from .sql import (
    CockroachDBAdapter,
    CockroachDBMetricsHelper,
    PostgreSQLAdapter,
    PostgreSQLExplainParser,
    PostgreSQLMetricsHelper,
    YugabyteDBAdapter,
    YugabyteDBParser,
)

__all__ = [
    # Models
    "ConnectionConfig",
    "QueryAnalysisReport",
    # Base
    "BaseAdapter",
    # Registry
    "AdapterRegistry",
    # SQL Adapters
    "CockroachDBAdapter",
    "CockroachDBMetricsHelper",
    "PostgreSQLAdapter",
    "PostgreSQLExplainParser",
    "PostgreSQLMetricsHelper",
    "YugabyteDBAdapter",
    "YugabyteDBParser",
    # NoSQL Adapters
    "MongoDBAdapter",
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
