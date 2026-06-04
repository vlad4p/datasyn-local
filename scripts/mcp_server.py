#!/usr/bin/env python3
"""Start DuckDB MCP server exposing project tables via stdio."""

from __future__ import annotations

import argparse
import sys

from src.db import connect, get_db_path, list_tables
from src.trace import log_event


def run_check() -> None:
    con = connect()
    try:
        con.execute("INSTALL duckdb_mcp FROM community")
        con.execute("LOAD duckdb_mcp")
        tables = list_tables(con)
        print(
            f"duckdb_mcp loaded. DB file: {get_db_path().name} (data/duckdb/). "
            f"Tables: {', '.join(tables) or '(none)'}"
        )
        log_event(
            "mcp.check",
            actor="cli",
            source="scripts/mcp_server.py",
            data={"tables": tables},
        )
    finally:
        con.close()


def run_server() -> None:
    """Run MCP on stdio. Do not write to stdout — JSON-RPC uses it."""
    con = connect()
    con.execute("INSTALL duckdb_mcp FROM community")
    con.execute("LOAD duckdb_mcp")

    tables = list_tables(con)
    for table in tables:
        uri = f"data://tables/{table}"
        con.execute(f"PRAGMA mcp_publish_table('{table}', '{uri}', 'json')")

    log_event(
        "mcp.server_start",
        actor="mcp",
        source="scripts/mcp_server.py",
        data={"tables": tables},
    )
    # PRAGMA blocks and serves MCP until stdin closes. Never call con.close() here.
    con.execute("PRAGMA mcp_server_start('stdio')")


def main() -> None:
    parser = argparse.ArgumentParser(description="DuckDB MCP server for datasyn-local")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify extension without starting server",
    )
    args = parser.parse_args()

    if args.check:
        run_check()
    else:
        run_server()


if __name__ == "__main__":
    main()
