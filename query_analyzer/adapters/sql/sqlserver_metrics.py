"""SQL Server metrics helper using DMV queries."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class MSSQLMetricsHelper:
    """Helper to query SQL Server DMVs for metrics and engine info."""

    @staticmethod
    def get_version(connection: Any) -> str:
        """Get SQL Server version via SELECT @@VERSION."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT @@VERSION")
                row = cursor.fetchone()
                return row[0] if row else "unknown"
        except Exception as e:
            logger.debug(f"Failed to get version: {e}")
            return "unknown"

    @staticmethod
    def get_product_version(connection: Any) -> str:
        """Get product version via SERVERPROPERTY."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT CAST(SERVERPROPERTY('ProductVersion') AS NVARCHAR(128))")
                row = cursor.fetchone()
                return row[0] if row else "unknown"
        except Exception as e:
            logger.debug(f"Failed to get product version: {e}")
            return "unknown"

    @staticmethod
    def get_edition(connection: Any) -> str:
        """Get edition via SERVERPROPERTY."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT CAST(SERVERPROPERTY('Edition') AS NVARCHAR(128))")
                row = cursor.fetchone()
                return row[0] if row else "unknown"
        except Exception as e:
            logger.debug(f"Failed to get edition: {e}")
            return "unknown"

    @staticmethod
    def get_db_stats(connection: Any) -> dict[str, Any]:
        """Get database-level metrics from DMVs."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM sys.dm_exec_connections")
                active_connections = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT counter_name, cntr_value
                    FROM sys.dm_os_performance_counters
                    WHERE counter_name IN (
                        'Batch Requests/sec',
                        'SQL Compilations/sec',
                        'SQL Re-Compilations/sec',
                        'User Connections'
                    )
                """)
                perf_dict = {}
                for row in cursor.fetchall():
                    key = row[0].replace(" ", "_").replace("/", "_").lower()
                    perf_dict[key] = row[1]

                return {
                    "active_connections": int(active_connections),
                    **perf_dict,
                }
        except Exception as e:
            logger.debug(f"Failed to get DB stats: {e}")
            return {}

    @staticmethod
    def get_slow_queries_from_dmv(
        connection: Any, threshold_ms: int = 1000, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get slow queries from sys.dm_exec_query_stats."""
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT TOP (%s)
                        SUBSTRING(st.text,
                            (qs.statement_start_offset/2)+1,
                            ((CASE qs.statement_end_offset
                                WHEN -1 THEN DATALENGTH(st.text)
                                ELSE qs.statement_end_offset
                             END - qs.statement_start_offset)/2)+1
                        ) AS query_text,
                        qs.execution_count,
                        qs.total_elapsed_time / 1000.0 AS total_elapsed_time_ms,
                        qs.last_elapsed_time / 1000.0 AS last_elapsed_time_ms,
                        qs.min_elapsed_time / 1000.0 AS min_elapsed_time_ms,
                        qs.max_elapsed_time / 1000.0 AS max_elapsed_time_ms,
                        qs.total_logical_reads,
                        qs.total_logical_writes,
                        qs.creation_time,
                        qs.last_execution_time
                    FROM sys.dm_exec_query_stats qs
                    CROSS APPLY sys.dm_exec_sql_text(qs.sql_handle) st
                    WHERE qs.last_elapsed_time / 1000.0 > %s
                    ORDER BY qs.last_elapsed_time DESC
                """,
                    (limit, threshold_ms),
                )

                results = []
                for row in cursor.fetchall():
                    results.append(
                        {
                            "query": row[0],
                            "execution_count": int(row[1]),
                            "total_elapsed_time_ms": float(row[2]),
                            "last_elapsed_time_ms": float(row[3]),
                            "min_elapsed_time_ms": float(row[4]),
                            "max_elapsed_time_ms": float(row[5]),
                            "total_logical_reads": int(row[6]),
                            "total_logical_writes": int(row[7]),
                            "creation_time": str(row[8]) if row[8] else None,
                            "last_execution_time": str(row[9]) if row[9] else None,
                        }
                    )
                return results
        except Exception as e:
            logger.debug(f"Failed to get slow queries: {e}")
            return []

    @staticmethod
    def get_settings(connection: Any) -> dict[str, Any]:
        """Get SQL Server configuration settings from sys.configurations."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT name, value_in_use
                    FROM sys.configurations
                    WHERE name IN (
                        'max server memory (MB)',
                        'min server memory (MB)',
                        'max degree of parallelism',
                        'cost threshold for parallelism',
                        'optimize for ad hoc workloads'
                    )
                """)
                settings = {}
                for row in cursor.fetchall():
                    key = row[0].replace(" ", "_").replace("(", "").replace(")", "")
                    settings[key] = row[1]
                return settings
        except Exception as e:
            logger.debug(f"Failed to get settings: {e}")
            return {}
