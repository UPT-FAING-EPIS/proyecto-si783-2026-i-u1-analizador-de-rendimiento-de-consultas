from typing import Any


class MySQLMetricsHelper:
    @staticmethod
    def get_table_count(connection: Any) -> int:
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE()"
            )
            result = cursor.fetchone()
            cursor.close()
            return result[0] if result else 0
        except Exception:
            return 0

    @staticmethod
    def get_index_count(connection: Any) -> int:
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT COUNT(DISTINCT INDEX_NAME) FROM information_schema.statistics "
                "WHERE table_schema = DATABASE() AND INDEX_NAME != 'PRIMARY'"
            )
            result = cursor.fetchone()
            cursor.close()
            return result[0] if result else 0
        except Exception:
            return 0

    @staticmethod
    def get_database_size(connection: Any) -> int:
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT SUM(data_length + index_length) FROM information_schema.tables "
                "WHERE table_schema = DATABASE()"
            )
            result = cursor.fetchone()
            cursor.close()
            return result[0] if result and result[0] is not None else 0
        except Exception:
            return 0

    @staticmethod
    def get_table_info(connection: Any, table_name: str) -> dict[str, Any]:
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT TABLE_ROWS, DATA_LENGTH, INDEX_LENGTH "
                "FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = %s",
                (table_name,),
            )
            result = cursor.fetchone()
            cursor.close()

            if result:
                return {
                    "table_name": table_name,
                    "rows": result[0] or 0,
                    "data_length": result[1] or 0,
                    "index_length": result[2] or 0,
                    "total_length": (result[1] or 0) + (result[2] or 0),
                }
            return {"table_name": table_name, "rows": 0, "data_length": 0}
        except Exception:
            return {"table_name": table_name, "rows": 0, "data_length": 0}

    @staticmethod
    def list_tables(connection: Any) -> list[str]:
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT TABLE_NAME FROM information_schema.tables "
                "WHERE table_schema = DATABASE()"
            )
            results = cursor.fetchall()
            cursor.close()
            return [row[0] for row in results] if results else []
        except Exception:
            return []

    @staticmethod
    def get_engine_version(connection: Any) -> str:
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT VERSION()")
            result = cursor.fetchone()
            cursor.close()
            return result[0] if result else "unknown"
        except Exception:
            return "unknown"

    @staticmethod
    def get_pragmas(connection: Any) -> dict[str, Any]:
        try:
            cursor = connection.cursor()
            vars_to_get = [
                "max_connections",
                "max_allowed_packet",
                "tmp_table_size",
                "max_heap_table_size",
                "query_cache_size",
                "query_cache_type",
                "sort_buffer_size",
            ]

            result = {}
            for var in vars_to_get:
                try:
                    cursor.execute("SHOW VARIABLES LIKE %s", (var,))
                    row = cursor.fetchone()
                    if row:
                        result[var] = row[1]
                except Exception:
                    pass

            cursor.close()
            return result
        except Exception:
            return {}

    @staticmethod
    def get_slow_queries(
        connection: Any, threshold_ms: int = 1000
    ) -> list[dict[str, Any]]:
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT query_text, execution_time_ms FROM slow_queries_log "
                "WHERE execution_time_ms > %s ORDER BY execution_time_ms DESC LIMIT 100",
                (threshold_ms,),
            )
            results = cursor.fetchall()
            cursor.close()

            if not results:
                return []

            return [
                {
                    "query": row[0],
                    "execution_time_ms": row[1],
                }
                for row in results
            ]
        except Exception:
            return []
