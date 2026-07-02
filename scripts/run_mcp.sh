#!/usr/bin/env bash
# DuckDB MCP entrypoint for Cursor / VS Code (stdio).
# Compatibility shim — delegates to scripts/sh/mcp-serve.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "${ROOT}/scripts/sh/mcp-serve.sh"
