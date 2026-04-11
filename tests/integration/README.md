# Integration Tests for SQL Drivers

This directory contains comprehensive integration tests for all SQL database adapters in the Query Analyzer project.

## Overview

The integration test suite validates all five SQL drivers (PostgreSQL, MySQL, SQLite, CockroachDB, YugabyteDB) against real databases running in Docker containers. Tests cover:

- **Connection Management**: Connect/disconnect, context managers, credential validation
- **Query Analysis**: EXPLAIN analysis with parametrized anti-pattern queries
- **Anti-Pattern Detection**: Seq scans, index scans, JOINs, SELECT *, LIKE with wildcards, etc.
- **Error Handling**: Invalid tables, columns, syntax errors, DDL rejection
- **Metrics Collection**: Database metrics and engine information
- **Scoring Validation**: Score thresholds for different query patterns

## Structure

`
tests/integration/
├── conftest.py                           # Base pytest configuration
├── conftest_integration.py                # Database-specific fixtures
├── test_postgresql_integration.py        # PostgreSQL tests (30+ tests)
├── test_mysql_integration.py              # MySQL tests (20+ tests)
├── test_sqlite_integration.py             # SQLite tests (20+ tests)
├── test_cockroachdb_integration.py        # CockroachDB tests (30+ tests, CRDB-specific)
└── test_yugabytedb_integration.py         # YugabyteDB tests (20+ tests)
`

## Running Tests Locally

### Prerequisites

1. Install dependencies:
   `ash
   uv sync
   `

2. Start Docker services:
   `ash
   make up
   make wait-healthy
   make seed
   `

### Run All Integration Tests

`ash
python -m pytest tests/integration/ -v
`

### Run Tests for Specific Database

`ash
# PostgreSQL only
python -m pytest tests/integration/test_postgresql_integration.py -v

# MySQL only
python -m pytest tests/integration/test_mysql_integration.py -v

# SQLite only
python -m pytest tests/integration/test_sqlite_integration.py -v

# CockroachDB only
python -m pytest tests/integration/test_cockroachdb_integration.py -v

# YugabyteDB only
python -m pytest tests/integration/test_yugabytedb_integration.py -v
`

### Run Specific Test Class

`ash
python -m pytest tests/integration/test_postgresql_integration.py::TestPostgreSQLIntegrationExplain -v
`

### Run Tests with Coverage

`ash
python -m pytest tests/integration/ --cov=query_analyzer --cov-report=html
`

### Run Tests with Verbose Output

`ash
python -m pytest tests/integration/ -vv --tb=short
`

## Parametrized Anti-Pattern Queries

Each driver includes 10 parametrized test cases covering common SQL anti-patterns:

1. **index_scan_by_id** - SELECT with index (score >= 80)
2. **seq_scan_large_table** - SELECT without index on large table (score <= 75)
3. **join_with_index** - JOIN with index (score >= 70)
4. **select_star** - SELECT * (score <= 95)
5. **like_leading_wildcard** - LIKE with % prefix (score <= 80)
6. **missing_where** - Full table scan (score <= 85)
7. **nested_subquery** - Nested SELECT (score >= 60)
8. **index_on_date** - SELECT with date index (score >= 70)
9. **cartesian_product** - JOIN without condition (score >= 60)
10. **limit_no_order** - LIMIT without ORDER BY (score >= 50)

### Expected Test Results

- **PostgreSQL**: ~30 tests (all patterns supported)
- **MySQL**: ~20 tests (MySQL-specific patterns)
- **SQLite**: ~20 tests (SQLite QUERY PLAN format)
- **CockroachDB**: ~30 tests (includes CRDB-specific metrics: Lookup Joins, Zigzag Joins, Distributed Execution)
- **YugabyteDB**: ~20 tests (PostgreSQL wire protocol compatibility)

**Total: 126 integration tests**

## Test Fixtures

### Base Fixtures (conftest.py)
- nti_pattern_query - Parametrized fixture with 10 anti-pattern query definitions

### Driver-Specific Fixtures (conftest_integration.py)
- docker_postgres_config, pg_adapter - PostgreSQL connection config and adapter
- docker_mysql_config, mysql_adapter - MySQL connection config and adapter
- sqlite_config, sqlite_adapter - SQLite connection config and adapter
- docker_cockroachdb_config, cockroachdb_adapter - CockroachDB connection config and adapter
- docker_yugabyte_config, yugabyte_adapter - YugabyteDB connection config and adapter
- sql_adapter_pg_mysql - Parametrized fixture for PostgreSQL and MySQL

