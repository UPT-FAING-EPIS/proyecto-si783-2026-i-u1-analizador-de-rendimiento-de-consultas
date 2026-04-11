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
	@scripts/wait-for-services.sh

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
	@echo "🌱 Seeding databases with test data..."
	@echo ""
	@echo "📦 PostgreSQL..."
	docker compose -f docker/compose.yml exec -T postgres psql -U postgres -d query_analyzer -f /docker-entrypoint-initdb.d/init-postgres.sql 2>/dev/null || \
	docker exec query-analyzer-postgres psql -U postgres -d query_analyzer -f /tmp/init-postgres.sql || \
	cat docker/seed/init-postgres.sql | docker compose -f docker/compose.yml exec -T postgres psql -U postgres -d query_analyzer
	@echo "✅ PostgreSQL seeded!"
	@echo ""
	@echo "🐬 MySQL..."
	cat docker/seed/init-mysql.sql | docker compose -f docker/compose.yml exec -T mysql mysql -u analyst -pmysql123 query_analyzer
	@echo "✅ MySQL seeded!"
	@echo ""
	@echo "🍃 MongoDB..."
	docker compose -f docker/compose.yml exec -T mongodb mongosh --authenticationDatabase admin -u admin -p mongodb123 query_analyzer --eval "db.orders.deleteMany({});" 2>/dev/null || true
	docker compose -f docker/compose.yml exec -T mongodb mongoimport --authenticationDatabase admin -u admin -p mongodb123 --db query_analyzer --collection orders --type json --file /tmp/init-mongodb.json 2>/dev/null || \
	cat docker/seed/init-mongodb.json | docker compose -f docker/compose.yml exec -T mongodb mongosh --authenticationDatabase admin -u admin -p mongodb123 query_analyzer --eval "db.orders.insertMany(JSON.parse(require('fs').readFileSync('/dev/stdin', 'utf8')))"
	@echo "✅ MongoDB seeded!"
	@echo ""
	@echo "🌍 All databases seeded successfully!"

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
	@python -m pytest tests/integration/ -v
	@echo "✅ All tests completed!"

test-unit:
	@echo "🧪 Running unit tests only..."
	@python -m pytest tests/unit/ -v
	@echo "✅ Unit tests completed!"

test-fast:
	@echo "⚡ Running quick unit tests (no Docker)..."
	@python -m pytest tests/unit/ -v --timeout=10
	@echo "✅ Quick tests completed!"

test-coverage:
	@echo "📊 Running tests with coverage report..."
	@python -m pytest tests/ --cov=query_analyzer --cov-report=term-missing --cov-report=html
	@echo "✅ Coverage report generated! Open htmlcov/index.html to view."

test-pg: wait-healthy seed
	@echo "🐘 Running PostgreSQL integration tests..."
	@python -m pytest tests/integration/test_postgresql_integration.py -v
	@echo "✅ PostgreSQL tests completed!"

test-mysql: wait-healthy seed
	@echo "🐬 Running MySQL integration tests..."
	@python -m pytest tests/integration/test_mysql_integration.py -v
	@echo "✅ MySQL tests completed!"

test-sqlite: wait-healthy seed
	@echo "📁 Running SQLite integration tests..."
	@python -m pytest tests/integration/test_sqlite_integration.py -v
	@echo "✅ SQLite tests completed!"

test-crdb: wait-healthy seed
	@echo "🦀 Running CockroachDB integration tests..."
	@python -m pytest tests/integration/test_cockroachdb_integration.py -v
	@echo "✅ CockroachDB tests completed!"

test-yugabyte: wait-healthy seed
	@echo "🌊 Running YugabyteDB integration tests..."
	@python -m pytest tests/integration/test_yugabytedb_integration.py -v
	@echo "✅ YugabyteDB tests completed!"

test-verbose: wait-healthy seed
	@echo "🗣️  Running all tests with verbose output..."
	@python -m pytest tests/integration/ -vv --tb=short
	@echo "✅ Tests completed!"

test-clean:
	@echo "🧹 Cleaning test artifacts..."
	@rm -rf .pytest_cache .coverage htmlcov *.coverage
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Test artifacts cleaned!"
