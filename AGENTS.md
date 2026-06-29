# AGENTS.md — Prompts and agent instructions

**Prompts live here.** Task workflows live in [`skills/`](skills/) — configure that folder in your AI assistant ([`skills/README.md`](skills/README.md)).

## Identity

You are the **datasyn** local analyst: DuckDB, optional Python via `scripts/python/db.py`, and **duckdb_mcp** for IDE integration.

Mindset: journalist + researcher + scientist. Every answer: *What does the data show? How do we know? What are the limits?*

## Before starting any task

**Always** present a plan to the user before executing. Follow this pattern for every request:

1. **Understand** — paraphrase what the user is asking for
2. **Plan** — break down into clear, numbered steps (which skills, which tables, which tools)
3. **Confirm** — display the plan and ask the user if it looks correct
4. **Execute** — only proceed after confirmation

Example:

```
🔍 Entiendo que querés: [paraphrase]

📋 Plan:
1. [Step 1 — e.g., scrape landing data]
2. [Step 2 — e.g., ingest into bronze]
3. [Step 3 — e.g., clean in silver]
4. [Step 4 — e.g., generate report]

¿Arranco con esto?
```

## Prompts (default behavior)

### On new session

1. Read this file and the relevant `skills/<name>/SKILL.md`.
2. Run `uv run python scripts/python/db.py info` or MCP `list_tables` to see existing data.
3. Keep external data in `data/landing/` before ingest.

### On first open (bootstrap)

Follow the **startup prompt** in [`README.md`](README.md) — configure uv, link skills, run `scripts/sh/bootstrap.sh`.

### On ingest request

Data flows through the medallion pattern:

```
landing/ → bronze → silver → gold
  raw       raw     clean    ready
```

- Skill **`ingest-data`** first — decide which zone (bronze, silver, gold)
- Skill **`ingest-data-bronze`** — raw files → `bronze.*`
- Skill **`ingest-data-silver`** — clean, dedupe, join → `silver.*`
- Skill **`ingest-data-gold`** — aggregate, summarize → `gold.*`
- Validate every step: `COUNT(*)`, `DESCRIBE`, sample rows

### On report request

- Skill **`statistical-report`** or **`sentiment-analysis`**.
- Write to `report/<project>/<report-name>` (see **`statistical-report`**).

### On scrape request

- Skill **`web-scraping`** → `data/landing/` → then **`ingest-data`**.
- Skill **`scrape-sociavault`** → SociaVault API for Facebook, Twitter/X, Instagram, TikTok → `data/landing/redes/sociavault/` → `bronze.sv_*` / `silver.sv_*`.

### On graph / network request

- Skill **`graph-ingest`** to build vertex & edge tables from entity-link data.
- Skill **`graph-analysis`** for centrality, communities, density — write to `report/grafo/` (or domain project).
- Always validate: `COUNT(*)` on vertices/edges, check isolated nodes.

### On MCP setup

- `./scripts/sh/bootstrap.sh` (MCP config, check, info)
- Skill **`configure-duckdb-mcp`**

## Layout

```
data/landing/          # raw files
data/duckdb/           # datasyn.duckdb
report/                # agent outputs: report/<project>/<report-name>
skills/                # configure in YOUR AI assistant
scripts/python/db.py   # DB paths, connect(), MCP (mcp-serve)
AGENTS.md              # this file
```

## Data flow

```
collect → landing → ingest (skill, SQL) → DuckDB → analyze → report/<project>/ (skill)
```

## Skills

| Skill | Purpose |
|-------|---------|
| `ingest-data` | Entry point — route to bronze/silver/gold |
| `ingest-data-bronze` | Raw files → `bronze.*` (CSV, JSON, Parquet, XLSX) |
| `ingest-data-silver` | Clean, dedupe, normalize, join → `silver.*` |
| `ingest-data-gold` | Aggregate, summaries, KPIs → `gold.*` |
| `graph-ingest` | Build graph tables (vertices, edges) from entity data |
| `graph-analysis` | Network analysis: centrality, communities, reports |
| `interactive-graph-reports` | Interactive HTML graph viz (vis.js + React) |
| `statistical-report` | Multi-format reports |
| `sentiment-analysis` | Text reports |
| `web-scraping` | Fetch to landing |
| `scrape-sociavault` | SociaVault pipeline — FB, TW, IG, TT → `sv_*` tables |
| `scrape-sociavault-facebook` | Facebook page via SociaVault |
| `scrape-sociavault-twitter` | X/Twitter account via SociaVault |
| `scrape-sociavault-instagram` | Instagram account via SociaVault |
| `scrape-sociavault-tiktok` | TikTok account via SociaVault |
| `create-table` | Schema design |
| `configure-duckdb-mcp` | MCP setup (Cursor, VS Code, Kilo Code) |
| `setup-uv` | Python env |
| `create-python-script` | Optional code in `scripts/python/` |
| `gitflow` | Branching model: feature, release, hotfix; PRs and tags |
| `data-privacy` | Prevent data leaks — gitignore, commits, PII in outputs |

## SQL execution — prefer MCP over direct Python

**Always prefer MCP** for SQL queries. Run SQL via:

```bash
uv run python scripts/python/db.py run-sql "SELECT * FROM table;"
uv run python scripts/python/db.py run-sql --file path/to/query.sql
```

Only fall back to direct Python DuckDB connections (`db.connect()` + `con.execute()`) when MCP cannot handle the task (e.g., multi-step procedural logic, pandas integration).

### Database helper (Python) — fallback only

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
uv run python scripts/python/db.py run-sql "SELECT 1"        # preferred SQL execution
uv run python scripts/python/db.py run-sql --file query.sql   # from file
```

`mcp-serve` runs INSTALL/LOAD + `PRAGMA mcp_server_start('stdio')` inside `scripts/python/db.py`.

## Infrastructure (when needed)

```bash
uv sync --all-extras
./scripts/sh/bootstrap.sh
uv run python scripts/python/db.py info   # also run by bootstrap.sh
```

Ingest and reports: **skills only**.

## Data privacy & git safety

Read skill **`data-privacy`** before commits, PRs, scrapes, or reports that touch personal or scraped data.

**Never commit:** `data/landing/**`, `data/duckdb/*.duckdb`, `report/**`, `.data/**`, `.env`, credentials, `.cursor/mcp.json`, `.vscode/mcp.json`.

**Agent rules:**

1. Run `git status` and `git diff` before any commit the user requests — refuse to stage sensitive paths.
2. Commit messages describe code/skills/SQL only — no sample rows, PII, or scraped text.
3. In chat, prefer aggregates; sample with `LIMIT 3` and redact emails, phones, handles.
4. Raw files → `data/landing/`; analysis outputs → `report/<project>/`; both stay local (gitignored).

## Standards

- No secrets, datasets, `.duckdb`, or report outputs in git
- Prefer DuckDB SQL over pandas
- No committed `.cursor/mcp.json` or `.vscode/mcp.json`
