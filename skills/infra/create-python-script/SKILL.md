---
name: create-python-script
description: >-
  Add optional Python helpers under scripts/python/ (not for ingest or
  reports — those are skills). Use when reusable code beyond DuckDB SQL is needed.
---

# Create Python in scripts/python/

## Scope

- **Allowed:** extend `scripts/python/db.py` or new modules under the taxonomy below
- **Not for:** ingest or report pipelines — use skills `ingest-data` and `statistical-report`
- **Exception:** report exporters in `scripts/python/reports/` — extend via skill [`redes-analysis`](../analyze/reports/redes-analysis/SKILL.md) or [`social-monitor`](../analyze/reports/social-monitor/SKILL.md)
- **SQL queries:** prefer MCP (`db.py run-sql`) over direct `db.connect()` + `con.execute()`

## Where to put a new script

| Kind | Folder |
|------|--------|
| Scrape / download | `scripts/python/scrape/<domain>/` |
| LLM classify / label | `scripts/python/classify/` |
| Report HTML/CSV export | `scripts/python/reports/` (+ `templates/` if needed) |
| Graph / entity analysis helpers | `scripts/python/analyze/` |
| Misc utilities | `scripts/python/tools/` |
| DuckDB / MCP / Quack | extend `scripts/python/db.py` |

SQL files go under `scripts/sql/<domain>/` (see [`scripts/sql/README.md`](../../../scripts/sql/README.md)). Use `db.resolve_sql("basename.sql")` so basename lookups still work.

## Workflow

1. Confirm a skill (SQL) is insufficient
2. Add module under the matching folder above
3. Reuse `import db` for connections and paths (`sys.path` → `scripts/python`)
4. `uv add <package>` if needed
5. Document usage in `scripts/python/README.md`

## SQL execution

When the script needs to run SQL, **prefer MCP** (subprocess call to `db.py run-sql`):

```python
import subprocess
sql = "SELECT COUNT(*) FROM my_table;"
subprocess.run(["uv", "run", "python", "scripts/python/db.py", "run-sql", sql])
```

Only use direct `db.connect()` when MCP cannot handle the task (e.g., pandas/DataFrame operations, multi-step procedural logic).

## Import pattern (for direct DB connection — fallback only)

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path("scripts/python").resolve()))
import db

con = db.connect()
sql_path = db.resolve_sql("ingest_identidades.sql")
```

## Standards

- Run via `uv run python scripts/python/...`
- No secrets in code
