#!/usr/bin/env python3
"""Ingest CSV, JSON, or XLSX from landing into DuckDB."""

from __future__ import annotations

import sys
from pathlib import Path

from src.db import PROJECT_ROOT, connect, quote_identifier, resolve_landing_file, validate_table_name
from src.trace import log_event


def ingest_file(file_path: Path, table_name: str) -> None:
    validate_table_name(table_name)
    resolved = resolve_landing_file(file_path)
    qtable = quote_identifier(table_name)

    suffix = resolved.suffix.lower()
    con = connect()
    try:
        path_arg = str(resolved)
        if suffix == ".csv":
            con.execute(
                f"CREATE OR REPLACE TABLE {qtable} AS SELECT * FROM read_csv_auto(?)",
                [path_arg],
            )
        elif suffix == ".json":
            con.execute(
                f"CREATE OR REPLACE TABLE {qtable} AS SELECT * FROM read_json_auto(?)",
                [path_arg],
            )
        elif suffix in (".xlsx", ".xls"):
            con.execute("INSTALL excel FROM community")
            con.execute("LOAD excel")
            con.execute(
                f"CREATE OR REPLACE TABLE {qtable} AS SELECT * FROM read_xlsx(?)",
                [path_arg],
            )
        else:
            raise ValueError(f"Unsupported format: {suffix}. Use .csv, .json, or .xlsx")

        count = con.sql(f"SELECT COUNT(*) FROM {qtable}").fetchone()[0]
        print(f"Ingested {count} rows into '{table_name}' from {resolved.relative_to(PROJECT_ROOT)}")
        log_event(
            "ingest.complete",
            actor="cli",
            source="scripts/ingest.py",
            data={
                "table": table_name,
                "file": str(resolved.relative_to(PROJECT_ROOT)),
                "rows": count,
            },
        )
    finally:
        con.close()


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: ingest.py <file> <table_name>")
        sys.exit(1)
    ingest_file(Path(sys.argv[1]), sys.argv[2])


if __name__ == "__main__":
    main()
