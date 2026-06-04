# Landing zone

Raw files **before** DuckDB. Do not edit originals in place.

## Ingest

Use the **`ingest-data`** skill (`skills/ingest-data/SKILL.md`): DuckDB SQL only — CSV, TSV, JSON, JSONL, Parquet, XLSX, etc.

Example ask to your agent:

> Ingest `data/landing/my_file.csv` as table `my_table` using read_csv_auto.

## Demo file

```bash
cp samples/example.csv data/landing/demo.csv
```

Then ingest via the agent and skill (not `make ingest`).
