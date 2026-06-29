"""Scrape a public X/Twitter account via SociaVault → data/landing/redes/sociavault/twitter/.

Usage:
    uv run python scripts/python/scrape_sociavault_twitter.py \\
        --handle levelsio --fetch-replies

Note: Twitter replies are often incomplete (API limitation). See skill docs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sociavault_client import SociaVaultClient, SociaVaultCreditsError, SociaVaultError
from sociavault_scrape_common import (
    account_slug,
    append_jsonl,
    dig,
    make_run_dir,
    repo_relative,
    run_ingest_sql,
    write_current_run,
    write_json,
    write_manifest,
)


def _tweet_id(tweet: dict) -> str | None:
    tid = tweet.get("rest_id") or dig(tweet, "legacy", "id_str") or tweet.get("id_str")
    return str(tid) if tid is not None else None


def _tweet_url(tweet: dict, handle: str) -> str | None:
    url = tweet.get("url")
    if url:
        return url
    tid = _tweet_id(tweet)
    if tid:
        return f"https://x.com/{handle.lstrip('@')}/status/{tid}"
    return None


def scrape_twitter(*, handle: str, fetch_replies: bool, ingest: bool) -> Path:
    handle = handle.lstrip("@")
    slug = account_slug(handle)
    run_dir = make_run_dir("twitter", slug)
    client = SociaVaultClient()

    profile = client.scrape("twitter", "profile", {"handle": handle})
    write_json(run_dir / "profile.json", profile)

    tweets_page = client.scrape("twitter", "user-tweets", {"handle": handle, "trim": "false"})
    tweets_path = run_dir / "tweets.json"
    write_json(tweets_path, tweets_page)

    tweets_raw = (
        dig(tweets_page, "data", "tweets")
        or dig(tweets_page, "data", "data", "tweets")
        or {}
    )
    if isinstance(tweets_raw, dict):
        tweets = [v for v in tweets_raw.values() if isinstance(v, dict)]
    elif isinstance(tweets_raw, list):
        tweets = tweets_raw
    else:
        tweets = []

    if fetch_replies:
        for tweet in tweets:
            tweet_url = _tweet_url(tweet, handle)
            tweet_id = _tweet_id(tweet)
            if not tweet_url or not tweet_id:
                continue
            replies_path = run_dir / f"replies_{tweet_id}.jsonl"
            cursor: str | None = None
            while True:
                params: dict = {"url": tweet_url}
                if cursor:
                    params["cursor"] = cursor
                try:
                    page = client.scrape("twitter", "tweet/replies", params)
                except SociaVaultError as exc:
                    append_jsonl(replies_path, {"error": str(exc), "tweet_url": tweet_url})
                    break
                append_jsonl(replies_path, page)
                cursor = dig(page, "data", "cursor") or dig(page, "data", "nextCursor")
                if not cursor:
                    break

    write_current_run(
        "twitter",
        {
            "run_dir": repo_relative(run_dir),
            "profile_path": repo_relative(run_dir / "profile.json"),
            "tweets_path": repo_relative(tweets_path),
            "replies_glob": repo_relative(run_dir / "replies_*.jsonl"),
        },
    )
    write_manifest(run_dir, platform="twitter", account=handle, client=client)

    if ingest:
        run_ingest_sql("ingest_sociavault_twitter.sql")
        run_ingest_sql("ingest_sociavault_twitter_silver.sql")

    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape X/Twitter account via SociaVault")
    parser.add_argument("--handle", required=True, help="Twitter handle (with or without @)")
    parser.add_argument("--fetch-replies", action="store_true", help="Fetch replies per tweet")
    parser.add_argument("--ingest", action="store_true", help="Run bronze+silver SQL after scrape")
    args = parser.parse_args()

    try:
        run_dir = scrape_twitter(
            handle=args.handle,
            fetch_replies=args.fetch_replies,
            ingest=args.ingest,
        )
        print(f"Saved to {run_dir}")
        return 0
    except SociaVaultCreditsError as exc:
        print(f"Insufficient credits: {exc}", file=sys.stderr)
        return 2
    except SociaVaultError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
