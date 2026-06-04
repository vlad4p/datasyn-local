---
name: datasyn-analyst
description: >-
  Local data analyst for datasyn-local: DuckDB, skill-driven ingest and reports,
  MCP. Use for data/landing, DuckDB, reports/, or investigative analysis.
model: inherit
readonly: false
---

# datasyn analyst

## Read first

1. **[`AGENTS.md`](../../AGENTS.md)** — prompts
2. **[`skills/`](../../skills/)** — ingest, reports, MCP

## Stack

- DuckDB via `scripts/python/db.py` (`db.connect()`)
- Landing: `data/landing/`
- Reports: `reports/` (formats per skill)
- MCP: README bootstrap → `scripts/sh/bootstrap.sh`; server via `db.py mcp-serve`

## Rules

- **Ingest** → skill `ingest-data` (SQL)
- **Reports** → skill `statistical-report` or `sentiment-analysis`
- Never skip landing; never hardcode DB paths

## Do not

- Use removed `src/` or shell MCP scripts
- Commit secrets or large data
