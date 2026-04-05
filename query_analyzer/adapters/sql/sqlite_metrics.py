"""SQLite Metrics Helper.

Utility class for extracting metrics and statistics from SQLite databases.
"""

import sqlite3
from pathlib import Path
from typing import Any


class SQLiteMetricsHelper:
    """Static helper methods for SQLite metrics extraction."""

    @staticmethod
    def get_table_count(connection: sqlite3.Connection) -> int:
        """Count total tables in database (excluding system tables).

        Args:
            connection: Active SQLite connection

        Returns:
            Number of user tables
        """
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception:
            return 0

    @staticmethod
    def get_index_count(connection: sqlite3.Connection) -> int:
        """Count total indexes in database (excluding system indexes).

        Args:
            connection: Active SQLite connection

        Returns:
            Number of user-defined indexes
        """
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
            )
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception:
            return 0

    @staticmethod
    def get_database_size(connection: sqlite3.Connection, db_path: str | Path) -> int:
        """Get database file size in bytes.

        Args:
            connection: Active SQLite connection (for consistency, not used directly)
            db_path: Path to SQLite database file

        Returns:
            File size in bytes (or -1 if unavailable)
        """
        try:
            db_path = Path(db_path)
            if db_path.exists():
                return db_path.stat().st_size
            return -1
        except Exception:
            return -1

    @staticmethod
    def get_page_stats(connection: sqlite3.Connection) -> dict[str, Any]:
        """Get page configuration and statistics.

        Args:
            connection: Active SQLite connection

        Returns:
            Dict with: page_size, page_count, total_size_bytes
        """
        try:
            cursor = connection.cursor()

            # Get page size
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]

            # Get page count
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]

            return {
                "page_size": page_size,
                "page_count": page_count,
                "total_size_bytes": page_size * page_count,
            }
        except Exception:
            return {"page_size": -1, "page_count": -1, "total_size_bytes": -1}

    @staticmethod
    def get_cache_settings(connection: sqlite3.Connection) -> dict[str, Any]:
        """Get cache configuration.

        Args:
            connection: Active SQLite connection

        Returns:
            Dict with: cache_size, cache_size_bytes
        """
        try:
            cursor = connection.cursor()

            cursor.execute("PRAGMA cache_size")
            cache_size = cursor.fetchone()[0]

            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]

            cache_bytes = abs(cache_size) * page_size if cache_size > 0 else abs(cache_size)

            return {
                "cache_size_pages": cache_size,
                "cache_size_bytes": cache_bytes,
                "page_size": page_size,
            }
        except Exception:
            return {"cache_size_pages": -1, "cache_size_bytes": -1, "page_size": -1}

    @staticmethod
    def get_pragmas(connection: sqlite3.Connection) -> dict[str, Any]:
        """Get useful PRAGMA settings.

        Args:
            connection: Active SQLite connection

        Returns:
            Dict with pragma values
        """
        pragma_settings = {
            "journal_mode": "PRAGMA journal_mode",
            "foreign_keys": "PRAGMA foreign_keys",
            "synchronous": "PRAGMA synchronous",
            "query_only": "PRAGMA query_only",
        }

        result = {}
        try:
            cursor = connection.cursor()
            for key, pragma in pragma_settings.items():
                try:
                    cursor.execute(pragma)
                    value = cursor.fetchone()
                    result[key] = value[0] if value else None
                except Exception:
                    result[key] = None
        except Exception:
            pass

        return result

    @staticmethod
    def get_table_info(connection: sqlite3.Connection, table: str) -> dict[str, Any]:
        """Get information about a specific table.

        Args:
            connection: Active SQLite connection
            table: Table name

        Returns:
            Dict with: column_count, has_primary_key, indexed_columns
        """
        try:
            cursor = connection.cursor()

            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()

            has_pk = any(col[5] == 1 for col in columns)  # pk column is index 5

            cursor.execute(f"PRAGMA index_list({table})")
            indexes = cursor.fetchall()
            indexed_columns = [idx[2] for idx in indexes]

            return {
                "column_count": len(columns),
                "has_primary_key": has_pk,
                "indexed_columns": indexed_columns,
                "columns": [col[1] for col in columns],
            }
        except Exception:
            return {
                "column_count": 0,
                "has_primary_key": False,
                "indexed_columns": [],
                "columns": [],
            }

    @staticmethod
    def list_tables(connection: sqlite3.Connection) -> list[str]:
        """Get list of all user tables.

        Args:
            connection: Active SQLite connection

        Returns:
            List of table names
        """
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
            return [row[0] for row in cursor.fetchall()]
        except Exception:
            return []
