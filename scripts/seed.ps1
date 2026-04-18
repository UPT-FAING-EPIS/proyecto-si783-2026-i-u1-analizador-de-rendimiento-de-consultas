#!/usr/bin/env powershell
# Seed databases with test data

Write-Host "Seeding databases with test data..." -ForegroundColor Green
Write-Host ""

# PostgreSQL Seeding
Write-Host "PostgreSQL..." -ForegroundColor Cyan
$postgresScript = Get-Content "docker/seed/init-postgres.sql" -Raw
$postgresScript | docker compose -f docker/compose.yml exec -T postgres psql -U qa -d query_analyzer

if ($LASTEXITCODE -ne 0) {
    Write-Host "PostgreSQL seeding warning" -ForegroundColor Yellow
}
Write-Host "PostgreSQL seeded!" -ForegroundColor Green
Write-Host ""

# MySQL Seeding
Write-Host "MySQL..." -ForegroundColor Cyan
$mysqlScript = Get-Content "docker/seed/init-mysql.sql" -Raw
$mysqlScript | docker compose -f docker/compose.yml exec -T mysql mysql -u qa -pQAnalyze query_analyzer

if ($LASTEXITCODE -eq 0) {
    Write-Host "MySQL seeded!" -ForegroundColor Green
} else {
    Write-Host "MySQL seeding failed!" -ForegroundColor Red
    exit 1
}
Write-Host ""

# SQLite Seeding
Write-Host "SQLite..." -ForegroundColor Cyan
& uv run python scripts/seed_sqlite.py query_analyzer.db docker/seed/init-sqlite.sql

if ($LASTEXITCODE -eq 0) {
    Write-Host "SQLite seeded!" -ForegroundColor Green
} else {
    Write-Host "SQLite seeding warning (non-critical)" -ForegroundColor Yellow
}
Write-Host ""

# CockroachDB Seeding
Write-Host "CockroachDB..." -ForegroundColor Cyan
$cockroachScript = Get-Content "docker/seed/init-cockroachdb.sql" -Raw
$cockroachScript | docker compose -f docker/compose.yml exec -T cockroachdb cockroach sql --insecure

if ($LASTEXITCODE -eq 0) {
    Write-Host "CockroachDB seeded!" -ForegroundColor Green
} else {
    Write-Host "CockroachDB seeding warning" -ForegroundColor Yellow
}
Write-Host ""

# YugabyteDB Seeding
Write-Host "YugabyteDB..." -ForegroundColor Cyan
$yugabyteScript = Get-Content "docker/seed/init-yugabytedb.sql" -Raw

# Wait for YugabyteDB YSQL to be ready (takes 60+ seconds) with retry mechanism
Write-Host "  Waiting for YSQL port to be ready..." -ForegroundColor Gray
$yugabyteReady = $false
for ($i = 1; $i -le 12; $i++) {
    try {
        $testResult = docker compose -f docker/compose.yml exec -T yugabytedb ysqlsh -U yugabyte -d query_analyzer -c "\dt" 2>$null
        $yugabyteReady = $true
        Write-Host "  YSQL port ready, seeding..." -ForegroundColor Gray
        Write-Host "  [$(Get-Date -Format 'HH:mm:ss')] Executing seed script..." -ForegroundColor Gray

        # Execute seed script without stderr redirection to properly capture exit code
        $yugabyteScript | docker compose -f docker/compose.yml exec -T yugabytedb ysqlsh -U yugabyte -d query_analyzer
        $exitCode = $LASTEXITCODE

        if ($exitCode -eq 0) {
            Write-Host "  [$(Get-Date -Format 'HH:mm:ss')] Seed completed successfully" -ForegroundColor Gray
            Write-Host "YugabyteDB seeded!" -ForegroundColor Green
        } else {
            Write-Host "  [$(Get-Date -Format 'HH:mm:ss')] Seed command returned exit code: $exitCode" -ForegroundColor Yellow
            Write-Host "YugabyteDB seeding warning (check logs above)" -ForegroundColor Yellow
        }
        break
    } catch {
        if ($i -lt 12) {
            Write-Host "  Attempt $i/12: YSQL not ready, waiting 10s..." -ForegroundColor Gray
            Start-Sleep -Seconds 10
        }
    }
}

