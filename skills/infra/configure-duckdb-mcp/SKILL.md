---
name: configure-duckdb-mcp
description: Configure duckdb_mcp for Cursor, VS Code, Kilo Code, or other MCP IDEs.
disable-model-invocation: true
---

# Configure DuckDB MCP

References: [duckdb.org](https://duckdb.org/community_extensions/extensions/duckdb_mcp) · [GitHub README](https://github.com/teaguesterling/duckdb_mcp/blob/main/README.md)

## Quick setup

```bash
./scripts/sh/bootstrap.sh
# or:
uv run python scripts/python/db.py mcp-config
uv run python scripts/python/db.py mcp-check
```

Then in **Cursor → Settings → MCP**: enable **`datasyn-duckdb`** (or **`duckdb-local`**) → **Restart**.

Entrypoint script (must exist):

```
scripts/run_mcp.sh  →  scripts/sh/mcp-serve.sh  →  db.py mcp-serve
```

---

## Fix: `spawn .../scripts/run_mcp.sh ENOENT`

Cursor log shows:

```
Connection failed: spawn /Users/.../datasyn-local/scripts/run_mcp.sh ENOENT
```

**Cause:** MCP config points to `scripts/run_mcp.sh` but the file was missing.

**Fix:**

```bash
chmod +x scripts/run_mcp.sh scripts/sh/mcp-serve.sh
uv run python scripts/python/db.py mcp-config
```

In **Cursor → Settings → MCP → duckdb-local** (user server), set:

| Field | Value |
|-------|-------|
| Command | `/Users/you/project/datasyn-local/scripts/run_mcp.sh` |
| Cwd | `/Users/you/project/datasyn-local` |
| Env | `DATASYN_DB_PATH=/Users/you/project/datasyn-local/data/duckdb/datasyn.duckdb` |

Restart MCP. Verify:

```bash
uv run python scripts/python/db.py mcp-status   # should show a PID after Cursor connects
```

---

## Ingest vs query (important)

DuckDB allows **one writer** at a time. MCP holds the file lock while enabled.

| Task | Tool | Command / action |
|------|------|------------------|
| **Query / schema / reports** | MCP in chat | Keep MCP enabled |
| **Ingest / scrape / MERGE** | Python API (write) | `db.py mcp-stop` first |

```bash
# Before ingest
uv run python scripts/python/db.py mcp-stop

# Ingest SQL
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_....sql

# After ingest — restart MCP in Cursor to query again
```

Optional: `DATASYN_RELEASE_MCP_FOR_WRITE=1` auto-stops MCP in `connect_for_ingest()`.

---

## How to use MCP (in chat)

Once MCP is connected, ask in natural language. The assistant uses these tools:

| MCP tool | Use for | Example prompt |
|----------|---------|----------------|
| `list_tables` | See what's in the DB | *"List all tables in silver schema"* |
| `describe` | Column types for one table | *"Describe silver.tk_tw_tweet"* |
| `query` | Run SELECT SQL | *"How many tweets in tk_tw_tweet?"* |
| `database_info` | DB path, version, stats | *"Show database info"* |
| `export` | Export query results | *"Export top 10 tweets to CSV"* |

### Example prompts (Twitter / twikit)

```
Show the schema for silver.tk_tw_tweet and silver.tk_tw_profile.

How many rows in silver.tk_tw_tweet? Show created_at, like_count, left(text,80) for the last 5.

List all silver tables that start with tk_tw_.

DESCRIBE silver.tk_tw_user — what columns exist?
```

### Example SQL (via MCP `query`)

```sql
SELECT table_schema, table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'silver' AND table_name LIKE 'tk_tw_%'
ORDER BY table_name, ordinal_position;
```

```sql
SELECT tweet_id, created_at, like_count, retweet_count, reply_count, LEFT(text, 100) AS preview
FROM silver.tk_tw_tweet
ORDER BY created_at_ts DESC
LIMIT 5;
```

---

## Cursor configuration

### Project-level (recommended)

`uv run python scripts/python/db.py mcp-config` writes `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "datasyn-duckdb": {
      "command": "/abs/path/to/datasyn-local/scripts/run_mcp.sh",
      "cwd": "/abs/path/to/datasyn-local",
      "env": {
        "DATASYN_DB_PATH": "/abs/path/to/datasyn-local/data/duckdb/datasyn.duckdb"
      }
    }
  }
}
```

Reload MCP in Cursor. Do **not** commit `.cursor/mcp.json`. Template: `.cursor/mcp.json.example`.

### User-level server (`duckdb-local` / `user-duckdb-local`)

If you configured MCP globally in Cursor, use the **same command path** as above (`scripts/run_mcp.sh`). Both names work; only the entrypoint path must be correct.

---

## VS Code / Kilo Code

```bash
uv run python scripts/python/db.py mcp-config
cp .cursor/mcp.json .vscode/mcp.json
```

Edit `.vscode/mcp.json`: rename `"mcpServers"` → `"servers"`.

Reload window: `Cmd+Shift+P` → **Developer: Reload Window**.

---

## CLI helpers

```bash
uv run python scripts/python/db.py mcp-config    # write .cursor/mcp.json
uv run python scripts/python/db.py mcp-check     # verify duckdb_mcp extension
uv run python scripts/python/db.py mcp-status    # is mcp-serve running? which PID?
uv run python scripts/python/db.py mcp-stop      # stop MCP before ingest (write)
uv run python scripts/python/db.py quack-info    # show Quack host/port/token presence
uv run python scripts/python/db.py quack-check   # attach to remote warehouse and list tables
```

`mcp-serve` is started by Cursor automatically — do not run it manually unless debugging.
`quack-serve` is the same for the remote warehouse (`datasyn-quack` MCP server).

---

## Remote warehouse (Quack)

[DuckDB Quack](https://duckdb.org/docs/current/quack/overview) exposes a remote warehouse over HTTP.
`datasyn-local` can attach as a Quack client (same protocol used by `datasyn-duckdb`'s MCP bridge).

### Env (`.env` — never commit)

Copy from `datasyn-duckdb/.env` / align with the fleet Quack server:

```bash
QUACK_HOST=10.13.10.119
QUACK_PORT=9494
QUACK_TOKEN=…          # same token as datasyn-duckdb QUACK_TOKEN
QUACK_DISABLE_SSL=true
```

See `.env.example` for the template. Defaults in `db.py`: host `10.13.10.119`, port `9494`, SSL disabled.

### Verify

```bash
uv run python scripts/python/db.py quack-info
uv run python scripts/python/db.py quack-check
# Non-main schemas (bronze/silver/gold): use quack-sql — Quack 1.5.x cannot
# scan them via FROM bronze.t after ATTACH (duckdb/duckdb-quack#144).
uv run python scripts/python/db.py quack-sql "SELECT count(*) FROM bronze.clarin_noticias"
uv run python scripts/python/db.py quack-sql "SELECT * FROM bronze.clarin_noticias LIMIT 3"
```

Attach under the hood:

```sql
INSTALL quack; LOAD quack;
ATTACH 'quack:HOST:PORT' AS "datasyn-rlab" (TYPE quack, TOKEN '…', DISABLE_SSL true);
USE "datasyn-rlab";
-- main works directly; other schemas need the attachment query macro:
FROM "datasyn-rlab".query('SELECT * FROM bronze.clarin_noticias LIMIT 10');
```

### Cursor MCP (`datasyn-quack`)

```bash
uv run python scripts/python/db.py mcp-config
```

Writes both servers into `.cursor/mcp.json` (gitignored):

| Server | Role |
|--------|------|
| `datasyn-duckdb` | Local file DB (`data/duckdb/datasyn.duckdb`) via `scripts/run_mcp.sh` |
| `datasyn-quack` | Remote Quack warehouse via `scripts/sh/quack-serve.sh` |

Enable **`datasyn-quack`** in Cursor → Settings → MCP → Restart. Query with the same MCP tools (`list_tables`, `query`, …) against the remote warehouse.

Local ingest still uses the file DB (`mcp-stop` + `connect_for_ingest`). Quack is a separate opt-in connection.

### Hybrid: local write + remote read (`--attach-quack`)

Stage remote bronze into the local file DB (default catalog stays local; no `USE`):

```bash
uv run python scripts/python/db.py mcp-stop
uv run python scripts/python/db.py run-sql --ingest --attach-quack \
  --file scripts/sql/ingest_lanacion_silver.sql
```

SQL pattern (one `.query()` per statement — Quack streaming limit):

```sql
CREATE OR REPLACE TABLE bronze.lanacion_noticias AS
SELECT * FROM "datasyn-rlab".query(
  'SELECT * FROM bronze.lanacion_noticias'
);
-- then transform into silver.* on the local catalog
```

Helpers in `db.py`: `attach_quack()`, `quack_remote_sql()`, `quack_execute()`, CLI `quack-sql`.

---

## Built-in MCP tools

`query`, `describe`, `list_tables`, `database_info`, `export`.

## Prompts vs skills

- Workflow rules: `AGENTS.md`
- This file: MCP wiring and usage only
