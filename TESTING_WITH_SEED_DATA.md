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

**Test Commands:**

```bash
# Via Query Analyzer CLI - GROUP BY distribuido
qa analyze "SELECT status, COUNT(*) FROM orders GROUP BY status ORDER BY status;" --profile cockroachdb

# Manual test - Ver plan distribuido
docker compose exec cockroachdb cockroach sql --insecure -d query_analyzer -e "EXPLAIN SELECT c.name, COUNT(o.id) FROM customers c JOIN orders o ON c.id = o.customer_id GROUP BY c.id, c.name LIMIT 20;"

# Búsqueda por país (distribuida)
qa analyze "SELECT country, COUNT(*) FROM customers GROUP BY country;" --profile cockroachdb

# JOIN distribuido
qa analyze "SELECT o.id, oi.product_id, oi.quantity FROM orders o JOIN order_items oi ON o.id = oi.order_id WHERE o.status = 'shipped';" --profile cockroachdb
```

**Expected Results:**
- ✅ Planes de query distribuidos (muestra rangos de scan)
- ✅ Sintaxis PostgreSQL-compatible (puede usar EXPLAIN)
- ✅ Uso de índices similar a PostgreSQL
- ✅ Overhead distribuido visible (incluso en modo single-node)

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
| **Bounded Time-Series** | `range(start: -7d) \| mean()` | Range Scan + Aggregate | 100 | 1-5 ms | ✅ Rápido - bounded query |
| **Unbounded Time-Series** | `filter(...) \| mean()` | Full Bucket Scan | 450 | 50-200 ms | ❌ Muy lento - sin range |
| **High Cardinality TS** | `group(columns: [...4 tags...])` | Range + Multi-Group | variable | 20-100 ms | ⚠️ Riesgo OOM - demasiadas dimensiones |

### Performance by Engine (with Seed Data)

| Operation | PostgreSQL | MySQL | SQLite | CockroachDB | YugabyteDB | InfluxDB |
|-----------|-----------|-------|--------|-------------|------------|----------|
| **Index Scan (1 row)** | 0.1-0.5 ms | 0.5-2 ms | 0.2-1 ms | 5-10 ms | 10-20 ms | N/A |
| **Index Scan (20 rows)** | 0.3-1 ms | 1-3 ms | 0.5-2 ms | 8-15 ms | 15-30 ms | N/A |
| **Seq Scan (2K of 10K)** | 20-30 ms | 30-50 ms | 50-100 ms | 80-150 ms | 150-250 ms | N/A |
| **GROUP BY (4 status)** | 1-2 ms | 2-5 ms | 2-5 ms | 10-20 ms | 20-40 ms | N/A |
| **GROUP BY (10 category)** | 3-5 ms | 5-10 ms | 5-10 ms | 20-40 ms | 40-80 ms | N/A |
| **JOIN (100+500 rows)** | 5-10 ms | 10-20 ms | 15-30 ms | 30-80 ms | 80-200 ms | N/A |
| **Bounded TS (range + agg)** | N/A | N/A | N/A | N/A | N/A | 1-5 ms |
| **Unbounded TS (no range)** | N/A | N/A | N/A | N/A | N/A | 50-200 ms |
| **High Cardinality TS** | N/A | N/A | N/A | N/A | N/A | 20-100 ms |
| **Excessive Transforms TS** | N/A | N/A | N/A | N/A | N/A | 30-150 ms |

*Notas:*
- *CockroachDB y YugabyteDB tienen overhead distribuido incluso en single-node*
- *SQLite es embebido pero puede ser más lento que PostgreSQL en queries complejas*
- *InfluxDB optimizado para time-series; queries sin range() son extremadamente caras*
- *InfluxDB high cardinality (4+ tags) puede causar OOM en buckets grandes*
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



---

## Next Steps

1. ✅ All databases seeded and ready
2. ✅ Query Analyzer CLI tested on multiple engines
3. 📊 Analyze your own queries using `qa analyze`
4. 🔍 Compare performance across engines
5. 🚀 Deploy to production with appropriate engine selection