if (-not $yugabyteReady) {
    Write-Host "YugabyteDB seeding warning (YSQL port not ready after 120s)" -ForegroundColor Yellow
}
Write-Host ""

# MongoDB Seeding
Write-Host "MongoDB..." -ForegroundColor Cyan

# Clear existing data
docker compose -f docker/compose.yml exec -T mongodb mongosh --authenticationDatabase admin -u admin -p mongodb123 query_analyzer --eval "db.orders.deleteMany({});" 2>$null

# Seed orders collection
$ordersScript = Get-Content "docker/seed/init-mongodb.json" -Raw
$ordersScript | docker compose -f docker/compose.yml exec -T mongodb mongosh --authenticationDatabase admin -u admin -p mongodb123 query_analyzer --eval "db.orders.insertMany(JSON.parse(require('fs').readFileSync('/dev/stdin', 'utf8')))"

# Seed users collection with index
$usersScript = Get-Content "docker/seed/init-mongodb-users.json" -Raw
$usersScript | docker compose -f docker/compose.yml exec -T mongodb mongosh --authenticationDatabase admin -u admin -p mongodb123 query_analyzer --eval "db.users.deleteMany({}); db.users.insertMany(JSON.parse(require('fs').readFileSync('/dev/stdin', 'utf8'))); db.users.createIndex({'email': 1});"

# Seed logs collection without index (for COLLSCAN test)
$logsScript = Get-Content "docker/seed/init-mongodb-logs.json" -Raw
$logsScript | docker compose -f docker/compose.yml exec -T mongodb mongosh --authenticationDatabase admin -u admin -p mongodb123 query_analyzer --eval "db.logs.deleteMany({}); db.logs.insertMany(JSON.parse(require('fs').readFileSync('/dev/stdin', 'utf8')));"

if ($LASTEXITCODE -eq 0) {
    Write-Host "MongoDB seeded!" -ForegroundColor Green
} else {
    Write-Host "MongoDB seeding warning" -ForegroundColor Yellow
}
Write-Host ""

# InfluxDB Seeding
Write-Host "InfluxDB..." -ForegroundColor Cyan

$env:INFLUXDB_HOST = "localhost"
$env:INFLUXDB_PORT = "8086"
$env:INFLUXDB_TOKEN = "influxdb123"
$env:INFLUXDB_ORG = ""
$env:INFLUXDB_BUCKET = "query_analyzer"

& python docker/seed/init-influxdb.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "InfluxDB seeded!" -ForegroundColor Green
} else {
    Write-Host "InfluxDB seeding warning (non-critical)" -ForegroundColor Yellow
}
Write-Host ""

# Redis Seeding
Write-Host "Redis..." -ForegroundColor Cyan
& python docker/seed/init-redis.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "Redis seeded!" -ForegroundColor Green
} else {
    Write-Host "Redis seeding warning (non-critical)" -ForegroundColor Yellow
}
Write-Host ""

# Neo4j Seeding
Write-Host "Neo4j..." -ForegroundColor Cyan
$neo4jScript = Get-Content "docker/seed/init-neo4j.cypher" -Raw
$neo4jScript | docker compose -f docker/compose.yml exec -T neo4j cypher-shell -u neo4j -p neo4j123 -d system --non-interactive

if ($LASTEXITCODE -eq 0) {
    Write-Host "Neo4j seeded!" -ForegroundColor Green
} else {
    Write-Host "Neo4j seeding warning (non-critical)" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "All databases seeded successfully!" -ForegroundColor Green
