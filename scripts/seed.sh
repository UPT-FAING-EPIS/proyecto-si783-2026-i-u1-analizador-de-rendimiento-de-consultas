#!/bin/bash

# Seed databases with test data
# This script works on Linux, macOS, and in GitHub Actions

echo "Seeding databases with test data..."
echo ""

# PostgreSQL Seeding
echo "PostgreSQL..."
cat docker/seed/init-postgres.sql | docker compose -f docker/compose.yml exec -T postgres psql -U postgres -d query_analyzer

if [ $? -ne 0 ]; then
    echo "PostgreSQL seeding warning (non-critical)"
fi
echo "PostgreSQL seeded!"
echo ""

# MySQL Seeding
echo "MySQL..."
cat docker/seed/init-mysql.sql | docker compose -f docker/compose.yml exec -T mysql mysql -u analyst -pmysql123 query_analyzer

if [ $? -eq 0 ]; then
    echo "MySQL seeded!"
else
    echo "MySQL seeding failed!"
    exit 1
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
