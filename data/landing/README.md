# Landing zone

Place raw files here before ingestion into DuckDB:

- CSV, JSON, XLSX exports
- Scraped HTML/JSON snapshots
- Downloaded datasets

Files in this folder are gitignored by default. Only structure and this README are tracked.

Ingest with:

```bash
make ingest FILE=data/landing/example.csv TABLE=example
```

Or ask the agent to use the `ingest-data` skill.
