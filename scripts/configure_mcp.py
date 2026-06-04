#!/usr/bin/env python3
"""Write .cursor/mcp.json with absolute paths for this machine (local only, gitignored)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".cursor" / "mcp.json"


def main() -> None:
    launcher = ROOT / "scripts" / "run_mcp.sh"
    db_path = ROOT / "data" / "duckdb" / "datasyn.duckdb"
    if not launcher.is_file():
        print(f"Missing launcher: {launcher}", file=sys.stderr)
        sys.exit(1)

    config = {
        "mcpServers": {
            "datasyn-duckdb": {
                "command": str(launcher.resolve()),
                "env": {"DATASYN_DB_PATH": str(db_path.resolve())},
            }
        }
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(config, indent=2) + "\n")
    print(f"Wrote {OUT}")
    print("This file is gitignored. Commit only .cursor/mcp.json.example.")


if __name__ == "__main__":
    main()
