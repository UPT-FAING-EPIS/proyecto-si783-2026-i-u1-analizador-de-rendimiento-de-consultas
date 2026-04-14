# Cassandra Query Performance Analyzer

Comprehensive query performance analysis for Apache Cassandra with anti-pattern detection.

## Features

### ✅ TRACING Support
- Captures event timeline via `TRACING ON`
- Analyzes coordinator and replica operations
- Measures execution time and distributed access patterns

### 🚨 Anti-Pattern Detection (7 Patterns)

| Anti-Pattern | Severity | Penalty | Detection Method |
|---|---|---|---|
| **ALLOW FILTERING** | CRITICAL | -40 pts | Query text regex |
| **Full Cluster Scan** | CRITICAL | -40 pts | Query filters on non-partition-key columns |
| **Wide Distributed Query** | HIGH | -25 pts | Replica touch count >5 |
| **Unfiltered Query** | HIGH | -25 pts | No WHERE clause |
| **No LIMIT Clause** | MEDIUM | -15 pts | WHERE without LIMIT |
| **Clustering Without Partition Key** | MEDIUM | -15 pts | Clustering filters without partition key |
| **N+1 Query Pattern** | MEDIUM | -15 pts | Multiple queries instead of batch |

### 📊 Metrics & Analysis

- **Schema Analysis**: Partition key, clustering key, and column detection
- **Execution Timeline**: Trace events from coordinator and replicas
- **Partition Size Estimation**: Via `system.size_estimates` table
- **Cluster Topology**: Node count, replication factor analysis
- **Scoring**: 0-100 scale with cumulative penalties

## Installation

### Step 1: Install cassandra-driver

```bash
pip install cassandra-driver==3.29.3
```

> **Note**: `cassandra-driver` is optional and made available separately due to Windows+Python 3.14 build issues.

### Step 2: Verify Installation

```bash
python -c "from cassandra.cluster import Cluster; print('OK')"
```

## Usage

### Basic Connection

```python
from query_analyzer.adapters import CassandraAdapter, ConnectionConfig

config = ConnectionConfig(
    engine="cassandra",
    host="127.0.0.1",
    port=9042,
    database="my_keyspace",
    username="cassandra",
    password="cassandra",
    extra={"protocol_version": 3}
)

adapter = CassandraAdapter(config)
adapter.connect()
```

### Analyze Query

```python
query = "SELECT * FROM users WHERE email = 'test@example.com' ALLOW FILTERING"
report = adapter.execute_explain(query)

print(f"Score: {report.score}/100")
print(f"Execution time: {report.execution_time_ms:.2f}ms")
print(f"Warnings: {len(report.warnings)}")
print(f"Recommendations: {len(report.recommendations)}")

# Print recommendations
for rec in report.recommendations:
    print(f"  - {rec.title}")
```

### Example Output

```
Score: 60/100
Execution time: 50.23ms
Warnings: 2
Recommendations: 2
  - Remove ALLOW FILTERING and add partition key to WHERE clause
  - Add partition key filter to WHERE clause. Partition keys are: user_id
```

## Adapter Architecture

### Components

1. **CassandraAdapter** (`query_analyzer/adapters/nosql/cassandra.py`)
   - Connection management
   - Query execution with tracing
   - Schema caching from system tables
   - Integration with anti-pattern detector

2. **CassandraExplainParser** (`query_analyzer/adapters/nosql/cassandra_parser.py`)
   - Trace event parsing
   - Replica touch counting
   - Partition key analysis
   - Query-to-plan-tree conversion

3. **CassandraAntiPatternDetector** (`query_analyzer/core/cassandra_anti_pattern_detector.py`)
   - Anti-pattern detection
   - Score calculation (0-100)
   - Recommendation generation
   - Engine-agnostic design

### Query Flow

```
User Query
    ↓
CassandraAdapter.execute_explain()
    ↓
[Parse Query] → Extract table name
    ↓
[Load Schema] → Get partition/clustering keys from system_schema.columns
    ↓
[Execute with TRACING] → Capture event timeline
    ↓
CassandraExplainParser.parse()
    ↓
[Normalize Plan] → Standard format for detection
    ↓
CassandraAntiPatternDetector.analyze()
    ↓
[Generate Report] → Score, warnings, recommendations
    ↓
QueryAnalysisReport
```

## Configuration

### ConnectionConfig Fields

| Field | Type | Required | Default | Notes |
|---|---|---|---|---|
| `engine` | str | ✅ | - | Must be "cassandra" |
| `host` | str | ✅ | - | IP or hostname of contact point |
| `port` | int | ❌ | 9042 | Cassandra native port |
| `database` | str | ✅ | - | Keyspace name |
| `username` | str | ❌ | None | For authentication |
| `password` | str | ❌ | None | For authentication |
| `extra` | dict | ❌ | {} | `{"protocol_version": 3}` or `4` |

### Example Configurations

**Local Development**
```python
ConnectionConfig(
    engine="cassandra",
    host="localhost",
    port=9042,
    database="development",
)
```

