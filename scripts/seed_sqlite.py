#!/usr/bin/env python3
"""Helper script to seed SQLite database from SQL file."""

import sqlite3
import sys


def seed_sqlite(db_path: str, sql_file: str) -> bool:
    """Seed SQLite database from SQL file."""
    try:
        with open(sql_file) as f:
            sql = f.read()

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Execute each statement separately
        for statement in sql.split(";"):
            stmt = statement.strip()
            if stmt:
                try:
                    cursor.execute(stmt)
                except sqlite3.Error:
                    # Continue on errors like duplicate indexes
                    pass

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "query_analyzer.db"
    sql_file = sys.argv[2] if len(sys.argv) > 2 else "docker/seed/init-sqlite.sql"

    if seed_sqlite(db_path, sql_file):
        print(f"SQLite seeded: {db_path}")
        sys.exit(0)
    else:
        print(f"Failed to seed SQLite: {db_path}", file=sys.stderr)
        sys.exit(1)
