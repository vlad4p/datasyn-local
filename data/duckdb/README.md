# DuckDB storage

Persistent database files for this project. Default: `datasyn.duckdb`.

- Path override: `DATASYN_DB_PATH` or `config/settings.yaml`
- Connect in Python: `from src.db import connect`
- Database files are **gitignored**; only this README and `.gitkeep` are tracked.

Create tables by ingesting from `data/landing/`:

```bash
make ingest FILE=data/landing/example.csv TABLE=example
```
