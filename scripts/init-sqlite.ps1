#!/usr/bin/env powershell
# Initialize SQLite database for Query Analyzer
# This script creates a clean SQLite database with schema
# (tables, indexes) but WITHOUT data.
# Data population is handled separately by seed.ps1

$ErrorActionPreference = "Stop"

$DBFile = "query_analyzer.db"
$SchemaFile = "docker/seed/init-sqlite.sql"

Write-Host "Initializing SQLite database..." -ForegroundColor Cyan
Write-Host ""

# Check if schema file exists
if (-not (Test-Path $SchemaFile)) {
    Write-Host "ERROR: Schema file not found: $SchemaFile" -ForegroundColor Red
    exit 1
}

# Remove existing database for clean slate
if (Test-Path $DBFile) {
    Write-Host "Removing existing database: $DBFile" -ForegroundColor Yellow
    Remove-Item $DBFile -Force
}

Write-Host "Creating new database: $DBFile" -ForegroundColor Green

# Try to use sqlite3 CLI if available
$sqlite3Available = $false
try {
    $sqlite3Available = Get-Command sqlite3 -ErrorAction SilentlyContinue
} catch {
    $sqlite3Available = $false
}

if ($sqlite3Available) {
    Write-Host "  Using sqlite3 CLI..." -ForegroundColor Gray

    try {
        $schemaContent = Get-Content $SchemaFile -Raw
        $schemaContent | & sqlite3 $DBFile

        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Failed to initialize database with sqlite3" -ForegroundColor Red
            exit 1
        }
    } catch {
        Write-Host "ERROR: $_" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  Using Python fallback (sqlite3 CLI not found)..." -ForegroundColor Gray

    # Create temporary Python script
    $tempPyScript = Join-Path $env:TEMP "init_sqlite_temp.py"

    $pythonCode = @"
import sqlite3
import sys

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
"@

    Set-Content -Path $tempPyScript -Value $pythonCode -Encoding UTF8

    try {
        & uv run python $tempPyScript

        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Failed to initialize database with Python" -ForegroundColor Red
            exit 1
        }
    } catch {
        Write-Host "ERROR: $_" -ForegroundColor Red
        exit 1
    } finally {
        if (Test-Path $tempPyScript) {
            Remove-Item $tempPyScript -Force
        }
    }
}

Write-Host ""

# Verify database was created
if (Test-Path $DBFile) {
    $size = (Get-Item $DBFile).Length
    $sizeStr = if ($size -lt 1MB) {
        "$([math]::Round($size / 1KB, 2)) KB"
    } else {
        "$([math]::Round($size / 1MB, 2)) MB"
    }

    Write-Host "OK: SQLite database created successfully!" -ForegroundColor Green
    Write-Host "   File: $DBFile" -ForegroundColor Gray
    Write-Host "   Size: $sizeStr" -ForegroundColor Gray
} else {
    Write-Host "ERROR: Database file was not created" -ForegroundColor Red
    exit 1
}
