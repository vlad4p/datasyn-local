#!/usr/bin/env python3
"""Generate a statistical report for a DuckDB table."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from src.db import connect, get_db_path

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"


def generate_report(table_name: str) -> Path:
    con = connect()
    try:
        tables = [r[0] for r in con.sql("SHOW TABLES").fetchall()]
        if table_name not in tables:
            raise ValueError(f"Table '{table_name}' not found. Available: {', '.join(tables) or 'none'}")

        row_count = con.sql(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        describe = con.sql(f"DESCRIBE {table_name}").df()
        summarize = con.sql(f"SUMMARIZE {table_name}").df()
    finally:
        con.close()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / f"{table_name}_report_{datetime.now():%Y%m%d_%H%M%S}.md"

    lines = [
        f"# Statistical Report: `{table_name}`",
        "",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"Database: `{get_db_path()}`",
        "",
        "## Overview",
        "",
        f"- **Row count:** {row_count:,}",
        f"- **Column count:** {len(describe)}",
        "",
        "## Schema",
        "",
        describe.to_markdown(index=False),
        "",
        "## Summary Statistics",
        "",
        summarize.to_markdown(index=False),
        "",
    ]

    out.write_text("\n".join(lines))
    print(f"Report written to {out}")
    return out


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: stat_report.py <table_name>")
        sys.exit(1)
    generate_report(sys.argv[1])


if __name__ == "__main__":
    main()
