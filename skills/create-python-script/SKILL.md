---
name: create-python-script
description: >-
  Add optional Python helpers under scripts/python/ (not for ingest or
  reports — those are skills). Use when reusable code beyond DuckDB SQL is needed.
---

# Create Python in scripts/python/

## Scope

- **Allowed:** extend `scripts/python/db.py` or new modules in `scripts/python/`
- **Not for:** ingest or report pipelines — use skills `ingest-data` and `statistical-report`

## Workflow

1. Confirm a skill (SQL) is insufficient
2. Add module under `scripts/python/`
3. Reuse `import db` for connections and paths
4. `uv add <package>` if needed
5. Document usage in `scripts/python/README.md`

## Import pattern

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path("scripts/python").resolve()))
import db

con = db.connect()
```

## Standards

- Run via `uv run python scripts/python/...`
- No secrets in code
