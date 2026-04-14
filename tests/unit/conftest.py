"""Pytest configuration and fixtures for unit tests."""

import sys

import pytest


@pytest.fixture(scope="session", autouse=True)
def _ensure_all_adapters_registered() -> None:
    """Ensure all adapters are registered in AdapterRegistry.

    This fixture runs once per test session at the very beginning,
    before any test collection or execution, guaranteeing that all
    adapter imports trigger their @AdapterRegistry.register() decorators.
    """
    from query_analyzer.adapters import (  # noqa: F401
        CockroachDBAdapter,
        InfluxDBAdapter,
        MongoDBAdapter,
        MySQLAdapter,
        Neo4jAdapter,
        PostgreSQLAdapter,
        YugabyteDBAdapter,
    )


def pytest_runtest_setup(item) -> None:
    """Hook that runs BEFORE each test method is executed.

    This is the right place to re-register adapters that may have been
    cleared by clean_registry fixture, without reloading modules.
    """
    from query_analyzer.adapters import AdapterRegistry

    # Check if registry is empty (e.g., clean_registry cleared it)
    if not AdapterRegistry.list_engines():
        # Registry was cleared - re-register adapters by manually invoking
        # the @register decorator on classes already loaded in sys.modules

        adapter_classes_to_register = [
            ("query_analyzer.adapters.sql.cockroachdb", "CockroachDBAdapter", "cockroachdb"),
            ("query_analyzer.adapters.sql.mysql", "MySQLAdapter", "mysql"),
            ("query_analyzer.adapters.sql.postgresql", "PostgreSQLAdapter", "postgresql"),
            ("query_analyzer.adapters.sql.yugabytedb", "YugabyteDBAdapter", "yugabytedb"),
            ("query_analyzer.adapters.sql.sqlite", "SQLiteAdapter", "sqlite"),
            ("query_analyzer.adapters.document.mongodb", "MongoDBAdapter", "mongodb"),
            ("query_analyzer.adapters.graph.neo4j", "Neo4jAdapter", "neo4j"),
            ("query_analyzer.adapters.timeseries.influxdb", "InfluxDBAdapter", "influxdb"),
        ]

        for module_name, class_name, engine_name in adapter_classes_to_register:
            if module_name in sys.modules:
                module = sys.modules[module_name]
                if hasattr(module, class_name):
                    adapter_class = getattr(module, class_name)
                    # Manually invoke the register decorator to re-register the class
                    AdapterRegistry.register(engine_name)(adapter_class)
