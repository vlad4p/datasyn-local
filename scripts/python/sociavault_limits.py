"""Count-based limits for SociaVault scrape scripts (last N items by publish time)."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from sociavault_client import SociaVaultClient
from sociavault_scrape_common import append_jsonl, dig

Platform = str  # facebook | twitter | instagram | tiktok


@dataclass(frozen=True)
class ScrapeLimits:
    """How many most-recent items to keep after sorting by publish time."""

    last: int

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> ScrapeLimits:
        n = getattr(args, "last", None)
        alias = (
            getattr(args, "max_posts", None)
            or getattr(args, "max_tweets", None)
            or getattr(args, "max_videos", None)
        )
        if alias is not None:
            n = alias
        if n is None:
            n = 10
        if n < 1:
            raise ValueError("--last must be >= 1")
        return cls(last=n)

    def to_manifest_dict(self) -> dict[str, Any]:
        return {"last": self.last}


def add_limit_args(parser: argparse.ArgumentParser, *, alias_flag: str = "max-posts") -> None:
    """Add --last and optional platform alias (--max-posts, --max-tweets, --max-videos)."""
    parser.add_argument(
        "--last",
        type=int,
        default=None,
        help="Number of most recent posts/tweets/videos to keep (default: 10)",
    )
    if alias_flag == "max-videos":
        parser.add_argument("--max-videos", type=int, default=None, help="Alias for --last")
    elif alias_flag == "max-tweets":
        parser.add_argument("--max-tweets", type=int, default=None, help="Alias for --last")
    else:
        parser.add_argument("--max-posts", type=int, default=None, help="Alias for --last")


def _ensure_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _parse_unix(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        n = int(float(str(value)))
        if n > 1_000_000_000_000:
            n = n // 1000
        return datetime.fromtimestamp(n, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return _ensure_utc(datetime.fromisoformat(text))
    except ValueError:
        pass
    try:
        return _ensure_utc(parsedate_to_datetime(text))
    except (TypeError, ValueError):
        return None


def parse_item_timestamp(platform: Platform, item: dict[str, Any]) -> datetime | None:
    """Extract publish time from a post/tweet/video dict."""
    if not isinstance(item, dict):
        return None

    if platform == "facebook":
        for key in ("publishTime", "created_time", "createdAt", "timestamp"):
            ts = _parse_unix(item.get(key))
            if ts:
                return ts

    elif platform == "twitter":
        legacy = item.get("legacy") or {}
        ts = _parse_iso(legacy.get("created_at") or item.get("created_at"))
        if ts:
            return ts

    elif platform == "instagram":
        for key in ("taken_at", "taken_at_timestamp", "created_at", "timestamp"):
            raw = item.get(key)
            ts = _parse_unix(raw) or _parse_iso(raw)
            if ts:
                return ts
        caption = item.get("caption")
        if isinstance(caption, dict):
            ts = _parse_unix(caption.get("created_at"))
            if ts:
                return ts

    elif platform == "tiktok":
        for key in ("createTime", "create_time", "created_at"):
            ts = _parse_unix(item.get(key))
            if ts:
                return ts

    return None


def item_dedupe_key(platform: Platform, item: dict[str, Any]) -> str | None:
    """Stable ID for deduplication across paginated pages."""
    if not isinstance(item, dict):
        return None
    if platform == "twitter":
        tid = item.get("rest_id") or dig(item, "legacy", "id_str") or item.get("id_str")
        return str(tid) if tid is not None else None
    if platform == "instagram":
        pid = item.get("id") or item.get("pk") or item.get("code")
        return str(pid) if pid is not None else None
    if platform == "tiktok":
        vid = item.get("id") or item.get("video_id") or item.get("aweme_id")
        return str(vid) if vid is not None else None
    pid = item.get("id") or item.get("post_id") or item.get("postId")
    return str(pid) if pid is not None else None


def dedupe_items(items: list[dict[str, Any]], platform: Platform) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        key = item_dedupe_key(platform, item)
        if key is None:
            out.append(item)
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def select_most_recent(
    items: list[dict[str, Any]], platform: Platform, n: int
) -> list[dict[str, Any]]:
    """Sort by publish time DESC; items without timestamp go last; take first n."""
    unique = dedupe_items(items, platform)

    def sort_key(item: dict[str, Any]) -> tuple[int, float]:
        ts = parse_item_timestamp(platform, item)
        if ts is None:
            return (1, 0.0)
        return (0, -ts.timestamp())

    ranked = sorted(unique, key=sort_key)
    return ranked[:n]


def extract_posts_from_page(page: dict[str, Any], platform: Platform) -> list[dict[str, Any]]:
    """Normalize posts/tweets/videos list from an API page response."""
    if platform == "twitter":
        raw = dig(page, "data", "tweets") or dig(page, "data", "data", "tweets") or {}
        if isinstance(raw, dict):
            return [v for v in raw.values() if isinstance(v, dict)]
        if isinstance(raw, list):
            return [v for v in raw if isinstance(v, dict)]
        return []

    key = "posts" if platform != "tiktok" else "videos"
    raw = (
        dig(page, "data", key)
        or dig(page, "data", "data", key)
        or dig(page, "data", "items")
        or []
    )
    if isinstance(raw, dict):
        return [v for v in raw.values() if isinstance(v, dict)]
    if isinstance(raw, list):
        return [v for v in raw if isinstance(v, dict)]
    return []


def page_cursor(page: dict[str, Any]) -> str | None:
    return dig(page, "data", "cursor") or dig(page, "data", "nextCursor")


def paginate_collect_items(
    client: SociaVaultClient,
    *,
    platform: Platform,
    resource: str,
    base_params: dict[str, Any],
    raw_path: Path,
) -> list[dict[str, Any]]:
    """Fetch all pages from an endpoint; append raw pages to raw_path."""
    all_items: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        params = dict(base_params)
        if cursor:
            params["cursor"] = cursor
        page = client.scrape(platform, resource, params)
        append_jsonl(raw_path, page)
        all_items.extend(extract_posts_from_page(page, platform))
        cursor = page_cursor(page)
        if not cursor:
            break
    return all_items
