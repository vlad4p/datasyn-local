"""DuckDB paths, connection, and duckdb_mcp for datasyn-local.

Run from repo root:
  uv run python scripts/python/db.py info
  uv run python scripts/python/db.py mcp-check
  uv run python scripts/python/db.py mcp-config
  uv run python scripts/python/db.py mcp-serve
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import duckdb
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MCP_JSON = PROJECT_ROOT / ".cursor" / "mcp.json"
_MCP_JSON_EXAMPLE = PROJECT_ROOT / ".cursor" / "mcp.json.example"

# duckdb_mcp stdio server — https://github.com/teaguesterling/duckdb_mcp
_MCP_EXTENSION = "duckdb_mcp"


def load_settings() -> dict[str, Any]:
    settings_path = PROJECT_ROOT / "config" / "settings.yaml"
    if not settings_path.exists():
        return {}
    with settings_path.open() as f:
        return yaml.safe_load(f) or {}


def _path_from_settings(env_key: str, settings_key: tuple[str, str], default: str) -> Path:
    env_path = os.getenv(env_key)
    if env_path:
        return Path(env_path).expanduser().resolve()
    settings = load_settings()
    node: Any = settings
    for key in settings_key:
        node = node.get(key, {}) if isinstance(node, dict) else {}
    rel = node if isinstance(node, str) and node else default
    return (PROJECT_ROOT / rel).resolve()


def get_db_path() -> Path:
    return _path_from_settings(
        "DATASYN_DB_PATH",
        ("database", "path"),
        "data/duckdb/datasyn.duckdb",
    )


def get_landing_path() -> Path:
    return _path_from_settings(
        "DATASYN_LANDING_PATH",
        ("paths", "landing"),
        "data/landing",
    )


def get_reports_path() -> Path:
    return _path_from_settings(
        "DATASYN_REPORTS_PATH",
        ("paths", "reports"),
        "reports",
    )


def ensure_dirs() -> None:
    get_db_path().parent.mkdir(parents=True, exist_ok=True)
    get_landing_path().mkdir(parents=True, exist_ok=True)
    get_reports_path().mkdir(parents=True, exist_ok=True)


def validate_table_name(name: str) -> str:
    if not _TABLE_NAME_RE.fullmatch(name):
        raise ValueError(
            f"Invalid table name {name!r}. Use letters, digits, underscore; must start with letter or _."
        )
    return name


def quote_identifier(name: str) -> str:
    validate_table_name(name)
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def resolve_landing_file(file_path: Path) -> Path:
    landing = get_landing_path().resolve()
    resolved = file_path.expanduser().resolve()
    try:
        resolved.relative_to(landing)
    except ValueError as exc:
        raise ValueError(f"File must be inside landing directory ({landing})") from exc
    if not resolved.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    return resolved


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    ensure_dirs()
    return duckdb.connect(str(get_db_path()), read_only=read_only)


def list_tables(con: duckdb.DuckDBPyConnection | None = None) -> list[str]:
    close = False
    if con is None:
        con = connect()
        close = True
    try:
        rows = con.sql("SHOW TABLES").fetchall()
        return [r[0] for r in rows]
    finally:
        if close:
            con.close()


def load_mcp_extension(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(f"INSTALL {_MCP_EXTENSION} FROM community")
    con.execute(f"LOAD {_MCP_EXTENSION}")


def start_mcp_stdio_server(con: duckdb.DuckDBPyConnection) -> None:
    """Install duckdb_mcp and start stdio JSON-RPC server (blocks until disconnect)."""
    load_mcp_extension(con)
    con.execute("PRAGMA mcp_server_start('stdio')")


def mcp_check() -> int:
    con = connect()
    try:
        load_mcp_extension(con)
        status = con.execute("SELECT mcp_server_status()").fetchone()[0]
        tables = list_tables(con)
        print(
            f"duckdb_mcp OK. DB: {get_db_path().name} (data/duckdb/). "
            f"Tables: {', '.join(tables) or '(none)'}. Status: {status}"
        )
        return 0
    finally:
        con.close()


def _uv_cli() -> str:
    return os.getenv("UV_BIN") or shutil.which("uv") or "uv"


def mcp_config() -> int:
    """Write .cursor/mcp.json (gitignored). MCP bootstrap lives in this module."""
    db_path = get_db_path()
    db_script = (PROJECT_ROOT / "scripts" / "python" / "db.py").resolve()
    _MCP_JSON.parent.mkdir(parents=True, exist_ok=True)

    config = {
        "mcpServers": {
            "datasyn-duckdb": {
                "command": _uv_cli(),
                "args": ["run", "python", str(db_script), "mcp-serve"],
                "cwd": str(PROJECT_ROOT),
                "env": {"DATASYN_DB_PATH": str(db_path)},
            }
        }
    }

    _MCP_JSON.write_text(json.dumps(config, indent=2) + "\n")
    print(f"Wrote {_MCP_JSON}")
    print(f"Template: {_MCP_JSON_EXAMPLE}")
    return 0


def mcp_serve() -> None:
    """Start duckdb_mcp stdio server (blocks; used by Cursor MCP)."""
    con = connect()
    start_mcp_stdio_server(con)


def cmd_info() -> int:
    print(f"Root:     {PROJECT_ROOT}")
    print(f"Database: {get_db_path()}")
    print(f"Landing:  {get_landing_path()}")
    print(f"Reports:  {get_reports_path()}")
    print(f"MCP:      scripts/python/db.py mcp-serve ({_MCP_EXTENSION})")
    print("Tables:", ", ".join(list_tables()) or "(none)")
    return 0


def cmd_run_sql(sql: str) -> int:
    """Execute one or more SQL statements (;) and show results."""
    con = connect()
    try:
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for stmt in statements:
            try:
                result = con.sql(stmt)
                if result is not None and result.description:
                    result.show(max_width=120)
                else:
                    print("✅ OK")
            except Exception as e:
                print(f"❌ Error: {e}", file=sys.stderr)
                return 1
        return 0
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="datasyn-local database and MCP")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("info", help="Show paths and tables")
    sub.add_parser("mcp-check", help="Verify duckdb_mcp extension")
    sub.add_parser("mcp-config", help="Write .cursor/mcp.json")
    sub.add_parser("mcp-serve", help="Start MCP stdio server (blocking)")
    sql_parser = sub.add_parser("run-sql", help="Execute SQL statements")
    sql_parser.add_argument("sql", nargs="?", help="SQL statement(s) to execute")
    sql_parser.add_argument(
        "--file", "-f", type=str, help="Read SQL from file instead of argument"
    )

    args = parser.parse_args(argv)

    if args.command == "info":
        return cmd_info()
    if args.command == "mcp-check":
        return mcp_check()
    if args.command == "mcp-config":
        return mcp_config()
    if args.command == "mcp-serve":
        mcp_serve()
        return 0
    if args.command == "run-sql":
        if args.file:
            sql = Path(args.file).read_text()
        elif args.sql:
            sql = args.sql
        else:
            sql = sys.stdin.read()
        return cmd_run_sql(sql)
    return 1


if __name__ == "__main__":
    sys.exit(main())
