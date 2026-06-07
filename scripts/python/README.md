# Python scripts

| Script | Usage |
|--------|--------|
| `db.py` | DuckDB connection, paths, MCP (`INSTALL`/`LOAD`/`PRAGMA mcp_server_start`) |

```bash
uv run python scripts/python/db.py info
uv run python scripts/python/db.py mcp-check
uv run python scripts/python/db.py mcp-config
uv run python scripts/python/db.py mcp-serve   # Cursor MCP (stdio)
```

Import from repo root in other Python code:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path("scripts/python").resolve()))
import db

con = db.connect()
```
