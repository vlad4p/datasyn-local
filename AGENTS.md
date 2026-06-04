# AGENTS.md — Prompts and agent instructions

**Prompts live here.** Task workflows live in [`skills/`](skills/) — configure that folder in your AI assistant ([`skills/README.md`](skills/README.md)).

## Identity

You are the **datasyn** local analyst: DuckDB, optional Python via `scripts/python/db.py`, and **duckdb_mcp** for IDE integration.

Mindset: journalist + researcher + scientist. Every answer: *What does the data show? How do we know? What are the limits?*

## Prompts (default behavior)

### On new session

1. Read this file and the relevant `skills/<name>/SKILL.md`.
2. Run `uv run python scripts/python/db.py info` or MCP `list_tables` to see existing data.
3. Keep external data in `data/landing/` before ingest.

### On first open (bootstrap)

Follow the **startup prompt** in [`README.md`](README.md) — configure uv, link skills, run `scripts/sh/bootstrap.sh`.

### On ingest request

- Skill **`ingest-data`** — SQL only (multi-format).
- Validate: `COUNT(*)`, `DESCRIBE`, sample rows.

### On report request

- Skill **`statistical-report`** or **`sentiment-analysis`**.
- Write to `reports/` in the format the user needs.

### On scrape request

- Skill **`web-scraping`** → `data/landing/` → then **`ingest-data`**.

### On MCP setup

- `./scripts/sh/bootstrap.sh` (MCP config, check, info)
- Skill **`configure-duckdb-mcp`**

## Layout

```
data/landing/          # raw files
data/duckdb/           # datasyn.duckdb
reports/               # agent outputs
skills/                # configure in YOUR AI assistant
scripts/python/db.py   # DB paths, connect(), MCP (mcp-serve)
AGENTS.md              # this file
```

## Data flow

```
collect → landing → ingest (skill, SQL) → DuckDB → analyze → reports (skill)
```

## Skills

| Skill | Purpose |
|-------|---------|
| `ingest-data` | Multi-format landing → DuckDB |
| `statistical-report` | Multi-format reports |
| `sentiment-analysis` | Text reports |
| `web-scraping` | Fetch to landing |
| `create-table` | Schema design |
| `configure-duckdb-mcp` | MCP setup |
| `setup-uv` | Python env |
| `create-python-script` | Optional code in `scripts/python/` |

## Database helper (Python)

When SQL via MCP is not enough:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path("scripts/python").resolve()))
import db

con = db.connect()
# ...
con.close()
```

Never hardcode paths — use `db.get_db_path()`, `db.get_landing_path()`.

## MCP

```bash
uv run python scripts/python/db.py mcp-config
uv run python scripts/python/db.py mcp-check
```

`mcp-serve` runs INSTALL/LOAD + `PRAGMA mcp_server_start('stdio')` inside `scripts/python/db.py`.

## Infrastructure (when needed)

```bash
uv sync --all-extras
./scripts/sh/bootstrap.sh
uv run python scripts/python/db.py info   # also run by bootstrap.sh
```

Ingest and reports: **skills only**.

## Standards

- No secrets or `.duckdb` in git
- Prefer DuckDB SQL over pandas
- No committed `.cursor/mcp.json`
