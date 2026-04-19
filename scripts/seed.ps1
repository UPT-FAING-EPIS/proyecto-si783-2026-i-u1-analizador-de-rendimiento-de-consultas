#!/usr/bin/env powershell
# Seed databases with test data

function Invoke-SeedFile {
    param(
        [Parameter(Mandatory = $true)][string]$Service,
        [Parameter(Mandatory = $true)][string]$LocalPath,
        [Parameter(Mandatory = $true)][string]$RemotePath,
        [Parameter(Mandatory = $true)][string]$ExecCommand
    )

    $containerName = "query-analyzer-$Service"
    docker cp $LocalPath "${containerName}:$RemotePath" *> $null
    if ($LASTEXITCODE -ne 0) {
        return $false
    }

    docker compose -f docker/compose.yml exec -T $Service sh -lc $ExecCommand
    return ($LASTEXITCODE -eq 0)
}

Write-Host "Seeding databases with test data..." -ForegroundColor Green
Write-Host ""

# Prefer bash implementation on Windows when available.
# This avoids PowerShell native-pipe encoding issues and keeps behavior aligned with macOS/Linux.
$bashCommand = Get-Command bash -ErrorAction SilentlyContinue
if ($null -ne $bashCommand) {
    & bash -lc "true" *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Using bash seeding script for cross-platform compatibility..." -ForegroundColor Gray
        & bash "scripts/seed.sh"
        exit $LASTEXITCODE
    }
}

# PostgreSQL Seeding
Write-Host "PostgreSQL..." -ForegroundColor Cyan
if (-not (Invoke-SeedFile -Service "postgres" -LocalPath "docker/seed/init-postgres.sql" -RemotePath "/tmp/init-postgres.sql" -ExecCommand "psql -U qa -d query_analyzer -f /tmp/init-postgres.sql")) {
    Write-Host "PostgreSQL seeding warning" -ForegroundColor Yellow
}
Write-Host "PostgreSQL seeded!" -ForegroundColor Green
Write-Host ""

# MySQL Seeding
Write-Host "MySQL..." -ForegroundColor Cyan
if (Invoke-SeedFile -Service "mysql" -LocalPath "docker/seed/init-mysql.sql" -RemotePath "/tmp/init-mysql.sql" -ExecCommand "mysql -u qa -pQAnalyze query_analyzer < /tmp/init-mysql.sql") {
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
if (Invoke-SeedFile -Service "cockroachdb" -LocalPath "docker/seed/init-cockroachdb.sql" -RemotePath "/tmp/init-cockroachdb.sql" -ExecCommand "cockroach sql --insecure < /tmp/init-cockroachdb.sql") {
    Write-Host "CockroachDB seeded!" -ForegroundColor Green
} else {
    Write-Host "CockroachDB seeding warning" -ForegroundColor Yellow
}
Write-Host ""

# YugabyteDB Seeding
Write-Host "YugabyteDB..." -ForegroundColor Cyan
docker cp "docker/seed/init-yugabytedb.sql" "query-analyzer-yugabytedb:/tmp/init-yugabytedb.sql" *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "YugabyteDB seeding warning (failed to copy seed file)" -ForegroundColor Yellow
}

