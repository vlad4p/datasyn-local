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
(`uv run python scripts/python/db.py run-sql "SQL..."`), then **write the file** under
`report/<project>/<report-name>`.

## Output layout

```
report/<project>/<report-name>
```

| Segment | Example | Rule |
|---------|---------|------|
| `<project>` | `redes`, `grafo`, `nyt`, `boletin` | Kebab-case domain or dataset slug |
| `<report-name>` | `fb-silver-report_20260629.html` | Descriptive filename; optional `_YYYYMMDD` before extension |

**Examples:**

```
report/redes/fb-silver-report_20260629.html
report/redes/fb-silver-report_data_20260629.json
report/redes/tw-silver-report_20260629.html
report/grafo/reporte_20260611.md
report/nyt/sentiment_20260606.md
```

Python fallback (helpers only): `db.get_report_path("redes", "fb-silver-report_20260629.html")`.

## Prerequisites

- Table exists in DuckDB (`SHOW TABLES`)
- Output root: `report/` (gitignored — may contain PII or scraped text; never commit outputs)
- Before any git commit: follow **`data-privacy`** — commit SQL/skills only, not report files

## Workflow

1. **Clarify format** — ask or infer from user request (see matrix)
2. **Choose `<project>`** — match the dataset or investigation (e.g. `redes` for FB/TW silver)
3. **Profile in SQL** — `COUNT`, `DESCRIBE`, `SUMMARIZE`, domain queries
4. **Draft report** — markdown/HTML/JSON/CSV per template
5. **Save** — `report/<project>/<report-name>` (create project subdir if needed)

## Output format matrix

| Format | Extension | Best for | Agent action |
|--------|-----------|----------|--------------|
| **Markdown EDA** | `.md` | Full statistical profile | SQL → structured sections below |
| **Executive brief** | `.md` | 1-page decision summary | Top metrics + 3–5 bullet findings |
| **JSON metrics** | `.json` | Dashboards / downstream tools | Export key scalars + small tables as JSON |
| **CSV profile** | `.csv` | Spreadsheet handoff | `COPY (SUMMARIZE t) TO 'report/...'` |
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
-- CSV slice (adjust project and report-name)
COPY (SELECT * FROM {table} LIMIT 1000)
TO 'report/{project}/{table}_sample_{YYYYMMDD}.csv' (HEADER, DELIMITER ',');

-- JSON metrics file
COPY (SELECT COUNT(*) AS row_count FROM {table})
TO 'report/{project}/{table}_metrics_{YYYYMMDD}.json';
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

Pair HTML with a JSON metrics sibling when dashboards need structured data:

```
report/redes/fb-silver-report_20260629.html
report/redes/fb-silver-report_data_20260629.json
```

## File naming

```
report/{project}/{table}_eda_{YYYYMMDD}.md
report/{project}/{table}_executive_{YYYYMMDD}.md
report/{project}/{table}_metrics_{YYYYMMDD}.json
report/{project}/{table}_sample_{YYYYMMDD}.csv
report/{project}/{table}_summary_{YYYYMMDD}.html
```

## Persona

**Expert data analyst**: every claim tied to a query result; state limits; suggest follow-up analyses.

## Related skills

- [`graph-analysis`](../../graph/graph-analysis/SKILL.md) — network reports → `report/grafo/`
- [`sentiment-analysis`](../sentiment-analysis/SKILL.md) — text tone → `report/<project>/`
- [`interactive-graph-reports`](../../graph/interactive-graph-reports/SKILL.md) — HTML graphs → `report/<project>/`
