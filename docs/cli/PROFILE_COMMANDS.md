# Query Analyzer CLI - Profile Commands

This document provides comprehensive documentation for the **Profile Management** commands in the Query Analyzer CLI.

## Overview

Profile commands allow you to configure and manage database connection profiles. Each profile stores connection details (host, port, credentials, etc.) for a specific database instance.

## Command Syntax

All profile commands follow this syntax:
```
qa profile <command> [options]
```

---

## Commands

### 1. `profile add` - Add a New Profile

**Purpose**: Create a new database connection profile with interactive or CLI-based configuration.

**Syntax**:
```bash
qa profile add [NAME] [OPTIONS]
```

**Arguments**:
- `NAME` (optional): Unique profile name. If omitted, you'll be prompted interactively.
  - Requirements: 2+ characters, alphanumeric/dash/underscore only
  - Examples: `local-dev`, `staging_prod`, `db-01`

**Options**:
| Option | Short | Type | Description | Required |
|--------|-------|------|-------------|----------|
| `--engine` | `-e` | string | Database engine: `postgresql`, `mysql`, `sqlite`, `cockroachdb`, `yugabytedb` | No* |
| `--host` | `-h` | string | Database host/IP address | No* |
| `--port` | `-p` | integer | Database port (1-65535) | No* |
| `--database` | `-d` | string | Database name | No* |
| `--username` | `-u` | string | Database username | No* |
| `--password` | `-pw` | string | Database password (always hidden when entered interactively) | No* |

*If not provided, you'll be prompted interactively.

**Examples**:

**Fully interactive** (prompts for all values):
```bash
qa profile add
Profile Name: staging
Select database engine:
▶ PostgreSQL
  MySQL
  SQLite
  CockroachDB
  YugabyteDB
Host [localhost]: db.staging.example.com
Port [5432]:
Database: analytics_db
Username: analyst
Password (hidden): ****
✓ Perfil 'staging' agregado exitosamente
```

**With name, engine interactive**:
```bash
qa profile add production -h prod-db.example.com -p 5432 -d prod_db -u postgres -pw secret
✓ Perfil 'production' agregado exitosamente
```

**Completely non-interactive** (all CLI args):
```bash
qa profile add local-dev -e postgresql -h localhost -p 5432 -d dev_db -u postgres -pw devpass
✓ Perfil 'local-dev' agregado exitosamente
```

**Port selection with defaults**:
```bash
qa profile add mysql-prod
Select database engine:
  PostgreSQL
▶ MySQL
  SQLite
Port [3306]:          # Uses MySQL default
Database: reports_db
Username: root
Password (hidden): ****
✓ Perfil 'mysql-prod' agregado exitosamente
```

**Features**:
- ✅ Arrow-key navigation (↑/↓) for engine selection
- ✅ Input validation (name length, alphanumeric checks)
- ✅ Engine-specific port defaults (PostgreSQL=5432, MySQL=3306, etc.)
- ✅ Password always hidden (masked input)
- ✅ Credentials encrypted in configuration file
- ✅ Ctrl+C cancellation support

---

### 2. `profile list` - List All Profiles

**Purpose**: Display all configured database connection profiles in a formatted table.

**Syntax**:
```bash
qa profile list
```

**No arguments or options**.

**Output**:
```
Perfiles de Conexion
┏━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━┓
┃ Nombre     ┃ Engine    ┃ Host      ┃ DB   ┃ Usuario ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━┩
│ local-dev* │ postgre   │ localhost │ devdb│ postgres│
│ staging    │ mysql     │ staging.. │ stgdb│ analyst │
│ production │ postgre   │ prod-db..│ proddb│ admin  │
└━━━━━━━━━━━━┴━━━━━━━━━━━┴━━━━━━━━━━━┴━━━━━━┴━━━━━━━━━┘
```

**Legend**:
- `*` = Default profile (used when no `--profile` specified in `analyze`)
- Passwords are **never** displayed for security

**Examples**:
```bash
$ qa profile list
# Shows table above

# With no profiles configured
$ qa profile list
[INFO] No hay perfiles configurados
```

---

### 3. `profile test` - Test a Profile Connection

**Purpose**: Validate that a profile has an active, working connection to the database.

**Syntax**:
```bash
qa profile test [NAME]
```

**Arguments**:
- `NAME` (optional): Profile name to test. If omitted, shows interactive menu.

