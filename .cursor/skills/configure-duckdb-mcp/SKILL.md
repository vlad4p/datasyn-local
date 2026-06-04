---
name: configure-duckdb-mcp
description: >-
  Configure DuckDB MCP extension for AI agent integration via Model Context
  Protocol. Use when setting up MCP, exposing DuckDB to Cursor, duckdb_mcp,
  or connecting SQL databases to MCP servers.
---

# Configure DuckDB MCP

Reference: [duckdb_mcp community extension](https://duckdb.org/community_extensions/extensions/duckdb_mcp)

## Two modes

1. **Client** — DuckDB queries remote MCP resources via `mcp://`
2. **Server** — DuckDB exposes tables as MCP resources for AI tools

## Install extension

```sql
INSTALL duckdb_mcp FROM community;
LOAD duckdb_mcp;
```

Python:

```python
from src.db import connect

con = connect()
con.execute("INSTALL duckdb_mcp FROM community")
con.execute("LOAD duckdb_mcp")
```

## Server mode (expose database to MCP clients)

```sql
SELECT mcp_server_start('stdio');
SELECT mcp_publish_table('articles', 'data://tables/articles', 'json');
SELECT mcp_server_status();
SELECT * FROM mcp_resources();
SELECT mcp_server_stop();
```

## Client mode (query remote MCP from SQL)

```sql
ATTACH 'python3' AS data_server (
    TYPE mcp,
    TRANSPORT 'stdio',
    ARGS '["path/to/mcp_server.py"]'
);

SELECT * FROM read_csv('mcp://data_server/file:///data.csv');
SELECT mcp_list_resources('data_server');
```

## Security settings

```sql
SET allowed_mcp_commands = '/usr/bin/python3';
SET allowed_mcp_urls = 'https://api.example.com';
SET mcp_log_level = 'info';
```

## Cursor MCP config

Use the launcher script (works regardless of Cursor cwd):

```json
{
  "mcpServers": {
    "datasyn-duckdb": {
      "command": "/absolute/path/to/datasyn-local/scripts/run_mcp.sh",
      "env": {
        "DATASYN_DB_PATH": "/absolute/path/to/datasyn-local/data/duckdb/datasyn.duckdb"
      }
    }
  }
}
```

Generate local config (gitignored, no personal paths in repo):

```bash
make mcp-config
```

Template: `.cursor/mcp.json.example`. Global copy: `~/.cursor/mcp.json`.

**Do not** commit `.cursor/mcp.json` or use relative `command` paths in global MCP config — Cursor may run from `$HOME` and fail.

## Helper script

Use `scripts/mcp_server.py` — loads duckdb_mcp, publishes all tables, starts stdio transport.

## Verification

```bash
uv run python scripts/mcp_server.py --check
```
