# CONTEXT.md — Shared vocabulary

Concise domain language for datasyn-local. Agents read this for terminology; active workflows live in [`skills/`](skills/).

## Data zones (medallion)

| Term | Path / schema | Meaning |
|------|---------------|---------|
| **landing** | `data/landing/` | Immutable raw files — downloads, scrapes, exports. Never mutate in place. |
| **bronze** | `bronze.*` | Raw ingest into DuckDB — preserve source shape, no cleaning. |
| **silver** | `silver.*` | Clean, dedupe, normalize, join — analysis-ready tables. |
| **gold** | `gold.*` | Aggregates, KPIs, summaries — report-ready datasets. |
| **report** | `reports/<project>/<report-slug>/` | Agent outputs — one folder per report with its data files. Gitignored. |

Flow: `landing → bronze → silver → gold → report`

## Tool split (DuckDB lock)

| Mode | Tool | When |
|------|------|------|
| **MCP read** | `query`, `list_tables`, `describe` | Reports, EDA, exploration — MCP holds read access |
| **Python ingest write** | `db.connect_for_ingest()` or `db.py run-sql --ingest` | DDL, MERGE, scrape ingest — stop MCP first (`db.py mcp-stop`) |

One writer at a time on `data/duckdb/datasyn.duckdb`.

## Collection

| Term | Meaning |
|------|---------|
| **web-scraping** | Generic fetch to `data/landing/` (HTML, APIs, files). |
| **SociaVault scrape** | Social API pipeline — scrape by **count** (`--last N`), not date range. |
| **sv_*** | SociaVault tables (`bronze.sv_*`, `silver.sv_*`) — Facebook/Instagram/TikTok preferred; Twitter/X SociaVault **deprecated** (use twikit). |
| **fb_*** | Legacy Facebook CSV dumps (`data/landing/redes/data-fb/`). Gold redes (`gold.v_*`, `gold.grafo_*`) via skill `redes-gold` is **FB-only**. |
| **tk_tw_*** | Twikit Twitter/X — sole Twitter pipeline (`silver.tk_tw_*`, `silver.tk_tw_user`, `gold.tk_hater_*`, `gold.tk_troll_blacklist`). Legacy `tw_*` retired. |

Landing layout for SociaVault: `data/landing/redes/sociavault/<platform>/`.

## Analysis

| Term | Meaning |
|------|---------|
| **report slug** | `reports/<project>/<report-slug>/` — e.g. `reports/redes/dashboard/report.html` |
| **grafo** | Default project slug for graph/network reports. |
| **graph tables** | `grafo_vertices`, `grafo_edges`, `grafo_edges_agg` — built by `graph-ingest`. |

## Skills layout

Skills are grouped by scope under [`skills/`](skills/):

| Scope | Bucket | Router skill |
|-------|--------|--------------|
| Collect | `skills/collect/` | `scrape-sociavault` (platform sub-scope) |
| Ingest | `skills/ingest/` | `ingest-data` (bronze / silver / gold) |
| Analyze | `skills/analyze/` | — (pick report or graph skill) |
| Schema | [`skills/schema/`](skills/schema/README.md) | `create-table` |
| Infra | `skills/infra/` | — |
| Engineering | `skills/engineering/` | `gitflow`, `data-privacy` |

Index: [`skills/README.md`](skills/README.md). User flow router: [`datasyn-router`](skills/datasyn-router/SKILL.md). Layout guide: [`docs/skills-layout.md`](docs/skills-layout.md).

## Privacy

Never commit: `data/landing/**`, `*.duckdb`, `reports/**`, `.env`, credentials, MCP config. See skill `data-privacy`.
