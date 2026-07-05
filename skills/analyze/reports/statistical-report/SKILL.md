---
name: statistical-report
description: >-
  Generate analysis reports from DuckDB tables using SQL via MCP only (no Python
  report scripts, no direct Python DuckDB connections). Supports markdown EDA,
  executive brief, JSON metrics, CSV extracts, and HTML summary.
  Use for profiling, EDA, data quality, or report requests.
---

# Generate reports (skill — SQL via MCP only)

Do **not** run `make report` or Python report modules. Query with DuckDB via MCP
(`uv run python scripts/python/db.py run-sql "SQL..."`), then **write files** under
`reports/<project>/<report-slug>/`.

## Output layout

```
reports/<project>/<report-slug>/
  report.<ext>          # main deliverable (html, md, pdf)
  data.json             # optional structured export
  README.md             # optional methodology / interpretation
  assets/               # optional CSV, images
```

| Segment | Example | Rule |
|---------|---------|------|
| `<project>` | `redes`, `grafo`, `nyt`, `boletin` | Kebab-case domain or dataset slug |
| `<report-slug>` | `gold-report`, `sentiment-brief` | Kebab-case; **one folder per report** |

**Examples:**

```
reports/redes/gold-report/report.html
reports/redes/gold-report/data.json
reports/redes/trolls-grafo/report.html
reports/redes/trolls-grafo/grafo.json
reports/grafo/co-ocurrencia/report.md
reports/nyt/sentiment-brief/report.md
```

Path helpers (`scripts/python/db.py`):

- `get_report_bundle(project, slug)` → `reports/<project>/<slug>/` (**preferred**)
- `get_report_path(project, name)` → single file under project (simple/legacy)

## Prerequisites

- Table exists in DuckDB (`SHOW TABLES`)
- Output root: `reports/` (gitignored — may contain PII or scraped text; never commit outputs)
- Before any git commit: follow **`data-privacy`** — commit SQL/skills only, not report files

## Workflow

1. **Clarify format** — ask or infer from user request (see matrix)
2. **Choose `<project>`** — match the dataset or investigation (e.g. `redes` for FB/TW silver)
3. **Profile in SQL** — `COUNT`, `DESCRIBE`, `SUMMARIZE`, domain queries
4. **Draft report** — markdown/HTML/JSON/CSV per template
5. **Save** — create `reports/<project>/<report-slug>/` and write `report.<ext>` plus optional `data.json`, `README.md`

## Output format matrix

| Format | Extension | Best for | Agent action |
|--------|-----------|----------|--------------|
| **Markdown EDA** | `.md` | Full statistical profile | SQL → structured sections below |
| **Executive brief** | `.md` | 1-page decision summary | Top metrics + 3–5 bullet findings |
| **JSON metrics** | `.json` | Dashboards / downstream tools | Export key scalars + small tables as JSON |
| **CSV profile** | `.csv` | Spreadsheet handoff | `COPY` to `reports/<project>/<slug>/assets/` |
| **HTML summary** | `.html` | Readable shareable snapshot | Minimal HTML + embedded tables/charts |
| **Sentiment / text** | `.md` | News, articles | Use skill `sentiment-analysis` instead |

## Core SQL (all formats)

```sql
SELECT COUNT(*) AS row_count FROM {table};
DESCRIBE {table};
SUMMARIZE {table};
```

### Extra profiling

```sql
-- Null-heavy columns
SELECT * FROM (SUMMARIZE {table}) WHERE null_percentage > 0;

-- Top categories
SELECT col, COUNT(*) AS n FROM {table} GROUP BY 1 ORDER BY 2 DESC LIMIT 15;

-- Date span
SELECT MIN(date_col), MAX(date_col) FROM {table};
```

### Export helpers

```sql
-- CSV slice (adjust project and report slug)
COPY (SELECT * FROM {table} LIMIT 1000)
TO 'reports/{project}/{table}_sample_{YYYYMMDD}.csv' (HEADER, DELIMITER ',');

-- JSON metrics file
COPY (SELECT COUNT(*) AS row_count FROM {table})
TO 'reports/{project}/{table}_metrics_{YYYYMMDD}.json';
```

## Template: Markdown EDA (`.md`)

```markdown
# Report: `{table}`

Generated: {date}
Format: markdown_eda
Project: {project}

## Executive summary
[2–3 sentences with numbers]

## Overview
- Rows: …
- Columns: …

## Schema
[DESCRIBE as table]

## Summary statistics
[SUMMARIZE highlights]

## Data quality
- Nulls, duplicates, outliers

## Findings
- …

## Limits
- What was not checked; sampling bias

## Methods
- SQL used (brief)
```

## Template: Executive brief (`.md`)

```markdown
# Executive brief: `{table}`

**Bottom line:** …

| Metric | Value |
|--------|-------|
| Rows | … |

## Findings
1. …
2. …

## Recommended next steps
- …
```

## Template: JSON metrics (`.json`)

```json
{
  "table": "{table}",
  "project": "{project}",
  "generated": "{iso_date}",
  "format": "json_metrics",
  "row_count": 0,
  "columns": [],
  "quality_flags": [],
  "notes": ""
}
```

Fill with query results; keep files small.

## Template: HTML summary (`.html`)

Minimal single-file HTML: `<h1>`, one `<table>` for schema, one for top summary stats, footer with generation time. Chart.js optional for time-series or distribution charts. No PII in aggregates.

Pair HTML with a JSON sibling in the **same bundle folder**:

```
reports/redes/gold-report/report.html
reports/redes/gold-report/data.json
```

For **full PTS redes dashboards** (sentimiento, trolls, ráfagas, grafos) use skill [`redes-analysis`](redes-analysis/SKILL.md) instead of hand-written HTML.

## File naming

```
reports/{project}/{slug}/report_{YYYYMMDD}.md     # optional date suffix on main file
reports/{project}/{slug}/report.md                # or stable report.md / report.html
reports/{project}/{slug}/data.json
reports/{project}/{slug}/assets/{table}_sample.csv
```

## Persona

**Expert data analyst**: every claim tied to a query result; state limits; suggest follow-up analyses.

## Related skills

- [`graph-analysis`](../../graph/graph-analysis/SKILL.md) — network reports → `reports/grafo/`
- [`sentiment-analysis`](../sentiment-analysis/SKILL.md) — text tone → `reports/<project>/`
- [`interactive-graph-reports`](../../graph/interactive-graph-reports/SKILL.md) — HTML graphs → `reports/<project>/`
