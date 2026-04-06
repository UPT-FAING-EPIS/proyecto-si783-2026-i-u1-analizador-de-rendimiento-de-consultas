"""PostgreSQL metrics extraction utilities."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PostgreSQLMetricsHelper:
    """Helper class for extracting system metrics from PostgreSQL."""

    @staticmethod
    def get_db_stats(connection: Any) -> dict[str, Any]:
        """Extract database statistics from pg_stat_database.

        Args:
            connection: psycopg2 connection object

        Returns:
            Dict with database statistics (empty dict if query fails; strategy: fail-safe).

        Note:
            Errores en consultas retornan dict vacío en lugar de propagar
            excepciones, permitiendo análisis parcial.
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        datname,
                        numbackends,
                        tup_returned,
                        tup_fetched,
                        tup_inserted,
                        tup_updated,
                        tup_deleted,
                        conflicts,
                        xact_commit,
                        xact_rollback
                    FROM pg_stat_database
                    WHERE datname = current_database()
                    """
                )
                row = cursor.fetchone()

                if not row:
                    return {}

                return {
                    "database": row[0],
                    "active_connections": int(row[1]),
                    "tup_returned": int(row[2]),
                    "tup_fetched": int(row[3]),
                    "tup_inserted": int(row[4]),
                    "tup_updated": int(row[5]),
                    "tup_deleted": int(row[6]),
                    "conflicts": int(row[7]),
                    "transactions_committed": int(row[8]),
                    "transactions_rolled_back": int(row[9]),
                }
        except Exception as e:
            logger.debug(f"Failed to get database stats: {e}")
            return {}

    @staticmethod
    def get_cache_hit_ratio(connection: Any) -> float:
        """Calculate cache hit ratio from pg_statio_user_tables.

        Returns:
            Float between 0 and 1 (-1.0 if unable to calculate; strategy: fail-safe).

        Note:
            Errores en consultas retornan -1.0 en lugar de propagar excepciones,
            permitiendo análisis parcial.
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        COALESCE(SUM(heap_blks_hit), 0) as cache_hit,
                        COALESCE(SUM(heap_blks_read), 0) as cache_read
                    FROM pg_statio_user_tables
                    """
                )
                hit, read = cursor.fetchone()

                total = hit + read
                if total == 0:
                    return 1.0

                return float(hit / total)
        except Exception as e:
            logger.debug(f"Failed to get cache hit ratio: {e}")
            return -1.0

    @staticmethod
    def get_settings(connection: Any, setting_names: list[str]) -> dict[str, str]:
        """Get PostgreSQL configuration settings.

        Args:
            connection: psycopg2 connection object
            setting_names: List of setting names to retrieve

        Returns:
            Dict mapping setting names to their values (empty dict if query fails; strategy: fail-safe).

        Note:
            Errores en consultas retornan dict vacío en lugar de propagar
            excepciones, permitiendo análisis parcial.
        """
        try:
            with connection.cursor() as cursor:
                result = {}
                for setting in setting_names:
                    cursor.execute("SHOW %s", (setting,))
                    value = cursor.fetchone()
                    if value:
                        result[setting] = value[0]
                return result
        except Exception as e:
            logger.debug(f"Failed to get settings: {e}")
            return {}

    @staticmethod
    def check_pg_stat_statements_available(connection: Any) -> bool:
        """Check if pg_stat_statements extension is installed and available.

        Args:
            connection: psycopg2 connection object

        Returns:
            True if extension is available, False otherwise (returns False if query fails; strategy: fail-safe).

        Note:
            Errores en consultas retornan False en lugar de propagar excepciones,
            permitiendo análisis parcial.
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = 'pg_stat_statements'
                    )
                    """
                )
                exists = cursor.fetchone()[0]
                return bool(exists)
        except Exception as e:
            logger.debug(f"Failed to check pg_stat_statements: {e}")
            return False

    @staticmethod
    def get_slow_queries_from_pg_stat_statements(
        connection: Any, threshold_ms: int = 1000, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get slow queries from pg_stat_statements.

        Args:
            connection: psycopg2 connection object
            threshold_ms: Threshold in milliseconds
            limit: Maximum number of queries to return

        Returns:
            List of dicts with query and timing information (empty list if query fails; strategy: fail-safe).

        Note:
            Errores en consultas retornan lista vacía en lugar de propagar
            excepciones, permitiendo análisis parcial.
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        query,
                        calls,
                        total_time,
                        mean_time,
                        max_time,
                        min_time
                    FROM pg_stat_statements
                    WHERE mean_time > %s
                    ORDER BY mean_time DESC
                    LIMIT %s
                    """,
                    (threshold_ms, limit),
                )

                results = []
                for row in cursor.fetchall():
                    results.append(
                        {
                            "query": row[0],
                            "calls": int(row[1]),
                            "total_time_ms": float(row[2]),
                            "mean_time_ms": float(row[3]),
                            "max_time_ms": float(row[4]),
                            "min_time_ms": float(row[5]),
                        }
                    )
                return results
        except Exception as e:
            logger.debug(f"Failed to get slow queries: {e}")
            return []
