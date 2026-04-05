"""CockroachDB EXPLAIN parser.

Per YAGNI principle, we reuse PostgreSQLExplainParser directly without creating
a subclass. CockroachDB's JSON format (via wire protocol) is compatible with
PostgreSQL's JSON output.

If CRDB-specific node types or metrics emerge during testing, create
CockroachDBExplainParser subclass in this file. For now: direct reuse.
"""

# Placeholder for potential future subclass
# For v1: import PostgreSQLExplainParser in adapter and use directly
#
# Example of future subclass (if needed):
#
# from .postgresql_parser import PostgreSQLExplainParser
#
# class CockroachDBExplainParser(PostgreSQLExplainParser):
#     """CockroachDB-specific parser with custom node handling."""
#
#     def _categorize_joins(self, all_nodes: list[dict[str, Any]]) -> ...:
#         # Override if CRDB join types differ significantly
#         pass
