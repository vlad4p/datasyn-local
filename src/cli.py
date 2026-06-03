"""Minimal CLI for datasyn-local."""

from __future__ import annotations

import argparse

from src.db import connect, get_db_path, list_tables


def main() -> None:
    parser = argparse.ArgumentParser(description="datasyn-local CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("info", help="Show database path and table list")
    sql_parser = sub.add_parser("sql", help="Run a SQL query")
    sql_parser.add_argument("query", help="SQL to execute")

    args = parser.parse_args()

    if args.command == "info":
        print(f"Database: {get_db_path()}")
        print("Tables:", ", ".join(list_tables()) or "(none)")
    elif args.command == "sql":
        con = connect()
        try:
            con.sql(args.query).show()
        finally:
            con.close()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
