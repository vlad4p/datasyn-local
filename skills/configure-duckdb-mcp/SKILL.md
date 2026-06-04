---
name: configure-duckdb-mcp
description: >-
  Configure duckdb_mcp for AI agents. Use for MCP setup, Cursor integration,
  or exposing DuckDB over stdio.
---

# Configure DuckDB MCP

References: [duckdb.org](https://duckdb.org/community_extensions/extensions/duckdb_mcp) · [GitHub README](https://github.com/teaguesterling/duckdb_mcp/blob/main/README.md)

## Setup (this repo)

MCP bootstrap is embedded in **`scripts/python/db.py`**:

```python
# start_mcp_stdio_server()
INSTALL duckdb_mcp FROM community;
LOAD duckdb_mcp;
PRAGMA mcp_server_start('stdio');
```

```bash
./scripts/sh/bootstrap.sh
```

Or individually: `uv run python scripts/python/db.py mcp-config` and `mcp-check`.

## Cursor

Bootstrap writes `.cursor/mcp.json` pointing to:

```text
uv run python scripts/python/db.py mcp-serve
```

Reload MCP in Cursor. Do not commit `.cursor/mcp.json`. Template: `.cursor/mcp.json.example`.

Built-in tools: `query`, `describe`, `list_tables`, `database_info`, `export`.

## Prompts vs skills

- Prompts: `AGENTS.md`
- This file: MCP wiring only
