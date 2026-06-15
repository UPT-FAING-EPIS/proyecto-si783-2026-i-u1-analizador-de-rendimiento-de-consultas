---
name: query-analyzer-mcp
description: Use when Codex needs to configure, verify, or operate the Query Analyzer MCP server for SQL performance analysis through agent clients such as Claude Desktop, Cursor, Claude Code, or other Model Context Protocol hosts. Trigger for requests involving query_analyzer MCP setup, analyzing selected SQL through MCP, configuring mcpServers entries, choosing Query Analyzer profiles for MCP tools, or troubleshooting the analyze_query MCP tool.
---

# Query Analyzer MCP

## Overview

Use this skill to connect agents to the `query_analyzer` project through its MCP server. The MCP tool runs against Query Analyzer profiles and exposes `analyze_query(query, profile)` for factual EXPLAIN analysis.

## Local Setup

Start from the repository root and use `uv` only:

```bash
uv sync
uv run python -m query_analyzer.mcp_server
```

Before relying on the MCP tool, confirm Query Analyzer has at least one usable profile:

```bash
uv run qa profile list
uv run qa profile set-default <profile-name>
```

If no default profile is set, pass the `profile` argument when calling `analyze_query`.

## Client Configuration

Prefer stdio transport for local programming-agent clients:

```json
{
  "mcpServers": {
    "query_analyzer": {
      "command": "uv",
      "args": ["run", "python", "-m", "query_analyzer.mcp_server"]
    }
  }
}
```

If the client cannot run from the repository root, set the command to an absolute `uv` path or configure the client working directory to the repo.

## Tool Usage

Call `analyze_query` with:

- `query`: the SQL or supported read-only query text to analyze.
- `profile`: optional Query Analyzer profile name; omitted means use the configured default profile.

Expected response fields:

- `success`, `profile`, `engine`, `query`
- `execution_time_ms`, `plan_summary`, `metrics`, `raw_plan`, `analyzed_at`
- `error` when analysis fails

Do not invent recommendations from the MCP response. Treat `plan_summary`, `metrics`, and `raw_plan` as factual engine output, and clearly separate any agent-authored interpretation.

## Troubleshooting

- If the tool says no profile is configured, run `uv run qa profile list` and set a default or pass `profile`.
- If the client cannot start the server, verify `uv run python -m query_analyzer.mcp_server` works from the repo root.
- If database analysis fails, reproduce with `uv run qa analyze --profile <profile-name> "<query>"`.
- If an external web agent needs access to the REST API instead of stdio MCP, run `uv run qa-api` and expose port `8000` separately with ngrok; do not expose database credentials in prompts or logs.
