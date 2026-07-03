# Bronze format reference

Format-specific load strategies for [`ingest-data-bronze`](../ingest-data-bronze/SKILL.md).

## Format matrix

| Format | Extension | DuckDB approach | Notes |
|--------|-----------|-----------------|-------|
| CSV | `.csv` | `read_csv_auto('path')` | Add `header=true`, `delim=';'`, `encoding='UTF-8'` as needed |
| TSV | `.tsv`, `.txt` | `read_csv('path', delim='\t', header=true)` | |
| JSON array | `.json` | `read_json_auto('path')` | |
| JSON Lines | `.jsonl`, `.ndjson` | `read_json_auto('path', format='newline_delimited')` | |
| Parquet | `.parquet` | `read_parquet('path')` | |
| XLSX / XLS | `.xlsx`, `.xls` | `read_xlsx('path')` | `INSTALL excel FROM community; LOAD excel;` first |
| Multiple CSV | `*.csv` | `read_csv(['a.csv','b.csv'], union_by_name=true)` | Or ingest separately |
| Existing DuckDB | `.duckdb` | `ATTACH 'path' AS src; CREATE TABLE AS SELECT * FROM src.main.table` | |
| Plain SQL dump | `.sql` | Execute statements in a controlled session | Review before run |

## SQL templates

```sql
-- CSV (default)
CREATE OR REPLACE TABLE bronze.my_table AS
SELECT * FROM read_csv_auto('data/landing/file.csv');

-- TSV
CREATE OR REPLACE TABLE bronze.my_table AS
SELECT * FROM read_csv('data/landing/file.tsv', delim = '\t', header = true);

-- JSON Lines
CREATE OR REPLACE TABLE bronze.my_table AS
SELECT * FROM read_json_auto('data/landing/file.jsonl', format = 'newline_delimited');

-- Parquet
CREATE OR REPLACE TABLE bronze.my_table AS
SELECT * FROM read_parquet('data/landing/file.parquet');

-- XLSX
INSTALL excel FROM community;
LOAD excel;
CREATE OR REPLACE TABLE bronze.my_table AS
SELECT * FROM read_xlsx('data/landing/file.xlsx', sheet = 'Sheet1');
```

### Typed / messy CSV

```sql
CREATE OR REPLACE TABLE bronze.my_table AS
SELECT * FROM read_csv(
  'data/landing/file.csv',
  header = true,
  ignore_errors = true,
  encoding = 'latin-1'
);
```

### Nested JSON

```sql
CREATE OR REPLACE TABLE bronze.my_table AS
SELECT * FROM read_json('data/landing/file.json');
-- follow with UNNEST / struct extraction in further SQL
```

## Error handling

| Issue | Action |
|-------|--------|
| Wrong delimiter | Set `delim` explicitly |
| Encoding | `encoding='latin-1'` or convert file in landing |
| Type inference | `read_csv(..., dtypes={...})` or cast in `SELECT` |
| Huge files | `LIMIT` while exploring; consider `WHERE` on ingest |
| XLSX fails | Confirm `excel` extension loaded |
