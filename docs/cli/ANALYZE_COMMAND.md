# Query Analyzer CLI - Analyze Command

This document provides comprehensive documentation for the **Analyze** command in the Query Analyzer CLI.

## Overview

The `analyze` command executes an SQL query against a configured database profile and provides a detailed performance analysis report using database-native EXPLAIN output.

## Command Syntax

```
qa analyze [QUERY] [OPTIONS]
```
qa analyze [QUERY] [OPTIONS]
```

---

## Command Details

### `analyze` - Analyze Query Performance

**Purpose**: Execute SQL query with EXPLAIN analysis and generate performance insights.

**Syntax**:
```bash
qa analyze [QUERY] [OPTIONS]
```

**Arguments**:
- `QUERY` (optional): SQL query string to analyze
  - If omitted, you'll be prompted interactively
  - Must start with: SELECT, UPDATE, DELETE, INSERT, or WITH
  - Must be a single statement (no multi-statement injection)

**Options**:
| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--profile` | `-p` | string | (default profile) | Profile name to use for connection |
| `--file` | `-f` | path | — | Read query from file instead of argument |
| `--output` | `-o` | string | `rich` | Output format: `rich`, `json`, `markdown` |
| `--timeout` | `-t` | integer | 30 | Query timeout in seconds |
| `--verbose` | `-v` | flag | — | Enable verbose debugging output |

---

## Query Input Methods

The query can be provided in 4 ways (use **exactly one**):

### 1. Positional Argument (Direct)
```bash
qa analyze "SELECT * FROM users WHERE status = 'active'"
```

### 2. File Path
```bash
qa analyze --file complex_query.sql
```

### 3. Stdin (Piped)
```bash
cat queries/top_tables.sql | qa analyze
```

```bash
cat <<EOF | qa analyze
SELECT COUNT(*) as total_users,
       AVG(age) as avg_age
FROM users
WHERE created_at > '2024-01-01'
EOF
```

### 4. Interactive Prompt (No Query Provided)
```bash
$ qa analyze
Enter your SQL query (Ctrl+D to submit):
SELECT * FROM products
WHERE category = 'electronics'
AND price > 100
```

**Invalid**: Multiple sources
```bash
# ❌ ERROR: Query provided from multiple sources
qa analyze "SELECT ..." --file query.sql

# ❌ ERROR: Query provided from multiple sources
cat query.sql | qa analyze "SELECT ..."
```

---

## Profile Selection

### 1. Explicit Profile
```bash
qa analyze --profile staging "SELECT * FROM users"
```

### 2. Default Profile (No --profile)
```bash
# Uses default profile set via: qa profile set-default <name>
qa analyze "SELECT * FROM users"
```

### 3. Interactive Profile Selection (No default set)
```bash
$ qa analyze "SELECT * FROM users"
Select Profile:
▶ local-dev (postgresql)
  staging (mysql)
  production (postgresql) [DEFAULT]

Analyzing with profile 'local-dev'...
```

**If no profiles exist**:
```
[ERROR] No profile specified.
No --profile provided and no default profile configured.

Usage:
  qa analyze --profile mydb "SELECT..."

Or set a default profile:
  qa profile set-default staging
  qa analyze "SELECT..."
```

---

## Output Formats

The output format can be selected in **3 ways**:

### 1. Explicit --output Flag
```bash
qa analyze "SELECT * FROM users" --output json
qa analyze "SELECT * FROM users" --output markdown
qa analyze "SELECT * FROM users" --output rich
```

### 2. Interactive Menu (Omit --output flag)
```bash
$ qa analyze "SELECT * FROM users"
Select output format:
▶ rich (formatted table)
  json (machine-readable)
  markdown (for documentation)

Query Performance Analysis
...
```

### 3. Default (No flag, no TTY)
In non-interactive mode (CI/scripts), defaults to `json` (most portable).

---

### Format Details

#### 1. Rich Table (Default - Formatted)
```bash
qa analyze "SELECT * FROM users LIMIT 10"
```

**Output**:
```
Query Performance Analysis
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Metric          ┃ Value        ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ Profile         │ local-dev    │
│ Engine          │ PostgreSQL   │
│ Execution Time  │ 12ms         │
│ Rows Returned   │ 10           │
│ Score           │ 85/100       │
└━━━━━━━━━━━━━━━━━┴━━━━━━━━━━━━━━┘

Warnings
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ⚠ Sequential Scan on table   ┃
┃ ⚠ Missing index on user_id   ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

Recommendations
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ✓ CREATE INDEX idx_user_id   ┃
┃ ✓ Add LIMIT to query         ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

### 2. JSON Format (Machine-Readable)
```bash
qa analyze "SELECT * FROM users" --output json
```

**Output**:
```json
{
  "profile": "local-dev",
  "engine": "postgresql",
  "query": "SELECT * FROM users",
  "execution_time_ms": 12.5,
  "rows_returned": 10,
  "score": 85,
  "warnings": [
    "Sequential Scan on table users",
    "Missing index on user_id"
  ],
  "recommendations": [
    "CREATE INDEX idx_user_id ON users(id)",
    "Add LIMIT to query"
  ],
  "explain_output": "Seq Scan on users..."
}
```

### 3. Markdown Format (Documentation)
```bash
qa analyze "SELECT * FROM users" --output markdown
```

**Output**:
```markdown
# Query Performance Analysis

