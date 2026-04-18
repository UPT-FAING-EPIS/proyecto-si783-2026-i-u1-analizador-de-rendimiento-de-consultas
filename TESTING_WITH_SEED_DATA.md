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
6. [Advanced Testing Scenarios](#advanced-testing-scenarios)
7. [Troubleshooting](#troubleshooting)
8. [Performance Expectations](#performance-expectations)

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
qa analyze "SELECT * FROM customers WHERE email = 'customer50@example.com';" --profile postgresql
qa analyze "SELECT o.id, o.status, o.total_amount FROM orders o WHERE o.customer_id = 25;" --profile postgresql
```

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
qa analyze "SELECT country, COUNT(*) FROM customers GROUP BY country;" --profile mysql
qa analyze "SELECT status, COUNT(*) FROM orders GROUP BY status;" --profile mysql
```

---

### SQLite

**Connection Details:**
- Database file: `query_analyzer.db` (local file in project directory)
- User: Not needed (SQLite has no authentication)
- No port (file-based)
- Profile name: `sqlite`

**Test Commands:**

```bash
qa analyze "SELECT email, country FROM customers WHERE email = 'customer50@example.com';" --profile sqlite
qa analyze "SELECT * FROM customers WHERE id = 75;" --profile sqlite
qa analyze "SELECT * FROM large_table WHERE numeric_value > 30000;" --profile sqlite
qa analyze "SELECT o.id, oi.product_id FROM orders o JOIN order_items oi ON o.id = oi.order_id WHERE o.customer_id = 5;" --profile sqlite
qa analyze "SELECT category, COUNT(*) as count FROM large_table GROUP BY category;" --profile sqlite
qa analyze "SELECT * FROM orders ORDER BY order_date DESC LIMIT 10;" --profile sqlite
qa analyze "SELECT * FROM customers WHERE name LIKE '%Customer 5%';" --profile sqlite
qa analyze "SELECT * FROM large_table WHERE category = 'A' LIMIT 5;" --profile sqlite
```

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
qa analyze "SELECT user_id, name, email FROM regional_users WHERE region = 'US' AND email LIKE '%@us-company.com' LIMIT 10;" --profile cockroachdb
qa analyze "SELECT region, COUNT(*) as user_count FROM regional_users GROUP BY region ORDER BY user_count DESC;" --profile cockroachdb
qa analyze "SELECT u.region, u.name, COUNT(t.txn_id) as txn_count FROM regional_users u JOIN regional_transactions t ON u.user_id = t.user_id WHERE t.status = 'completed' GROUP BY u.region, u.name HAVING COUNT(t.txn_id) > 3;" --profile cockroachdb
qa analyze "SELECT region, AVG(amount) as avg_txn_amount, MAX(amount) as max_txn_amount, COUNT(*) as total_txns FROM regional_transactions WHERE txn_timestamp > NOW() - INTERVAL '7 days' GROUP BY region ORDER BY avg_txn_amount DESC;" --profile cockroachdb
```

---

### YugabyteDB

**Connection Details:**
- Host: `localhost`
- Port: `5433` (YSQL port, NOT 5432 which is PostgreSQL)
- User: `yugabyte`
- Password: `yugabyte`
- Database: `query_analyzer`

**Test Commands:**

```bash
qa analyze "SELECT * FROM customers WHERE email = 'john@ex.com';" --profile yugabytedb
qa analyze "SELECT * FROM customers WHERE id = 1;" --profile yugabytedb
qa analyze "SELECT * FROM large_table WHERE numeric_value > 1000;" --profile yugabytedb
qa analyze "SELECT c.id, o.id FROM customers c JOIN orders o ON c.id = o.customer_id;" --profile yugabytedb
qa analyze "SELECT COUNT(*) FROM orders;" --profile yugabytedb
qa analyze "SELECT * FROM customers ORDER BY email;" --profile yugabytedb
qa analyze "SELECT * FROM large_table WHERE data_value LIKE '%value%';" --profile yugabytedb
qa analyze "SELECT * FROM customers LIMIT 5;" --profile yugabytedb
```

---

### InfluxDB

**Connection Details:**
- Host: `localhost`
- Port: `8086`
- Token: `mytoken`
- Organization: `myorg`
- Bucket: `query_analyzer`

**Test Commands:**

```bash
qa analyze 'from(bucket:"query_analyzer") |> range(start: -7d) |> filter(fn: (r) => r._measurement == "cpu") |> filter(fn: (r) => r.host == "server1") |> mean()' --profile influxdb
qa analyze 'from(bucket:"query_analyzer") |> filter(fn: (r) => r._measurement == "memory") |> mean()' --profile influxdb
qa analyze 'from(bucket:"query_analyzer") |> range(start: -24h) |> filter(fn: (r) => r._measurement == "query_latency") |> group(columns: ["host", "region", "service", "endpoint"]) |> mean()' --profile influxdb
qa analyze 'from(bucket:"query_analyzer") |> range(start: -7d) |> filter(fn: (r) => r._measurement == "disk") |> derivative() |> mean() |> sort(columns: ["_value"]) |> limit(n: 100) |> map(fn: (r) => ({r with value_doubled: r._value * 2}))' --profile influxdb
```

---

### Elasticsearch

**Connection Details:**
- Host: `localhost`
- Port: `9200`
- Index: `test_products`
- No authentication (dev/testing mode)

**Test Commands:**

```bash
qa analyze '{"match_all": {}}' --profile elasticsearch
qa analyze '{"term": {"status": {"value": "active"}}}' --profile elasticsearch
qa analyze '{"bool": {"filter": [{"term": {"status": "active"}}, {"term": {"category": "electronics"}}]}}' --profile elasticsearch
qa analyze '{"wildcard": {"name": {"value": "*test*"}}}' --profile elasticsearch
qa analyze '{"script_score": {"query": {"match_all": {}}, "script": {"source": "_score * params.factor", "params": {"factor": 1.2}}}}' --profile elasticsearch
qa analyze '{"bool": {"should": [{"wildcard": {"name": {"value": "*laptop*"}}}, {"script_score": {"query": {"match_all": {}}, "script": {"source": "_score"}}}]}}' --profile elasticsearch
qa analyze '{"match": {"name": "laptop"}}' --profile elasticsearch
qa analyze '{"bool": {"filter": [{"range": {"price": {"gte": 50, "lte": 500}}}]}}' --profile elasticsearch
```

---

### Redis

**Connection Details:**
- Host: `localhost`
- Port: `6379`
- Database: `0` (default)
- No authentication (dev/testing mode)

**Test Commands:**

```bash
qa analyze "SET key1 value1" --profile redis
qa analyze "GET key1" --profile redis
qa analyze "HSET user:1 name John email john@example.com" --profile redis
qa analyze "LPUSH queue:tasks task1 task2 task3" --profile redis
qa analyze "FLUSHDB" --profile redis
qa analyze "KEYS *" --profile redis
qa analyze "INFO server" --profile redis
qa analyze "SET session:abc xyz EX 3600" --profile redis
```

---

### MongoDB

**Connection Details:**
- Host: `localhost`
- Port: `27017`
- User: `admin`
- Password: `mongodb123`
- Database: `query_analyzer`

**Test Commands:**

```bash
qa analyze '{"collection":"users","filter":{"age":{"$gt":30}}}' --profile mongodb
qa analyze '{"collection":"logs","filter":{"level":"ERROR"}}' --profile mongodb
qa analyze '{"collection":"users","filter":{"premium":true},"projection":{"name":1,"email":1}}' --profile mongodb
qa analyze '{"collection":"users","filter":{"status":"active"},"sort":{"created_at":-1}}' --profile mongodb
qa analyze '{"collection":"users","filter":{"_id":1}}' --profile mongodb
qa analyze '{"collection":"nonexistent"}' --profile mongodb
```

---

### Neo4j

**Connection Details:**
- Host: `localhost`
- Port: `7687` (Bolt protocol)
- User: `neo4j`
- Password: `neo4j123`
- Database: `neo4j` (default)

**Test Commands:**

```bash
qa analyze "MATCH (u:User {country: 'US'}) RETURN u.id, u.name, u.email LIMIT 5" --profile neo4j
qa analyze "MATCH (u:User)-[:FOLLOWS]->(f:User) RETURN DISTINCT u.country, f.country, COUNT(*) as follows_per_pair" --profile neo4j
qa analyze "MATCH (u:User)-[:FOLLOWS]->(f:User)-[:PURCHASED]->(p:Product)-[:COMMENTED]->(c:User) RETURN COUNT(DISTINCT p) as product_count" --profile neo4j
qa analyze "MATCH (a:User)-[:COMMENTED]->(p:Product)<-[:COMMENTED]-(b:User) WHERE a.country = b.country RETURN a.country, COUNT(DISTINCT a) as users, COUNT(DISTINCT p) as products" --profile neo4j
``
