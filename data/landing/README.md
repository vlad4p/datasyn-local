# Landing zone

Raw inputs live here **before** they enter DuckDB. Nothing in this folder is transformed in place — files are copied or downloaded, then ingested.

## What belongs here

- CSV, JSON, XLSX exports
- Scraped HTML/JSON snapshots (keep scrape order in filenames or subfolders)
- API downloads and manual exports

## Workflow

```
scrape / download → data/landing/ → make ingest → data/duckdb/datasyn.duckdb → reports/
```

## Ingest

```bash
cp samples/example.csv data/landing/demo.csv
make ingest FILE=data/landing/demo.csv TABLE=demo
```

Large files and scrapes are **gitignored**; only this README and `.gitkeep` are tracked.
