#!/usr/bin/env python3
"""Execute Neo4j test queries directly."""

from query_analyzer.adapters.models import ConnectionConfig
from query_analyzer.adapters.registry import AdapterRegistry
from query_analyzer.config.manager import ConfigManager

# Load config
config_manager = ConfigManager()
neo4j_profile = config_manager.get_profile("neo4j")

# Convert ProfileConfig to ConnectionConfig
neo4j_config = ConnectionConfig(
    engine=neo4j_profile.engine,
    host=neo4j_profile.host,
    port=neo4j_profile.port,
    database=neo4j_profile.database,
    username=neo4j_profile.username,
    password=neo4j_profile.password,
    extra=neo4j_profile.extra,
)

# Create adapter
adapter = AdapterRegistry.create("neo4j", neo4j_config)
adapter.connect()

# Define the 4 queries
queries = [
    (
        "Q1: Simple Label Scan + WHERE",
        "MATCH (u:User {country: 'US'}) RETURN u.name, u.email LIMIT 10",
    ),
    (
        "Q2: Label Scan + Aggregation",
        "MATCH (u:User)-[:PURCHASED]->(p:Product) WITH u.country as country, COUNT(p) as purchase_count RETURN country, purchase_count ORDER BY purchase_count DESC",
    ),
    (
        "Q3: Relationship Join",
        "MATCH (u:User)-[:FOLLOWS]->(f:User)-[:PURCHASED]->(p:Product) WHERE p.price > 100 RETURN u.name, f.name, p.title LIMIT 20",
    ),
    (
        "Q4: Variable-Length Path (Unbounded)",
        "MATCH (u:User {id: 1})-[*1..5]-(related) WHERE NOT (related:User) RETURN COUNT(distinct related)",
    ),
]

for name, query in queries:
    print(f"\n{'=' * 80}")
    print(f"{name}")
    print(f"{'=' * 80}")
    print(f"Query: {query}\n")
    try:
        report = adapter.execute_explain(query)
        print(f"Score: {report.score}")
        print(f"Execution Time: {report.execution_time_ms}ms")
        print(f"Warnings: {len(report.warnings)}")
        for w in report.warnings:
            print(f"  - {w.severity}: {w.message}")
        print(f"Recommendations: {len(report.recommendations)}")
        for r in report.recommendations:
            print(f"  - {r}")
    except Exception as e:
        print(f"ERROR: {str(e)[:200]}")

adapter.disconnect()
print("\n[OK] Query execution complete")
