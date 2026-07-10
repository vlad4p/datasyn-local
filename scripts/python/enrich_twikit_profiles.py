"""Enrich top hater (or listed) X profiles via twikit.

Fetches full profile (bio + metrics), recent posts, and follower/following
lists with conservative rate-limiting to reduce ban risk.

Usage:
    uv run python scripts/python/enrich_twikit_profiles.py --top-haters 10 \\
      --max-posts 100 --max-follows 2000 --ingest

    uv run python scripts/python/enrich_twikit_profiles.py \\
      --handles capibara_mood,CCDeville88 --ingest
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402
from scrape_twikit_twitter import (  # noqa: E402
    DEFAULT_COOKIES,
    TwikitScrapeError,
    _login_client,
    _tweet_to_dict,
    _user_to_dict,
    account_slug,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_MIN_DELAY_S = 3.0
DEFAULT_JITTER_S = 2.0
DEFAULT_PROFILE_PAUSE_S = 35.0
DEFAULT_MAX_POSTS = 100
DEFAULT_MAX_FOLLOWS = 2000
RATE_LIMIT_BUFFER_S = 10.0


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n")


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def _write_jsonl_marker(path: Path) -> None:
    """Non-empty placeholder so DuckDB can read the file; filtered out on ingest."""
    path.write_text(json.dumps({"_empty": True}) + "\n")


def _repo_relative(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _profile_complete(run_dir: Path) -> bool:
    required = (
        "profile.json",
        "posts.jsonl",
        "followers.jsonl",
        "following.jsonl",
        "manifest.json",
    )
    return all((run_dir / name).is_file() for name in required)


def _make_run_dir(slug: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    run_dir = db.get_landing_path() / "redes" / "twikit" / "profiles" / f"{slug}_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


async def _rate_sleep(min_delay: float, jitter: float) -> None:
    await asyncio.sleep(min_delay + random.uniform(0, jitter))


async def _wait_rate_limit(exc: Exception) -> None:
    reset = getattr(exc, "rate_limit_reset", None)
    now = time.time()
    if reset is not None:
        wait = max(0.0, float(reset) - now) + RATE_LIMIT_BUFFER_S
    else:
        wait = 60.0 + RATE_LIMIT_BUFFER_S
    print(f"  rate-limit hit; sleeping {wait:.0f}s…")
    await asyncio.sleep(wait)


async def _call_with_retry(coro_factory, *, min_delay: float, jitter: float, label: str):
    from twikit.errors import TooManyRequests

    for attempt in range(1, 6):
        await _rate_sleep(min_delay, jitter)
        try:
            return await coro_factory()
        except TooManyRequests as exc:
            print(f"  {label}: TooManyRequests (attempt {attempt})")
            await _wait_rate_limit(exc)
        except Exception as exc:
            if attempt >= 5:
                raise
            print(f"  {label}: {exc} (attempt {attempt}); retrying…")
            await asyncio.sleep(5 * attempt)
    raise TwikitScrapeError(f"Failed after retries: {label}")


def _load_top_haters(n: int) -> list[str]:
    con = db.connect(read_only=True)
    try:
        rows = con.execute(
            """
            SELECT username
            FROM silver.tk_tw_user
            WHERE is_hater
              AND username IS NOT NULL
              AND LENGTH(TRIM(username)) > 0
            ORDER BY hater_replies_count DESC NULLS LAST,
                     replies_observed_count DESC NULLS LAST
            LIMIT ?
            """,
            [n],
        ).fetchall()
    finally:
        con.close()
    return [str(r[0]).lstrip("@") for r in rows]


async def _safe_user_tweets_page(
    client: Any,
    user_id: str,
    tweet_type: str,
    count: int,
    cursor: str | None,
) -> tuple[list[Any], str | None]:
    """Parse user timeline without twikit's brittle cursor KeyError('value')."""
    from twikit.tweet import tweet_from_data
    from twikit.utils import find_dict

    tweet_type = tweet_type.capitalize()
    gql = {
        "Tweets": client.gql.user_tweets,
        "Replies": client.gql.user_tweets_and_replies,
        "Media": client.gql.user_media,
        "Likes": client.gql.user_likes,
    }[tweet_type]
    response, _ = await gql(user_id, count, cursor)
    instructions_ = find_dict(response, "instructions", True)
    if not instructions_:
        return [], None
    instructions = instructions_[0]
    items = instructions[-1]["entries"]
    if tweet_type == "Media" and cursor is None and items:
        nested = items[0].get("content", {}).get("items")
        if nested:
            items = nested
        else:
            module_items = instructions[0].get("moduleItems") if instructions else None
            if module_items:
                items = module_items

    next_cursor: str | None = None
    for item in reversed(items if isinstance(items, list) else []):
        content = item.get("content", {})
        entry_id = str(item.get("entryId", ""))
        if "value" not in content:
            continue
        if entry_id.startswith("cursor-bottom") or content.get("cursorType") == "Bottom":
            next_cursor = content["value"]
            break

    results: list[Any] = []
    for item in items if isinstance(items, list) else []:
        entry_id = str(item.get("entryId", ""))
        if not entry_id.startswith(("tweet", "profile-conversation", "profile-grid")):
            continue
        if entry_id.startswith("profile-conversation"):
            tweets = item.get("content", {}).get("items") or []
            if not tweets:
                continue
            item = tweets[0]
        tweet = tweet_from_data(client, item)
        if tweet is not None:
            results.append(tweet)
    return results, next_cursor


