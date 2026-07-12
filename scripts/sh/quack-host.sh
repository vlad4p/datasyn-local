#!/usr/bin/env bash
# Host local datasyn.duckdb as a Quack HTTP warehouse (RW owner of the file).
# Not the same as quack-serve.sh (MCP client attached to a remote Quack).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
UV_BIN="${UV_BIN:-$(command -v uv)}"
exec "${UV_BIN}" run python scripts/python/db.py quack-host
