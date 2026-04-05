"""CockroachDB metrics helper.

Minimal scope for v1: only non-admin queries.
Node count, replication factor → v2 (require admin privileges).
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class CockroachDBMetricsHelper:
    """Helper for CockroachDB metrics extraction.

    Provides minimal metrics for v1, non-admin queries only.
    """

    @staticmethod
    def get_version(connection: Any) -> str:
        """Get CockroachDB version string.

        Args:
            connection: psycopg2 connection object

        Returns:
            Version string, or empty string if query fails
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT version()")
                result = cursor.fetchone()
                if result is not None:
                    return str(result[0])
                return ""
        except Exception as e:
            logger.warning(f"Failed to get version: {e}")
            return ""

    @staticmethod
    def get_node_count(connection: Any) -> int:
        """Try to get node count from crdb_internal.node_build_info.

        Silently returns 0 if permission denied (non-admin user).

        Args:
            connection: psycopg2 connection object

        Returns:
            Node count, or 0 if unavailable (expected for non-admin)
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM crdb_internal.node_build_info")
                return int(cursor.fetchone()[0])
        except Exception as e:
            logger.debug(f"Node count unavailable (expected for non-admin): {e}")
            return 0
