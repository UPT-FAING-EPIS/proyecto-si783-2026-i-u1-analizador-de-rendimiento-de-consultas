"""Fix execution_time_ms defaults in adapters."""

files = [
    "query_analyzer/adapters/sql/postgresql.py",
    "query_analyzer/adapters/sql/yugabytedb.py",
]

for filepath in files:
    with open(filepath) as f:
        content = f.read()

    original = content
    content = content.replace(
        'metrics.get("execution_time_ms", 0.0)', 'metrics.get("execution_time_ms", 1.0)'
    )

    if content != original:
        with open(filepath, "w") as f:
            f.write(content)
        print(f"Updated {filepath}")
    else:
        print(f"No changes in {filepath}")
