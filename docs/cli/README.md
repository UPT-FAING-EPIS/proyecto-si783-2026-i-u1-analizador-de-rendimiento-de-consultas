# Query Analyzer CLI - Complete Documentation

Welcome to the comprehensive CLI documentation for the Query Analyzer application.

## Quick Navigation

This directory contains detailed documentation for all CLI commands:

### 📋 Available Commands

1. **[Profile Commands](./PROFILE_COMMANDS.md)** - Manage database connection profiles
   - `qa profile add` - Add new database profile
   - `qa profile list` - List all configured profiles
   - `qa profile test` - Test profile connection
   - `qa profile set-default` - Set default profile
   - `qa profile delete` - Remove profile
   - `qa profile show` - Display profile details

2. **[Analyze Command](./ANALYZE_COMMAND.md)** - Analyze SQL query performance
   - `qa analyze` - Execute query with EXPLAIN analysis
   - Multiple input methods (argument, file, stdin, interactive)
   - Multiple output formats (rich table, JSON, Markdown)
   - Verbose debugging and performance scoring

---

## Getting Started

### Installation & Setup

1. **Install the Query Analyzer**:
   ```bash
   pip install query-analyzer
   # or with uv:
   uv run query_analyzer
   ```

2. **Create Your First Profile**:
   ```bash
   qa profile add
   # Follow interactive prompts
   ```

3. **Test the Connection**:
   ```bash
   qa profile test <profile-name>
   ```

4. **Analyze a Query**:
   ```bash
   qa analyze "SELECT * FROM users LIMIT 10"
   ```

---

## Command Overview

### Profile Management
Profiles store database connection information (host, port, credentials, etc.).

**Essential workflow**:
```bash
qa profile add                    # Create profile (interactive)
qa profile list                   # View all profiles
qa profile test staging           # Verify connection
qa profile set-default staging    # Make it default
qa profile delete old-profile     # Remove profile
```

**Learn more**: [Profile Commands Documentation](./PROFILE_COMMANDS.md)

### Query Analysis
Analyze SQL queries for performance issues and anti-patterns.

**Essential workflow**:
```bash
qa analyze "SELECT ..."                      # Direct query
qa analyze --file query.sql                  # From file
cat query.sql | qa analyze                   # From stdin
qa analyze "SELECT ..." --profile staging    # Specific profile
qa analyze --output json "SELECT ..."        # JSON output
```

**Learn more**: [Analyze Command Documentation](./ANALYZE_COMMAND.md)

---

## Supported Databases

All commands support these database engines:

- **PostgreSQL** (Port: 5432)
- **MySQL** (Port: 3306)
- **SQLite** (File-based)
- **CockroachDB** (Port: 26257)
- **YugabyteDB** (Port: 5433)

---

## Interaction Modes

### 🖥️ Interactive Mode (Terminal)
When running in a terminal with arguments missing:
- **Arrow-key menus** (↑/↓) for selections
- **Input validation** with error messages
- **Password masking** for secure entry
- **Smart defaults** for common values

```bash
$ qa profile add
Profile Name: staging
Select database engine:
▶ PostgreSQL
  MySQL
  SQLite
...
```

### 🔧 Non-Interactive Mode (CI/Scripts)
When running in scripts, CI/CD, or with piped input:
- **All arguments required** via CLI
- **No prompts** appear
- **Sensible defaults** for optional values
- **Perfect for automation**

```bash
qa profile add ci-db \
  -e postgresql \
  -h $DB_HOST \
  -p 5432 \
  -d $DB_NAME \
  -u $DB_USER \
  -pw $DB_PASS
```

---

## Output Formats

### Rich Table (Default)
Human-readable, colorized output with visual formatting:
```bash
qa analyze "SELECT * FROM users"
```

### JSON (Machine-Readable)
Structured data for programmatic processing:
```bash
qa analyze "SELECT * FROM users" --output json | jq '.recommendations'
```

### Markdown (Documentation)
Report-ready format for sharing and archiving:
```bash
qa analyze "SELECT * FROM users" --output markdown > report.md
```

---

## Common Workflows

### 1. Setup New Environment
```bash
# Create profile for new database
qa profile add prod-replica -e postgresql -h prod-replica.example.com

# Verify connection
qa profile test prod-replica

# Set as default
qa profile set-default prod-replica

# Confirm it worked
qa profile list
```

### 2. Analyze Single Query
```bash
# Quick analysis with default profile
qa analyze "SELECT COUNT(*) FROM orders WHERE status = 'pending'"

# Specific profile
qa analyze --profile staging "SELECT * FROM users LIMIT 100"

# From file
qa analyze --file queries/slow_report.sql
```

### 3. Batch Analysis (Multiple Queries)
```bash
# Loop through query files
for file in queries/*.sql; do
  qa analyze --file "$file" --output json
done > results.json
```

### 4. CI/CD Pipeline
```bash
# Add temporary profile (non-interactive)
qa profile add ci-db -e postgresql -h $DB_HOST -u $DB_USER -pw $DB_PASS

# Run analysis
qa analyze --profile ci-db --file migrations/critical_query.sql

# Output as JSON for processing
qa analyze --profile ci-db --file queries/perf_check.sql --output json
```

### 5. Performance Monitoring
```bash
# Analyze query and save report with timestamp
qa analyze --file queries/key_report.sql \
  --output markdown > reports/analysis_$(date +%Y%m%d_%H%M%S).md

# Track performance over time by comparing reports
```

