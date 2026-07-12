#!/usr/bin/env bash
# DuckDB MCP stdio server attached to a remote Quack warehouse.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
UV_BIN="${UV_BIN:-$(command -v uv)}"
exec "${UV_BIN}" run python scripts/python/db.py quack-serve