async def _fetch_posts(
    client: Any,
    user_id: str,
    *,
    max_posts: int,
    min_delay: float,
    jitter: float,
) -> list[dict[str, Any]]:
    """Fetch recent posts; fall back Tweets → Media if timeline is empty/broken."""
    collected: list[dict[str, Any]] = []
    seen: set[str] = set()

    async def _absorb(tweet_type: str) -> None:
        nonlocal collected
        cursor: str | None = None
        pages = 0
        while len(collected) < max_posts and pages < 20:
            tweets, cursor = await _call_with_retry(
                lambda c=cursor, tt=tweet_type: _safe_user_tweets_page(
                    client, user_id, tt, 40, c
                ),
                min_delay=min_delay,
                jitter=jitter,
                label=f"tweets:{tweet_type}:{user_id}",
            )
            pages += 1
            if not tweets:
                break
            for tweet in tweets:
                row = _tweet_to_dict(tweet)
                tid = str(row.get("id") or "")
                if not tid or tid in seen:
                    continue
                seen.add(tid)
                collected.append(row)
                if len(collected) >= max_posts:
                    break
            if not cursor:
                break

    await _absorb("Tweets")
    if not collected:
        print("  Tweets empty/broken; trying Media…")
        await _absorb("Media")
    return collected[:max_posts]


async def _fetch_user_list(
    client: Any,
    user_id: str,
    *,
    direction: str,
    max_follows: int,
    expected_count: int | None,
    min_delay: float,
    jitter: float,
) -> tuple[list[dict[str, Any]], str]:
    """Return (users_or_ids, mode) where mode is 'users' or 'ids'."""
    if expected_count is not None and expected_count > max_follows:
        print(
            f"  {direction}: count={expected_count} > max_follows={max_follows}; "
            "falling back to IDs-only"
        )
        return await _fetch_follower_ids(
            client,
            user_id,
            max_follows=max_follows,
            min_delay=min_delay,
            jitter=jitter,
        ), "ids"

    method = (
        client.get_user_followers
        if direction == "followers"
        else client.get_user_following
    )
    collected: list[dict[str, Any]] = []
    seen: set[str] = set()
    result = await _call_with_retry(
        lambda: method(user_id, count=100),
        min_delay=min_delay,
        jitter=jitter,
        label=f"{direction}:{user_id}",
    )
    while result and len(collected) < max_follows:
        for user in result:
            row = _user_to_dict(user)
            uid = str(row.get("id") or "")
            if not uid or uid in seen:
                continue
            seen.add(uid)
            collected.append(row)
            if len(collected) >= max_follows:
                break
        if len(collected) >= max_follows:
            break
        try:
            result = await _call_with_retry(
                lambda r=result: r.next(),
                min_delay=min_delay,
                jitter=jitter,
                label=f"{direction}-next:{user_id}",
            )
        except Exception as exc:
            print(f"  {direction} pagination stopped: {exc}")
            break
        if not result:
            break
    return collected[:max_follows], "users"


async def _fetch_follower_ids(
    client: Any,
    user_id: str,
    *,
    max_follows: int,
    min_delay: float,
    jitter: float,
) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    seen: set[str] = set()
    result = await _call_with_retry(
        lambda: client.get_followers_ids(user_id=user_id, count=min(5000, max_follows)),
        min_delay=min_delay,
        jitter=jitter,
        label=f"follower-ids:{user_id}",
    )
    while result and len(collected) < max_follows:
        for uid in result:
            sid = str(uid)
            if not sid or sid in seen:
                continue
            seen.add(sid)
            collected.append({"id": sid})
            if len(collected) >= max_follows:
                break
        if len(collected) >= max_follows:
            break
        try:
            result = await _call_with_retry(
                lambda r=result: r.next(),
                min_delay=min_delay,
                jitter=jitter,
                label=f"follower-ids-next:{user_id}",
            )
        except Exception as exc:
            print(f"  follower-ids pagination stopped: {exc}")
            break
        if not result:
            break
    return collected[:max_follows]


