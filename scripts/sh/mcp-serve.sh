#!/usr/bin/env bash
# DuckDB MCP stdio server — Cursor / VS Code integration via duckdb_mcp.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
UV_BIN="${UV_BIN:-$(command -v uv)}"
exec "${UV_BIN}" run python scripts/python/db.py mcp-serve
