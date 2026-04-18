#!/bin/bash

# Initialize SQLite database for Query Analyzer
# This script creates a clean SQLite database with schema
# (tables, indexes) but WITHOUT data.
# Data population is handled separately by seed.sh

set -e  # Exit on error

DB_FILE="query_analyzer.db"
SCHEMA_FILE="docker/seed/init-sqlite.sql"

echo "Initializing SQLite database..."
echo ""

# Check if schema file exists
if [ ! -f "$SCHEMA_FILE" ]; then
    echo "ERROR: Schema file not found: $SCHEMA_FILE"
    exit 1
fi

# Remove existing database for clean slate
if [ -f "$DB_FILE" ]; then
    echo "Removing existing database: $DB_FILE"
    rm -f "$DB_FILE"
fi

echo "Creating new database: $DB_FILE"

# Try to use sqlite3 CLI if available
if command -v sqlite3 &> /dev/null; then
    echo "  Using sqlite3 CLI..."
    sqlite3 "$DB_FILE" < "$SCHEMA_FILE"

    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to initialize database with sqlite3"
        exit 1
    fi
else
    echo "  Using Python fallback (sqlite3 CLI not found)..."
    uv run python << 'EOF'
import sqlite3
import sys
import os

db_file = "query_analyzer.db"
schema_file = "docker/seed/init-sqlite.sql"

try:
    # Read schema file
    with open(schema_file, 'r') as f:
        sql_content = f.read()

    # Connect and execute
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Split by semicolon and execute each statement
    for statement in sql_content.split(';'):
        if statement.strip():
            cursor.execute(statement)

    conn.commit()
    conn.close()

    print("OK: Database initialized: {}".format(db_file))
except Exception as e:
    print("ERROR: {}".format(e), file=sys.stderr)
    sys.exit(1)
EOF

    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to initialize database with Python"
        exit 1
    fi
fi

echo ""
# Verify database was created
if [ -f "$DB_FILE" ]; then
    size=$(du -h "$DB_FILE" | cut -f1)
    echo "OK: SQLite database created successfully!"
    echo "   File: $DB_FILE"
    echo "   Size: $size"
else
    echo "ERROR: Database file was not created"
    exit 1
fi
