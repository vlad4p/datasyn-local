"""Minimal CLI for datasyn-local."""

from __future__ import annotations

import argparse

from src.db import connect, get_db_path, get_landing_path, get_logs_path, list_tables
from src.trace import log_event


def main() -> None:
    parser = argparse.ArgumentParser(description="datasyn-local CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("info", help="Show database path and table list")
    sql_parser = sub.add_parser("sql", help="Run a SQL query")
    sql_parser.add_argument("query", help="SQL to execute")

    args = parser.parse_args()

    if args.command == "info":
        print(f"Database: {get_db_path()}")
        print(f"Landing:  {get_landing_path()}")
        print(f"Logs:     {get_logs_path()}")
        print("Tables:", ", ".join(list_tables()) or "(none)")
        log_event("cli.info", actor="cli", source="datasyn-cli")
    elif args.command == "sql":
        con = connect()
        try:
            con.sql(args.query).show()
            log_event(
                "cli.sql",
                actor="cli",
                source="datasyn-cli",
                data={"query_preview": args.query[:200]},
            )
        finally:
            con.close()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
