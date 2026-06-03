#!/usr/bin/env python3
"""Ingest CSV, JSON, or XLSX from landing into DuckDB."""

from __future__ import annotations

import sys
from pathlib import Path

from src.db import connect, get_landing_path


def ingest_file(file_path: Path, table_name: str) -> None:
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    landing = get_landing_path().resolve()
    resolved = file_path.resolve()
    if landing not in resolved.parents and resolved != landing:
        print(f"Warning: {file_path} is outside landing zone ({landing})")

    suffix = file_path.suffix.lower()
    con = connect()
    try:
        if suffix == ".csv":
            con.sql(
                f"CREATE OR REPLACE TABLE {table_name} AS "
                f"SELECT * FROM read_csv_auto('{file_path}')"
            )
        elif suffix == ".json":
            con.sql(
                f"CREATE OR REPLACE TABLE {table_name} AS "
                f"SELECT * FROM read_json_auto('{file_path}')"
            )
        elif suffix in (".xlsx", ".xls"):
            con.execute("INSTALL excel FROM community")
            con.execute("LOAD excel")
            con.sql(
                f"CREATE OR REPLACE TABLE {table_name} AS "
                f"SELECT * FROM read_xlsx('{file_path}')"
            )
        else:
            raise ValueError(f"Unsupported format: {suffix}. Use .csv, .json, or .xlsx")

        count = con.sql(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        print(f"Ingested {count} rows into '{table_name}' from {file_path}")
    finally:
        con.close()


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: ingest.py <file> <table_name>")
        sys.exit(1)
    ingest_file(Path(sys.argv[1]), sys.argv[2])


if __name__ == "__main__":
    main()