# Wait for YugabyteDB YSQL to be ready (takes 60+ seconds) with retry mechanism
Write-Host "  Waiting for YSQL port to be ready..." -ForegroundColor Gray
$yugabyteReady = $false
for ($i = 1; $i -le 12; $i++) {
    docker compose -f docker/compose.yml exec -T yugabytedb bash -lc "PGPASSWORD=yugabyte bin/ysqlsh -h yugabytedb -p 5433 -U yugabyte -d yugabyte -c 'SELECT 1'" *> $null
    if ($LASTEXITCODE -eq 0) {
        $yugabyteReady = $true
        Write-Host "  YSQL port ready, seeding..." -ForegroundColor Gray
        Write-Host "  [$(Get-Date -Format 'HH:mm:ss')] Executing seed script..." -ForegroundColor Gray

        docker compose -f docker/compose.yml exec -T yugabytedb bash -lc "PGPASSWORD=yugabyte bin/ysqlsh -h yugabytedb -p 5433 -U yugabyte -d yugabyte -c 'CREATE DATABASE query_analyzer'" *> $null

        docker compose -f docker/compose.yml exec -T yugabytedb sh -lc "PGPASSWORD=yugabyte bin/ysqlsh -h yugabytedb -p 5433 -U yugabyte -d query_analyzer < /tmp/init-yugabytedb.sql"
        $exitCode = $LASTEXITCODE

        if ($exitCode -eq 0) {
            Write-Host "  [$(Get-Date -Format 'HH:mm:ss')] Seed completed successfully" -ForegroundColor Gray
            Write-Host "YugabyteDB seeded!" -ForegroundColor Green
        } else {
            Write-Host "  [$(Get-Date -Format 'HH:mm:ss')] Seed command returned exit code: $exitCode" -ForegroundColor Yellow
            Write-Host "YugabyteDB seeding warning (check logs above)" -ForegroundColor Yellow
        }
        break
    }

    if ($i -lt 12) {
        Write-Host "  Attempt $i/12: YSQL not ready, waiting 10s..." -ForegroundColor Gray
        Start-Sleep -Seconds 10
    }
}

if (-not $yugabyteReady) {
    Write-Host "YugabyteDB seeding warning (YSQL port not ready after 120s)" -ForegroundColor Yellow
}
Write-Host ""

# MongoDB Seeding
Write-Host "MongoDB..." -ForegroundColor Cyan

docker cp "docker/seed/init-mongodb.json" "query-analyzer-mongodb:/tmp/init-mongodb.json" *> $null
docker cp "docker/seed/init-mongodb-users.json" "query-analyzer-mongodb:/tmp/init-mongodb-users.json" *> $null
docker cp "docker/seed/init-mongodb-logs.json" "query-analyzer-mongodb:/tmp/init-mongodb-logs.json" *> $null

# Clear existing data
docker compose -f docker/compose.yml exec -T mongodb mongosh --authenticationDatabase admin -u admin -p mongodb123 query_analyzer --eval "db.orders.deleteMany({});" 2>$null

# Seed orders collection
docker compose -f docker/compose.yml exec -T mongodb mongosh --authenticationDatabase admin -u admin -p mongodb123 query_analyzer --eval "db.orders.insertMany(JSON.parse(require('fs').readFileSync('/tmp/init-mongodb.json', 'utf8')))"

# Seed users collection with index
docker compose -f docker/compose.yml exec -T mongodb mongosh --authenticationDatabase admin -u admin -p mongodb123 query_analyzer --eval "db.users.deleteMany({}); db.users.insertMany(JSON.parse(require('fs').readFileSync('/tmp/init-mongodb-users.json', 'utf8'))); db.users.createIndex({'email': 1});"

# Seed logs collection without index (for COLLSCAN test)
docker compose -f docker/compose.yml exec -T mongodb mongosh --authenticationDatabase admin -u admin -p mongodb123 query_analyzer --eval "db.logs.deleteMany({}); db.logs.insertMany(JSON.parse(require('fs').readFileSync('/tmp/init-mongodb-logs.json', 'utf8')));"

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

& uv run python docker/seed/init-influxdb.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "InfluxDB seeded!" -ForegroundColor Green
} else {
    Write-Host "InfluxDB seeding warning (non-critical)" -ForegroundColor Yellow
}
Write-Host ""

# Redis Seeding
Write-Host "Redis..." -ForegroundColor Cyan
& uv run python docker/seed/init-redis.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "Redis seeded!" -ForegroundColor Green
} else {
    Write-Host "Redis seeding warning (non-critical)" -ForegroundColor Yellow
}
Write-Host ""

# Neo4j Seeding
Write-Host "Neo4j..." -ForegroundColor Cyan
& uv run python scripts/clear_neo4j.py *> $null
& uv run python scripts/load_neo4j_seed.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "Neo4j seeded!" -ForegroundColor Green
} else {
    Write-Host "Neo4j seeding warning (non-critical)" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "All databases seeded successfully!" -ForegroundColor Green