async def enrich_one(
    client: Any,
    handle: str,
    *,
    max_posts: int,
    max_follows: int,
    min_delay: float,
    jitter: float,
) -> Path:
    handle = handle.lstrip("@")
    slug = account_slug(handle)
    run_dir = _make_run_dir(slug)

    if _profile_complete(run_dir):
        print(f"Checkpoint skip @{handle} → {run_dir} (already complete)")
        return run_dir

    print(f"=== Enriching @{handle} ===")
    user = await _call_with_retry(
        lambda: client.get_user_by_screen_name(handle),
        min_delay=min_delay,
        jitter=jitter,
        label=f"profile:{handle}",
    )
    profile = _user_to_dict(user)
    profile["scraped_handle"] = handle
    profile["scraped_at"] = datetime.now(timezone.utc).isoformat()
    profile["is_protected"] = getattr(user, "protected", None) or getattr(
        user, "is_protected", None
    )
    _write_json(run_dir / "profile.json", profile)
    user_id = str(getattr(user, "id", "") or "")
    print(
        f"  profile id={user_id} followers={profile.get('followers_count')} "
        f"following={profile.get('following_count')}"
    )

    posts = await _fetch_posts(
        client,
        user_id,
        max_posts=max_posts,
        min_delay=min_delay,
        jitter=jitter,
    )
    posts_path = run_dir / "posts.jsonl"
    if posts_path.exists():
        posts_path.unlink()
    for row in posts:
        _append_jsonl(posts_path, row)
    print(f"  posts: {len(posts)}")

    followers_path = run_dir / "followers.jsonl"
    following_path = run_dir / "following.jsonl"
    if followers_path.exists():
        followers_path.unlink()
    if following_path.exists():
        following_path.unlink()

    is_protected = bool(profile.get("is_protected"))
    followers: list[dict[str, Any]] = []
    following: list[dict[str, Any]] = []
    followers_mode = "skipped"
    following_mode = "skipped"

    if is_protected:
        print("  protected account — skipping follower/following lists")
    else:
        fo_count = int(profile.get("followers_count") or 0)
        fl_count = int(profile.get("following_count") or 0)
        following, following_mode = await _fetch_user_list(
            client,
            user_id,
            direction="following",
            max_follows=max_follows,
            expected_count=fl_count,
            min_delay=min_delay,
            jitter=jitter,
        )
        followers, followers_mode = await _fetch_user_list(
            client,
            user_id,
            direction="followers",
            max_follows=max_follows,
            expected_count=fo_count,
            min_delay=min_delay,
            jitter=jitter,
        )

    for row in followers:
        _append_jsonl(followers_path, row)
    for row in following:
        _append_jsonl(following_path, row)
    # DuckDB read_json_auto fails on empty files — write a skip marker.
    if not followers_path.exists() or followers_path.stat().st_size == 0:
        _write_jsonl_marker(followers_path)
    if not following_path.exists() or following_path.stat().st_size == 0:
        _write_jsonl_marker(following_path)
    if not posts_path.exists() or posts_path.stat().st_size == 0:
        _write_jsonl_marker(posts_path)

    print(
        f"  followers={len(followers)} ({followers_mode}) "
        f"following={len(following)} ({following_mode})"
    )

    _write_json(
        run_dir / "manifest.json",
        {
            "source": "twikit",
            "platform": "twitter",
            "kind": "profile_enrich",
            "account": handle,
            "user_id": user_id,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "max_posts": max_posts,
            "max_follows": max_follows,
            "posts_count": len(posts),
            "followers_count_scraped": len(followers),
            "following_count_scraped": len(following),
            "followers_mode": followers_mode,
            "following_mode": following_mode,
            "is_protected": is_protected,
            "landing": _repo_relative(run_dir),
        },
    )
    return run_dir


def _run_ingest(run_dirs: list[Path]) -> None:
    """Write batch pointer + run ingest SQL via db.cmd_run_sql."""
    root = db.get_landing_path() / "redes" / "twikit" / "profiles"
    root.mkdir(parents=True, exist_ok=True)
    pointer = {
        "run_dirs": [_repo_relative(p) for p in run_dirs],
        "profiles_glob": _repo_relative(root / "*" / "profile.json"),
        "posts_glob": _repo_relative(root / "*" / "posts.jsonl"),
        "followers_glob": _repo_relative(root / "*" / "followers.jsonl"),
        "following_glob": _repo_relative(root / "*" / "following.jsonl"),
        "manifests_glob": _repo_relative(root / "*" / "manifest.json"),
    }
    _write_json(root / "_current_batch.json", pointer)

    sql_path = REPO_ROOT / "scripts" / "sql" / "ingest_twikit_profiles.sql"
    sql = sql_path.read_text()
    for key, value in pointer.items():
        if isinstance(value, list):
            continue
        sql = sql.replace(f"{{{{{key}}}}}", str(value).replace("'", "''"))
    if "{{" in sql:
        missing = re.findall(r"\{\{(\w+)\}\}", sql)
        raise TwikitScrapeError(f"Unresolved SQL tokens: {', '.join(missing)}")

    print("Ingest ingest_twikit_profiles.sql…")
    con = db.connect_for_ingest(release_mcp=True)
    try:
        for stmt in _split_sql(sql):
            con.execute(stmt)
        print("  OK ingest_twikit_profiles.sql")
    finally:
        con.close()