## Profile
- **Name**: local-dev
- **Engine**: PostgreSQL
- **Host**: localhost:5432

## Performance Metrics
| Metric | Value |
|--------|-------|
| Execution Time | 12ms |
| Rows Returned | 10 |
| Score | 85/100 |

## Warnings
- ⚠ Sequential Scan on table users
- ⚠ Missing index on user_id

## Recommendations
- ✓ CREATE INDEX idx_user_id ON users(id)
- ✓ Add LIMIT to query

## Raw EXPLAIN Output
\`\`\`
Seq Scan on users
...
\`\`\`
```

---

## Examples

### Basic Analysis
```bash
qa analyze "SELECT * FROM orders WHERE status = 'pending'"
```

### With Specific Profile
```bash
qa analyze --profile staging "SELECT COUNT(*) FROM products"
```

### From File
```bash
# Query stored in complex_report.sql
qa analyze --file complex_report.sql
```

### From Stdin
```bash
# Via pipe
cat query.sql | qa analyze

# Via heredoc
qa analyze <<EOF
SELECT u.id, u.name, COUNT(o.id) as total_orders
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
GROUP BY u.id, u.name
ORDER BY total_orders DESC
LIMIT 100
EOF
```

### Custom Timeout

You can specify timeout in **3 ways**:

#### 1. Explicit --timeout Flag
```bash
# Increase timeout for large tables (60 seconds)
qa analyze --timeout 60 "SELECT * FROM huge_table"

# Decrease timeout for quick checks (5 seconds)
qa analyze --timeout 5 "SELECT COUNT(*) FROM users"
```

**Valid range**: 1-300 seconds

#### 2. Interactive Timeout Presets Menu (Omit --timeout flag)
```bash
$ qa analyze "SELECT * FROM huge_table"
Select query timeout:
▶ 30 seconds (default)
  60 seconds
  120 seconds
  Custom (enter value)
```

Select "Custom (enter value)" to enter custom timeout:
```bash
Enter timeout in seconds (1-300): 45
```

#### 3. Default (No flag, no TTY)
In non-interactive mode (CI/scripts), defaults to 30 seconds.

**Examples**:
```bash
# With presets menu (interactive)
$ qa analyze "SELECT * FROM large_table"
Select query timeout:
▶ 30 seconds (default)
  60 seconds
  120 seconds
  Custom (enter value)

# With explicit timeout
$ qa analyze --timeout 120 "SELECT * FROM large_table"

# With custom timeout via menu
$ qa analyze "SELECT * FROM large_table"
# Select "Custom (enter value)"
# Enter timeout in seconds (1-300): 75
```

---

### Verbose Debugging
```bash
qa analyze --verbose "SELECT * FROM users" 2>&1

# Output includes step-by-step processing:
# [INFO] Parsing query input...
# [INFO] Query received: 45 chars
# [INFO] Resolving output format...
# [INFO] Output format: rich
# [INFO] Resolving timeout...
# [INFO] Timeout: 30s
# [INFO] Resolving profile...
# [INFO] Using profile: local-dev (default)
# [INFO] Loading profile configuration...
# [INFO] Engine: postgresql @ localhost:5432
# [INFO] Creating adapter...
# [INFO] Connecting with 30s timeout...
# [INFO] Connection established
# [INFO] Executing EXPLAIN...
# [INFO] Analysis complete: score=85, warnings=2, recommendations=2
# [INFO] Formatting output as rich...
# [INFO] Done!
```

---

### JSON Output for Parsing
```bash
qa analyze "SELECT * FROM users" --output json | jq '.recommendations'

# Output:
# [
#   "CREATE INDEX idx_user_id ON users(id)",
#   "Add LIMIT to query"
# ]
```

### Markdown Export for Documentation
```bash
qa analyze "SELECT u.*, o.* FROM users u JOIN orders o..." \
  --output markdown > analysis_report.md

# Use in documentation or share with team
```

### Fully Interactive Mode (All Menus)
```bash
# No flags, all inputs interactive
$ qa analyze
Select Profile:
▶ local-dev (postgresql)
  staging (mysql)
  production (postgresql) [DEFAULT]

Enter your SQL query (Ctrl+D to submit):
SELECT * FROM users WHERE status = 'active'

Select output format:
▶ rich (formatted table)
  json (machine-readable)
  markdown (for documentation)

Select query timeout:
▶ 30 seconds (default)
  60 seconds
  120 seconds
  Custom (enter value)

Query Performance Analysis
...
```

---

## Performance Score

The **Score** (0-100) indicates query efficiency:

- **90-100**: Excellent - Optimal performance
- **70-89**: Good - Minor improvements possible
- **50-69**: Fair - Optimization recommended
- **30-49**: Poor - Significant improvements needed
- **0-29**: Critical - Major performance issues

