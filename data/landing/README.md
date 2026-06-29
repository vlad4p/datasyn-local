# Landing zone

Raw files **before** DuckDB. Do not edit originals in place.

**Privacy:** everything in this folder stays on your machine. It is **gitignored**
(including subfolders like `redes/`). Never commit CSV, JSON, exports, or scrapes.
Commit only ingest SQL, skills, or scripts — see `skills/data-privacy/SKILL.md`.

## Ingest

Use the **`ingest-data`** skill (`skills/ingest-data/SKILL.md`): DuckDB SQL only — CSV, TSV, JSON, JSONL, Parquet, XLSX, etc.

Example ask to your agent:

> Ingest `data/landing/my_file.csv` as table `my_table` using read_csv_auto.