**Production with Auth**
```python
ConnectionConfig(
    engine="cassandra",
    host="cassandra-prod.example.com",
    port=9042,
    database="production",
    username="analytics_user",
    password=os.environ["CASSANDRA_PASSWORD"],
    extra={"protocol_version": 4}
)
```

**Docker Compose**
```python
ConnectionConfig(
    engine="cassandra",
    host="cassandra",  # service name
    port=9042,
    database="demo",
)
```

## Query Analysis Examples

### ✅ Good Query

```python
query = "SELECT id, name FROM users WHERE user_id = ? LIMIT 100"
report = adapter.execute_explain(query)
# Score: 100/100 - Optimal
```

### ❌ ALLOW FILTERING (Critical)

```python
query = "SELECT * FROM users WHERE email = ? ALLOW FILTERING"
report = adapter.execute_explain(query)
# Score: 60/100 - Critical issue
# Recommendation: Remove ALLOW FILTERING, add partition key filter
```

### ❌ Full Cluster Scan

```python
query = "SELECT * FROM users WHERE email = 'test@example.com'"
report = adapter.execute_explain(query)
# Score: 60/100 - Will scan entire cluster
# Recommendation: Filter by partition key (user_id) first
```

### ⚠️ No LIMIT

```python
query = "SELECT * FROM audit_log WHERE date > '2024-01-01'"
report = adapter.execute_explain(query)
# Score: 75/100 - May return large result set
# Recommendation: Add LIMIT clause and paginate
```

## System Tables Required

The adapter queries these Cassandra system tables:

| Table | Purpose |
|---|---|
| `system.local` | Cluster name, version, schema version |
| `system.peers` | Node count |
| `system_schema.columns` | Table schema, partition/clustering keys |
| `system.size_estimates` | Partition size estimation |

> **Note**: User must have read permissions on system tables.

## Limitations

1. **No Native EXPLAIN**: Cassandra doesn't have EXPLAIN PLAN like SQL databases
   - Workaround: Uses TRACING and schema analysis

2. **No Slow Query Log**: Unlike MySQL/PostgreSQL, Cassandra has no built-in slow query log
   - Workaround: Application-level metrics or custom instrumentation

3. **Sampling-Based**: `system.size_estimates` is a sample, not exact count
   - Accuracy: ±10-20% for large tables

4. **Version Support**: Tested with Cassandra 3.11+
   - Compatibility with 4.x via `protocol_version` config

5. **No Query Hints**: Anti-pattern detection is heuristic-based
   - May have false positives for edge cases

## Testing

### Unit Tests (33 tests, all passing)

```bash
# Run parser tests
uv run python -m pytest tests/unit/test_cassandra_parser.py -v

# Run detector tests
uv run python -m pytest tests/unit/test_cassandra_anti_pattern_detector.py -v

# Run all tests
uv run python -m pytest tests/unit/test_cassandra*.py -v
```

### Integration Tests (requires Docker)

```bash
# Start Cassandra service
make up

# Run integration tests
uv run python -m pytest tests/integration/test_cassandra_integration.py -v

# Cleanup
make down
```

## Troubleshooting

### cassandra-driver Installation Fails

```
# Windows + Python 3.14 compatibility issue
# Solution: Use pre-built wheel or alternative container
pip install --only-binary :all: cassandra-driver
```

### Connection Refused

```
ConnectionError: Failed to connect to Cassandra cluster at 127.0.0.1:9042

# Troubleshooting:
1. Check Cassandra is running: docker ps | grep cassandra
2. Verify port: telnet 127.0.0.1 9042
3. Check credentials: Try without auth first
4. Check protocol_version matches cluster
```

### Authentication Failed

```
ConnectionError: Invalid authentication or keyspace

# Solutions:
1. Verify username/password are correct
2. Check user has access to keyspace
3. Verify authentication is enabled in cassandra.yaml
4. Try default credentials: cassandra/cassandra
```

### Trace is Empty

```
# If trace.events is empty:
1. Cassandra tracing may be disabled
2. TRACING ON requires permission
3. Trace may not persist (try re-running)
```

## Performance Notes

- **Query Analysis**: 50-100ms per query (depends on cluster size)
- **Schema Cache**: Loaded once per table (minimal overhead)
- **Memory**: ~1KB per table schema cached
- **Network**: Minimal - only system table queries

## Related Documentation

- [Apache Cassandra Query Tracing](https://cassandra.apache.org/doc/latest/cassandra/troubleshooting/debugging.html#tracing)
- [Cassandra Data Modeling](https://cassandra.apache.org/doc/latest/cassandra/data-modeling/intro.html)
- [cassandra-driver Python](https://datastax-oss.atlassian.net/wiki/spaces/PYTHONDRIVER/pages/25689095/Connecting)

## Contributing

To extend anti-pattern detection:

1. Add new pattern to `CassandraAntiPatternDetector.analyze()`
2. Create test case in `test_cassandra_anti_pattern_detector.py`
3. Add recommendation logic in `_generate_recommendations()`
4. Update this README with new pattern

## License

Part of query-analyzer project - See LICENSE file.
