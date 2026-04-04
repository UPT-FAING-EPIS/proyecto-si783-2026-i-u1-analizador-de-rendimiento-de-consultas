"""Adapters module - Drivers por motor de base de datos."""

from .base import BaseAdapter
from .exceptions import (
    AdapterException,
    ConnectionConfigError,
    ConnectionError,
    DisconnectionError,
    QueryAnalysisError,
)
from .models import ConnectionConfig, QueryAnalysisReport

__all__ = [
    # Models
    "ConnectionConfig",
    "QueryAnalysisReport",
    # Base
    "BaseAdapter",
    # Exceptions
    "AdapterException",
    "ConnectionError",
    "ConnectionConfigError",
    "QueryAnalysisError",
    "DisconnectionError",
]
