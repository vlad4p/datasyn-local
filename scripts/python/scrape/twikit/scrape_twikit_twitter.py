"""Scrape a public X/Twitter account via twikit → data/landing/redes/twikit/twitter/.

Auth: TWITTER_USERNAME / TWITTER_EMAIL / TWITTER_PASSWORD in .env, or cookies file
(TWITTER_COOKIES_PATH, default .data/twikit_cookies.json — gitignored).

Usage:
    # All posts in July 2026 + top ~100 replies (Semaphore 3) + ingest
    uv run python scripts/python/scrape/twikit/scrape_twikit_twitter.py \\
        --handle myriambregman \\
        --since 2026-07-01 --until 2026-08-01 \\
        --fetch-replies --max-replies 100 --concurrency 3 \\
        --ingest

Docs: https://twikit.readthedocs.io/en/latest/twikit.html
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import db  # noqa: E402

REPO_ROOT = db.PROJECT_ROOT
DEFAULT_COOKIES = REPO_ROOT / ".data" / "twikit_cookies.json"
RATE_SLEEP_S = 1.2
RATE_JITTER_S = 0.4
DEFAULT_CONCURRENCY = 3
DEFAULT_MAX_REPLIES = 100


class TwikitScrapeError(Exception):
    """Scrape or auth failure."""


def account_slug(value: str) -> str:
    value = value.strip().lstrip("@").rstrip("/")
    return re.sub(r"[^a-zA-Z0-9_-]", "_", value).lower()


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n")


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


async def _rate_sleep(mult: float = 1.0) -> None:
    await asyncio.sleep(RATE_SLEEP_S * mult + random.uniform(0, RATE_JITTER_S))


def _parse_day(value: str) -> date:
    return date.fromisoformat(value)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _tweet_day(tweet: Any) -> date | None:
    dt = _aware(getattr(tweet, "created_at_datetime", None))
    return dt.date() if dt else None


def _user_to_dict(user: Any) -> dict[str, Any]:
    if user is None:
        return {}
    return {
        "id": getattr(user, "id", None),
        "screen_name": getattr(user, "screen_name", None),
        "name": getattr(user, "name", None),
        "description": getattr(user, "description", None),
        "location": getattr(user, "location", None),
        "followers_count": getattr(user, "followers_count", None),
        "following_count": getattr(user, "following_count", None)
        or getattr(user, "friends_count", None),
        "statuses_count": getattr(user, "statuses_count", None),
        "favourites_count": getattr(user, "favourites_count", None),
        "listed_count": getattr(user, "listed_count", None),
        "created_at": getattr(user, "created_at", None),
        "verified": getattr(user, "verified", None),
        "is_blue_verified": getattr(user, "is_blue_verified", None),
        "profile_image_url": getattr(user, "profile_image_url", None)
        or getattr(user, "profile_image_url_https", None),
        "url": getattr(user, "url", None),
    }


def _safe_list_attr(obj: Any, name: str) -> list[Any]:
    try:
        val = getattr(obj, name, None)
        return list(val) if val else []
    except Exception:
        return []


def _tweet_to_dict(tweet: Any, *, include_user: bool = True) -> dict[str, Any]:
    if tweet is None:
        return {}
    user = getattr(tweet, "user", None)
    created_dt = _aware(getattr(tweet, "created_at_datetime", None))
    row: dict[str, Any] = {
        "id": getattr(tweet, "id", None),
        "text": getattr(tweet, "text", None),
        "lang": getattr(tweet, "lang", None),
        "created_at": getattr(tweet, "created_at", None),
        "created_at_iso": created_dt.isoformat() if created_dt else None,
        "in_reply_to": getattr(tweet, "in_reply_to", None),
        "is_quote_status": getattr(tweet, "is_quote_status", None),
        "reply_count": getattr(tweet, "reply_count", None),
        "favorite_count": getattr(tweet, "favorite_count", None),
        "retweet_count": getattr(tweet, "retweet_count", None),
        "quote_count": getattr(tweet, "quote_count", None),
        "view_count": getattr(tweet, "view_count", None),
        "bookmark_count": getattr(tweet, "bookmark_count", None),
        "hashtags": _safe_list_attr(tweet, "hashtags"),
        "urls": _safe_list_attr(tweet, "urls"),
        "possibly_sensitive": getattr(tweet, "possibly_sensitive", None),
    }
    if include_user and user is not None:
        row["user"] = {
            "id": getattr(user, "id", None),
            "screen_name": getattr(user, "screen_name", None),
            "name": getattr(user, "name", None),
        }
    quote = getattr(tweet, "quote", None)
    if quote is not None:
        row["quote_id"] = getattr(quote, "id", None)
    rt = getattr(tweet, "retweeted_tweet", None)
    if rt is not None:
        row["retweeted_tweet_id"] = getattr(rt, "id", None)
    media = getattr(tweet, "media", None) or []
    if media:
        row["media_count"] = len(media)
        row["media_types"] = [type(m).__name__ for m in media]
    return row


def _tweet_sort_key(tweet: Any) -> datetime:
    dt = _aware(getattr(tweet, "created_at_datetime", None))
    return dt or datetime.min.replace(tzinfo=timezone.utc)


def _make_run_dir(slug: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    run_dir = db.get_landing_path() / "redes" / "twikit" / "twitter" / f"{slug}_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _repo_relative(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


async def _login_client(cookies_path: Path):
    from twikit import Client

    load_dotenv(REPO_ROOT / ".env")
    client = Client("en-US")
    cookies_path = cookies_path.expanduser()
    if cookies_path.is_file():
        client.load_cookies(str(cookies_path))
        print(f"Loaded cookies from {cookies_path}")
        return client

    username = os.getenv("TWITTER_USERNAME") or os.getenv("TWITTER_AUTH_INFO_1")
    email = os.getenv("TWITTER_EMAIL") or os.getenv("TWITTER_AUTH_INFO_2")
    password = os.getenv("TWITTER_PASSWORD")
    totp = os.getenv("TWITTER_TOTP_SECRET")
    if not username or not password:
        raise TwikitScrapeError(
            "No cookies and missing TWITTER_USERNAME / TWITTER_PASSWORD in .env. "
            f"Expected cookies at {cookies_path} or credentials in .env "
            "(see .env.example)."
        )

    cookies_path.parent.mkdir(parents=True, exist_ok=True)
    print("Logging in to X via twikit…")
    await client.login(
        auth_info_1=username,
        auth_info_2=email,
        password=password,
        totp_secret=totp,
        cookies_file=str(cookies_path),
        enable_ui_metrics=False,
    )
    print(f"Login OK — cookies saved to {cookies_path}")
    return client


async def _collect_by_search(
    client: Any,
    handle: str,
    since: date,
    until: date,
) -> list[Any]:
    """Collect tweets with X search: from:handle since: until: (until exclusive)."""
    query = f"from:{handle} since:{since.isoformat()} until:{until.isoformat()}"
    print(f"Search: {query}")
    collected: list[Any] = []
    seen: set[str] = set()
    result = await client.search_tweet(query, "Latest", count=20)
    pages = 0
    while result:
        pages += 1
        batch_n = 0
        for tweet in result:
            tid = str(getattr(tweet, "id", "") or "")
            if not tid or tid in seen:
                continue
            day = _tweet_day(tweet)
            if day is not None and (day < since or day >= until):
                continue
            seen.add(tid)
            collected.append(tweet)
            batch_n += 1
        print(f"  search page {pages}: +{batch_n} (total {len(collected)})")
        await _rate_sleep()
        try:
            result = await result.next()
        except Exception as exc:
            print(f"  search pagination stopped: {exc}")
            break
        if not result:
            break
    collected.sort(key=_tweet_sort_key, reverse=True)
    return collected


async def _collect_by_timeline(
    client: Any,
    user_id: str,
    since: date | None,
    until: date | None,
    last: int | None,
    tweet_type: str,
) -> list[Any]:
    """Paginate user timeline; optional date window and/or last N."""
    collected: list[Any] = []
    seen: set[str] = set()
    result = await client.get_user_tweets(user_id, tweet_type, count=40)
    pages = 0
    stop = False
    while result and not stop:
        pages += 1
        batch_n = 0
        oldest_in_page: date | None = None
        for tweet in result:
            tid = str(getattr(tweet, "id", "") or "")
            if not tid or tid in seen:
                continue
            day = _tweet_day(tweet)
            if day is not None:
                oldest_in_page = day if oldest_in_page is None else min(oldest_in_page, day)
                if until is not None and day >= until:
                    continue
                if since is not None and day < since:
                    continue
            seen.add(tid)
            collected.append(tweet)
            batch_n += 1
            if last is not None and len(collected) >= last:
                stop = True
                break
        print(f"  timeline page {pages}: +{batch_n} (total {len(collected)})")
        if since is not None and oldest_in_page is not None and oldest_in_page < since:
            print("  reached tweets older than --since; stopping")
            break
        if stop:
            break
        await _rate_sleep()
        try:
            result = await result.next()
        except Exception as exc:
            print(f"  timeline pagination stopped: {exc}")
            break
        if not result:
            break
    collected.sort(key=_tweet_sort_key, reverse=True)
    if last is not None:
        collected = collected[:last]
    return collected


async def _fetch_replies_for_tweet(
    client: Any,
    tweet_id: str,
    replies_path: Path,
    *,
    max_replies: int,
    sem: asyncio.Semaphore,
) -> dict[str, Any]:
    """Fetch up to max_replies, keep top by favorite_count, write JSONL page."""
    async with sem:
        if replies_path.exists():
            replies_path.unlink()
        all_replies: list[dict[str, Any]] = []
        seen: set[str] = set()
        pages = 0

        def _absorb(tweet_obj: Any) -> None:
            if tweet_obj is None:
                return
            row = _tweet_to_dict(tweet_obj)
            rid = str(row.get("id") or "")
            if rid and rid != tweet_id and rid not in seen:
                seen.add(rid)
                all_replies.append(row)
            nested = getattr(tweet_obj, "replies", None)
            if nested:
                for child in nested:
                    _absorb(child)

        try:
            await _rate_sleep()
            tweet = await client.get_tweet_by_id(tweet_id)
        except Exception as exc:
            _append_jsonl(
                replies_path,
                {"error": str(exc), "tweet_id": tweet_id, "page": 0},
            )
            return {
                "tweet_id": tweet_id,
                "reply_pages_fetched": 0,
                "replies_collected": 0,
                "replies_kept": 0,
                "error": str(exc),
            }

        replies = getattr(tweet, "replies", None)
        while replies and len(all_replies) < max_replies * 2:
            for r in replies:
                _absorb(r)
            pages += 1
            if len(all_replies) >= max_replies * 2:
                break
            await _rate_sleep()
            try:
                replies = await replies.next()
            except Exception:
                break
            if not replies:
                break

        all_replies.sort(
            key=lambda r: (
                int(r.get("favorite_count") or 0),
                int(r.get("reply_count") or 0),
            ),
            reverse=True,
        )
        kept = all_replies[:max_replies]
        _append_jsonl(
            replies_path,
            {
                "tweet_id": tweet_id,
                "page": 0,
                "count": len(kept),
                "collected_before_rank": len(all_replies),
                "replies": kept,
            },
        )
        print(
            f"  replies {tweet_id}: collected={len(all_replies)} kept={len(kept)} pages={pages}"
        )
        return {
            "tweet_id": tweet_id,
            "reply_pages_fetched": pages,
            "replies_collected": len(all_replies),
            "replies_kept": len(kept),
            "reply_count": getattr(tweet, "reply_count", None),
        }


def _run_ingest(run_dir: Path) -> int:
    """Write pointer + run bronze/silver SQL via db.py."""
    pointer = {
        "run_dir": _repo_relative(run_dir),
        "profile_path": _repo_relative(run_dir / "profile.json"),
        "tweets_path": _repo_relative(run_dir / "tweets.jsonl"),
        "selected_path": _repo_relative(run_dir / "selected.json"),
        "replies_glob": _repo_relative(run_dir / "replies_*.jsonl"),
        "manifest_path": _repo_relative(run_dir / "manifest.json"),
    }
    root = db.get_landing_path() / "redes" / "twikit" / "twitter"
    root.mkdir(parents=True, exist_ok=True)
    _write_json(root / "_current_run.json", pointer)

    for sql_file in ("ingest_twikit_twitter.sql", "ingest_twikit_twitter_silver.sql"):
        sql_path = db.resolve_sql(sql_file)
        sql = sql_path.read_text()
        for key, value in pointer.items():
            sql = sql.replace(f"{{{{{key}}}}}", value.replace("'", "''"))
        if "{{" in sql:
            missing = re.findall(r"\{\{(\w+)\}\}", sql)
            raise TwikitScrapeError(f"Unresolved SQL tokens: {', '.join(missing)}")
        print(f"Ingest {sql_file}…")
        con = db.connect_for_ingest(release_mcp=True)
        try:
            con.execute(sql)
            print(f"  OK {sql_file}")
        finally:
            con.close()
    return 0


async def scrape_twitter(
    *,
    handle: str,
    last: int | None,
    since: date | None,
    until: date | None,
    fetch_replies: bool,
    max_replies: int,
    concurrency: int,
    cookies_path: Path,
    tweet_type: str,
    use_search: bool,
    ingest: bool,
) -> Path:
    handle = handle.lstrip("@")
    slug = account_slug(handle)
    run_dir = _make_run_dir(slug)
    client = await _login_client(cookies_path)

    await _rate_sleep()
    user = await client.get_user_by_screen_name(handle)
    profile = _user_to_dict(user)
    profile["scraped_handle"] = handle
    profile["scraped_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(run_dir / "profile.json", profile)
    print(f"Profile @{handle} id={user.id}")

    if use_search and since is not None and until is not None:
        pool = await _collect_by_search(client, handle, since, until)
    else:
        pool = await _collect_by_timeline(
            client,
            str(user.id),
            since=since,
            until=until,
            last=last,
            tweet_type=tweet_type,
        )

    tweets_path = run_dir / "tweets.jsonl"
    if tweets_path.exists():
        tweets_path.unlink()
    selected_rows: list[dict[str, Any]] = []
    for tweet in pool:
        row = _tweet_to_dict(tweet)
        _append_jsonl(tweets_path, row)
        selected_rows.append(row)

    _write_json(
        run_dir / "selected.json",
        {
            "handle": handle,
            "last": last,
            "since": since.isoformat() if since else None,
            "until": until.isoformat() if until else None,
            "tweet_type": tweet_type,
            "use_search": use_search and since is not None and until is not None,
            "selected_count": len(selected_rows),
            "tweets": selected_rows,
        },
    )
    print(f"Selected {len(selected_rows)} tweets → {tweets_path}")

    reply_stats: list[dict[str, Any]] = []
    if fetch_replies and pool:
        sem = asyncio.Semaphore(max(1, concurrency))
        print(
            f"Fetching replies (max {max_replies}/tweet, concurrency={concurrency})…"
        )
        tasks = [
            _fetch_replies_for_tweet(
                client,
                str(getattr(tweet, "id", "")),
                run_dir / f"replies_{getattr(tweet, 'id', '')}.jsonl",
                max_replies=max_replies,
                sem=sem,
            )
            for tweet in pool
            if getattr(tweet, "id", None)
        ]
        reply_stats = list(await asyncio.gather(*tasks))

    cookies_out = Path(os.getenv("TWITTER_COOKIES_PATH", str(DEFAULT_COOKIES))).expanduser()
    cookies_out.parent.mkdir(parents=True, exist_ok=True)
    try:
        client.save_cookies(str(cookies_out))
    except Exception:
        pass

    _write_json(
        run_dir / "manifest.json",
        {
            "source": "twikit",
            "platform": "twitter",
            "account": handle,
            "user_id": getattr(user, "id", None),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "last": last,
            "since": since.isoformat() if since else None,
            "until": until.isoformat() if until else None,
            "tweet_type": tweet_type,
            "selected_count": len(selected_rows),
            "fetch_replies": fetch_replies,
            "max_replies": max_replies,
            "concurrency": concurrency,
            "reply_stats": reply_stats,
            "landing": _repo_relative(run_dir),
            "docs": "https://twikit.readthedocs.io/en/latest/twikit.html",
        },
    )

    if ingest:
        _run_ingest(run_dir)

    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape X/Twitter account via twikit (session cookies / login)"
    )
    parser.add_argument("--handle", required=True, help="Twitter handle (with or without @)")
    parser.add_argument(
        "--last",
        type=int,
        default=None,
        help="Keep N most recent tweets (ignored when --since/--until set with search)",
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="Inclusive start date YYYY-MM-DD (e.g. 2026-07-01)",
    )
    parser.add_argument(
        "--until",
        type=str,
        default=None,
        help="Exclusive end date YYYY-MM-DD (e.g. 2026-08-01 for all of July)",
    )
    parser.add_argument(
        "--tweet-type",
        choices=["Tweets", "Replies", "Media", "Likes"],
        default="Tweets",
        help="Timeline tab when not using search (default: Tweets)",
    )
    parser.add_argument(
        "--no-search",
        action="store_true",
        help="Force timeline pagination instead of search_tweet for date ranges",
    )
    parser.add_argument(
        "--fetch-replies",
        action="store_true",
        help="Fetch reply threads for each selected tweet",
    )
    parser.add_argument(
        "--max-replies",
        type=int,
        default=DEFAULT_MAX_REPLIES,
        help=f"Max replies kept per tweet after ranking by likes (default: {DEFAULT_MAX_REPLIES})",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"asyncio.Semaphore size for reply fetches (default: {DEFAULT_CONCURRENCY})",
    )
    parser.add_argument(
        "--cookies",
        type=Path,
        default=None,
        help=f"Cookies JSON path (default: TWITTER_COOKIES_PATH or {DEFAULT_COOKIES})",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Ingest landing → bronze.tk_tw_* / silver.tk_tw_* after scrape",
    )
    args = parser.parse_args()

    since = _parse_day(args.since) if args.since else None
    until = _parse_day(args.until) if args.until else None
    if (since is None) ^ (until is None):
        print("Provide both --since and --until, or neither", file=sys.stderr)
        return 1
    if since and until and since >= until:
        print("--since must be < --until", file=sys.stderr)
        return 1
    if args.last is None and since is None:
        args.last = 10
    if args.last is not None and args.last < 1:
        print("--last must be >= 1", file=sys.stderr)
        return 1
    if args.max_replies < 1 or args.concurrency < 1:
        print("--max-replies and --concurrency must be >= 1", file=sys.stderr)
        return 1

    load_dotenv(REPO_ROOT / ".env")
    cookies_path = args.cookies or Path(
        os.getenv("TWITTER_COOKIES_PATH", str(DEFAULT_COOKIES))
    )
    use_search = since is not None and until is not None and not args.no_search

    try:
        run_dir = asyncio.run(
            scrape_twitter(
                handle=args.handle,
                last=args.last,
                since=since,
                until=until,
                fetch_replies=args.fetch_replies,
                max_replies=args.max_replies,
                concurrency=args.concurrency,
                cookies_path=cookies_path,
                tweet_type=args.tweet_type,
                use_search=use_search,
                ingest=args.ingest,
            )
        )
        print(f"Saved to {run_dir}")
        return 0
    except TwikitScrapeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
