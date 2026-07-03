---
name: ingest-data-bronze
description: >-
  Ingest raw files from data/landing into the bronze schema. First layer
  of the medallion pattern — preserve originals, no transformations.
  Supports CSV, TSV, JSON, JSONL, Parquet, XLSX. Use when importing,
  scraping, or loading raw data into DuckDB for the first time.
---

# Ingest data — Bronze (raw layer)

**Zone:** Bronze — `bronze.*` schema.
**Source:** files in `data/landing/` or direct scrapes (local only — gitignored).
**Goal:** load raw data as-is into DuckDB tables. No cleaning, no joins.

**Privacy:** landing files and the `.duckdb` database must not be committed. Commit ingest SQL/skills only — see **`data-privacy`**.

---

## Start here — analyze before you act

1. **What is the source?** → landing file (CSV, JSON, Parquet, etc.) or scrape result
2. **Is it raw?** → yes → this is **bronze**
3. **Any transformations needed?** → no → bronze; if yes → consider **silver** after this step

---

## Workflow

1. **Inspect** — format, encoding, headers (`head`, `file`, or MCP `query` with `read_* LIMIT 5`)
2. **Create schema** — `CREATE SCHEMA IF NOT EXISTS bronze`
3. **Choose load strategy** → see [`references/formats.md`](../references/formats.md)
4. **Create table** — `CREATE OR REPLACE TABLE bronze.{name} AS SELECT ... FROM read_*`
5. **Validate** — `COUNT(*)`, `DESCRIBE`, sample rows via MCP

---

## Validation (via MCP)

```sql
SELECT COUNT(*) AS rows FROM bronze.my_table;
DESCRIBE bronze.my_table;
SELECT * FROM bronze.my_table LIMIT 5;
```

---

## After bronze → go to silver

Once data is in bronze, use [`ingest-data-silver`](../../silver/ingest-data-silver/SKILL.md)
to clean, deduplicate, normalize, or join tables.
