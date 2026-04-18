#!/usr/bin/env python3
"""Clear Neo4j database."""

from neo4j import GraphDatabase

uri = "bolt://localhost:7687"
driver = GraphDatabase.driver(uri, auth=("neo4j", "neo4j123"))

with driver.session(database="neo4j") as session:
    session.run("MATCH (n) DETACH DELETE n")
    print("[OK] Database cleared")

driver.close()
