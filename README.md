# datasyn-local

**Local-first data analysis blueprint** for the [datasyn](https://github.com/) project. Collect data, structure it in [DuckDB](https://duckdb.org/docs/current/clients/python/overview), analyze with Python and SQL, and expose results to AI agents via [MCP](https://duckdb.org/community_extensions/extensions/duckdb_mcp).

Think like a journalist, researcher, and scientist: reproducible pipelines, clear provenance, evidence-backed insights.

## What this repo provides

| Layer | Purpose |
|-------|---------|
| `data/landing/` | Raw files (CSV, JSON, XLSX, scrapes) before ingestion |
| `data/duckdb/` | Persistent DuckDB database |
| `src/` | Python modules and pipelines |
| `scripts/` | CLI utilities (ingest, reports, MCP server) |
| `reports/` | Generated markdown analysis |
| `.cursor/skills/` | Cursor agent skills for common workflows |
| `AGENTS.md` | Agent personas and subagent definitions |

## Project structure

```
datasyn-local/
├── AGENTS.md                 # Agent instructions & subagent personas
├── Makefile                  # Common tasks
├── pyproject.toml            # Dependencies (uv)
├── config/settings.yaml      # Paths and defaults
├── data/
│   ├── landing/              # Download / scrape / export zone
│   └── duckdb/               # datasyn.duckdb lives here
├── src/
│   ├── db.py                 # DuckDB connection helpers
│   └── cli.py                # CLI entry point
├── scripts/
│   ├── ingest.py             # CSV / JSON / XLSX → DuckDB
│   ├── stat_report.py        # Statistical reports
│   └── mcp_server.py         # MCP server for AI integration
├── reports/                  # Analysis output (gitignored content)
└── .cursor/
    ├── skills/               # 8 task skills
    ├── rules/                # Cursor rules
    └── mcp.json              # MCP server config for Cursor
```

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

### Steps

```bash
# 1. Clone and enter the repo
cd datasyn-local

# 2. Install uv (if needed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Create virtualenv and install dependencies
make install
# equivalent: uv sync --all-extras

# 4. Optional: copy environment config
cp .env.example .env
```

Verify:

```bash
make debug
uv run python -c "import duckdb; print('DuckDB', duckdb.__version__)"
```

## Local configuration

### Database path

Default: `data/duckdb/datasyn.duckdb`

Override via environment:

```bash
export DATASYN_DB_PATH=data/duckdb/my_project.duckdb
```

Or edit `config/settings.yaml`:

```yaml
database:
  path: data/duckdb/datasyn.duckdb
paths:
  landing: data/landing
```

### Landing zone

Drop raw files into `data/landing/` before ingestion. See `data/landing/README.md`.

## Usage

### Ingest data

```bash
# CSV, JSON, or XLSX
make ingest FILE=data/landing/sales.csv TABLE=sales
make ingest FILE=data/landing/articles.json TABLE=articles
```

### Query

```bash
make info
make sql QUERY="SELECT * FROM sales LIMIT 5"
uv run python -m src.cli sql "SHOW TABLES"
```

### Statistical report

```bash
make report TABLE=sales
# Output: reports/sales_report_YYYYMMDD_HHMMSS.md
```

### Python REPL

```bash
make shell
```

```python
from src.db import connect
con = connect()
con.sql("SHOW TABLES").show()
```

## Cursor agent skills

Skills live in `.cursor/skills/`. The agent uses them automatically when relevant:

| Skill | Trigger |
|-------|---------|
| `ingest-data` | Import CSV, JSON, XLSX |
| `statistical-report` | EDA, table profiling |
| `sentiment-analysis` | Tone and sentiment on text |
| `create-table` | New DuckDB schema |
| `create-python-script` | New module in `src/` |
| `web-scraping` | Fetch data from URLs |
| `setup-uv` | Virtual environment setup |
| `configure-duckdb-mcp` | MCP + DuckDB integration |

See `AGENTS.md` for subagent personas (data engineer, analyst, journalist).

## MCP configuration

Expose DuckDB tables to Cursor and other MCP clients using the [duckdb_mcp](https://duckdb.org/community_extensions/extensions/duckdb_mcp) extension.

1. Ensure tables exist in the database
2. Check MCP setup:

```bash
uv run python scripts/mcp_server.py --check
```

3. Cursor reads `.cursor/mcp.json` (or `~/.cursor/mcp.json`) — use **absolute paths** via `scripts/run_mcp.sh`

4. Manual SQL (DuckDB CLI or Python):

```sql
INSTALL duckdb_mcp FROM community;
LOAD duckdb_mcp;
SELECT mcp_server_start('stdio');
SELECT mcp_publish_table('my_table', 'data://tables/my_table', 'json');
```

## Debugging

### Environment check

```bash
make debug
```

### Common issues

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: src` | Run from repo root; use `uv run python` |
| Database locked | Close other DuckDB connections / CLI sessions |
| XLSX ingest fails | Extension installs on first run; retry ingest |
| Empty table list | Ingest data first: `make ingest FILE=... TABLE=...` |
| uv not found | Install uv and restart terminal |

### Verbose DuckDB

```python
from src.db import connect
con = connect()
con.sql("SET enable_progress_bar = true")
con.sql("YOUR QUERY HERE").show()
```

### Inspect landing files

```bash
ls -la data/landing/
head data/landing/example.csv
```

### Reset database

```bash
rm data/duckdb/datasyn.duckdb
make ingest FILE=data/landing/example.csv TABLE=example
```

## Development

```bash
uv add <package>          # add dependency
uv add --dev pytest       # dev dependency
uv run ruff check src/    # lint
```

## License

Part of the datasyn project. Adapt freely for local investigative and analytical work.
# datasyn-local
