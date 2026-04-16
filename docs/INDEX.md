# 📖 Documentation Index

Quick navigation to all documentation sections.

## 🎯 Start Here

- **[CLI Quick Start](./cli/README.md)** - Get started with CLI commands in 5 minutes
- **Main README** - [../../README.md](../../README.md) - Project overview

---

## 📋 CLI Documentation

Complete documentation for command-line interface:

### Profile Management
- **[Profile Commands Guide](./cli/PROFILE_COMMANDS.md)**
  - Add new connection profiles
  - List and manage profiles
  - Set default profile
  - Test connections
  - Delete profiles
  - Show profile details

### Query Analysis
- **[Analyze Command Guide](./cli/ANALYZE_COMMAND.md)**
  - Analyze SQL queries
  - Multiple input methods
  - Output formatting
  - Performance scoring
  - Anti-pattern detection
  - Error handling

### Quick Reference
- **[CLI README](./cli/README.md)** - Overview, workflows, and quick reference card

---

## 🗄️ Adapter Documentation

Database-specific documentation:

### DynamoDB
- **[DynamoDB Adapter Guide](./adapters/DYNAMODB.md)**
  - 8 anti-patterns detected
  - Query optimization tips
  - Examples and troubleshooting

---

## 💡 Common Tasks

### Set Up New Database Connection
1. Start: [Profile Commands > Add](./cli/PROFILE_COMMANDS.md#1-profile-add---add-a-new-profile)
2. Test: [Profile Commands > Test](./cli/PROFILE_COMMANDS.md#3-profile-test---test-a-profile-connection)
3. Set Default: [Profile Commands > Set Default](./cli/PROFILE_COMMANDS.md#4-profile-set-default---set-default-profile)

### Analyze Your First Query
1. Start: [Analyze Command > Examples](./cli/ANALYZE_COMMAND.md#examples)
2. Learn Input Methods: [Analyze Command > Query Input Methods](./cli/ANALYZE_COMMAND.md#query-input-methods)
3. Understand Output: [Analyze Command > Output Formats](./cli/ANALYZE_COMMAND.md#output-formats)

### Use in CI/CD
1. Read: [CLI README > Non-Interactive Mode](./cli/README.md#-non-interactive-mode-ciscripts---no-tty)
2. Examples: [Analyze Command > CI/CD Integration](./cli/ANALYZE_COMMAND.md#cicd-integration)

### Debug Performance Issues
1. Run: [Analyze Command > Verbose Debugging](./cli/ANALYZE_COMMAND.md#verbose-debugging)
2. Check Anti-Patterns: [Analyze Command > Anti-Patterns Detected](./cli/ANALYZE_COMMAND.md#anti-patterns-detected)

---

## 🔍 Search by Topic

### Profiles
- [Create new profile](./cli/PROFILE_COMMANDS.md#1-profile-add---add-a-new-profile)
- [List all profiles](./cli/PROFILE_COMMANDS.md#2-profile-list---list-all-profiles)
- [Test connection](./cli/PROFILE_COMMANDS.md#3-profile-test---test-a-profile-connection)
- [Set default profile](./cli/PROFILE_COMMANDS.md#4-profile-set-default---set-default-profile)
- [Delete profile](./cli/PROFILE_COMMANDS.md#5-profile-delete---delete-a-profile)
- [Show profile details](./cli/PROFILE_COMMANDS.md#6-profile-show---display-profile-details)
- [Configuration file](./cli/PROFILE_COMMANDS.md#configuration-file)

### Query Analysis
- [Analyze query](./cli/ANALYZE_COMMAND.md#analyze---analyze-query-performance)
- [Input methods](./cli/ANALYZE_COMMAND.md#query-input-methods)
- [Output formats](./cli/ANALYZE_COMMAND.md#output-formats)
- [Performance scoring](./cli/ANALYZE_COMMAND.md#performance-score)
- [Anti-pattern detection](./cli/ANALYZE_COMMAND.md#anti-patterns-detected)
- [Error handling](./cli/ANALYZE_COMMAND.md#error-handling)
- [Performance tips](./cli/ANALYZE_COMMAND.md#tips--best-practices)

### Troubleshooting
- [Profile not found](./cli/PROFILE_COMMANDS.md#error-messages--troubleshooting)
- [Connection failed](./cli/PROFILE_COMMANDS.md#error-messages--troubleshooting)
- [Query validation error](./cli/ANALYZE_COMMAND.md#query-validation-errors)
- [Non-interactive mode error](./cli/PROFILE_COMMANDS.md#non-interactive-mode)

### Advanced Topics
- [Interactive vs Non-Interactive Mode](./cli/PROFILE_COMMANDS.md#interaction-modes)
- [Keyboard Shortcuts](./cli/PROFILE_COMMANDS.md#keyboard-shortcuts)
- [Configuration File](./cli/PROFILE_COMMANDS.md#configuration-file)
- [Common Workflows](./cli/PROFILE_COMMANDS.md#common-workflows)
- [CI/CD Integration](./cli/ANALYZE_COMMAND.md#cicd-integration)
- [Batch Analysis](./cli/ANALYZE_COMMAND.md#batch-analysis)

---

## 📱 Documentation by Format

### For Quick Start
- [CLI Quick Reference Card](./cli/README.md#quick-reference-card) - Cheat sheet of all commands

### For Detailed Reference
- [Profile Commands Guide](./cli/PROFILE_COMMANDS.md) - 50+ examples, all options explained
- [Analyze Command Guide](./cli/ANALYZE_COMMAND.md) - Complete guide with workflows

### For Automation/Scripts
- [Non-Interactive Mode](./cli/README.md#-non-interactive-mode-ciscripts---no-tty)
- [JSON Output Format](./cli/ANALYZE_COMMAND.md#2-json-format-machine-readable)
- [CI/CD Integration](./cli/ANALYZE_COMMAND.md#cicd-integration)

### For Troubleshooting
- [Profile Troubleshooting](./cli/PROFILE_COMMANDS.md#error-messages--troubleshooting)
- [Analyze Troubleshooting](./cli/ANALYZE_COMMAND.md#error-handling)

---

## 📊 Supported Databases

| Database | CLI Support | Documentation |
|----------|:-----------:|---|
| PostgreSQL | ✅ | Included in CLI guides |
| MySQL | ✅ | Included in CLI guides |
| SQLite | ✅ | Included in CLI guides |
| CockroachDB | ✅ | Included in CLI guides |
| YugabyteDB | ✅ | Included in CLI guides |
| MongoDB | ✅ | Included in CLI guides |
| DynamoDB | ✅ | [Adapter Guide](./adapters/DYNAMODB.md) |
| InfluxDB | ✅ | Included in CLI guides |
| Neo4j | ✅ | Included in CLI guides |

---

## 🤔 FAQ

**Q: Where do I start?**
A: Start with [CLI Quick Start](./cli/README.md) or [Profile Commands Guide](./cli/PROFILE_COMMANDS.md#1-profile-add---add-a-new-profile)

**Q: How do I add a database profile?**
A: Follow the ["Add a New Profile" guide](./cli/PROFILE_COMMANDS.md#1-profile-add---add-a-new-profile)

**Q: How do I analyze a query?**
A: See ["Analyze Query Performance" guide](./cli/ANALYZE_COMMAND.md#analyze---analyze-query-performance)

**Q: Can I use this in CI/CD?**
A: Yes! See [Non-Interactive Mode](./cli/README.md#-non-interactive-mode-ciscripts---no-tty) and [CI/CD Integration](./cli/ANALYZE_COMMAND.md#cicd-integration)

**Q: How do I get JSON output?**
A: Use `qa analyze ... --output json` - see [JSON Output Format](./cli/ANALYZE_COMMAND.md#2-json-format-machine-readable)

**Q: What keyboard shortcuts are available?**
A: See [Keyboard Shortcuts](./cli/PROFILE_COMMANDS.md#keyboard-shortcuts)

**Q: How do I troubleshoot connection issues?**
A: See [Troubleshooting Guide](./cli/PROFILE_COMMANDS.md#error-messages--troubleshooting)

---

## 📝 Version Info

| Item | Version |
|------|---------|
| Documentation | 1.0 |
| Last Updated | 2026-04-15 |
| Python | 3.14+ |

---

## 🔗 Related Links

- **Main Repository**: [GitHub](https://github.com/anomalyco/opencode)
- **Bug Reports**: [GitHub Issues](https://github.com/anomalyco/opencode/issues)
- **Feature Requests**: [GitHub Discussions](https://github.com/anomalyco/opencode/discussions)

---

**👉 Next Step**: Go to [CLI Quick Start](./cli/README.md) to begin!
