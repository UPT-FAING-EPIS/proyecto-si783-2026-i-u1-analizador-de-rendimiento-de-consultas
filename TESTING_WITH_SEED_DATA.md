# Testing with Seed Data

Complete guide for testing Query Analyzer with the pre-seeded databases.

> **ℹ️ CLI COMMAND SYNTAX**
>
> The command is: **`qa analyze`** (single command, not duplicated)
>
> **Examples:**
> ```bash
> qa analyze "SELECT * FROM customers LIMIT 5;"
> qa analyze --profile postgresql "SELECT COUNT(*) FROM orders;"
> qa analyze --output json "SELECT * FROM large_table WHERE category = 'A';"
> ```

## Table of Contents

1. [Quick Start](#quick-start)
2. [Full Setup](#full-setup)
3. [Testing by Engine](#testing-by-engine)
4. [Query Performance Patterns](#query-performance-patterns)
5. [Using `qa analyze` Command](#using-qa-analyze-command)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start

### 1. Start Services
```bash
# Start all services (PostgreSQL, MySQL, CockroachDB, YugabyteDB, MongoDB, etc.)
# Note: SQLite is local, not a Docker service
make up

# Wait for all services to be healthy
make health

# This usually takes 30-45 seconds (YugabyteDB is slowest to initialize)
```

### 2. Seed Databases
```bash
# Seed all databases with test data
make seed

# Or manually:
./scripts/seed.sh              # Linux/macOS
./scripts/seed.ps1             # PowerShell
```

### 3. Create Database Profiles
```bash
# Create profiles automatically from docker-compose.yml
make create-profiles

# Verify profiles were created
make profiles-check

# Expected output:
# 10 profiles configured:
#   * postgresql (DEFAULT)
#   * mysql
#   * sqlite
#   * mongodb
#   * redis
#   * cockroachdb
#   * yugabytedb
#   * neo4j
#   * influxdb
#   * elasticsearch
#
# (Profile names match docker-compose services)
```

### 4. Test Query Analyzer
```bash
# Run analysis on a test query (NOTA: comando es "qa analyze")
qa analyze "SELECT * FROM customers WHERE email = 'customer50@example.com';"

# With different output formats
qa analyze --output rich "SELECT COUNT(*) FROM large_table WHERE category = 'A';"
qa analyze --output json "SELECT * FROM orders WHERE customer_id = 5;"
qa analyze --output markdown "SELECT * FROM large_table WHERE numeric_value > 30000;"
```

---

## Full Setup

### Prerequisites

```bash
# Python 3.10+
python --version

# Docker & Docker Compose
docker --version
docker compose --version

# (Optional) CLI tools for manual testing:
# - PostgreSQL: psql
# - MySQL: mysql
# - SQLite: sqlite3 (recommended for local database)
# - CockroachDB: cockroach
# - YugabyteDB: psql (use YSQL client)
```

### Installation

```bash
# Clone repo
git clone <repo-url>
cd proyecto-si783-2026-i-u1-analizador-de-rendimiento-de-consultas

# Install dependencies
uv sync

# Create profiles automatically from docker-compose.yml
make create-profiles

# Verify profiles were created
make profiles-check
```

### Start & Verify

```bash
# Start Docker services
make up

# Wait for all services to be ready
make health

# Expected output:
# query-analyzer-postgres       ✓ Healthy
# query-analyzer-mysql          ✓ Healthy
# query-analyzer-sqlite         ✓ Healthy
# query-analyzer-cockroachdb    ✓ Healthy
# query-analyzer-yugabytedb     ✓ Healthy
# query-analyzer-mongodb        ✓ Healthy
# ... (other services)

# Seed the databases
make seed
```

---

## Testing by Engine

### PostgreSQL

**Connection Details:**
- Host: `localhost`
- Port: `5432`
- User: `qa`
- Password: `QAnalyze`
- Database: `query_analyzer`

**Test Commands:**

```bash
# Via Query Analyzer CLI
qa analyze "SELECT * FROM customers WHERE email = 'customer50@example.com';" --profile postgresql

# Manual test via psql - Mostrar plan con timings
psql -h localhost -U qa -d query_analyzer -c "EXPLAIN ANALYZE SELECT * FROM large_table WHERE category = 'A' ORDER BY numeric_value LIMIT 100;"

# Via Docker - Contar órdenes por estado
docker compose exec postgres psql -U qa -d query_analyzer -c "SELECT status, COUNT(*) FROM orders GROUP BY status;"

# Buscar órdenes de un cliente específico
qa analyze "SELECT o.id, o.status, o.total_amount FROM orders o WHERE o.customer_id = 25;" --profile postgresql
```

**Expected Results:**
- ✅ Index scans on `email` column (muy rápido, ~0.1ms)
- ✅ Sequential scans en `large_table.numeric_value` sin índice (~50ms)
- ✅ Index scans en `orders.customer_id` (rápido, FK indexado)
- ✅ GROUP BY rápido en `orders.status` (solo 4 valores)

---

### MySQL

**Connection Details:**
- Host: `localhost`
- Port: `3306`
- User: `qa`
- Password: `QAnalyze`
- Database: `query_analyzer`

**Test Commands:**

```bash
# Via Query Analyzer CLI - Buscar órdenes por estado (4 categorías)

# Manual test via mysql - Mostrar plan de ejecución
mysql -h localhost -u qa -pQAnalyze query_analyzer -e "EXPLAIN SELECT * FROM large_table WHERE category IN ('A', 'B', 'C') LIMIT 100;"

# Via Docker - Contar items por orden
docker compose exec mysql mysql -u qa -pQAnalyze query_analyzer -e "SELECT COUNT(*) FROM order_items WHERE order_id <= 50;"

# Búsqueda por país (distribuido: ~20 por país)
qa analyze "SELECT country, COUNT(*) FROM customers GROUP BY country;" --profile mysql
```

**Expected Results:**
- ✅ Conversiones de tipos diferentes que PostgreSQL
- ✅ Comportamiento optimizador diferente pero eficiente
- ✅ Uso de índices similar a PostgreSQL
- ✅ Velocidades comparables (algunas queries más rápidas/lentas que PG)

---

### SQLite

**Connection Details:**
- Database file: `query_analyzer.db` (local file in project directory)
- User: Not needed (SQLite has no authentication)
- No port (file-based)

**Test Commands:**

```bash
# Via Query Analyzer CLI - Búsqueda por categoría (SÍ tiene índice)
qa analyze "SELECT COUNT(*) as count FROM large_table WHERE category = 'D';" --profile sqlite

# Manual test via sqlite3 CLI - Ver plan de query
sqlite3 query_analyzer.db "EXPLAIN QUERY PLAN SELECT * FROM customers WHERE email = 'customer75@example.com';"

# Crear índice y comparar rendimiento
sqlite3 query_analyzer.db << 'EOF'
-- Mostrar qué índices existen
.indices large_table

-- Ver plan antes y después de crear índice
EXPLAIN QUERY PLAN SELECT * FROM large_table WHERE numeric_value > 40000 LIMIT 100;
EOF

# Búsqueda sin índice (lenta)
qa analyze "SELECT COUNT(*) FROM large_table WHERE numeric_value > 40000;" --profile sqlite

# Conteo rápido en orders
qa analyze "SELECT COUNT(*) FROM orders WHERE status = 'delivered';" --profile sqlite
```

**Expected Results:**
- ✅ `EXPLAIN QUERY PLAN` formato diferente (simple vs PostgreSQL/MySQL)
- ✅ Index scans mostrados como `SEARCH` en output
- ✅ Full table scans como `SCAN TABLE`
- ✅ SQLite generalmente rápido para queries simples
- ✅ Sin índice en `numeric_value` = scan completo lento

---

### CockroachDB

**Connection Details:**
- Host: `localhost`
- Port: `26257`
- User: `qa`
- Password: `QAnalyze`
- Database: `query_analyzer`
- Flag: `--insecure` (for dev/testing)
- **Architecture:** Single-node deployment (but distributed query simulation)

**Test Commands:**

```bash
# Query 1: LOCAL SHARD QUERY (Score 100/100 - Optimal)
# Single region scan, no cross-shard communication
qa analyze "SELECT user_id, name, email FROM regional_users WHERE region = 'US' AND email LIKE '%@us-company.com' LIMIT 10;" --profile cockroachdb

# Query 2: CROSS-SHARD GROUP BY (Score 70-80/100 - Overhead visible)
# Scans all 5 regional shards, requires consolidation
qa analyze "SELECT region, COUNT(*) as user_count FROM regional_users GROUP BY region ORDER BY user_count DESC;" --profile cockroachdb

# Query 3: DISTRIBUTED JOIN (Score 60-70/100 - Heavy)
# JOIN across shards with reshuffling, HAVING clause adds cost
qa analyze "SELECT u.region, u.name, COUNT(t.txn_id) as txn_count FROM regional_users u JOIN regional_transactions t ON u.user_id = t.user_id WHERE t.status = 'completed' GROUP BY u.region, u.name HAVING COUNT(t.txn_id) > 3;" --profile cockroachdb

# Query 4: MULTI-REGION AGGREGATION (Score 75-85/100 - Complex)
# Aggregation per shard + central consolidation
qa analyze "SELECT region, AVG(amount) as avg_txn_amount, MAX(amount) as max_txn_amount, COUNT(*) as total_txns FROM regional_transactions WHERE txn_timestamp > NOW() - INTERVAL '7 days' GROUP BY region ORDER BY avg_txn_amount DESC;" --profile cockroachdb

# Manual test - Ver plan distribuido
docker compose exec cockroachdb cockroach sql --insecure -d query_analyzer -e "EXPLAIN SELECT region, COUNT(*) FROM regional_users GROUP BY region;"

# Ver datos de distribución
docker compose exec cockroachdb cockroach sql --insecure -d query_analyzer -e "SELECT region, COUNT(*) FROM regional_users GROUP BY region;"
```

**Expected Results:**
- ✅ Query 1 (Local Shard): Score 100/100, 0 warnings — Single region, minimal latency (~1-5ms)
- ⚠️ Query 2 (Cross-Shard GROUP BY): Score 70-80/100, 1 warning — Multi-region consolidation, observable latency (~50-150ms)
- ⚠️ Query 3 (Distributed JOIN): Score 60-70/100, 2 warnings — Data reshuffling between regions, high latency (~200-500ms)
- ⚠️ Query 4 (Multi-Region Aggregation): Score 75-85/100, 1-2 warnings — Per-shard aggregation + consolidation (~150-300ms)

**Key Differences from PostgreSQL:**
- ✅ CockroachDB distributes data by shard key (region in this case)
- ⚠️ Local shard queries are fast (similar to PostgreSQL)
- ⚠️ Cross-shard queries incur network overhead even in single-node
- ⚠️ GROUP BY, JOIN, and AGGREGATION across shards require data movement
- ℹ️ Single-node CockroachDB still shows distributed query patterns (educational)

**Real Seed Data (Distributed Sharding Simulation):**
- **regional_users** (1,000 rows): Distributed across 5 regions (US, EU, APAC, LATAM, MENA) × 200 users each
  - Indexes: region, email
  - Shard key: region (determines which node/range owns data)
  - Regional affinity: user5@us-company.com, user6@eu-company.com, etc.

- **regional_transactions** (5,000 rows): ~5 transactions per user, same region as user
  - Columns: user_id (FK), region, amount, status (pending/completed/failed/refunded)
  - Indexes: region, status, user_id
  - Distributed by: region (same region as owning user)
  - Status distribution: 25% each (pending, completed, failed, refunded)

- **shard_distribution** (5 rows): Meta-information about shard distribution
  - Columns: region, user_count (200), transaction_count (1000), avg_latency_ms
  - Shows expected latency increase with geographic distance: US (5.2ms) → EU (8.5ms) → APAC (12.3ms) → LATAM (15.7ms) → MENA (18.9ms)

- **hot_keys_log** (500 rows): Simulates hotspot monitoring
  - Tracks per-region contention patterns
  - Access patterns by key_pattern (txn_user_0 through txn_user_50)
  - Conflict rates 0-100%

---

### YugabyteDB

**Connection Details:**
- Host: `localhost`
- Port: `5433` (NOT 5432, reserved for PostgreSQL)
- User: `qa`
- Password: `QAnalyze`
- Database: `query_analyzer`
- YSQL (PostgreSQL-compatible)

**Test Commands:**

```bash
# Via Query Analyzer CLI - JOIN sobre órdenes e items
qa analyze "SELECT o.id, o.status, COUNT(oi.id) as item_count FROM orders o JOIN order_items oi ON o.id = oi.order_id GROUP BY o.id, o.status;" --profile yugabytedb

# Manual test via psql (IMPORTANTE: puerto 5433, no 5432)
psql -h localhost -U qa -d query_analyzer -p 5433 -c "EXPLAIN ANALYZE SELECT * FROM large_table WHERE category IN ('A', 'B', 'C') ORDER BY numeric_value LIMIT 50;"

# Via Docker con ysqlsh
docker compose exec yugabytedb ysqlsh -U ya -d query_analyzer -c "SELECT COUNT(*) FROM orders WHERE status = 'delivered';"

# Búsqueda por país
qa analyze "SELECT c.name, COUNT(o.id) FROM customers c LEFT JOIN orders o ON c.id = o.customer_id WHERE c.country = 'USA' GROUP BY c.id, c.name;" --profile yugabytedb
```

**Expected Results:**
- ✅ Info de ejecución distribuida
- ✅ Salida compatible con PostgreSQL
- ✅ Features de alta disponibilidad NO visibles en single-node (replicas para HA no activas)
- ⏳ Nota: YSQL port (5433) es lento al iniciar, esperar a `make health` ✓

---

### InfluxDB

**Connection Details:**
- Host: `localhost`
- Port: `8086`
- Token: `mytoken`
- Organization: `myorg`
- Bucket: `query_analyzer`
- Query Language: Flux (time-series specific)

**Test Commands:**

```bash
# Via Query Analyzer CLI - Bounded Query (Good performance)
qa analyze 'from(bucket:"query_analyzer") |> range(start: -7d) |> filter(fn: (r) => r._measurement == "cpu") |> filter(fn: (r) => r.host == "server1") |> mean()' --profile influxdb

# Via Query Analyzer CLI - Unbounded Query (Poor performance - missing range)
qa analyze 'from(bucket:"query_analyzer") |> filter(fn: (r) => r._measurement == "memory") |> mean()' --profile influxdb

# Via Query Analyzer CLI - High Cardinality Query
qa analyze 'from(bucket:"query_analyzer") |> range(start: -24h) |> filter(fn: (r) => r._measurement == "query_latency") |> group(columns: ["host", "region", "service", "endpoint"]) |> mean()' --profile influxdb

# Via Query Analyzer CLI - Excessive Transformations
qa analyze 'from(bucket:"query_analyzer") |> range(start: -7d) |> filter(fn: (r) => r._measurement == "disk") |> derivative() |> mean() |> sort(columns: ["_value"]) |> limit(n: 100) |> map(fn: (r) => ({r with value_doubled: r._value * 2}))' --profile influxdb

# Manual test via influx CLI
docker compose exec influxdb influx query 'from(bucket:"query_analyzer") |> range(start: -24h) |> filter(fn: (r) => r._measurement == "cpu") |> limit(n: 10)'

# Ver datos disponibles en bucket
docker compose exec influxdb influx query 'from(bucket:"query_analyzer") |> range(start: -7d) |> group(columns: ["_measurement"]) |> first()'
```

**Expected Results:**
- ✅ Query 1 (Bounded): Score 100/100, 0 warnings — Efficient range, specific filter, proper aggregation
- ⚠️ Query 2 (Unbounded): Score 70/100, 1 critical warning — Missing time range, scans entire bucket
- ⚠️ Query 3 (High Cardinality): Score 85/100, 1 high warning — Too many group dimensions, potential memory issues
- ⚠️ Query 4 (Excessive Transformations): Score 80/100, 2 warnings — Multiple expensive operations, map() can be slow

**Key Differences from SQL Engines:**
- ✅ Time-series optimized (range queries, aggregations)
- ✅ Flux is functional programming language (not SQL)
- ⚠️ Unbounded queries scan entire bucket (very expensive)
- ⚠️ High cardinality grouping can cause OOM
- ⚠️ Multiple transformations compound performance cost

**Real Seed Data (450 time-series points):**
- **cpu** (100 points): host=server1|server2|server3|server4|server5, region=us|eu|asia, values: 20-95%
- **memory** (100 points): host=server1|server2|server3|server4|server5, region=us|eu|asia, values: 30-85%
- **disk** (50 points): host=server1|server2|server3|server4|server5, region=us|eu|asia, values: 10-90%
- **network** (100 points): host=server1|server2|server3|server4|server5, interface=eth0|eth1, region=us|eu|asia, values: 100-9999 Mbps
- **query_latency** (100 points): service=api|db|cache, endpoint=/search|/users|/orders, region=us|eu|asia, values: 10-5000ms

---

### Neo4j

**Connection Details:**
- Host: `localhost`
- Port: `7687` (Bolt protocol)
- User: `neo4j`
- Password: `neo4j123`
- Database: `neo4j` (default)
- Query Language: Cypher (graph query language)

**Test Commands:**

```bash
# Query 1: Simple Indexed Lookup (Score ~100/100 - OPTIMAL)
# Uses index on country property, minimal result set
qa analyze "MATCH (u:User {country: 'US'}) RETURN u.id, u.name, u.email LIMIT 5" --profile neo4j

# Query 2: Relationship Expansion without Bounds (Score ~70/100 - MODERATE)
# Expands relationships across entire dataset without filtering
# Traverses: 500 users × ~6 FOLLOWS per user = large expansion
qa analyze "MATCH (u:User)-[:FOLLOWS]->(f:User) RETURN DISTINCT u.country, f.country, COUNT(*) as follows_per_pair" --profile neo4j

# Query 3: Multiple Relationship Hops (Score ~55/100 - INEFFICIENT)
# Multi-hop without property-level filtering causes Cartesian expansion
# u->f->p->c creates many intermediate results
qa analyze "MATCH (u:User)-[:FOLLOWS]->(f:User)-[:PURCHASED]->(p:Product)-[:COMMENTED]->(c:User) RETURN COUNT(DISTINCT p) as product_count" --profile neo4j

# Query 4: High-Cardinality Aggregation (Score ~40/100 - POOR)
# Groups on many dimensions without early filtering, full graph scan pattern
qa analyze "MATCH (a:User)-[:COMMENTED]->(p:Product)<-[:COMMENTED]-(b:User) WHERE a.country = b.country RETURN a.country, COUNT(DISTINCT a) as users, COUNT(DISTINCT p) as products" --profile neo4j

# Manual test via cypher-shell
docker compose exec neo4j cypher-shell -u neo4j -p neo4j123 "MATCH (u:User) RETURN COUNT(u) as user_count;"

# View graph statistics
docker compose exec neo4j cypher-shell -u neo4j -p neo4j123 "MATCH (n) RETURN labels(n)[0] as label, COUNT(n) as count GROUP BY label;"
```

**Expected Results:**
- ✅ Query 1 (Index Lookup): Score ~100/100, 0 warnings — Indexed property lookup, minimal traversal (~8-10ms)
- ⚠️ Query 2 (Expansion): Score ~70/100, warnings — Relationship expansion without early filtering (~80-120ms)
- ⚠️ Query 3 (Multi-Hop): Score ~55/100, multiple warnings — 4-hop traversal causes result explosion (~150-250ms)
- ❌ Query 4 (Aggregation): Score ~40/100, critical warnings — High-cardinality joins without filtering (~300-500ms)

**Key Differences from SQL/Time-Series Engines:**
- ✅ Graph-native queries using relationship navigation (MATCH, EXPAND)
- ✅ Efficient multi-hop traversals (2-5 relationship hops in milliseconds)
- ✅ Variable-length paths with bounded ranges prevent unbounded expansion
- ⚠️ No traditional JOIN syntax; relationships are first-class
- ⚠️ Aggregations use WITH clause (not GROUP BY like SQL)

**Real Seed Data (Social Commerce Graph - 610 nodes, 3,398 relationships):**
- **Users** (500 nodes): Distributed across 5 countries (US, UK, DE, FR, JP) × 100 users each
  - Properties: id (unique), name, email, country, registration_date
  - Indexes: idx_user_country, idx_user_id

- **Products** (100 nodes): Distributed across 10 categories
  - Properties: id (unique), title, price, category_id, stock, created_date
  - Indexes: idx_product_id, idx_product_price

- **Categories** (10 nodes): Product taxonomy
  - Properties: id (unique), name, description

- **Relationships:**
  - **PURCHASED** (899 edges): User → Product (transaction history)
    - Properties: quantity, purchase_date
    - Density: ~1.8 per user
  - **VIEWED** (1,600 edges): User → Product (browsing behavior)
    - Properties: view_date
    - Density: ~3.2 per user
  - **FOLLOWS** (499 edges): User → User (social connections)
    - Properties: since
    - Density: ~1.0 per user
  - **LIKES** (400 edges): User → Product (preference signals)
    - Density: ~0.8 per user

---

## Query Performance Patterns

### Pattern 1: Index Scan (Fast)

**Query:** Buscar un cliente específico por email (usa índice)

```sql
-- Seed data: 100 customers con emails customer1@example.com a customer100@example.com
SELECT * FROM customers WHERE email = 'customer50@example.com';
```

**Expected Analysis:**
- Index Scan on `idx_customers_email`
- Cost: Very low (~0.27 in PostgreSQL)
- Rows: 1 (customer50 con país: Germany)
- Time: < 1ms
- Búsqueda instantánea gracias al índice

**Test Command:**
```bash
qa analyze "SELECT * FROM customers WHERE email = 'customer50@example.com';"

# O varios clientes
qa analyze "SELECT * FROM customers WHERE country = 'USA';" # ~20 clientes (i%5==0)
```

**Real Seed Data Breakdown:**
- Customers: 100 filas (customer1 a customer100)
- Countries: USA, UK, Canada, Germany, France (distribuidos: i % 5)
- USA: customers 5, 10, 15, ..., 100 (20 total)

---

### Pattern 2: Sequential Scan (Slower)

**Query:** Buscar en large_table sin índice en la columna de búsqueda

```sql
-- Seed data: 10,000 filas en large_table
-- Columnas: id, data_value, numeric_value (sin índice), category (A-J)
-- numeric_value: calculado como (i*7 + random(0..1000)) % 50000
SELECT * FROM large_table WHERE numeric_value > 40000;
```

**Expected Analysis:**
- Sequential/Full Table Scan (no hay índice en numeric_value)
- Cost: ~350 (sobre 10K filas)
- Rows: ~2000 (20% de 10K, distribuidos aleatoriamente)
- Time: 20-50ms (varía según I/O)
- **Sin índice = búsqueda lenta en toda la tabla**

**Test Command:**
```bash
# Búsqueda lenta: todo scans completos
qa analyze "SELECT * FROM large_table WHERE numeric_value > 40000;"

# Para comparar: búsqueda rápida con índice en categoria (SÍ tiene índice)
qa analyze "SELECT * FROM large_table WHERE category = 'A';"  # ~1,000 rows, Index Scan
```

**Real Seed Data:**
- large_table: 10,000 filas
- category: A, B, C, D, E, F, G, H, I, J (i % 10) → ~1,000 filas por categoría
- Índice en `category` → rápido
- Sin índice en `numeric_value` → lento
- Sin índice en `data_value` → lento

---

### Pattern 3: Nested Loop Join

**Query:** JOIN entre órdenes y items (algunos sin índices óptimos)

```sql
-- Seed data:
-- orders: 100 filas (customer_id: 1-100, status: pending/processing/shipped/delivered)
-- order_items: 500 filas (distribuidas sobre 100 órdenes: 5 items por orden)
SELECT o.id, o.customer_id, o.status, oi.product_id, oi.quantity
FROM orders o
JOIN order_items oi ON o.id = oi.order_id
WHERE o.customer_id BETWEEN 20 AND 30;  -- ~11 órdenes de 11 clientes
```

**Expected Analysis:**
- Nested Loop Join O Hash Join (depende del engine)
- Usa índice `idx_orders_customer_id` para filtro
- Usa índice `idx_order_items_order_id` para join
- Rows: ~55 (11 órdenes × ~5 items c/u)
- Cost: Bajo-Medio
- **Con índices → Join rápido**

**Test Command:**
```bash
# Join simple: rápido (ambas tablas tienen índices en FK)
qa analyze "SELECT o.id, oi.product_id FROM orders o JOIN order_items oi ON o.id = oi.order_id WHERE o.customer_id = 25;"

# Join sin filtro en orders (tabla más grande)
qa analyze "SELECT COUNT(*) FROM orders o JOIN order_items oi ON o.id = oi.order_id;"
```

**Real Seed Data Breakdown:**
- orders: 100 filas
  - customer_id: 1-100 (i % 100 + 1)
  - status: pending (25%), processing (25%), shipped (25%), delivered (25%)
  - order_date: últimos 30 días
- order_items: 500 filas
  - Distribuidas: ~5 items por orden (500 / 100)
  - order_id: usa CTE para mapear a IDs reales
  - product_id: 0-999 (aleatorio)
  - quantity: 1-10

---

### Pattern 4: Aggregate with GROUP BY

**Query:** Agregación con GROUP BY (con índice)

```sql
-- Seed data: 10,000 filas en large_table
-- category distribuida: A, B, C, D, E, F, G, H, I, J (i % 10)
-- Índice existe en category → fast GROUP BY
SELECT category, COUNT(*) as count, AVG(numeric_value) as avg_value
FROM large_table
GROUP BY category;
```

**Expected Analysis:**
- 10 grupos (A-J), ~1,000 filas cada uno
- Index Scan (u otro nodo efectivo) en category
- Group Aggregate: combina 10,000 → 10 filas
- Cost: Bajo-Medio
- Time: 5-15ms
- **Índice en GROUP BY column = optimización buena**

**Test Command:**
```bash
# Aggregation con GROUP BY (rápido por índice)
qa analyze "SELECT category, COUNT(*) FROM large_table GROUP BY category;"

# Contar órdenes por status (4 valores)
qa analyze "SELECT status, COUNT(*) FROM orders GROUP BY status;"
```

**Real Seed Data:**
- large_table.category: A(~1000), B(~1000), ..., J(~1000)
- orders.status: pending, processing, shipped, delivered (25% cada uno)
- slow_queries_log: 1,000 filas con tipos: SELECT, JOIN, AGGREGATE, UPDATE, DELETE

---

### Pattern 5: Complex Multi-Table Join

**Query:** JOIN complejo sobre 3+ tablas con múltiples condiciones

```sql
-- Seed data:
-- customers: 100, orders: 100, order_items: 500
-- Tabla lenta: 10,000 (numeric_value sin índice)
SELECT c.name, c.country, o.status, COUNT(oi.id) as item_count, lt.category
FROM customers c
JOIN orders o ON c.id = o.customer_id
JOIN order_items oi ON o.id = oi.order_id
JOIN large_table lt ON oi.product_id = lt.id % 10000  -- Producto aleatorio
WHERE o.status = 'delivered'
  AND c.country IN ('USA', 'Canada')
GROUP BY c.id, c.name, c.country, o.id, o.status, lt.category
ORDER BY o.order_date DESC
LIMIT 50;
```

**Expected Analysis:**
- Multiple joins: customers → orders → order_items → large_table
- Index usage en `status`, `country`, `customer_id`
- Possible sorts (ORDER BY o.order_date DESC)
- GROUP BY agregación
- Cost: Medium-High (4 tablas = complejidad)
- Time: 20-100ms

**Test Command:**
```bash
# JOIN complejo: 3 tablas con múltiples condiciones
qa analyze "SELECT c.name, COUNT(o.id) as order_count FROM customers c LEFT JOIN orders o ON c.id = o.customer_id WHERE c.country IN ('USA', 'Canada') GROUP BY c.id, c.name ORDER BY order_count DESC;"

# Versión más simple para comparar
qa analyze "SELECT c.name, o.total_amount FROM customers c JOIN orders o ON c.id = o.customer_id WHERE o.status = 'delivered' LIMIT 10;"
```

**Real Seed Data Structure:**
- customers.country: USA (20), UK (20), Canada (20), Germany (20), France (20)
- orders.status: 25 delivered, 25 pending, 25 processing, 25 shipped
- order_items por orden: ~5 items
- large_table.category: A-J distribuidos uniformemente
- Índices:
  - ✅ idx_customers_country (buscar por país = rápido)
  - ✅ idx_orders_status (buscar por status = rápido)
  - ❌ Sin índice en product_id de order_items (buscar lento)

---

## Using `qa analyze` Command

### Basic Usage

**IMPORTANTE:** El comando correcto es `qa analyze` (dos veces "analyze"):

```bash
# Default profile (postgresql)
qa analyze "SELECT * FROM customers LIMIT 10;"

# Specific profile
qa analyze "SELECT COUNT(*) FROM orders WHERE status = 'delivered';" --profile mysql

# Read from stdin
echo "SELECT * FROM large_table WHERE category = 'A' LIMIT 5;" | qa analyze

# From file
qa analyze < query.sql

# Con verbose para debugging
qa analyze "SELECT * FROM customers WHERE country = 'USA';" --verbose

# Alias corto si disponible
# (Verifica si existe: qa --help)
```

**Nota:** El primer `analyze` es el grupo de comandos, el segundo es el subcomando específico de análisis.

### Output Formats

#### 1. Rich (Default) - Terminal Rendering

```bash
qa analyze "SELECT * FROM customers WHERE email = 'customer50@example.com';"
```

**Output Expected:**
```
Query Analysis Report
═══════════════════════════════════════════════════════════════════

Query:
  SELECT * FROM customers WHERE email = 'customer50@example.com';

Engine: postgresql
Profile: postgresql

Execution Plan:
  ┌─ Index Scan using idx_customers_email on customers
  │  Index Cond: (email = 'customer50@example.com')
  │  Rows: 1
  │  Execution Time: 0.041 ms
  │  Planning Time: 0.123 ms
  └─ Total Rows Returned: 1

Score: 100/100 (Optimal - Index Scan on low cardinality)
Recommendations: ✓ No issues found
```

#### 2. JSON Format

```bash
qa analyze --format json "SELECT COUNT(*) FROM orders WHERE status = 'delivered';"
```

**Output:**
```json
{
  "query": "SELECT COUNT(*) FROM orders WHERE status = 'delivered';",
  "engine": "postgresql",
  "profile": "postgresql",
  "score": 100,
  "execution_time_ms": 0.342,
  "planning_time_ms": 0.155,
  "plan_tree": {
    "node_type": "Aggregate",
    "strategy": "Plain",
    "cost": 2.75,
    "actual_time_ms": 0.042,
    "actual_rows": 1,
    "plan_rows": 1,
    "children": [
      {
        "node_type": "Index Scan",
        "index_name": "idx_orders_status",
        "relation_name": "orders",
        "cost": 2.5,
        "actual_rows": 25,
        "filter": "status = 'delivered'"
      }
    ]
  },
  "metrics": {
    "planning_time_ms": 0.155,
    "execution_time_ms": 0.342,
    "total_cost": 2.75,
    "actual_rows_total": 25,
    "index_scans": 1,
    "seq_scans": 0
  },
  "recommendations": []
}
```

#### 3. Markdown Format

```bash
qa analyze --format markdown "SELECT * FROM large_table WHERE category = 'A' LIMIT 100;"
```

**Output:**
```markdown
# Query Analysis Report

## Query
\`\`\`sql
SELECT * FROM large_table WHERE category = 'A' LIMIT 100;
\`\`\`

**Engine:** postgresql
**Profile:** postgresql
**Score:** 95/100 (Good)

## Execution Plan

### Root Node: Index Scan
- **Node Type:** Index Scan
- **Index:** idx_large_table_category
- **Cost:** 4.28
- **Rows:** 1000 (100 limited)
- **Actual Time:** 2.456 ms
- **Filter:** category = 'A'

### Child Node: Index Cond
- **Rows Scanned:** 1000
- **Rows Returned:** 100 (LIMIT applied)

## Metrics
- **Planning Time:** 0.234 ms
- **Execution Time:** 2.456 ms
- **Total Cost:** 4.28
- **Cache Hit Rate:** 98%

## Recommendations
- ✓ Index used efficiently (idx_large_table_category)
- ✓ LIMIT clause applied correctly
- ✓ Query performance is good
```

---

## Advanced Testing Scenarios

### Scenario 1: Compare Index vs Sequential Scan

**Test:** Buscar en large_table (10,000 rows) - con y sin índice

```bash
# Query SIN índice - búsqueda lenta (numeric_value NO tiene índice)
qa analyze "SELECT COUNT(*) FROM large_table WHERE numeric_value > 40000;" --output json > numeric_no_index.json

# Query CON índice - búsqueda rápida (category SÍ tiene índice)
qa analyze "SELECT COUNT(*) FROM large_table WHERE category = 'A';" --output json > category_with_index.json

# Comparar execution time
echo "Sin índice (numeric_value > 40000):"
jq '.execution_time_ms' numeric_no_index.json

echo "Con índice (category = 'A'):"
jq '.execution_time_ms' category_with_index.json
```

**Expected:** Cost y time **disminuyen significativamente** con índice
- Sin índice: ~20-50ms (Seq Scan sobre 10K filas)
- Con índice: ~1-5ms (Index Scan sobre 1K filas)

---

### Scenario 2: Test Across All Engines

**Compare:** Misma query en 5 engines diferentes

```bash
QUERY="SELECT COUNT(*) FROM orders WHERE status = 'delivered';"

# Ejecutar en todos los engines
echo "=== PostgreSQL ===" && qa analyze "$QUERY" --profile postgresql --format json | jq '.metrics'
echo "=== MySQL ===" && qa analyze "$QUERY" --profile mysql --format json | jq '.metrics'
echo "=== SQLite ===" && qa analyze "$QUERY" --profile sqlite --format json | jq '.metrics'
echo "=== CockroachDB ===" && qa analyze "$QUERY" --profile cockroachdb --format json | jq '.metrics'
echo "=== YugabyteDB ===" && qa analyze "$QUERY" --profile yugabytedb --format json | jq '.metrics'

# Script para comparar execution times
for engine in postgresql mysql sqlite cockroachdb yugabytedb; do
    echo -n "$engine: "
    qa analyze "$QUERY" --profile $engine --output json 2>/dev/null | jq -r '.execution_time_ms' | xargs echo "ms"
done
```

**Expected Differences:**
- PostgreSQL: ~0.3ms (rápido, local)
- MySQL: ~2-5ms (algo más lento)
- SQLite: ~0.5-1ms (muy rápido, embedded)
- CockroachDB: ~10-20ms (overhead distribuido)
- YugabyteDB: ~20-50ms (overhead distribuido + latencia YSQL)

---

### Scenario 3: Batch Testing from Seed Data

**queries.sql:** Ejemplos específicos con datos del seed

```sql
-- Query 1: Index Scan - Búsqueda por email (1 row)
SELECT * FROM customers WHERE email = 'customer25@example.com';

-- Query 2: Filter por país - Estados Unidos (20 filas)
SELECT c.id, c.name, c.country FROM customers WHERE country = 'USA' LIMIT 10;

-- Query 3: Aggregate simple - Órdenes por status (4 categorías)
SELECT status, COUNT(*) as count FROM orders GROUP BY status ORDER BY count DESC;

-- Query 4: Sequential Scan lento - Sin índice
SELECT id, numeric_value, category FROM large_table WHERE numeric_value > 40000 LIMIT 20;

-- Query 5: JOIN con índices - Órdenes con items
SELECT o.id, o.status, COUNT(oi.id) as items FROM orders o JOIN order_items oi ON o.id = oi.order_id WHERE o.customer_id BETWEEN 10 AND 20 GROUP BY o.id, o.status;

-- Query 6: Complex JOIN - 3 tablas
SELECT c.name, c.country, COUNT(o.id) as order_count, COUNT(oi.id) as item_count
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id
LEFT JOIN order_items oi ON o.id = oi.order_id
WHERE c.country IN ('USA', 'Canada', 'Germany')
GROUP BY c.id, c.name, c.country
ORDER BY order_count DESC LIMIT 15;

-- Query 7: Búsqueda en large_table con categoría (SÍ tiene índice)
SELECT category, AVG(numeric_value), MIN(numeric_value), MAX(numeric_value)
FROM large_table WHERE category IN ('A', 'B', 'C') GROUP BY category;
```

**Test Script - batch_test.sh:**
```bash
#!/bin/bash
# Batch test de seed queries

PROFILE=${1:-postgresql}
OUTPUT=${2:-json}

echo "Testing seed queries on $PROFILE in $OUTPUT format..."
echo ""

# Counter
query_num=1

# Leer queries (separadas por "-- Query X:")
while IFS= read -r line; do
    # Skip comments y líneas vacías
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    [[ "$line" =~ ^[[:space:]]*-- ]] && continue

    # Acumular query
    query="$query $line"

    # Si termina con ;, ejecutar
    if [[ "$query" =~ \; ]]; then
        echo "[$query_num] $(echo "$query" | cut -c1-80)..."
        qa analyze "$query" --profile $PROFILE --output $OUTPUT | head -5
        echo "---"
        ((query_num++))
        query=""
    fi
done < queries.sql

echo "Batch testing complete!"
```

**Ejecutar:**
```bash
chmod +x batch_test.sh
./batch_test.sh postgresql json
./batch_test.sh mysql json
./batch_test.sh sqlite rich
```

---

## Troubleshooting

### Services Won't Start

```bash
# Check if services are running
docker compose ps

# View logs
docker compose logs postgres      # View PostgreSQL logs
docker compose logs cockroachdb   # View CockroachDB logs
docker compose logs yugabytedb    # View YugabyteDB logs
```

### Services Won't Seed

```bash
# Verificar que servicios están healthy
make health

# Manual seed test - verificar datos específicos
docker compose exec postgres psql -U qa -d query_analyzer -c "SELECT COUNT(*) FROM customers;" # Debe ser 100
docker compose exec postgres psql -U qa -d query_analyzer -c "SELECT COUNT(*) FROM orders;" # Debe ser 100
docker compose exec postgres psql -U qa -d query_analyzer -c "SELECT COUNT(*) FROM order_items;" # Debe ser 500
docker compose exec postgres psql -U qa -d query_analyzer -c "SELECT COUNT(*) FROM large_table;" # Debe ser 10,000

# Si alguno es 0, intentar re-seed
make seed
```

**Troubleshooting específico de datos:**
```bash
# Verificar distribución de órdenes por cliente
docker compose exec postgres psql -U qa -d query_analyzer -c "SELECT customer_id, COUNT(*) FROM orders GROUP BY customer_id ORDER BY count DESC LIMIT 5;"

# Verificar órdenes por estado
docker compose exec postgres psql -U qa -d query_analyzer -c "SELECT status, COUNT(*) FROM orders GROUP BY status;"

# Verificar categorías en large_table
docker compose exec postgres psql -U qa -d query_analyzer -c "SELECT category, COUNT(*) FROM large_table GROUP BY category ORDER BY category;"
```

### Query Analysis Fails

```bash
# Verify connection profile
qa profile list

# Test profile connection
qa profile test postgres-local

# Try manual query execution
docker compose exec postgres psql -U qa -d query_analyzer -c "EXPLAIN ANALYZE SELECT * FROM customers LIMIT 1;"
```

### SQLite Database File Issues

```bash
# Verify database file exists
ls -lh query_analyzer.db

# Check file size
du -h query_analyzer.db

# Verify it has data
sqlite3 query_analyzer.db "SELECT COUNT(*) FROM customers;"

# Re-seed if needed
sqlite3 query_analyzer.db < docker/seed/init-sqlite.sql
```

### CockroachDB Connection Issues

```bash
# CockroachDB requires --insecure flag in development
# Verify container is running
docker compose logs query-analyzer-cockroachdb

# Test connection
docker compose exec cockroachdb cockroach sql --insecure -e "SELECT 1;"
```

### YugabyteDB Connection Issues

```bash
# Verify using correct port (5433, not 5432)
psql -h localhost -U qa -p 5433 -d query_analyzer -c "SELECT 1;"

# YugabyteDB takes 30-45 seconds to fully initialize
# Wait for health check to pass
make health
```

---

## Performance Expectations (Real Seed Data)

### Query Types with Seed Data

| Query Type | Example | Expected Plan | Rows | Time (PG) | Notes |
|------------|---------|----------------|------|-----------|-------|
| **Index Scan** | `WHERE email = 'customer50@example.com'` | Index Scan idx_customers_email | 1 | 0.1-0.5 ms | ✅ Muy rápido - 1 row exacto |
| **Index Filter** | `WHERE country = 'USA'` | Index Scan idx_customers_country | 20 | 0.3-1 ms | ✅ Rápido - 20 rows (20% de 100) |
| **Seq Scan (lento)** | `WHERE numeric_value > 40000` | Seq Scan large_table | ~2000 | 20-50 ms | ❌ Lento - 20% of 10K sin índice |
| **Seq Scan (rápido)** | `WHERE category = 'A'` | Index Scan idx_large_table_category | 1000 | 2-5 ms | ✅ Rápido - Índice en category |
| **GROUP BY (4 grupos)** | `GROUP BY status` | Index Scan + GroupAggregate | 4 | 1-3 ms | ✅ Muy rápido - solo 4 valores |
| **GROUP BY (10 grupos)** | `GROUP BY category` | Index Scan + GroupAggregate | 10 | 3-8 ms | ✅ Rápido - 10 categorías |
| **JOIN (100+500)** | `orders JOIN order_items` | Hash/Nested Loop Join | 500 | 5-15 ms | ✅ Rápido - ambas tablas pequeñas |
| **Complex JOIN (3 tablas)** | `c JOIN o JOIN oi` | Multiple Joins + GroupAggregate | variable | 20-50 ms | ⚠️ Medio - depende de filters |
| **Aggregate** | `COUNT(*) FROM orders` | Aggregate | 1 | 0.5-2 ms | ✅ Rápido - agregación simple |
| **Local Shard Query (CRDB)** | `WHERE region = 'US'` | Index Scan (local) | 10 | 1-5 ms | ✅ Rápido - shard local, sin overhead |
| **Cross-Shard GROUP BY (CRDB)** | `GROUP BY region` | Dist. Scan + Consolidate | 5 | 50-150 ms | ⚠️ Network overhead - multi-region |
| **Distributed JOIN (CRDB)** | `u JOIN t ON u.id = t.user_id` | Data Reshuffling | variable | 200-500 ms | ❌ Costoso - data movement entre shards |
| **Bounded Time-Series** | `range(start: -7d) \| mean()` | Range Scan + Aggregate | 100 | 1-5 ms | ✅ Rápido - bounded query |
| **Unbounded Time-Series** | `filter(...) \| mean()` | Full Bucket Scan | 450 | 50-200 ms | ❌ Muy lento - sin range |
| **High Cardinality TS** | `group(columns: [...4 tags...])` | Range + Multi-Group | variable | 20-100 ms | ⚠️ Riesgo OOM - demasiadas dimensiones |
| **Label Scan + Filter (Neo4j)** | `MATCH (u:User {country: 'US'})` | NodeByLabelScan | 100 | 28-35 ms | ✅ Rápido - indexed property lookup |
| **Relationship Aggregation (Neo4j)** | `(u)-[:PURCHASED]->(p) COUNT(p)` | Expand + Aggregate | 5 | 95-105 ms | ✅ Eficiente - expansión y agrupación |
| **Multi-Hop Join (Neo4j)** | `(u)-[:FOLLOWS]->(f)-[:PURCHASED]->(p)` | Multi-Expand + Filter | 20 | 95-105 ms | ✅ Óptimo - sin Cartesian product |
| **Path Finding (Neo4j)** | `(u)-[*1..5]-(related)` | Variable-Length Expand | variable | 95-105 ms | ✅ Bounded - 1..5 hops seguros |

### Performance by Engine (with Seed Data)

| Operation | PostgreSQL | MySQL | SQLite | CockroachDB | YugabyteDB | InfluxDB | Neo4j |
|-----------|-----------|-------|--------|-------------|------------|----------|-------|
| **Index Scan (1 row)** | 0.1-0.5 ms | 0.5-2 ms | 0.2-1 ms | 5-10 ms | 10-20 ms | N/A | 28-35 ms |
| **Index Scan (20 rows)** | 0.3-1 ms | 1-3 ms | 0.5-2 ms | 8-15 ms | 15-30 ms | N/A | 28-35 ms |
| **Seq Scan (2K of 10K)** | 20-30 ms | 30-50 ms | 50-100 ms | 80-150 ms | 150-250 ms | N/A | N/A |
| **GROUP BY (4 status)** | 1-2 ms | 2-5 ms | 2-5 ms | 10-20 ms | 20-40 ms | N/A | N/A |
| **GROUP BY (10 category)** | 3-5 ms | 5-10 ms | 5-10 ms | 20-40 ms | 40-80 ms | N/A | N/A |
| **JOIN (100+500 rows)** | 5-10 ms | 10-20 ms | 15-30 ms | 30-80 ms | 80-200 ms | N/A | 95-105 ms |
| **Local Shard Query (1 region)** | N/A | N/A | N/A | 1-5 ms | N/A | N/A | N/A |
| **Cross-Shard GROUP BY (5 regions)** | N/A | N/A | N/A | 50-150 ms | N/A | N/A | N/A |
| **Distributed JOIN (reshuffling)** | N/A | N/A | N/A | 200-500 ms | N/A | N/A | N/A |
| **Multi-Region Aggregation** | N/A | N/A | N/A | 150-300 ms | N/A | N/A | N/A |
| **Bounded TS (range + agg)** | N/A | N/A | N/A | N/A | N/A | 1-5 ms | N/A |
| **Unbounded TS (no range)** | N/A | N/A | N/A | N/A | N/A | 50-200 ms | N/A |
| **High Cardinality TS** | N/A | N/A | N/A | N/A | N/A | 20-100 ms | N/A |
| **Excessive Transforms TS** | N/A | N/A | N/A | N/A | N/A | 30-150 ms | N/A |
| **Relationship Aggregation** | N/A | N/A | N/A | N/A | N/A | N/A | 95-105 ms |
| **Multi-Hop Join** | N/A | N/A | N/A | N/A | N/A | N/A | 95-105 ms |
| **Path Finding (Variable-Length)** | N/A | N/A | N/A | N/A | N/A | N/A | 95-105 ms |

*Notas:*
- *CockroachDB distributed queries show overhead even in single-node (educational demo of sharding)*
- *Local shard queries comparable to PostgreSQL; cross-shard queries show consolidation cost*
- *YugabyteDB overhead similar but different execution strategy*
- *SQLite es embebido pero puede ser más lento que PostgreSQL en queries complejas*
- *InfluxDB optimizado para time-series; queries sin range() son extremadamente caras*
- *InfluxDB high cardinality (4+ tags) puede causar OOM en buckets grandes*
- *Neo4j excels at relationship queries; simpler than SQL JOINs for multi-hop traversals*
- *Neo4j variable-length paths must be bounded [*1..N] to prevent unbounded expansion*
- *Neo4j aggregations use WITH clause (equivalent to GROUP BY in SQL)*
- *Tiempos incluyen planning + execution*
- *Real times varían según recursos del sistema y carga*

### Seed Data Statistics

| Table | Rows | Columns | Indexes | Key Features |
|-------|------|---------|---------|--------------|
| **customers** | 100 | 5 | email, country | Distribuida: 20/país (USA, UK, Canada, Germany, France) |
| **orders** | 100 | 5 | customer_id, order_date, status | Status: 25 pending, 25 processing, 25 shipped, 25 delivered |
| **order_items** | 500 | 5 | order_id (SÍ), NO product_id | ~5 items/orden, product_id: 0-999 random |
| **large_table** | 10,000 | 5 | category | Category: A-J (~1K c/u), numeric_value: NO tiene índice |
| **slow_queries_log** | 1,000 | 5 | execution_time | query_type: SELECT/JOIN/AGGREGATE/UPDATE/DELETE |

### CockroachDB-Specific Seed Data (Distributed Sharding)

| Table | Rows | Shard Key | Indexes | Distribution |
|-------|------|-----------|---------|--------------|
| **regional_users** | 1,000 | region | email, region | 5 regions × 200 users (US, EU, APAC, LATAM, MENA) |
| **regional_transactions** | 5,000 | region | status, user_id, region | ~5 txn/user, co-located with user region |
| **shard_distribution** | 5 | region | region (UNIQUE) | Meta-info: user/txn counts, latency per region |
| **hot_keys_log** | 500 | (none) | region | Hotspot monitoring, contention simulation |

**Sharding Pattern:**
- Data partitioned by `region` column (US, EU, APAC, LATAM, MENA)
- Each region represents a "node" in the distributed system
- Queries filtering by single region = LOCAL shard (fast, ~1-5ms)
- Queries across regions = CROSS-SHARD (slower, requires consolidation, ~50-500ms)
- Expected latency increase with geographic distance: US (5.2ms) → EU (8.5ms) → APAC (12.3ms) → LATAM (15.7ms) → MENA (18.9ms)

### Neo4j-Specific Seed Data (Social Commerce Graph)

| Node/Rel | Count | Indexes | Key Patterns | Characteristics |
|----------|-------|---------|--------------|-----------------|
| **Users** | 500 | user_id, country | 5 countries × 100 users (US, UK, DE, FR, JP) | Properties: id, name, email, country, registration_date |
| **Products** | 100 | product_id, price | 10 categories × 10 products | Properties: id, title, price, category_id, stock, created_date |
| **Categories** | 10 | category_id | Taxonomy for products | Properties: id, name, description |
| **PURCHASED** | 899 | (implicit) | ~1.8 per user, relationship history | Properties: quantity, purchase_date |
| **VIEWED** | 1,600 | (implicit) | ~3.2 per user, browsing behavior | Properties: view_date |
| **FOLLOWS** | 499 | (implicit) | ~1.0 per user, social network | Properties: since |
| **LIKES** | 400 | (implicit) | ~0.8 per user, preference signals | No properties |

**Graph Pattern:**
- Social commerce network: Users → Products (via PURCHASED, VIEWED, LIKES)
- Social connections: User → User (via FOLLOWS)
- Sparse network (3,398 total relationships, ~5.6 per node average)
- Multi-hop patterns safe: FOLLOWS-PURCHASED (3 hops) with no Cartesian risk
- Variable-length paths bounded [1..5] for safety: discover related products through network

**Index Strategy:**
- Label property indexes on high-cardinality columns: country, id, price
- No relationship indexes (implicit navigation via labels)
- Constraint indexes ensure uniqueness: user_id, product_id, category_id



---

## Next Steps

1. ✅ All databases seeded and ready
2. ✅ Query Analyzer CLI tested on multiple engines
3. 📊 Analyze your own queries using `qa analyze`
4. 🔍 Compare performance across engines
5. 🚀 Deploy to production with appropriate engine selection