---

## Keyboard Shortcuts

### Navigation in Menus
- **↑ / ↓** - Move up/down in menu
- **j / k** - Vim-style navigation
- **Ctrl+N / Ctrl+P** - Emacs-style navigation

### Input Entry
- **Enter** - Confirm selection or submit
- **Ctrl+D** - Submit multi-line input (stdin)
- **Ctrl+C** - Cancel operation

### All Modes
- **Ctrl+Z** - Suspend (Ctrl+C to resume)

---

## Configuration

### Profile Storage
All profiles are stored in: **`~/.query_analyzer/config.toml`**

**Features**:
- ✅ Passwords are encrypted (not plaintext)
- ✅ Restricted file permissions (chmod 600)
- ✅ TOML format (human-readable)

**⚠️ Security Note**: Never commit this file to version control!

### Example Config
```toml
[profiles.local-dev]
engine = "postgresql"
host = "localhost"
port = 5432
database = "dev_db"
username = "postgres"
password_encrypted = "..."

[default]
profile = "local-dev"
```

---

## Troubleshooting

### "Profile not found"
```bash
# List available profiles
qa profile list

# Create new profile
qa profile add <name>
```

### "Connection Failed"
```bash
# Check profile configuration
qa profile show <name>

# Verify connection
qa profile test <name>

# Show encrypted password
qa profile show <name> --show-password
```

### "Query validation error"
```bash
# Verify query syntax (must start with SELECT, UPDATE, DELETE, INSERT, or WITH)
qa analyze "SELECT * FROM table"

# Cannot use multi-statement queries
# ❌ qa analyze "SELECT * FROM users; SELECT * FROM orders;"
# ✅ qa analyze "SELECT * FROM users"
```

### "Non-interactive mode"
```bash
# Running in CI/scripts without providing all args?
# Provide explicit arguments:
qa profile add mydb -e postgresql -h localhost -p 5432 -d db -u user -pw pass
```

---

## Getting Help

### Command-Specific Help
```bash
qa profile --help
qa profile add --help
qa analyze --help
```

### Full CLI Help
```bash
qa --help
```

### Bug Reports & Feedback
Report issues at: https://github.com/anomalyco/opencode

---

## Performance Tips

### ✅ Best Practices
- ✅ Use `qa profile test` to verify before analyzing
- ✅ Set a default profile with `qa profile set-default`
- ✅ Use appropriate timeout: `qa analyze --timeout 60 "SELECT ..."`
- ✅ Export to JSON for automated processing
- ✅ Archive markdown reports for documentation

### ❌ Avoid
- ❌ Don't analyze queries on production during peak hours
- ❌ Don't use very short timeouts (< 5 seconds)
- ❌ Don't hardcode credentials in scripts
- ❌ Don't commit credentials to version control

---

## Advanced Topics

### Environment Variables
```bash
# Set default profile via environment
export QA_DEFAULT_PROFILE=staging

# Query Analyzer respects common database env vars
export DB_HOST=staging-db.example.com
export DB_USER=analyst
```

### Scripting & Automation
```bash
#!/bin/bash
# Analyze query with error handling

qa analyze --timeout 30 --file "$1" || {
  echo "Analysis failed"
  exit 1
}
```

### Integration with Other Tools
```bash
# Parse JSON output with jq
qa analyze "SELECT * FROM users" --output json | jq '.score'

# Create formatted report
qa analyze "SELECT * FROM users" --output markdown | pandoc -o report.pdf

# Send to monitoring system
qa analyze "SELECT ..." --output json | curl -X POST http://monitoring.local/api/analysis
```

---

## Document Index

- **[Profile Commands](./PROFILE_COMMANDS.md)** - Complete profile management guide
- **[Analyze Command](./ANALYZE_COMMAND.md)** - Complete query analysis guide

---

## Version & Updates

**Current Version**: 1.0
**Last Updated**: 2026-04-15

For the latest documentation and updates, check the [GitHub repository](https://github.com/anomalyco/opencode).

---

## Quick Reference Card

```
╔═══════════════════════════════════════════════════════════════════╗
║             QUERY ANALYZER CLI - QUICK REFERENCE                  ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  PROFILES                                                         ║
║  qa profile add [name]              Add new profile (interactive) ║
║  qa profile list                    List all profiles             ║
║  qa profile test <name>             Test connection               ║
║  qa profile set-default <name>      Set as default                ║
║  qa profile delete <name>           Remove profile                ║
║  qa profile show <name>             Display profile details       ║
║                                                                   ║
║  ANALYZE                                                          ║
║  qa analyze "SELECT ..."            Analyze direct query          ║
║  qa analyze --file query.sql        Analyze from file             ║
║  cat query.sql | qa analyze         Analyze from stdin            ║
║  qa analyze --profile prod "..."    Use specific profile          ║
║  qa analyze --output json "..."     JSON output format            ║
║  qa analyze --timeout 60 "..."      Custom timeout (seconds)      ║
║  qa analyze --verbose "..."         Verbose debugging output      ║
║                                                                   ║
║  NAVIGATION (in menus)                                            ║
║  ↑ / ↓                              Move up/down                  ║
║  j / k                              Vim navigation                ║
║  Enter                              Select                        ║
║  Ctrl+C                             Cancel                        ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

**Next Steps**: Explore the [Profile Commands](./PROFILE_COMMANDS.md) or [Analyze Command](./ANALYZE_COMMAND.md) documentation.
