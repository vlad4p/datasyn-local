"""Scrape a public X/Twitter account via twikit → data/landing/redes/twikit/twitter/.

Auth: TWITTER_USERNAME / TWITTER_EMAIL / TWITTER_PASSWORD in .env, or cookies file
(TWITTER_COOKIES_PATH, default .data/twikit_cookies.json — gitignored).

Usage:
    uv run python scripts/python/scrape_twikit_twitter.py \\
        --handle myriambregman --last 10 --fetch-replies

Docs: https://twikit.readthedocs.io/en/latest/twikit.html
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_COOKIES = REPO_ROOT / ".data" / "twikit_cookies.json"
RATE_SLEEP_S = 1.0


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


def _tweet_to_dict(tweet: Any, *, include_user: bool = True) -> dict[str, Any]:
    if tweet is None:
        return {}
    user = getattr(tweet, "user", None)
    created_dt = getattr(tweet, "created_at_datetime", None)
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
        "hashtags": list(getattr(tweet, "hashtags", None) or []),
        "urls": list(getattr(tweet, "urls", None) or []),
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
    dt = getattr(tweet, "created_at_datetime", None)
    if isinstance(dt, datetime):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return datetime.min.replace(tzinfo=timezone.utc)


def _make_run_dir(slug: str) -> Path:
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    run_dir = db.get_landing_path() / "redes" / "twikit" / "twitter" / f"{slug}_{date}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


async def _login_client(cookies_path: Path):
    from twikit import Client

    load_dotenv(REPO_ROOT / ".env")
    client = Client("en-US")
    cookies_path = cookies_path.expanduser()
    if cookies_path.is_file():
        client.load_cookies(str(cookies_path))
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
    await client.login(
        auth_info_1=username,
        auth_info_2=email,
        password=password,
        totp_secret=totp,
        cookies_file=str(cookies_path),
    )
    return client


async def _collect_user_tweets(
    client: Any,
    user_id: str,
    last: int,
    tweet_type: str = "Tweets",
) -> list[Any]:
    """Paginate get_user_tweets until we have `last` tweets (or timeline ends)."""
    collected: list[Any] = []
    seen: set[str] = set()
    page_count = min(40, max(last, 20))
    result = await client.get_user_tweets(user_id, tweet_type, count=page_count)
    while result:
        for tweet in result:
            tid = str(getattr(tweet, "id", "") or "")
            if not tid or tid in seen:
                continue
            seen.add(tid)
            collected.append(tweet)
        if len(collected) >= last:
            break
        time.sleep(RATE_SLEEP_S)
        try:
            result = await result.next()
        except Exception:
            break
        if not result:
            break
    collected.sort(key=_tweet_sort_key, reverse=True)
    return collected[:last]


async def _fetch_replies_for_tweet(
    client: Any,
    tweet_id: str,
    replies_path: Path,
    *,
    max_pages: int = 20,
) -> int:
    """Write reply pages to JSONL via get_tweet_by_id + Result.next()."""
    if replies_path.exists():
        replies_path.unlink()
    pages = 0
    try:
        tweet = await client.get_tweet_by_id(tweet_id)
    except Exception as exc:
        _append_jsonl(replies_path, {"error": str(exc), "tweet_id": tweet_id, "page": 0})
        return 0

    replies = getattr(tweet, "replies", None)
    while replies and pages < max_pages:
        batch = [_tweet_to_dict(r) for r in replies]
        _append_jsonl(
            replies_path,
            {
                "tweet_id": tweet_id,
                "page": pages,
                "count": len(batch),
                "replies": batch,
            },
        )
        pages += 1
        time.sleep(RATE_SLEEP_S)
        try:
            replies = await replies.next()
        except Exception:
            break
        if not replies:
            break
    return pages


async def scrape_twitter(
    *,
    handle: str,
    last: int,
    fetch_replies: bool,
    cookies_path: Path,
    tweet_type: str = "Tweets",
) -> Path:
    handle = handle.lstrip("@")
    slug = account_slug(handle)
    run_dir = _make_run_dir(slug)
    client = await _login_client(cookies_path)

    user = await client.get_user_by_screen_name(handle)
    profile = _user_to_dict(user)
    profile["scraped_handle"] = handle
    profile["scraped_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(run_dir / "profile.json", profile)

    pool = await _collect_user_tweets(
        client, str(user.id), last=last, tweet_type=tweet_type
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
            "tweet_type": tweet_type,
            "selected_count": len(selected_rows),
            "tweets": selected_rows,
        },
    )

    reply_stats: list[dict[str, Any]] = []
    if fetch_replies:
        for tweet in pool:
            tid = str(getattr(tweet, "id", "") or "")
            if not tid:
                continue
            pages = await _fetch_replies_for_tweet(
                client, tid, run_dir / f"replies_{tid}.jsonl"
            )
            reply_stats.append(
                {
                    "tweet_id": tid,
                    "reply_count": getattr(tweet, "reply_count", None),
                    "reply_pages_fetched": pages,
                }
            )

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
            "tweet_type": tweet_type,
            "selected_count": len(selected_rows),
            "fetch_replies": fetch_replies,
            "reply_stats": reply_stats,
            "landing": str(run_dir.relative_to(REPO_ROOT)),
            "docs": "https://twikit.readthedocs.io/en/latest/twikit.html",
        },
    )
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape X/Twitter account via twikit (session cookies / login)"
    )
    parser.add_argument("--handle", required=True, help="Twitter handle (with or without @)")
    parser.add_argument(
        "--last",
        type=int,
        default=10,
        help="Keep N most recent tweets from timeline pages (default: 10)",
    )
    parser.add_argument(
        "--tweet-type",
        choices=["Tweets", "Replies", "Media", "Likes"],
        default="Tweets",
        help="Timeline tab for get_user_tweets (default: Tweets)",
    )
    parser.add_argument(
        "--fetch-replies",
        action="store_true",
        help="Fetch reply threads for each selected tweet via get_tweet_by_id",
    )
    parser.add_argument(
        "--cookies",
        type=Path,
        default=None,
        help=f"Cookies JSON path (default: TWITTER_COOKIES_PATH or {DEFAULT_COOKIES})",
    )
    args = parser.parse_args()

    if args.last < 1:
        print("--last must be >= 1", file=sys.stderr)
        return 1

    load_dotenv(REPO_ROOT / ".env")
    cookies_path = args.cookies or Path(
        os.getenv("TWITTER_COOKIES_PATH", str(DEFAULT_COOKIES))
    )

    try:
        run_dir = asyncio.run(
            scrape_twitter(
                handle=args.handle,
                last=args.last,
                fetch_replies=args.fetch_replies,
                cookies_path=cookies_path,
                tweet_type=args.tweet_type,
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
