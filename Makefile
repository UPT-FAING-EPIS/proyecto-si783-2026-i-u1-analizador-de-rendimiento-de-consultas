.PHONY: help up down restart reset seed logs logs-postgres logs-mysql logs-mongodb logs-redis logs-influxdb logs-neo4j logs-cockroachdb health clean ps wait-healthy

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
