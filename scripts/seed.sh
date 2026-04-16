#!/bin/bash

# Seed databases with test data
# This script works on Linux, macOS, and in GitHub Actions

echo "Seeding databases with test data..."
echo ""

# PostgreSQL Seeding
echo "PostgreSQL..."
cat docker/seed/init-postgres.sql | docker compose -f docker/compose.yml exec -T postgres psql -U qa -d query_analyzer

if [ $? -ne 0 ]; then
    echo "PostgreSQL seeding warning (non-critical)"
fi
echo "PostgreSQL seeded!"
echo ""

# MySQL Seeding
echo "MySQL..."
cat docker/seed/init-mysql.sql | docker compose -f docker/compose.yml exec -T mysql mysql -u qa -pQAnalyze query_analyzer

if [ $? -eq 0 ]; then
    echo "MySQL seeded!"
else
    echo "MySQL seeding failed!"
    exit 1
fi
echo ""

# SQLite Seeding
echo "SQLite..."
if command -v sqlite3 &> /dev/null; then
    sqlite3 query_analyzer.db < docker/seed/init-sqlite.sql
else
    # Use Python if sqlite3 CLI not available
    python3 << 'EOF'
import sqlite3
with open('docker/seed/init-sqlite.sql', 'r') as f:
    sql = f.read()
conn = sqlite3.connect('query_analyzer.db')
cursor = conn.cursor()
for statement in sql.split(';'):
    if statement.strip():
        cursor.execute(statement)
conn.commit()
conn.close()
print("SQLite seeded!")
EOF
fi

if [ $? -eq 0 ]; then
    echo "SQLite seeded!"
else
    echo "SQLite seeding warning (non-critical)"
fi
echo ""

# CockroachDB Seeding
echo "CockroachDB..."
cat docker/seed/init-cockroachdb.sql | docker compose -f docker/compose.yml exec -T cockroachdb cockroach sql --insecure

if [ $? -eq 0 ]; then
    echo "CockroachDB seeded!"
else
    echo "CockroachDB seeding warning (non-critical)"
fi
echo ""

# YugabyteDB Seeding
echo "YugabyteDB..."
# Wait for YugabyteDB YSQL to be ready (takes 60+ seconds)
# with retry mechanism
echo "  Waiting for YSQL port to be ready..."
for i in {1..12}; do
    if docker compose -f docker/compose.yml exec -T yugabytedb ysqlsh -U yugabyte -d query_analyzer -c "\dt" 2>/dev/null | head -1 > /dev/null 2>&1; then
        echo "  YSQL port ready, seeding..."
        echo "  [$(date '+%H:%M:%S')] Executing seed script..."

        # Execute seed script without stderr redirection to properly capture exit code
        cat docker/seed/init-yugabytedb.sql | docker compose -f docker/compose.yml exec -T yugabytedb ysqlsh -U yugabyte -d query_analyzer
        exitCode=$?

        if [ $exitCode -eq 0 ]; then
            echo "  [$(date '+%H:%M:%S')] Seed completed successfully"
            echo "YugabyteDB seeded!"
        else
            echo "  [$(date '+%H:%M:%S')] Seed command returned exit code: $exitCode"
            echo "YugabyteDB seeding warning (check logs above)"
        fi
        break
    fi
    if [ $i -lt 12 ]; then
        echo "  Attempt $i/12: YSQL not ready, waiting 10s..."
        sleep 10
    fi
done
if [ $i -eq 12 ]; then
    echo "YugabyteDB seeding warning (YSQL port not ready after 120s)"
fi
echo ""

# MongoDB Seeding
echo "MongoDB..."

# Clear existing data
docker compose -f docker/compose.yml exec -T mongodb mongosh --authenticationDatabase admin -u admin -p mongodb123 query_analyzer --eval "db.orders.deleteMany({});" 2>/dev/null

# Seed orders collection
cat docker/seed/init-mongodb.json | docker compose -f docker/compose.yml exec -T mongodb mongosh --authenticationDatabase admin -u admin -p mongodb123 query_analyzer --eval "db.orders.insertMany(JSON.parse(require('fs').readFileSync('/dev/stdin', 'utf8')))"

# Seed users collection with index
cat docker/seed/init-mongodb-users.json | docker compose -f docker/compose.yml exec -T mongodb mongosh --authenticationDatabase admin -u admin -p mongodb123 query_analyzer --eval "db.users.deleteMany({}); db.users.insertMany(JSON.parse(require('fs').readFileSync('/dev/stdin', 'utf8'))); db.users.createIndex({'email': 1});"

# Seed logs collection without index (for COLLSCAN test)
cat docker/seed/init-mongodb-logs.json | docker compose -f docker/compose.yml exec -T mongodb mongosh --authenticationDatabase admin -u admin -p mongodb123 query_analyzer --eval "db.logs.deleteMany({}); db.logs.insertMany(JSON.parse(require('fs').readFileSync('/dev/stdin', 'utf8')));"

if [ $? -eq 0 ]; then
    echo "MongoDB seeded!"
else
    echo "MongoDB seeding warning (non-critical)"
fi
echo ""

echo "All databases seeded successfully!"
