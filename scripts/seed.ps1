#!/usr/bin/env powershell
# Seed databases with test data

Write-Host "Seeding databases with test data..." -ForegroundColor Green
Write-Host ""

# PostgreSQL Seeding
Write-Host "PostgreSQL..." -ForegroundColor Cyan
$postgresScript = Get-Content "docker/seed/init-postgres.sql" -Raw
$postgresScript | docker compose -f docker/compose.yml exec -T postgres psql -U postgres -d query_analyzer

if ($LASTEXITCODE -ne 0) {
    Write-Host "PostgreSQL seeding warning" -ForegroundColor Yellow
}
Write-Host "PostgreSQL seeded!" -ForegroundColor Green
Write-Host ""

# MySQL Seeding
Write-Host "MySQL..." -ForegroundColor Cyan
$mysqlScript = Get-Content "docker/seed/init-mysql.sql" -Raw
$mysqlScript | docker compose -f docker/compose.yml exec -T mysql mysql -u analyst -pmysql123 query_analyzer

if ($LASTEXITCODE -eq 0) {
    Write-Host "MySQL seeded!" -ForegroundColor Green
} else {
    Write-Host "MySQL seeding failed!" -ForegroundColor Red
    exit 1
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

Write-Host "All databases seeded successfully!" -ForegroundColor Green
