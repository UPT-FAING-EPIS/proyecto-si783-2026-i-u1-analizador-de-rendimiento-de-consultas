.PHONY: help up down restart reset seed logs logs-postgres logs-mysql logs-mongodb logs-redis logs-influxdb logs-neo4j logs-cockroachdb health clean ps wait-healthy test test-unit test-fast test-coverage test-pg test-mysql test-sqlite test-crdb test-yugabyte test-verbose test-clean

help:
	@echo "🔍 Query Analyzer - Docker Management"
	@echo ""
	@echo "Available commands:"
	@echo "  make up              - Start all database services (non-blocking)"
	@echo "  make down            - Stop all services (keep volumes)"
	@echo "  make restart         - Restart all services"
	@echo "  make reset           - Remove all containers and volumes (clean slate)"
	@echo "  make seed            - Populate databases with test data"
	@echo "  make health          - Check health status of all services"
	@echo "  make wait-healthy    - Wait for all services to be healthy (max 120s)"
	@echo "  make ps              - Show running containers"
	@echo "  make logs            - View logs from all services (follow)"
	@echo "  make logs-[service]  - View logs for specific service"
	@echo "  make clean           - Clean up Docker images (unused)"
	@echo ""
	@echo "Testing commands:"
	@echo "  make test            - Run all 126 integration tests (starts Docker)"
	@echo "  make test-unit       - Run unit tests only (no Docker needed)"
	@echo "  make test-fast       - Run quick unit tests (excludes integration tests)"
	@echo "  make test-coverage   - Run tests with coverage report"
	@echo "  make test-pg         - Run PostgreSQL integration tests only (30+ tests)"
	@echo "  make test-mysql      - Run MySQL integration tests only (20+ tests)"
	@echo "  make test-sqlite     - Run SQLite integration tests only (20+ tests)"
	@echo "  make test-crdb       - Run CockroachDB integration tests only (30+ tests)"
	@echo "  make test-yugabyte   - Run YugabyteDB integration tests only (20+ tests)"
	@echo "  make test-verbose    - Run all tests with verbose output"
	@echo "  make test-clean      - Remove pytest cache and coverage artifacts"
	@echo ""
	@echo "Services: postgres, mysql, mongodb, redis, influxdb, neo4j, cockroachdb"
	@echo ""

up:
	@echo "🚀 Starting all services..."
	docker compose -f docker/compose.yml up -d

wait-healthy:
	@bash scripts/wait-for-services.sh

down:
	@echo "⏹️  Stopping all services..."
	docker compose -f docker/compose.yml down

restart: down up
	@echo "🔄 Services restarted!"

reset:
	@echo "🗑️  Removing all containers and volumes..."
	docker compose -f docker/compose.yml down -v
	@echo "✅ Clean slate ready! Run 'make up' to start fresh."

seed:
ifeq ($(OS),Windows_NT)
	@powershell -ExecutionPolicy Bypass -File scripts/seed.ps1
else
	@bash scripts/seed.sh
endif

health:
	@echo "🏥 Checking service health..."
	@echo ""
	@docker compose -f docker/compose.yml ps --services | while read service; do \
		status=$$(docker compose -f docker/compose.yml ps $$service --format 'table {{.Status}}' | tail -1); \
		if echo "$$status" | grep -q "healthy\|running"; then \
			echo "✅ $$service: $$status"; \
		else \
			echo "❌ $$service: $$status"; \
		fi; \
	done
	@echo ""

ps:
	@docker compose -f docker/compose.yml ps

logs:
	docker compose -f docker/compose.yml logs -f

logs-postgres:
	docker compose -f docker/compose.yml logs -f postgres

logs-mysql:
	docker compose -f docker/compose.yml logs -f mysql

logs-mongodb:
	docker compose -f docker/compose.yml logs -f mongodb

logs-redis:
	docker compose -f docker/compose.yml logs -f redis

logs-influxdb:
	docker compose -f docker/compose.yml logs -f influxdb

logs-neo4j:
	docker compose -f docker/compose.yml logs -f neo4j

logs-cockroachdb:
	docker compose -f docker/compose.yml logs -f cockroachdb

clean:
	@echo "🧹 Cleaning up unused Docker images..."
	docker image prune -f
	@echo "✅ Cleanup complete!"

# ========================================
# Testing Targets
# ========================================

test: wait-healthy seed
	@echo "🧪 Running all 126 integration tests..."
	@uv run python -m pytest tests/integration/ -v
	@echo "✅ All tests completed!"

test-unit:
	@echo "🧪 Running unit tests only..."
	@uv run python -m pytest tests/unit/ -v
	@echo "✅ Unit tests completed!"

test-fast:
	@echo "⚡ Running quick unit tests (no Docker)..."
	@uv run python -m pytest tests/unit/ -v --timeout=10
	@echo "✅ Quick tests completed!"

test-coverage:
	@echo "📊 Running tests with coverage report..."
	@uv run python -m pytest tests/ --cov=query_analyzer --cov-report=term-missing --cov-report=html
	@echo "✅ Coverage report generated! Open htmlcov/index.html to view."

test-pg: wait-healthy seed
	@echo "🐘 Running PostgreSQL integration tests..."
	@uv run python -m pytest tests/integration/test_postgresql_integration.py -v
	@echo "✅ PostgreSQL tests completed!"

test-mysql: wait-healthy seed
	@echo "🐬 Running MySQL integration tests..."
	@uv run python -m pytest tests/integration/test_mysql_integration.py -v
	@echo "✅ MySQL tests completed!"

test-sqlite: wait-healthy seed
	@echo "📁 Running SQLite integration tests..."
	@uv run python -m pytest tests/integration/test_sqlite_integration.py -v
	@echo "✅ SQLite tests completed!"

test-crdb: wait-healthy seed
	@echo "🦀 Running CockroachDB integration tests..."
	@uv run python -m pytest tests/integration/test_cockroachdb_integration.py -v
	@echo "✅ CockroachDB tests completed!"

test-yugabyte: wait-healthy seed
	@echo "🌊 Running YugabyteDB integration tests..."
	@uv run python -m pytest tests/integration/test_yugabytedb_integration.py -v
	@echo "✅ YugabyteDB tests completed!"

test-verbose: wait-healthy seed
	@echo "🗣️  Running all tests with verbose output..."
	@uv run python -m pytest tests/integration/ -vv --tb=short
	@echo "✅ Tests completed!"

test-clean:
	@echo "🧹 Cleaning test artifacts..."
	@rm -rf .pytest_cache .coverage htmlcov *.coverage
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Test artifacts cleaned!"
