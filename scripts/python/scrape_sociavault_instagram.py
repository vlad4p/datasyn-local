"""Scrape a public Instagram account via SociaVault → data/landing/redes/sociavault/instagram/.

Usage:
    uv run python scripts/python/scrape_sociavault_instagram.py \\
        --handle instagram --max-posts 30 --fetch-comments
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


def _post_url(post: dict) -> str | None:
    return post.get("url") or post.get("postUrl") or post.get("link") or post.get("code")


def _post_id(post: dict) -> str | None:
    pid = post.get("id") or post.get("pk") or post.get("code")
    return str(pid) if pid is not None else None


def scrape_instagram(*, handle: str, max_posts: int, fetch_comments: bool, ingest: bool) -> Path:
    handle = handle.lstrip("@")
    slug = account_slug(handle)
    run_dir = make_run_dir("instagram", slug)
    client = SociaVaultClient()

    profile = client.scrape("instagram", "profile", {"handle": handle})
    write_json(run_dir / "profile.json", profile)

    posts_path = run_dir / "posts.jsonl"
    collected = 0
    cursor: str | None = None

    while collected < max_posts:
        params: dict = {"handle": handle}
        if cursor:
            params["cursor"] = cursor
        page = client.scrape("instagram", "posts", params)
        append_jsonl(posts_path, page)

        posts = dig(page, "data", "posts") or dig(page, "data", "data", "posts") or []
        if isinstance(posts, dict):
            posts = list(posts.values())

        if fetch_comments:
            for post in posts:
                if not isinstance(post, dict):
                    continue
                post_url = _post_url(post)
                post_id = _post_id(post)
                if not post_url:
                    continue
                comments_path = run_dir / f"comments_{post_id or 'unknown'}.jsonl"
                comment_cursor: str | None = None
                while True:
                    if post_url.startswith("http"):
                        cparams = {"url": post_url}
                    else:
                        cparams = {"handle": handle, "post_id": post_id}
                    if comment_cursor:
                        cparams["cursor"] = comment_cursor
                    try:
                        comments_page = client.scrape("instagram", "post/comments", cparams)
                    except SociaVaultError as exc:
                        append_jsonl(comments_path, {"error": str(exc), "post_id": post_id})
                        break
                    append_jsonl(comments_path, comments_page)
                    comment_cursor = dig(comments_page, "data", "cursor")
                    if not comment_cursor:
                        break

        collected += len(posts) if isinstance(posts, list) else 0
        cursor = dig(page, "data", "cursor") or dig(page, "data", "nextCursor")
        if not cursor or not posts:
            break

    write_current_run(
        "instagram",
        {
            "run_dir": repo_relative(run_dir),
            "profile_path": repo_relative(run_dir / "profile.json"),
            "posts_path": repo_relative(posts_path),
            "comments_glob": repo_relative(run_dir / "comments_*.jsonl"),
        },
    )
    write_manifest(run_dir, platform="instagram", account=handle, client=client)

    if ingest:
        run_ingest_sql("ingest_sociavault_instagram.sql")
        run_ingest_sql("ingest_sociavault_instagram_silver.sql")

    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape Instagram account via SociaVault")
    parser.add_argument("--handle", required=True, help="Instagram handle")
    parser.add_argument("--max-posts", type=int, default=30)
    parser.add_argument("--fetch-comments", action="store_true")
    parser.add_argument("--ingest", action="store_true")
    args = parser.parse_args()

    try:
        run_dir = scrape_instagram(
            handle=args.handle,
            max_posts=args.max_posts,
            fetch_comments=args.fetch_comments,
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
