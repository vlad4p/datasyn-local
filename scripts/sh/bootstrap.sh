#!/usr/bin/env bash
# Configure MCP, verify duckdb_mcp, and print database status.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

UV="${UV:-uv}"
DB_PY="scripts/python/db.py"

echo "=== MCP config ==="
"$UV" run python "$DB_PY" mcp-config

echo "=== MCP check ==="
"$UV" run python "$DB_PY" mcp-check

echo "=== Database info ==="
"$UV" run python "$DB_PY" info