**Factors Considered**:
- Execution time
- Index usage
- Full table scans
- Join efficiency
- Memory usage
- CPU load

---

## Anti-Patterns Detected

The analyzer automatically detects common SQL anti-patterns:

### Database-Specific Anti-Patterns

**PostgreSQL**:
- Sequential scans without indexes
- N+1 query patterns
- Missing VACUUM maintenance
- Inefficient JOIN orders

**MySQL**:
- Missing indexes on foreign keys
- SELECT * in JOINs
- Implicit type conversions
- Subqueries in WHERE clause

**SQLite**:
- Missing indexes
- Large IN() clauses
- Inefficient ORDER BY
- Cross joins

**CockroachDB / YugabyteDB**:
- Distributed transaction overhead
- Network latency issues
- Shard key inefficiency

---

## Error Handling

### Query Validation Errors
```
[ERROR] Query cannot be empty
→ Provide a query via argument, file, or stdin

[ERROR] Query must start with SELECT, UPDATE, DELETE, INSERT, or WITH
→ Invalid: "TRUNCATE table", "DROP table"
→ Valid: "SELECT * FROM table"

[ERROR] Multiple SQL statements not supported
→ Invalid: "SELECT * FROM users; SELECT * FROM orders;"
→ Valid: "SELECT * FROM users"
```

### Profile Errors
```
[ERROR] Profile 'unknown' not found.
Available profiles:
  • local-dev
  • staging
  • production

To create a new profile:
  qa profile add unknown -e postgresql ...
```

### Connection Errors
```
[ERROR] Connection Failed
Profile: production
Engine: postgresql
Host: prod-db.example.com:5432
Database: myapp_prod
User: analyst

Troubleshooting:
  1. Check profile: qa profile show production
  2. Test connection: qa profile test production
  3. Verify credentials: qa profile show production --show-password
```

### Timeout Errors
```
[ERROR] Connection Timeout
Query did not complete within 30 seconds.

Profile: staging
Engine: mysql
Host: staging-db.example.com:5432

Options:
  - Increase timeout: qa analyze ... --timeout 60
  - Check network connectivity
  - Verify database is running
```

### Engine Not Supported
```
[ERROR] Unsupported Engine
Engine 'cassandra' not supported for EXPLAIN analysis.

Supported engines:
  postgresql, mysql, sqlite, cockroachdb, yugabytedb
```

---

## Keyboard Shortcuts

### Input Entry
- **Ctrl+D**: Submit multi-line query (when in interactive prompt)
- **Ctrl+C**: Cancel operation (exit code 130)

### Output Navigation (Rich/JSON)
- **Page Down/Up**: Scroll through results
- **Ctrl+F**: Search in output (terminal dependent)

---

## Exit Codes

| Code | Meaning | Example |
|------|---------|---------|
| 0 | Success | Query analyzed, report generated |
| 1 | Error | Query syntax error, connection failed |
| 130 | Cancelled | User pressed Ctrl+C |

---

## Advanced Usage

### Analyze Multiple Queries
```bash
# Process queries from file, one per line
while read query; do
  qa analyze "$query" --output json >> results.json
done < queries.txt
```

### CI/CD Integration
```bash
# GitHub Actions
- name: Analyze Query
  run: |
    qa profile add ci-db \
      -e postgresql \
      -h ${{ secrets.DB_HOST }} \
      -p 5432 \
      -d ${{ secrets.DB_NAME }} \
      -u ${{ secrets.DB_USER }} \
      -pw ${{ secrets.DB_PASS }}

    qa analyze --profile ci-db --file queries/report.sql --output json
```

### Performance Monitoring
```bash
# Analyze query and save report
qa analyze --file queries/slow_query.sql \
  --output markdown > reports/$(date +%Y%m%d).md

# Track improvements over time
```

### Batch Analysis
```bash
# Analyze all queries in directory
for file in queries/*.sql; do
  echo "Analyzing $file..."
  qa analyze --file "$file" --output markdown
done
```

---

## Tips & Best Practices

### ✅ Do's
- ✅ Set a default profile to save typing: `qa profile set-default staging`
- ✅ Use `--output json` for automation and parsing
- ✅ Use `--output markdown` for reports and documentation
- ✅ Test on staging before running on production
- ✅ Increase timeout for known slow queries
- ✅ Use `--verbose` when debugging issues

### ❌ Don'ts
- ❌ Don't analyze production queries during peak hours
- ❌ Don't use extremely short timeouts (< 5 seconds)
- ❌ Don't analyze queries with `TRUNCATE`, `DROP`, `DELETE` in production
- ❌ Don't hardcode credentials in shell scripts
- ❌ Don't pipe sensitive data through logs

---

## Related Commands

For profile management:
- `qa profile add` - Create new database connection
- `qa profile list` - Show all profiles
- `qa profile test` - Test connection
- `qa profile set-default` - Set default profile

For detailed help:
```bash
qa analyze --help
qa profile --help
```

---

**Version**: 1.0
**Last Updated**: 2026-04-15
