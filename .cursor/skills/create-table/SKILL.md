---
name: create-table
description: >-
  Create DuckDB tables with proper schema, constraints, and documentation.
  Use when the user asks to create a table, define schema, model data,
  or set up a new dataset structure in datasyn-local.
---

# Create DuckDB Table

## Conventions

- Table names: `snake_case`, plural nouns (`articles`, `sales_events`)
- Primary keys: `id` (INTEGER or UUID) or natural key documented in comment
- Timestamps: `created_at TIMESTAMP DEFAULT current_timestamp`
- Always use `src.db.connect()` — never hardcode DB paths

## Workflow

1. **Define purpose** — what entity/event does this table represent?
2. **Draft schema** — columns, types, nullable rules
3. **Create** with SQL
4. **Document** — add SQL comment or note in report

## Templates

### From scratch

```sql
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY,
    source VARCHAR NOT NULL,
    headline VARCHAR,
    body TEXT,
    published_at TIMESTAMP,
    url VARCHAR,
    ingested_at TIMESTAMP DEFAULT current_timestamp
);
```

### From query

```sql
CREATE TABLE cleaned_sales AS
SELECT
    order_id,
    CAST(amount AS DECIMAL(12,2)) AS amount,
    CAST(order_date AS DATE) AS order_date
FROM raw_sales
WHERE amount IS NOT NULL;
```

### From pandas

```python
import pandas as pd
from src.db import connect

df = pd.DataFrame({...})
con = connect()
con.register("tmp_df", df)
con.sql("CREATE TABLE my_table AS SELECT * FROM tmp_df")
con.close()
```

## Post-create checklist

```sql
DESCRIBE table_name;
SELECT COUNT(*) FROM table_name;
```

## Type reference (DuckDB)

| Use case | Type |
|----------|------|
| IDs | `INTEGER`, `BIGINT`, `UUID` |
| Money | `DECIMAL(12,2)` |
| Text | `VARCHAR`, `TEXT` |
| Dates | `DATE`, `TIMESTAMP` |
| JSON payload | `JSON` |
| Lists | `VARCHAR[]`, `INTEGER[]` |