## GitHub Actions CI/CD

The test suite runs automatically on:
- Push to main or develop branches
- Pull requests targeting main or develop
- Manual trigger via workflow dispatch

### Workflow: .github/workflows/integration-tests.yml

**Steps:**
1. Checkout code
2. Set up Python 3.14
3. Start Docker services (docker-compose)
4. Wait for services to be healthy
5. Seed databases with test data
6. Run pre-commit hooks (ruff lint, format, mypy)
7. Run full integration test suite
8. Generate coverage report
9. Upload to Codecov (if available)
10. Collect Docker logs on failure

**Timeout**: 30 minutes per workflow

## Environment Variables

All database credentials can be customized via environment variables:

`ash
# PostgreSQL
DB_POSTGRES_HOST=localhost
DB_POSTGRES_PORT=5432
DB_POSTGRES_USER=postgres
DB_POSTGRES_PASSWORD=postgres123
DB_POSTGRES_NAME=query_analyzer

# MySQL
DB_MYSQL_HOST=localhost
DB_MYSQL_PORT=3306
DB_MYSQL_USER=analyst
DB_MYSQL_PASSWORD=mysql123
DB_MYSQL_NAME=query_analyzer

# SQLite
DB_SQLITE_PATH=:memory:  # or /path/to/file.db

# CockroachDB
DB_COCKROACH_HOST=localhost
DB_COCKROACH_PORT=26257

# YugabyteDB
DB_YUGABYTE_HOST=localhost
DB_YUGABYTE_PORT=5433
DB_YUGABYTE_USER=yugabyte
DB_YUGABYTE_PASSWORD=yugabyte
`

## Troubleshooting

### "Could not connect to Docker {database}" error

**Solution**: Ensure Docker services are running:
`ash
make up
make wait-healthy
`

### Tests timeout

**Solution**: Increase pytest timeout:
`ash
python -m pytest tests/integration/ --timeout=300 -v
`

### SQLite "database is locked" error

**Solution**: SQLite uses in-memory database for testing. If issues persist, use file-based:
`ash
export DB_SQLITE_PATH=/tmp/test.db
python -m pytest tests/integration/test_sqlite_integration.py -v
`

### CockroachDB "connection refused"

**Solution**: CockroachDB requires longer startup time:
`ash
make up
sleep 10
make wait-healthy
python -m pytest tests/integration/test_cockroachdb_integration.py -v
`

## Code Quality

All integration tests follow the project's code quality standards:

- **Linting**: Ruff (E/F/W/I/N/UP/B/D)
- **Formatting**: Ruff format
- **Type Checking**: MyPy (disallow_incomplete_defs = true)
- **Line Length**: 100 characters

Run pre-commit checks:
`ash
python -m pre-commit run --all-files
`

## Key Validation Criteria

Each test validates:

✅ **Connectivity**
- Successful connection to database
- Successful disconnection
- Context manager cleanup

✅ **Query Analysis**
- EXPLAIN plan parsing
- Score calculation (0-100)
- Execution time measurement
- Warnings list is populated
- Recommendations list is populated

✅ **Anti-Pattern Detection**
- Sequential scans trigger warnings
- Index scans achieve high scores
- SELECT * generates recommendations
- LIKE wildcards detected
- Missing indexes recommended

✅ **Error Handling**
- Invalid table raises clear error
- Invalid column raises clear error
- SQL syntax errors caught
- DDL statements rejected

✅ **Database-Specific Features**
- **PostgreSQL**: Full EXPLAIN ANALYZE support
- **MySQL**: EXPLAIN FORMAT=JSON, filesort detection
- **SQLite**: EXPLAIN QUERY PLAN format
- **CockroachDB**: Lookup/Zigzag join detection, distributed execution metrics
- **YugabyteDB**: YSQL port 5433, default credentials

## Next Steps

- Expand test data with more complex queries
- Add performance benchmarking tests
- Integrate with distributed tracing for CRDB/YugabyteDB
- Add NoSQL database tests (MongoDB, Redis, Neo4j)
- Add time-series database tests (InfluxDB)

## Support

For questions or issues with integration tests:
1. Check the AGENTS.md file for project guidelines
2. Review existing test patterns in test_*_integration.py files
3. Check GitHub Actions logs for CI failures
4. Open an issue with test output and Docker logs
