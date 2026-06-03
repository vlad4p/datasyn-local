---
name: create-python-script
description: >-
  Create Python scripts in src/ following datasyn-local conventions.
  Use when the user asks for a new script, module, pipeline step, or
  Python automation in this repository.
---

# Create Python Script in src/

## Agent persona

Act as an **expert Python developer and data engineer** who writes clean, typed, testable code and knows SQL/DuckDB.

## Conventions

- Place modules in `src/` (not root)
- Import DB via `from src.db import connect, get_landing_path, get_db_path`
- Use `pathlib.Path` for file paths
- Add type hints and docstrings for public functions
- CLI entry points: add to `src/cli.py` or standalone `scripts/` for one-offs

## Template

```python
"""Brief module description."""

from __future__ import annotations

from pathlib import Path

from src.db import connect


def run(input_path: Path) -> None:
    """Process data and write to DuckDB."""
    con = connect()
    try:
        con.sql("SELECT 1").show()
    finally:
        con.close()


if __name__ == "__main__":
    run(Path("data/landing/example.csv"))
```

## Checklist before finishing

- [ ] Uses `connect()` context manager or try/finally
- [ ] Paths relative to project root or from `get_landing_path()`
- [ ] No secrets in code — use `.env` / environment variables
- [ ] Runnable via `uv run python -m src.module_name` or documented CLI
- [ ] Dependencies added to `pyproject.toml` if new packages needed

## Adding CLI command

Extend `src/cli.py`:

```python
sub.add_parser("mycommand", help="Description")
# handle in main()
```

Then: `uv run python -m src.cli mycommand`
