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
from .models import ConnectionConfig, QueryAnalysisReport
from .registry import AdapterRegistry
from .sql import PostgreSQLAdapter, PostgreSQLExplainParser, PostgreSQLMetricsHelper

__all__ = [
    # Models
    "ConnectionConfig",
    "QueryAnalysisReport",
    # Base
    "BaseAdapter",
    # Registry
    "AdapterRegistry",
    # SQL Adapters
    "PostgreSQLAdapter",
    "PostgreSQLExplainParser",
    "PostgreSQLMetricsHelper",
    # Exceptions
    "AdapterError",
    "ConnectionError",
    "ConnectionConfigError",
    "QueryAnalysisError",
    "DisconnectionError",
    "UnsupportedEngineError",
]
