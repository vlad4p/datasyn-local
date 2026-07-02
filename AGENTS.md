# AGENTS.md — Prompts and agent instructions

**Prompts live here.** Task workflows live in [`skills/`](skills/) — configure that folder in your AI assistant ([`skills/README.md`](skills/README.md)).

Shared vocabulary: [`CONTEXT.md`](CONTEXT.md).

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

1. Read this file, [`CONTEXT.md`](CONTEXT.md), and the relevant skill from [`skills/`](skills/).
2. Run `uv run python scripts/python/db.py info` or MCP `list_tables` to see existing data.
3. Keep external data in `data/landing/` before ingest.

### On first open (bootstrap)

Follow the **startup prompt** in [`README.md`](README.md) — configure uv, link skills, run `scripts/sh/bootstrap.sh`.

### Routing requests

Use scope buckets in [`skills/README.md`](skills/README.md):

| Request type | Bucket | Start with |
|--------------|--------|------------|
| Scrape / download | [`collect/`](skills/collect/README.md) | `web-scraping` or `scrape-sociavault` |
| Ingest / clean / join | [`ingest/`](skills/ingest/README.md) | `ingest-data` |
| Reports / graphs | [`analyze/`](skills/analyze/README.md) | `statistical-report`, `graph-ingest`, etc. |
| Schema design | [`schema/`](skills/schema/create-table/SKILL.md) | `create-table` |
| Setup / MCP | [`infra/`](skills/infra/README.md) | `setup-uv`, `configure-duckdb-mcp` |
| Git / privacy | [`engineering/`](skills/engineering/README.md) | `data-privacy`, `gitflow` |

User flow router: [`datasyn-router`](skills/datasyn-router/SKILL.md). Layout guide: [`docs/skills-layout.md`](docs/skills-layout.md).

## Layout

```
data/landing/          # raw files
data/duckdb/           # datasyn.duckdb
report/                # agent outputs: report/<project>/<report-name>
skills/                # scoped task workflows (see skills/README.md)
scripts/python/db.py   # DB paths, connect(), MCP (mcp-serve)
CONTEXT.md             # shared vocabulary
AGENTS.md              # this file
```

## Data flow

```
collect → landing → ingest (skill, SQL) → DuckDB → analyze → report/<project>/ (skill)
```

## SQL execution — split by task

DuckDB allows **one writer** at a time. MCP (`mcp-serve`) holds the file lock while enabled in Cursor.

| Task | Tool | When |
|------|------|------|
| **Ingest / writes** (bronze, silver, scrape) | Python API — `db.connect_for_ingest()` or `db.py run-sql --ingest` | Stop MCP first: `db.py mcp-stop` |
| **Query / analysis** (reports, EDA, chat) | **MCP tools** (`query`, `list_tables`, `describe`) | MCP enabled in Cursor |

### Ingest (Python — writes)

```bash
# Release MCP lock, then ingest
uv run python scripts/python/db.py mcp-stop
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_sociavault_twitter_silver.sql

# Or auto-stop MCP before connect (scrape scripts use this)
DATASYN_RELEASE_MCP_FOR_WRITE=1 uv run python scripts/python/scrape_sociavault_twitter.py ...
```

```python
import db
con = db.connect_for_ingest(release_mcp=True)  # stops mcp-serve, opens read-write
```

### Query (MCP — reads)

Enable **datasyn-duckdb** in Cursor MCP settings, then use MCP tools in chat.

```bash
uv run python scripts/python/db.py mcp-status   # is MCP running?
uv run python scripts/python/db.py mcp-check    # verify extension
```

Do **not** use `run-sql` for analysis when MCP is available — use MCP `query` instead.

Only fall back to direct Python (`db.connect()`) when MCP cannot handle the task (e.g., multi-step procedural logic, pandas integration).

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
