"""DuckDB connection and path helpers for datasyn-local."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import duckdb
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "duckdb" / "datasyn.duckdb"
DEFAULT_LANDING = PROJECT_ROOT / "data" / "landing"


def load_settings() -> dict[str, Any]:
    settings_path = PROJECT_ROOT / "config" / "settings.yaml"
    if not settings_path.exists():
        return {}
    with settings_path.open() as f:
        return yaml.safe_load(f) or {}


def get_db_path() -> Path:
    env_path = os.getenv("DATASYN_DB_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()
    settings = load_settings()
    rel = settings.get("database", {}).get("path", "data/duckdb/datasyn.duckdb")
    return (PROJECT_ROOT / rel).resolve()


def get_landing_path() -> Path:
    env_path = os.getenv("DATASYN_LANDING_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()
    settings = load_settings()
    rel = settings.get("paths", {}).get("landing", "data/landing")
    return (PROJECT_ROOT / rel).resolve()


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
