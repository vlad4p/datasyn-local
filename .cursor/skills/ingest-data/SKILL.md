---
name: ingest-data
description: >-
  Ingest CSV, JSON, and XLSX files from data/landing into DuckDB tables.
  Use when importing data, loading files, ETL, or when the user mentions
  csv, json, xlsx, excel, or landing zone ingestion.
---

# Ingest Data into DuckDB

## Prerequisites

- File in `data/landing/` (or user-provided path)
- Virtual env active: `make install` or `uv sync`
- Database path: `data/duckdb/datasyn.duckdb` (override via `DATASYN_DB_PATH`)

## Workflow

1. **Inspect source file** — confirm format, encoding, headers, row count preview
2. **Choose table name** — snake_case, descriptive (e.g. `sales_2024`, `news_articles`)
3. **Ingest** using one of:

### CLI (preferred)

```bash
make ingest FILE=data/landing/example.csv TABLE=example
```

### Python script

```bash
uv run python scripts/ingest.py data/landing/example.csv example
```

### SQL (direct)

```python
from src.db import connect

con = connect()
# CSV
con.sql("CREATE OR REPLACE TABLE t AS SELECT * FROM read_csv_auto('data/landing/file.csv')")
# JSON
con.sql("CREATE OR REPLACE TABLE t AS SELECT * FROM read_json_auto('data/landing/file.json')")
# XLSX (requires excel extension)
con.execute("INSTALL excel FROM community")
con.execute("LOAD excel")
con.sql("CREATE OR REPLACE TABLE t AS SELECT * FROM read_xlsx('data/landing/file.xlsx')")
con.close()
```

## Format-specific notes

| Format | DuckDB function | Notes |
|--------|-----------------|-------|
| CSV | `read_csv_auto()` | Handles delimiter/header detection |
| JSON | `read_json_auto()` | Supports JSON lines and arrays |
| XLSX | `read_xlsx()` | Requires `excel` community extension |

## Validation

After ingest, always verify:

```sql
SELECT COUNT(*) FROM table_name;
DESCRIBE table_name;
SELECT * FROM table_name LIMIT 5;
```

## Error handling

- **Encoding issues (CSV):** add `encoding='latin-1'` or `ignore_errors=true`
- **Nested JSON:** use `read_json()` with explicit columns or unnest in follow-up SQL
- **Multi-sheet XLSX:** specify sheet: `read_xlsx('file.xlsx', sheet='Sheet2')`