**Interactive Menu** (when no name provided):
```bash
$ qa profile test
Select Profile:
▶ local-dev (postgresql)
  staging (mysql)
  production (postgresql) [DEFAULT]
```

**Output on Success**:
```bash
$ qa profile test local-dev
Testing connection to 'local-dev'...
[OK] Connection successful
[OK] postgresql
    Connection Metrics
+-------------------------+
| Metric          | Value |
|-----------------+-------|
| cache_hit_ratio | None  |
+-------------------------+
```

**Examples**:

**With explicit profile name (PostgreSQL)**:
```bash
$ qa profile test staging
Testing connection to 'staging'...
[OK] Connection successful
[OK] postgresql
    Connection Metrics
+-------------------------+
| Metric          | Value |
|-----------------+-------|
| cache_hit_ratio | None  |
+-------------------------+
```

**With explicit profile name (MySQL)**:
```bash
$ qa profile test mysql-prod
Testing connection to 'mysql-prod'...
[OK] Connection successful
[OK] mysql
       Connection Metrics
+-------------------------------+
| Metric              | Value   |
|---------------------+---------|
| tables              | 5       |
| indexes             | 9       |
| database_size_bytes | 2146304 |
| slow_queries_count  | 100     |
+-------------------------------+
```

**Interactive menu** (no name provided):
```bash
$ qa profile test
Select Profile:
▶ local-dev (postgresql)
   staging (mysql)
   production (postgresql) [DEFAULT]

Testing connection to 'local-dev'...
[OK] Connection successful
[OK] postgresql
    Connection Metrics
+-------------------------+
| Metric          | Value |
|-----------------+-------|
| cache_hit_ratio | None  |
+-------------------------+
```

**Non-existent profile**:
```bash
$ qa profile test unknown
[ERROR] Perfil no encontrado
```

**Troubleshooting on Connection Failure**:
If connection fails, helpful troubleshooting tips are provided:
```bash
$ qa profile test production
[ERROR] Connection failed: Failed to connect to PostgreSQL: connection to server at "localhost" (127.0.0.1), port 5432 failed: FATAL: password authentication failed for user "analyst"

Troubleshooting tips:
  1. Check profile config: qa profile show production
  2. Verify credentials: qa profile show production --show-password
  3. Check host and port are accessible
  4. Verify database is running: docker ps | grep postgresql
```

**Features**:
- ✅ Optional argument (interactive menu if omitted)
- ✅ Arrow-key navigation (↑/↓) in terminal
- ✅ Shows engine for each profile
- ✅ Marks [DEFAULT] profile visually
- ✅ Keyboard shortcuts: j/k or Ctrl+N/P to navigate
- ✅ Validates actual database connection with adapter
- ✅ Displays engine information (PostgreSQL, MySQL, etc.)
- ✅ Shows connection metrics in formatted table (engine-specific)
- ✅ Provides troubleshooting tips on connection failure
- ✅ Ctrl+C to cancel

---

### 4. `profile set-default` - Set Default Profile

**Purpose**: Mark a profile as the default, which will be used automatically when no `--profile` is specified in `analyze` commands.

**Syntax**:
```bash
qa profile set-default [NAME]
```

**Arguments**:
- `NAME` (optional): Profile name. If omitted, shows interactive menu.

**Examples**:

**With profile name**:
```bash
$ qa profile set-default production
✓ Perfil default establecido a 'production'
```

**Interactive menu** (no name provided):
```bash
$ qa profile set-default
Select Profile:
▶ local-dev (postgresql)
  staging (mysql)
  production (postgresql) [DEFAULT]

✓ Perfil default establecido a 'staging'
```

**Non-interactive (no TTY)**:
```bash
# In CI/scripts with no TTY, provide explicit name
qa profile set-default staging
```

**Features**:
- ✅ Arrow-key navigation (↑/↓) to select profile
- ✅ Shows current default with `[DEFAULT]` marker
- ✅ Ctrl+C cancellation support

---

### 5. `profile delete` - Delete a Profile

**Purpose**: Remove a profile from the configuration. Requires confirmation unless `--force` is used.

**Syntax**:
```bash
qa profile delete [NAME] [OPTIONS]
```

**Arguments**:
- `NAME` (optional): Profile name to delete. If omitted, shows interactive menu.

**Options**:
| Option | Short | Type | Description |
|--------|-------|------|-------------|
| `--force` | `-f` | flag | Skip confirmation prompt |

