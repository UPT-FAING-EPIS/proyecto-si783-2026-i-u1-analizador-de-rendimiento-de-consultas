"""Adapters module - Drivers por motor de base de datos."""

from .base import BaseAdapter
from .exceptions import (
    AdapterException,
    ConnectionConfigError,
    ConnectionError,
    DisconnectionError,
    QueryAnalysisError,
    UnsupportedEngineError,
)
from .models import ConnectionConfig, QueryAnalysisReport
from .registry import AdapterRegistry

__all__ = [
    # Models
    "ConnectionConfig",
    "QueryAnalysisReport",
    # Base
    "BaseAdapter",
    # Registry
    "AdapterRegistry",
    # Exceptions
    "AdapterException",
    "ConnectionError",
    "ConnectionConfigError",
    "QueryAnalysisError",
    "DisconnectionError",
    "UnsupportedEngineError",
]
