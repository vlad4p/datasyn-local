#!/usr/bin/env bash
# Launcher for Cursor MCP — resolves project root regardless of cwd.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export DATASYN_DB_PATH="${DATASYN_DB_PATH:-$ROOT/data/duckdb/datasyn.duckdb}"
export PYTHONPATH="${PYTHONPATH:-$ROOT}"
exec uv run python "$ROOT/scripts/mcp_server.py"