**Examples**:

**With confirmation prompt**:
```bash
$ qa profile delete staging
staging
  Engine: postgresql
  Host: staging-db.example.com:5432
  Database: staging_db
  Username: analyst
  Password: ****

¿Eliminar staging? [y/N]: y
✓ Perfil 'staging' eliminado
```

**Without confirmation (force delete)**:
```bash
$ qa profile delete staging --force
✓ Perfil 'staging' eliminado
```

**Interactive menu** (no name provided):
```bash
$ qa profile delete
Select Profile:
▶ local-dev (postgresql)
  staging (mysql)

staging
  Engine: postgresql
  Host: staging-db.example.com:5432
  Database: staging_db
  Username: analyst
  Password: ****

¿Eliminar staging? [y/N]: y
✓ Perfil 'staging' eliminado
```

**Safety Features**:
- ✅ Displays full profile details before deletion
- ✅ Requires explicit yes confirmation (unless --force)
- ✅ Arrow-key profile selection menu
- ✅ Cannot delete default profile without confirmation

---

### 6. `profile show` - Display Profile Details

**Purpose**: Show the complete configuration of a single profile, with optional password display.

**Syntax**:
```bash
qa profile show [NAME] [OPTIONS]
```

**Arguments**:
- `NAME` (optional): Profile name to display. If omitted, shows interactive menu.

**Options**:
| Option | Description |
|--------|-------------|
| `--show-password` | Display password in plaintext (default: masked) |

**Interactive Menu** (when no name provided):
```bash
$ qa profile show
Select Profile:
▶ local-dev (postgresql)
  staging (mysql)
  production (postgresql) [DEFAULT]
```

**Output**:

With explicit profile:
```bash
$ qa profile show production
Profile: production (DEFAULT)
Engine: postgresql
Host: prod-db.example.com
Port: 5432
Database: myapp_prod
User: analyst
Password: ****

$ qa profile show production --show-password
Profile: production (DEFAULT)
Engine: postgresql
Host: prod-db.example.com
Port: 5432
Database: myapp_prod
User: analyst
Password: super_secret_pwd_123
```

**Examples**:

**Show specific profile**:
```bash
$ qa profile show staging
Profile: staging (DEFAULT)
Engine: mysql
Host: staging-db.example.com
Port: 3306
Database: staging_db
User: analyst
Password: ****
```

**Show with password revealed**:
```bash
$ qa profile show staging --show-password
Profile: staging (DEFAULT)
Engine: mysql
Host: staging-db.example.com
Port: 3306
Database: staging_db
User: analyst
Password: secret123
```

**Interactive menu** (no name provided):
```bash
$ qa profile show
Select Profile:
▶ local-dev (postgresql)
  staging (mysql)
  production (postgresql) [DEFAULT]

Profile: local-dev
Engine: postgresql
Host: localhost
Port: 5432
Database: dev_db
User: postgres
Password: ****
```

**Features**:
- ✅ Optional argument (interactive menu if omitted)
- ✅ Arrow-key navigation (↑/↓) in terminal
- ✅ Shows engine for each profile
- ✅ Marks [DEFAULT] profile visually
- ✅ Keyboard shortcuts: j/k or Ctrl+N/P to navigate
- ✅ Password masked by default (security)
- ✅ `--show-password` flag to reveal credentials
- ✅ Ctrl+C to cancel

---

## Interaction Modes

### 1. Interactive Mode (with TTY - Terminal)

When running commands in a terminal without providing all arguments:
- **Prompts appear** with arrow-key navigation (↑/↓)
- **Defaults shown** in brackets `[value]`
- **Input validation** with error messages
- **Password hidden** with mask characters `****`

```bash
$ qa profile add
Profile Name: my-db
Select database engine:
▶ PostgreSQL
  MySQL
  SQLite
...
```

### 2. Non-Interactive Mode (CI/Scripts - No TTY)

When stdin is piped or redirected, or in CI environments:
- **Returns sensible defaults** instead of prompting
- **Required args must be provided** via CLI or will fail
- **Useful for**: GitLab CI, GitHub Actions, Docker, automation

```bash
# Will work (all args provided)
qa profile add local-dev -e postgresql -h localhost -p 5432 -d db -u user -pw pass

# Will fail (missing required args in non-interactive mode)
qa profile add local-dev
# Error: Profile name required (in non-interactive mode).
# Provide: qa profile add <name> [options]
```

