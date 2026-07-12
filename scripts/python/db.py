"""DuckDB paths, connection, and duckdb_mcp for datasyn-local.

Run from repo root:
  uv run python scripts/python/db.py info
  uv run python scripts/python/db.py mcp-check
  uv run python scripts/python/db.py mcp-config
  uv run python scripts/python/db.py mcp-stop
  uv run python scripts/python/db.py mcp-status
  uv run python scripts/python/db.py mcp-serve
  uv run python scripts/python/db.py quack-info
  uv run python scripts/python/db.py quack-check
  uv run python scripts/python/db.py quack-serve
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import duckdb
import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)

_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MCP_JSON = PROJECT_ROOT / ".cursor" / "mcp.json"
_MCP_JSON_EXAMPLE = PROJECT_ROOT / ".cursor" / "mcp.json.example"

# duckdb_mcp stdio server — https://github.com/teaguesterling/duckdb_mcp
_MCP_EXTENSION = "duckdb_mcp"

# Quack remote warehouse defaults (fleet host for datasyn-duckdb)
_QUACK_DEFAULT_HOST = "10.13.10.119"
_QUACK_DEFAULT_PORT = 9494
# Attach alias (quoted — hyphen). Non-main schemas need .query() — see quack_remote_sql.
QUACK_ALIAS = "datasyn-rlab"


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
    """Root directory for all report outputs (default: reports/)."""
    return _path_from_settings(
        "DATASYN_REPORTS_PATH",
        ("paths", "reports"),
        "reports",
    )


_PROJECT_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def get_report_path(project: str, name: str) -> Path:
    """Return reports/<project>/<name>, creating the project subdirectory.

    For multi-file reports prefer get_report_bundle() — one folder per report slug.
    """
    slug = project.strip().lower().replace("_", "-")
    if not _PROJECT_SLUG_RE.fullmatch(slug):
        raise ValueError(
            f"Invalid report project {project!r}. Use kebab-case slug (e.g. redes, grafo, nyt)."
        )
    if not name or "/" in name or name in (".", ".."):
        raise ValueError(f"Invalid report name {name!r}.")
    out_dir = get_reports_path() / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / name


def get_report_bundle(project: str, bundle: str) -> Path:
    """Return reports/<project>/<bundle>/ — one folder per report with its data files.

    Example: get_report_bundle("redes", "dashboard") → reports/redes/dashboard/
    """
    slug = project.strip().lower().replace("_", "-")
    if not _PROJECT_SLUG_RE.fullmatch(slug):
        raise ValueError(
            f"Invalid report project {project!r}. Use kebab-case slug (e.g. redes, grafo, nyt)."
        )
    bundle_slug = bundle.strip().lower().replace("_", "-")
    if not _PROJECT_SLUG_RE.fullmatch(bundle_slug):
        raise ValueError(
            f"Invalid report bundle {bundle!r}. Use kebab-case slug (e.g. dashboard, sentiment-brief)."
        )
    out_dir = get_reports_path() / slug / bundle_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


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


def _sql_str(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _as_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_quack_host() -> str:
    host = (os.getenv("QUACK_HOST") or "").strip()
    if host:
        return host
    settings = load_settings()
    quack = settings.get("quack", {}) if isinstance(settings, dict) else {}
    if isinstance(quack, dict):
        configured = (quack.get("host") or "").strip()
        if configured:
            return configured
    return _QUACK_DEFAULT_HOST


def get_quack_port() -> int:
    raw = (os.getenv("QUACK_PORT") or "").strip()
    if raw:
        return int(raw)
    settings = load_settings()
    quack = settings.get("quack", {}) if isinstance(settings, dict) else {}
    if isinstance(quack, dict) and quack.get("port") is not None:
        return int(quack["port"])
    return _QUACK_DEFAULT_PORT


def get_quack_token() -> str | None:
    token = (os.getenv("QUACK_TOKEN") or "").strip()
    return token or None


def get_quack_disable_ssl() -> bool:
    raw = os.getenv("QUACK_DISABLE_SSL")
    if raw is not None and raw.strip() != "":
        return _as_bool(raw, default=True)
    settings = load_settings()
    quack = settings.get("quack", {}) if isinstance(settings, dict) else {}
    if isinstance(quack, dict) and "disable_ssl" in quack:
        return bool(quack["disable_ssl"])
    return True


def get_quack_uri() -> str:
    return f"quack:{get_quack_host()}:{get_quack_port()}"


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


def _mcp_pgrep() -> list[tuple[str, str]]:
    """Return (pid, command) for running mcp-serve processes."""
    result = subprocess.run(
        ["pgrep", "-fl", "db.py mcp-serve"],
        capture_output=True,
        text=True,
    )
    rows: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2:
            rows.append((parts[0], parts[1]))
    return rows


def mcp_status() -> dict[str, Any]:
    """Report whether duckdb_mcp is running and holding the DB file."""
    processes = _mcp_pgrep()
    return {
        "running": bool(processes),
        "processes": [{"pid": pid, "command": cmd} for pid, cmd in processes],
        "db_path": str(get_db_path()),
    }


def mcp_stop() -> int:
    """Stop db.py mcp-serve processes so Python can open the DB for ingest."""
    processes = _mcp_pgrep()
    if not processes:
        print("MCP server not running.")
        return 0
    result = subprocess.run(["pkill", "-f", "db.py mcp-serve"])
    remaining = _mcp_pgrep()
    if remaining:
        print("Failed to stop MCP server:", file=sys.stderr)
        for pid, cmd in remaining:
            print(f"  PID {pid}: {cmd}", file=sys.stderr)
        return 1
    stopped = ", ".join(pid for pid, _ in processes)
    print(f"Stopped MCP server (PID {stopped}). Re-enable MCP in Cursor to query again.")
    return 0 if result.returncode in (0, 1) else result.returncode


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    ensure_dirs()
    return duckdb.connect(str(get_db_path()), read_only=read_only)


def _quack_attach_opts() -> list[str]:
    opts = ["TYPE quack"]
    token = get_quack_token()
    if token:
        opts.append(f"TOKEN {_sql_str(token)}")
    if get_quack_disable_ssl():
        opts.append("DISABLE_SSL true")
    return opts


def attach_quack(con: duckdb.DuckDBPyConnection, *, use: bool = False) -> None:
    """ATTACH remote Quack warehouse as QUACK_ALIAS on an existing connection.

    When ``use`` is False (default for local ingest), the connection's default
    catalog stays on the local file DB so CREATE TABLE silver.* writes locally
    while remote bronze is readable via ``"datasyn-rlab".query('…')``.
    """
    attach_uri = f"quack:{get_quack_host()}:{get_quack_port()}"
    con.execute("INSTALL quack;")
    con.execute("LOAD quack;")
    opts = _quack_attach_opts()
    con.execute(f'ATTACH {_sql_str(attach_uri)} AS "{QUACK_ALIAS}" ({", ".join(opts)});')
    if use:
        con.execute(f'USE "{QUACK_ALIAS}";')


def connect_quack() -> duckdb.DuckDBPyConnection:
    """Open an in-memory DuckDB session attached to a remote Quack warehouse."""
    con = duckdb.connect()
    attach_quack(con, use=True)
    return con


def quack_remote_sql(sql: str) -> str:
    """Wrap SQL for Quack's attachment ``.query()`` macro.

    Quack 1.5.x cannot scan non-``main`` schemas via ``FROM bronze.t`` after
    ATTACH (duckdb/duckdb-quack#144). Push the statement to the server with
    ``FROM "datasyn-rlab".query('…')`` instead.
    """
    return f'FROM "{QUACK_ALIAS}".query({_sql_str(sql)})'


def quack_execute(con: duckdb.DuckDBPyConnection, sql: str):
    """Run SQL on the remote Quack warehouse (works for any schema)."""
    return con.execute(quack_remote_sql(sql))


def quack_sql_relation(con: duckdb.DuckDBPyConnection, sql: str):
    """Like quack_execute but returns a Relation (supports .show())."""
    return con.sql(quack_remote_sql(sql))


def connect_for_ingest(
    *,
    release_mcp: bool | None = None,
    attach_quack_remote: bool = False,
) -> duckdb.DuckDBPyConnection:
    """Open a read-write connection for ingest (bronze/silver writes).

    DuckDB allows one writer process at a time. When MCP is running it holds
    the file lock — pass release_mcp=True (or set DATASYN_RELEASE_MCP_FOR_WRITE=1)
    to stop mcp-serve before connecting.

    When ``attach_quack_remote`` is True, also ATTACH the Quack warehouse as
    ``datasyn-rlab`` without USE so local writes + remote ``.query()`` reads
    share one session.
    """
    if release_mcp is None:
        release_mcp = os.getenv("DATASYN_RELEASE_MCP_FOR_WRITE", "").strip().lower() in {
            "1",
            "true",
            "yes",
        }
    if release_mcp:
        mcp_stop()
    try:
        con = connect(read_only=False)
    except duckdb.IOException as exc:
        locked = _duckdb_lock_message(exc)
        if locked and locked[1]:
            raise duckdb.IOException(
                f"{locked[0]} Run: uv run python scripts/python/db.py mcp-stop"
            ) from exc
        raise
    if attach_quack_remote:
        attach_quack(con, use=False)
    return con


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


def _duckdb_lock_message(exc: BaseException) -> tuple[str, bool] | None:
    """If exc is a DuckDB file lock, return (message, mcp_already_running)."""
    msg = str(exc)
    if "Conflicting lock" not in msg:
        return None
    pid_match = re.search(r"\(PID (\d+)\)", msg)
    if not pid_match:
        return (
            "Database is locked by another process. Stop MCP or other DuckDB clients and retry.",
            False,
        )
    pid = pid_match.group(1)
    try:
        cmd = subprocess.run(
            ["ps", "-p", pid, "-o", "command="],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        cmd = ""
    if "mcp-serve" in cmd or re.search(r"db\.py.*mcp-serve", cmd):
        return (
            f"duckdb_mcp OK (server already running). DB: {get_db_path().name} "
            f"(data/duckdb/). Locked by MCP PID {pid}. "
            "Disable MCP in Cursor to run a full check, or use MCP tools directly.",
            True,
        )
    detail = cmd or "unknown process"
    return (f"Database locked by PID {pid}: {detail}. Close it and retry.", False)


def mcp_check() -> int:
    try:
        con = connect()
    except duckdb.IOException as exc:
        locked = _duckdb_lock_message(exc)
        if locked:
            print(locked[0])
            return 0 if locked[1] else 1
        raise
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


def _mcp_server_entry() -> dict[str, Any]:
    db_path = get_db_path()
    mcp_script = (PROJECT_ROOT / "scripts" / "run_mcp.sh").resolve()
    return {
        "command": str(mcp_script),
        "cwd": str(PROJECT_ROOT),
        "env": {"DATASYN_DB_PATH": str(db_path)},
    }


def _quack_server_entry() -> dict[str, Any]:
    quack_script = (PROJECT_ROOT / "scripts" / "sh" / "quack-serve.sh").resolve()
    env: dict[str, str] = {
        "QUACK_HOST": get_quack_host(),
        "QUACK_PORT": str(get_quack_port()),
        "QUACK_DISABLE_SSL": "true" if get_quack_disable_ssl() else "false",
    }
    token = get_quack_token()
    if token:
        env["QUACK_TOKEN"] = token
    return {
        "command": str(quack_script),
        "cwd": str(PROJECT_ROOT),
        "env": env,
    }


def mcp_config() -> int:
    """Write .cursor/mcp.json (gitignored). MCP bootstrap lives in this module."""
    _MCP_JSON.parent.mkdir(parents=True, exist_ok=True)

    config = {
        "mcpServers": {
            "datasyn-duckdb": _mcp_server_entry(),
            "datasyn-quack": _quack_server_entry(),
        }
    }

    _MCP_JSON.write_text(json.dumps(config, indent=2) + "\n")
    print(f"Wrote {_MCP_JSON}")
    print(f"Template: {_MCP_JSON_EXAMPLE}")
    print()
    print("Cursor: Settings → MCP → enable 'datasyn-duckdb' and/or 'datasyn-quack' → Restart")
    print("If you use a global server 'duckdb-local', point command to:")
    print(f"  {_mcp_server_entry()['command']}")
    return 0


def mcp_serve() -> None:
    """Start duckdb_mcp stdio server (blocks; used by Cursor MCP)."""
    con = connect()
    start_mcp_stdio_server(con)


def quack_info() -> int:
    """Print resolved Quack connection settings (token redacted)."""
    token = get_quack_token()
    print(f"Quack URI:     {get_quack_uri()}")
    print(f"Host:          {get_quack_host()}")
    print(f"Port:          {get_quack_port()}")
    print(f"Disable SSL:   {get_quack_disable_ssl()}")
    print(f"Token:         {'set (' + str(len(token)) + ' chars)' if token else '(not set)'}")
    return 0


def quack_check() -> int:
    """Attach to the remote Quack warehouse and list schemas/tables."""
    uri = get_quack_uri()
    try:
        con = connect_quack()
    except Exception as exc:
        print(f"Quack attach failed ({uri}): {exc}", file=sys.stderr)
        return 1
    try:
        # Quack often leaves information_schema.tables empty; columns is reliable.
        rows = con.execute(
            """
            SELECT table_schema, table_name, count(*)::BIGINT AS ncols
            FROM information_schema.columns
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
            GROUP BY 1, 2
            ORDER BY 1, 2
            """
        ).fetchall()
        print(
            f'Quack OK. Attached {uri} AS "{QUACK_ALIAS}" '
            f"(ssl_disabled={get_quack_disable_ssl()})."
        )
        print(
            "Note: scan non-main schemas via "
            f'FROM "{QUACK_ALIAS}".query(\'SELECT … FROM schema.table\') '
            "or: db.py quack-sql '…'"
        )
        if not rows:
            print("Tables: (none)")
        else:
            print(f"Tables ({len(rows)}):")
            for schema, name, ncols in rows[:50]:
                n_rows = "?"
                try:
                    n_rows = quack_execute(
                        con, f"SELECT count(*) FROM {schema}.{name}"
                    ).fetchone()[0]
                except Exception:
                    pass
                print(f"  {schema}.{name} ({ncols} cols, {n_rows} rows)")
            if len(rows) > 50:
                print(f"  ... and {len(rows) - 50} more")
        return 0
    finally:
        con.close()


def quack_run_sql(sql: str) -> int:
    """Execute SQL against the remote Quack warehouse via .query()."""
    uri = get_quack_uri()
    try:
        con = connect_quack()
    except Exception as exc:
        print(f"Quack attach failed ({uri}): {exc}", file=sys.stderr)
        return 1
    try:
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for stmt in statements:
            try:
                result = quack_sql_relation(con, stmt)
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


def quack_serve() -> None:
    """Attach to Quack warehouse and start duckdb_mcp stdio server (blocks)."""
    con = connect_quack()
    start_mcp_stdio_server(con)


def cmd_info() -> int:
    print(f"Root:     {PROJECT_ROOT}")
    print(f"Database: {get_db_path()}")
    print(f"Landing:  {get_landing_path()}")
    print(f"Reports:  {get_reports_path()}")
    print(f"MCP:      scripts/sh/mcp-serve.sh ({_MCP_EXTENSION})")
    print(f"Quack:    {get_quack_uri()} (scripts/sh/quack-serve.sh)")
    print("Tables:", ", ".join(list_tables()) or "(none)")
    return 0


def cmd_run_sql(
    sql: str,
    *,
    for_ingest: bool = False,
    attach_quack_remote: bool = False,
) -> int:
    """Execute one or more SQL statements (;) and show results."""
    if for_ingest:
        con = connect_for_ingest(attach_quack_remote=attach_quack_remote)
    else:
        con = connect()
        if attach_quack_remote:
            attach_quack(con, use=False)
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
    sub.add_parser("mcp-stop", help="Stop mcp-serve so Python can ingest (write)")
    sub.add_parser("mcp-status", help="Show whether mcp-serve is running")
    sub.add_parser("quack-info", help="Show Quack remote connection settings")
    sub.add_parser("quack-check", help="Attach to Quack warehouse and list tables")
    sub.add_parser("quack-serve", help="Start MCP stdio server on Quack warehouse (blocking)")
    quack_sql_parser = sub.add_parser(
        "quack-sql",
        help="Run SQL on remote Quack (uses .query() — required for non-main schemas)",
    )
    quack_sql_parser.add_argument("sql", nargs="?", help="SQL statement(s) to execute remotely")
    quack_sql_parser.add_argument(
        "--file", "-f", type=str, help="Read SQL from file instead of argument"
    )
    sql_parser = sub.add_parser("run-sql", help="Execute SQL statements")
    sql_parser.add_argument("sql", nargs="?", help="SQL statement(s) to execute")
    sql_parser.add_argument(
        "--file", "-f", type=str, help="Read SQL from file instead of argument"
    )
    sql_parser.add_argument(
        "--ingest",
        action="store_true",
        help="Write mode: release MCP lock before running (bronze/silver ingest)",
    )
    sql_parser.add_argument(
        "--attach-quack",
        action="store_true",
        help=(
            f'ATTACH remote Quack as "{QUACK_ALIAS}" without USE '
            "(read remote via .query(); write local silver/gold)"
        ),
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
    if args.command == "mcp-stop":
        return mcp_stop()
    if args.command == "mcp-status":
        status = mcp_status()
        if status["running"]:
            for proc in status["processes"]:
                print(f"MCP running: PID {proc['pid']} — {proc['command']}")
            print(f"DB: {status['db_path']}")
            print("Query via MCP tools. For ingest: db.py mcp-stop first.")
        else:
            print(f"MCP not running. DB: {status['db_path']}")
            print("Enable MCP in Cursor to query, or use db.py run-sql directly.")
        return 0
    if args.command == "quack-info":
        return quack_info()
    if args.command == "quack-check":
        return quack_check()
    if args.command == "quack-serve":
        quack_serve()
        return 0
    if args.command == "quack-sql":
        if args.file:
            sql = Path(args.file).read_text()
        elif args.sql:
            sql = args.sql
        else:
            sql = sys.stdin.read()
        return quack_run_sql(sql)
    if args.command == "run-sql":
        if args.file:
            sql = Path(args.file).read_text()
        elif args.sql:
            sql = args.sql
        else:
            sql = sys.stdin.read()
        return cmd_run_sql(
            sql,
            for_ingest=args.ingest,
            attach_quack_remote=args.attach_quack,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