def _split_sql(sql: str) -> list[str]:
    """Split SQL into statements; strip full-line comments; keep non-empty."""
    lines: list[str] = []
    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    parts: list[str] = []
    buf: list[str] = []
    in_single = False
    for ch in cleaned:
        if ch == "'" and not in_single:
            in_single = True
            buf.append(ch)
        elif ch == "'" and in_single:
            in_single = False
            buf.append(ch)
        elif ch == ";" and not in_single:
            stmt = "".join(buf).strip()
            if stmt:
                parts.append(stmt)
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


async def enrich_profiles(
    *,
    handles: list[str],
    max_posts: int,
    max_follows: int,
    min_delay: float,
    jitter: float,
    profile_pause: float,
    cookies_path: Path,
    ingest: bool,
) -> list[Path]:
    client = await _login_client(cookies_path)
    run_dirs: list[Path] = []
    for i, handle in enumerate(handles):
        run_dir = await enrich_one(
            client,
            handle,
            max_posts=max_posts,
            max_follows=max_follows,
            min_delay=min_delay,
            jitter=jitter,
        )
        run_dirs.append(run_dir)
        if i < len(handles) - 1:
            print(f"Profile pause {profile_pause:.0f}s…")
            await asyncio.sleep(profile_pause)

    cookies_out = Path(os.getenv("TWITTER_COOKIES_PATH", str(DEFAULT_COOKIES))).expanduser()
    cookies_out.parent.mkdir(parents=True, exist_ok=True)
    try:
        client.save_cookies(str(cookies_out))
    except Exception:
        pass

    if ingest and run_dirs:
        _run_ingest(run_dirs)
    return run_dirs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enrich X profiles (bio, metrics, posts, followers/following) via twikit"
    )
    parser.add_argument(
        "--top-haters",
        type=int,
        default=None,
        help="Take top N haters from silver.tk_tw_user by hater_replies_count",
    )
    parser.add_argument(
        "--handles",
        type=str,
        default=None,
        help="Comma-separated handles (overrides --top-haters)",
    )
    parser.add_argument("--max-posts", type=int, default=DEFAULT_MAX_POSTS)
    parser.add_argument("--max-follows", type=int, default=DEFAULT_MAX_FOLLOWS)
    parser.add_argument("--min-delay", type=float, default=DEFAULT_MIN_DELAY_S)
    parser.add_argument("--jitter", type=float, default=DEFAULT_JITTER_S)
    parser.add_argument("--profile-pause", type=float, default=DEFAULT_PROFILE_PAUSE_S)
    parser.add_argument(
        "--cookies",
        type=Path,
        default=None,
        help=f"Cookies JSON (default: TWITTER_COOKIES_PATH or {DEFAULT_COOKIES})",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Ingest landing → bronze/silver after scrape",
    )
    args = parser.parse_args()

    if args.max_posts < 1 or args.max_follows < 1:
        print("--max-posts and --max-follows must be >= 1", file=sys.stderr)
        return 1
    if args.min_delay < 0 or args.profile_pause < 0:
        print("delays must be >= 0", file=sys.stderr)
        return 1

    if args.handles:
        handles = [h.strip().lstrip("@") for h in args.handles.split(",") if h.strip()]
    elif args.top_haters is not None:
        if args.top_haters < 1:
            print("--top-haters must be >= 1", file=sys.stderr)
            return 1
        handles = _load_top_haters(args.top_haters)
        print(f"Top {args.top_haters} haters: {', '.join(handles)}")
    else:
        print("Provide --top-haters N or --handles a,b,c", file=sys.stderr)
        return 1

    if not handles:
        print("No handles to enrich", file=sys.stderr)
        return 1

    load_dotenv(REPO_ROOT / ".env")
    cookies_path = args.cookies or Path(
        os.getenv("TWITTER_COOKIES_PATH", str(DEFAULT_COOKIES))
    )

    try:
        run_dirs = asyncio.run(
            enrich_profiles(
                handles=handles,
                max_posts=args.max_posts,
                max_follows=args.max_follows,
                min_delay=args.min_delay,
                jitter=args.jitter,
                profile_pause=args.profile_pause,
                cookies_path=cookies_path,
                ingest=args.ingest,
            )
        )
        for d in run_dirs:
            print(f"Saved {d}")
        return 0
    except TwikitScrapeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
