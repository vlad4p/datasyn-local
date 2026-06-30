"""Shared helpers for SociaVault platform scrape scripts."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db
from sociavault_client import SociaVaultClient

PLATFORM_SQL = {
    "facebook": ("ingest_sociavault_facebook.sql", "ingest_sociavault_facebook_silver.sql"),
    "twitter": ("ingest_sociavault_twitter.sql", "ingest_sociavault_twitter_silver.sql"),
    "instagram": ("ingest_sociavault_instagram.sql", "ingest_sociavault_instagram_silver.sql"),
    "tiktok": ("ingest_sociavault_tiktok.sql", "ingest_sociavault_tiktok_silver.sql"),
}


def account_slug(value: str) -> str:
    """Derive filesystem-safe slug from URL or handle."""
    value = value.strip().rstrip("/")
    if value.startswith("@"):
        return re.sub(r"[^a-zA-Z0-9_-]", "_", value[1:]).lower()
    if "://" in value:
        path = urlparse(value).path.strip("/")
        if path:
            return re.sub(r"[^a-zA-Z0-9_-]", "_", path.split("/")[-1]).lower()
    return re.sub(r"[^a-zA-Z0-9_-]", "_", value).lower()


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def repo_relative(path: Path) -> str:
    return str(path.relative_to(repo_root()))


def sociavault_root(platform: str) -> Path:
    return db.get_landing_path() / "redes" / "sociavault" / platform


def make_run_dir(platform: str, slug: str) -> Path:
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    run_dir = sociavault_root(platform) / f"{slug}_{date}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_current_run(platform: str, paths: dict[str, str]) -> Path:
    """Pointer file for bronze SQL ingest (gitignored landing)."""
    meta_path = sociavault_root(platform) / "_current_run.json"
    write_json(meta_path, paths)
    return meta_path


def write_manifest(
    run_dir: Path,
    *,
    platform: str,
    account: str,
    client: SociaVaultClient,
    extra: dict[str, Any] | None = None,
) -> Path:
    manifest = {
        "platform": platform,
        "account": account,
        "run_dir": repo_relative(run_dir),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "credits_used": client.credits_used,
        "requests": client.requests,
        **(extra or {}),
    }
    path = run_dir / "manifest.json"
    write_json(path, manifest)
    return path


def run_ingest_sql(sql_file: str) -> int:
    """Execute bronze/silver SQL via db.py."""
    root = repo_root()
    sql_path = root / "scripts" / "sql" / sql_file
    if not sql_path.is_file():
        print(f"SQL file not found: {sql_path}", file=sys.stderr)
        return 1
    result = subprocess.run(
        ["uv", "run", "python", "scripts/python/db.py", "run-sql", "--file", str(sql_path)],
        cwd=root,
    )
    return result.returncode


def run_ingest_full(
    platform: str,
    *,
    classify: bool = True,
    classify_limit: int = 500,
) -> int:
    """Run bronze → silver → entities → optional LLM classification."""
    if platform not in PLATFORM_SQL:
        print(f"Unknown platform: {platform}", file=sys.stderr)
        return 1

    bronze_sql, silver_sql = PLATFORM_SQL[platform]
    steps = [
        bronze_sql,
        silver_sql,
        "ingest_sociavault_classification.sql",
        "ingest_sociavault_entities.sql",
    ]
    for sql_file in steps:
        rc = run_ingest_sql(sql_file)
        if rc != 0:
            return rc

    if classify:
        root = repo_root()
        cmd = [
            "uv",
            "run",
            "python",
            "scripts/python/classify_sv_comments.py",
            "--platform",
            platform,
            "--limit",
            str(classify_limit),
        ]
        result = subprocess.run(cmd, cwd=root)
        if result.returncode != 0:
            return result.returncode

    return 0


def write_selected_snapshot(
    run_dir: Path,
    *,
    limits: Any,
    pool: list[dict[str, Any]],
    selected: list[dict[str, Any]],
) -> Path:
    path = run_dir / "selected.json"
    write_json(
        path,
        {
            "last": limits.last,
            "api_pool_size": len(pool),
            "selected_count": len(selected),
            "items": selected,
        },
    )
    return path


def dig(data: Any, *keys: str, default: Any = None) -> Any:
    node = data
    for key in keys:
        if not isinstance(node, dict):
            return default
        node = node.get(key)
    return node if node is not None else default
