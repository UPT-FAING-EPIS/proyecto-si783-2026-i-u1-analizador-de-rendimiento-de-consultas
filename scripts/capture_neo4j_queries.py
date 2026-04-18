#!/usr/bin/env python3
"""Execute and save Neo4j test query results."""

import json

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

# Define the 4 queries with metadata
queries_meta = [
    {
        "name": "Q1: Simple Label Scan + WHERE",
        "type": "Single-Region Filter",
        "query": "MATCH (u:User {country: 'US'}) RETURN u.name, u.email LIMIT 10",
        "description": "Optimal query: indexed lookup by country",
        "expected_score": "95-100",
        "expected_dbhits": "50-100",
    },
    {
        "name": "Q2: Label Scan + Aggregation",
        "type": "Distributed Aggregation",
        "query": "MATCH (u:User)-[:PURCHASED]->(p:Product) WITH u.country as country, COUNT(p) as purchase_count RETURN country, purchase_count ORDER BY purchase_count DESC",
        "description": "Aggregation across all users and purchases",
        "expected_score": "85-95",
        "expected_dbhits": "500-1000",
    },
    {
        "name": "Q3: Relationship Join",
        "type": "Relationship Join",
        "query": "MATCH (u:User)-[:FOLLOWS]->(f:User)-[:PURCHASED]->(p:Product) WHERE p.price > 100 RETURN u.name, f.name, p.title LIMIT 20",
        "description": "Multi-hop relationship join with price filter",
        "expected_score": "70-85",
        "expected_dbhits": "2000-5000",
    },
    {
        "name": "Q4: Variable-Length Path (Unbounded)",
        "type": "Path Finding",
        "query": "MATCH (u:User {id: 1})-[*1..5]-(related) WHERE NOT (related:User) RETURN COUNT(distinct related)",
        "description": "Variable-length path up to 5 hops - potential performance risk",
        "expected_score": "50-70",
        "expected_dbhits": "10000+",
    },
]

results = []

for query_meta in queries_meta:
    print(f"\nExecuting {query_meta['name']}...", end=" ", flush=True)
    try:
        report = adapter.execute_explain(query_meta["query"])
        result = {
            "name": query_meta["name"],
            "type": query_meta["type"],
            "description": query_meta["description"],
            "query": query_meta["query"],
            "expected_score": query_meta["expected_score"],
            "expected_dbhits": query_meta["expected_dbhits"],
            "score": report.score,
            "execution_time_ms": report.execution_time_ms,
            "warnings_count": len(report.warnings),
            "warnings": [{"severity": w.severity, "message": w.message} for w in report.warnings],
            "recommendations_count": len(report.recommendations),
            "recommendations": report.recommendations,
        }
        results.append(result)
        print(f"OK (score: {report.score})")
    except Exception as e:
        print(f"ERROR: {str(e)[:80]}")

# Save results to JSON
with open("/tmp/neo4j_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n[OK] Results saved to /tmp/neo4j_results.json")

# Print summary
print("\nSummary:")
print(f"  Total queries: {len(results)}")
for r in results:
    print(f"  - {r['name']}: {r['score']}/100 ({r['execution_time_ms']:.1f}ms)")

adapter.disconnect()
