---
name: ingest-data
description: >-
  Ingest files from data/landing into DuckDB using SQL only (no Python scripts).
  Supports CSV, TSV, JSON, JSONL, Parquet, XLSX, and DuckDB-native loads.
  Use when importing, ETL, loading files, or landing zone ingestion.
---

# Ingest data (skill — SQL only)

Do **not** use Python ingest scripts. Use DuckDB SQL via MCP or `scripts/python/db.py` + SQL.

## Prerequisites

- Raw file already in `data/landing/` (keep original; never mutate in place)
- Table name: `snake_case`, letters/digits/underscore only
- DB: `data/duckdb/datasyn.duckdb`

## Workflow

1. **Inspect** — format, encoding, headers, rough row count (`head`, `file`, or `SELECT * FROM read_* LIMIT 5`)
2. **Choose load strategy** from the matrix below
3. **Create table** — `CREATE OR REPLACE TABLE {name} AS SELECT ...`
4. **Validate** — `COUNT(*)`, `DESCRIBE`, sample rows

## Format matrix

| Format | Extension | DuckDB approach | Notes |
|--------|-----------|-----------------|-------|
| CSV | `.csv` | `read_csv_auto('path')` | Add `header=true`, `delim=';'`, `encoding='UTF-8'` as needed |
| TSV | `.tsv`, `.txt` | `read_csv('path', delim='\t', header=true)` | |
| JSON array | `.json` | `read_json_auto('path')` | |
| JSON Lines | `.jsonl`, `.ndjson` | `read_json_auto('path', format='newline_delimited')` | |
| Parquet | `.parquet` | `read_parquet('path')` | |
| XLSX / XLS | `.xlsx`, `.xls` | `read_xlsx('path')` | Run `INSTALL excel FROM community; LOAD excel;` first |
| Multiple CSV | `*.csv` | `read_csv(['a.csv','b.csv'], union_by_name=true)` | Or ingest separately |
| Existing DuckDB | `.duckdb` | `ATTACH 'path' AS src; CREATE TABLE t AS SELECT * FROM src.main.table` | |
| Plain SQL dump | `.sql` | Execute statements in a controlled session | Review before run |

## SQL templates

Paths must stay under `data/landing/`. Use absolute or project-relative paths consistently.

```sql
-- CSV (default)
CREATE OR REPLACE TABLE my_table AS
SELECT * FROM read_csv_auto('data/landing/file.csv');

-- TSV
CREATE OR REPLACE TABLE my_table AS
SELECT * FROM read_csv('data/landing/file.tsv', delim = '\t', header = true);

-- JSON Lines
CREATE OR REPLACE TABLE my_table AS
SELECT * FROM read_json_auto('data/landing/file.jsonl', format = 'newline_delimited');

-- Parquet
CREATE OR REPLACE TABLE my_table AS
SELECT * FROM read_parquet('data/landing/file.parquet');

-- XLSX (sheet optional)
INSTALL excel FROM community;
LOAD excel;
CREATE OR REPLACE TABLE my_table AS
SELECT * FROM read_xlsx('data/landing/file.xlsx', sheet = 'Sheet1');
```

### Typed / messy CSV

```sql
CREATE OR REPLACE TABLE my_table AS
SELECT * FROM read_csv(
  'data/landing/file.csv',
  header = true,
  ignore_errors = true,
  encoding = 'latin-1'
);
```

### Nested JSON

```sql
CREATE OR REPLACE TABLE my_table AS
SELECT * FROM read_json('data/landing/file.json');
-- follow with UNNEST / struct extraction in further SQL
```

## Validation queries

```sql
SELECT COUNT(*) AS n FROM my_table;
DESCRIBE my_table;
SELECT * FROM my_table LIMIT 5;
```

## Error handling

| Issue | Action |
|-------|--------|
| Wrong delimiter | Set `delim` explicitly |
| Encoding | `encoding='latin-1'` or convert file in landing |
| Type inference | `read_csv(..., dtypes={...})` or cast in `SELECT` |
| Huge files | `LIMIT` while exploring; consider `WHERE` on ingest |
| XLSX fails | Confirm `excel` extension loaded |

## Persona

**Data engineer**: reproducible SQL, document assumptions in a short note to the user, never skip landing provenance.
