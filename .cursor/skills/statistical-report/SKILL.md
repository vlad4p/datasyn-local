---
name: statistical-report
description: >-
  Generate statistical summaries and reports for DuckDB tables using DESCRIBE,
  SUMMARIZE, and markdown output. Use when the user asks for EDA, stats,
  distribution analysis, table profiling, or data quality reports.
---

# Statistical Report

## Output location

Reports go to `reports/` as markdown files.

## Quick run

```bash
make report TABLE=my_table
# or
uv run python scripts/stat_report.py my_table
```

## Manual workflow

1. Connect via `src.db.connect()`
2. Run profiling queries:

```sql
SELECT COUNT(*) AS rows FROM {table};
DESCRIBE {table};
SUMMARIZE {table};
```

3. Add domain-specific stats as needed:

```sql
-- Null rates
SELECT column_name, null_percentage
FROM (SUMMARIZE my_table);

-- Cardinality for categorical columns
SELECT category, COUNT(*) AS n
FROM my_table GROUP BY 1 ORDER BY 2 DESC LIMIT 20;

-- Date range
SELECT MIN(date_col), MAX(date_col) FROM my_table;
```

## Report template

```markdown
# Statistical Report: `{table}`

## Executive summary
[2-3 sentences: size, key columns, data quality issues]

## Overview
- Row count, column count, date range

## Schema
[DESCRIBE output]

## Summary statistics
[SUMMARIZE output]

## Notable patterns
- Outliers, skew, missing data, duplicates

## Recommendations
- Cleaning steps or follow-up analyses
```

## Agent persona

Act as an **expert data analyst**: translate numbers into insights, flag anomalies, suggest next steps. Cite exact counts and percentages from query results.
