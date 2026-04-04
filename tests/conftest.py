"""Pytest configuration and shared fixtures."""

import pytest
from query_analyzer.adapters import AdapterRegistry


@pytest.fixture(autouse=True)
def ensure_postgresql_registered() -> None:
    """Ensure PostgreSQL adapter is registered before each test.

    This is needed because some tests (like adapter_registry tests) may clear
    the registry, and we need to re-register PostgreSQL for subsequent tests.
    """
    # Import to trigger registration
    from query_analyzer.adapters.sql import PostgreSQLAdapter  # noqa: F401

    # If not registered, register it
    if not AdapterRegistry.is_registered("postgresql"):
        from query_analyzer.adapters.sql import PostgreSQLAdapter as PGAdapter

        AdapterRegistry.register("postgresql")(PGAdapter)
