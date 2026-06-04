"""DuckDB connection and path helpers for datasyn-local."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import duckdb
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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


def get_logs_path() -> Path:
    return _path_from_settings(
        "DATASYN_LOGS_PATH",
        ("paths", "logs"),
        ".logs",
    )


def validate_table_name(name: str) -> str:
    """Allow only simple SQL identifiers (prevents injection via table names)."""
    if not _TABLE_NAME_RE.fullmatch(name):
        raise ValueError(
            f"Invalid table name {name!r}. Use letters, digits, underscore; must start with letter or _."
        )
    return name


def quote_identifier(name: str) -> str:
    """Return a double-quoted DuckDB identifier after validation."""
    validate_table_name(name)
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def resolve_landing_file(file_path: Path) -> Path:
    """Resolve a path that must exist and lie under the landing directory."""
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
    """Open a persistent DuckDB connection, creating directories as needed."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    get_landing_path().mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path), read_only=read_only)


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