**TTY Detection**:
- ✅ Terminal: `sys.stdin.isatty() = True`
- ✅ Piped: `cat script.sh | bash` → `isatty() = False`
- ✅ CI: GitHub Actions, GitLab CI → `isatty() = False`

---

## Keyboard Shortcuts

### Navigation
- **↑/↓ Arrow Keys**: Move up/down in menu
- **j/k**: Vim-style navigation (j=down, k=up)
- **Ctrl+N/Ctrl+P**: Emacs-style navigation

### Confirmation
- **y**: Yes / **n**: No
- **Enter**: Confirm selection (in menus)
- **Ctrl+C**: Cancel operation (exit code 130)

---

## Configuration File

All profiles are stored in: `~/.query_analyzer/config.toml`

**Example**:
```toml
[profiles.local-dev]
engine = "postgresql"
host = "localhost"
port = 5432
database = "dev_db"
username = "postgres"
password_encrypted = "base64_encrypted_string..."

[profiles.staging]
engine = "mysql"
host = "staging-db.example.com"
port = 3306
database = "staging_db"
username = "analyst"
password_encrypted = "base64_encrypted_string..."

[default]
profile = "local-dev"
```

**Security**:
- Passwords are **encrypted** (not plaintext)
- Config file has **restricted permissions** (chmod 600)
- Never commit `config.toml` to version control

---

## Common Workflows

### Setup New Database Connection
```bash
# 1. Add profile (interactive)
qa profile add

# 2. Test connection
qa profile test <name>

# 3. Set as default (optional)
qa profile set-default <name>

# 4. List all profiles
qa profile list
```

### Switch Between Databases
```bash
# 1. List profiles
qa profile list

# 2. Set different default
qa profile set-default staging

# 3. Run analyze (will use staging by default)
qa analyze "SELECT * FROM users"
```

### Delete Old Profile
```bash
# 1. Show details
qa profile show old-prod

# 2. Delete with confirmation
qa profile delete old-prod

# 3. Verify
qa profile list
```

### CI/CD Pipeline
```bash
# Add profile programmatically (non-interactive)
qa profile add ci-db \
  -e postgresql \
  -h $DB_HOST \
  -p 5432 \
  -d $DB_NAME \
  -u $DB_USER \
  -pw $DB_PASS

# Run analysis
qa analyze --profile ci-db "SELECT * FROM large_table"
```

---

## Error Messages & Troubleshooting

### Profile Name Errors
```
[ERROR] Profile name cannot be empty
→ Provide at least 2 characters

[ERROR] Profile name must be at least 2 characters
→ Use 2+ character names (e.g., "db", "prod-1")

[ERROR] Profile name can only contain alphanumeric, dash, underscore
→ Invalid: my.db, my@db, my profile
→ Valid: my_db, my-db, mydb123
```

### Connection Errors
```
[ERROR] Perfil 'production' no encontrado
→ Profile doesn't exist. Use: qa profile list

[ERROR] Connection Failed: Host 'unknown.example.com' not found
→ Check host in: qa profile show production

[ERROR] Access denied for user 'analyst'@'host'
→ Verify credentials: qa profile show production --show-password
```

### Non-Interactive Mode
```
[ERROR] Profile name required (in non-interactive mode).
Provide: qa profile add <name> [options]

→ You're in a CI/script environment without a TTY.
→ Provide all required arguments via CLI options.
```

---

## Tips & Best Practices

### ✅ Do's
- ✅ Use descriptive profile names: `prod-analytics`, `staging-replica-01`
- ✅ Test connections after adding: `qa profile test <name>`
- ✅ Set a default profile for your primary database
- ✅ Use `--force` only in automated scripts
- ✅ Rotate credentials periodically and update profiles

### ❌ Don'ts
- ❌ Don't hardcode passwords in scripts (use `--password` flag or env vars)
- ❌ Don't commit `~/.query_analyzer/config.toml` to version control
- ❌ Don't use special characters in profile names
- ❌ Don't delete default profile if it's actively used
- ❌ Don't share config files with unencrypted passwords

---

## Related Commands

For analyzing queries with profiles, see:
- `qa analyze --profile <name> "SELECT ..."`
- `qa analyze --profile <name> --file query.sql`

For full help:
```bash
qa profile --help
qa profile add --help
qa profile list --help
```

---

**Version**: 1.0
**Last Updated**: 2026-04-15
