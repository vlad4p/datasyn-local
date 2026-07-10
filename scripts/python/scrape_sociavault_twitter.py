"""Scrape a public X/Twitter account via SociaVault → data/landing/redes/sociavault/twitter/.

Usage:
    uv run python scripts/python/scrape_sociavault_twitter.py \\
        --handle myriambregman --last 10 --fetch-replies --ingest-full

Note: user-tweets returns ~100 popular tweets; "last N" is best-effort by created_at.
Replies are often incomplete (API limitation). See skill docs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sociavault_client import SociaVaultClient, SociaVaultCreditsError, SociaVaultError
from sociavault_limits import (
    ScrapeLimits,
    add_limit_args,
    item_dedupe_key,
    page_cursor,
    paginate_collect_items,
    select_most_recent,
)
from sociavault_scrape_common import (
    account_slug,
    append_jsonl,
    dig,
    make_run_dir,
    repo_relative,
    run_ingest_full,
    run_ingest_sql,
    write_current_run,
    write_json,
    write_manifest,
    write_selected_snapshot,
)


def _tweet_id(tweet: dict) -> str | None:
    return item_dedupe_key("twitter", tweet)


def _tweet_url(tweet: dict, handle: str) -> str | None:
    url = tweet.get("url")
    if url:
        return url
    tid = _tweet_id(tweet)
    if tid:
        return f"https://x.com/{handle.lstrip('@')}/status/{tid}"
    return None


def _comments_cursor(page: dict) -> str | None:
    """Pagination cursor for twitter/comments (data.cursor.bottom)."""
    bottom = dig(page, "data", "cursor", "bottom")
    if bottom:
        return str(bottom)
    return page_cursor(page)


def _fetch_replies(client: SociaVaultClient, run_dir: Path, tweet: dict, handle: str) -> int:
    tweet_id = _tweet_id(tweet)
    if not tweet_id:
        return 0
    replies_path = run_dir / f"replies_{tweet_id}.jsonl"
    if replies_path.exists():
        replies_path.unlink()
    pages = 0
    cursor: str | None = None
    while True:
        params: dict = {"pid": tweet_id, "rankingMode": "Recency"}
        if cursor:
            params["cursor"] = cursor
        try:
            page = client.scrape("twitter", "comments", params)
        except SociaVaultError as exc:
            append_jsonl(replies_path, {"error": str(exc), "tweet_id": tweet_id})
            break
        append_jsonl(replies_path, page)
        pages += 1
        cursor = _comments_cursor(page)
        if not cursor:
            break
    return pages


def _enrich_tweets(
    client: SociaVaultClient,
    run_dir: Path,
    tweets: list[dict],
    handle: str,
) -> None:
    for tweet in tweets:
        tweet_url = _tweet_url(tweet, handle)
        tweet_id = _tweet_id(tweet)
        if not tweet_url or not tweet_id:
            continue
        try:
            detail = client.scrape("twitter", "tweet", {"url": tweet_url})
        except SociaVaultError as exc:
            write_json(
                run_dir / f"tweet_detail_{tweet_id}.json",
                {"error": str(exc), "url": tweet_url},
            )
            continue
        write_json(run_dir / f"tweet_detail_{tweet_id}.json", detail)


def scrape_twitter(
    *,
    handle: str,
    limits: ScrapeLimits,
    fetch_replies: bool,
    enrich: bool,
    ingest: bool,
    ingest_full: bool,
    classify_limit: int,
) -> Path:
    handle = handle.lstrip("@")
    slug = account_slug(handle)
    run_dir = make_run_dir("twitter", slug)
    client = SociaVaultClient()

    profile = client.scrape("twitter", "profile", {"handle": handle})
    write_json(run_dir / "profile.json", profile)

    tweets_path = run_dir / "tweets.jsonl"
    pool = paginate_collect_items(
        client,
        platform="twitter",
        resource="user-tweets",
        base_params={"handle": handle, "trim": "false"},
        raw_path=tweets_path,
    )

    selected = select_most_recent(pool, "twitter", limits.last)
    write_selected_snapshot(run_dir, limits=limits, pool=pool, selected=selected)

    if enrich:
        _enrich_tweets(client, run_dir, selected, handle)

    reply_stats: list[dict] = []
    if fetch_replies:
        for tweet in selected:
            pages = _fetch_replies(client, run_dir, tweet, handle)
            reply_stats.append(
                {
                    "tweet_id": _tweet_id(tweet),
                    "reply_count_api": dig(tweet, "legacy", "reply_count"),
                    "reply_pages_fetched": pages,
                }
            )

    write_current_run(
        "twitter",
        {
            "run_dir": repo_relative(run_dir),
            "profile_path": repo_relative(run_dir / "profile.json"),
            "tweets_path": repo_relative(tweets_path),
            "selected_path": repo_relative(run_dir / "selected.json"),
            "tweet_detail_glob": repo_relative(run_dir / "tweet_detail_*.json"),
            "replies_glob": repo_relative(run_dir / "replies_*.jsonl"),
            "limits": limits.to_manifest_dict(),
        },
    )
    write_manifest(
        run_dir,
        platform="twitter",
        account=handle,
        client=client,
        extra={
            "limits": limits.to_manifest_dict(),
            "api_pool_size": len(pool),
            "selected_count": len(selected),
            "enriched": enrich,
            "reply_stats": reply_stats,
        },
    )

    if ingest_full:
        rc = run_ingest_full("twitter", classify_limit=classify_limit)
        if rc != 0:
            raise SociaVaultError(f"Ingest full failed with exit code {rc}")
    elif ingest:
        run_ingest_sql("ingest_sociavault_twitter.sql")
        run_ingest_sql("ingest_sociavault_twitter_silver.sql")

    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape X/Twitter account via SociaVault")
    parser.add_argument("--handle", required=True, help="Twitter handle (with or without @)")
    add_limit_args(parser, alias_flag="max-tweets")
    parser.add_argument(
        "--fetch-replies",
        action="store_true",
        help="Fetch all replies per selected tweet",
    )
    parser.add_argument(
        "--enrich",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fetch full tweet detail per selected item (default: on)",
    )
    parser.add_argument("--ingest", action="store_true", help="Run bronze+silver SQL after scrape")
    parser.add_argument("--ingest-full", action="store_true")
    parser.add_argument("--classify-limit", type=int, default=500)
    args = parser.parse_args()

    try:
        limits = ScrapeLimits.from_args(args)
        run_dir = scrape_twitter(
            handle=args.handle,
            limits=limits,
            fetch_replies=args.fetch_replies,
            enrich=args.enrich,
            ingest=args.ingest,
            ingest_full=args.ingest_full,
            classify_limit=args.classify_limit,
        )
        print(f"Saved to {run_dir}")
        return 0
    except ValueError as exc:
        print(f"Invalid arguments: {exc}", file=sys.stderr)
        return 1
    except SociaVaultCreditsError as exc:
        print(f"Insufficient credits: {exc}", file=sys.stderr)
        return 2
    except SociaVaultError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
