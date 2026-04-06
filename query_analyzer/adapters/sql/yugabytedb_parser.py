"""YugabyteDB EXPLAIN plan parser and analyzer.

YugabyteDB is PostgreSQL-compatible and uses standard PostgreSQL EXPLAIN output.
Unlike CockroachDB, distribution is implicit (handled by DocDB storage layer) and
not visible in query plans. For MVP, we reuse PostgreSQLExplainParser directly.

Future enhancements (v1.1):
- Detect colocation hints in query context (via system queries)
- Extract tablet-level metrics (yb_local_tablets(), yb_tablet_servers())
- Warn on potential inter-tablet seeks and cross-region patterns
"""

from query_analyzer.adapters.sql.postgresql_parser import PostgreSQLExplainParser


class YugabyteDBParser(PostgreSQLExplainParser):
    """YugabyteDB parser extending PostgreSQL parser.

    YugabyteDB implements PostgreSQL wire protocol and standard EXPLAIN format.
    Distribution is transparent to the query optimizer (handled by DocDB), so
    node types are identical to PostgreSQL.

    For MVP (v1), this is a minimal wrapper. Future versions will add:
    - Tablet distribution detection via system tables
    - Colocation warnings
    - Cross-region query detection

    Attributes:
        seq_scan_threshold: Row count threshold for Seq Scan warning (inherited)
    """

    def __init__(self, seq_scan_threshold: int = 10000) -> None:
        """Initialize YugabyteDB parser.

        Args:
            seq_scan_threshold: Table row count threshold for Seq Scan warning
                (default: 10000)
        """
        super().__init__(seq_scan_threshold=seq_scan_threshold)
