"""Scrape a public Facebook page via SociaVault → data/landing/redes/sociavault/facebook/.

Usage:
    uv run python scripts/python/scrape_sociavault_facebook.py \\
        --url "https://www.facebook.com/example" \\
        --max-posts 50 --fetch-comments

Then ingest bronze + silver SQL under scripts/sql/ingest_sociavault_facebook*.sql
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
    return post.get("url") or post.get("postUrl") or post.get("link")


def _post_id(post: dict) -> str | None:
    pid = post.get("id") or post.get("post_id") or post.get("postId")
    return str(pid) if pid is not None else None


def scrape_facebook(
    *,
    url: str,
    max_posts: int,
    fetch_comments: bool,
    ingest: bool,
) -> Path:
    slug = account_slug(url)
    run_dir = make_run_dir("facebook", slug)
    client = SociaVaultClient()

    profile = client.scrape("facebook", "profile", {"url": url})
    write_json(run_dir / "profile.json", profile)

    page_id = dig(profile, "data", "id") or dig(profile, "data", "data", "id")
    posts_params: dict = {"url": url}
    if page_id:
        posts_params["pageId"] = str(page_id)

    posts_path = run_dir / "posts.jsonl"
    collected = 0
    cursor: str | None = None

    while collected < max_posts:
        params = dict(posts_params)
        if cursor:
            params["cursor"] = cursor
        page = client.scrape("facebook", "profile/posts", params)
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
                comments_file = run_dir / f"comments_{post_id or 'unknown'}.jsonl"
                comment_cursor: str | None = None
                while True:
                    cparams = {"url": post_url}
                    if comment_cursor:
                        cparams["cursor"] = comment_cursor
                    try:
                        comments_page = client.scrape("facebook", "post/comments", cparams)
                    except SociaVaultCreditsError:
                        raise
                    except SociaVaultError as exc:
                        append_jsonl(comments_file, {"error": str(exc), "post_url": post_url})
                        break
                    append_jsonl(comments_file, comments_page)
                    comment_cursor = dig(comments_page, "data", "cursor") or dig(
                        comments_page, "data", "nextCursor"
                    )
                    if not comment_cursor:
                        break

        collected += len(posts) if isinstance(posts, list) else 0
        cursor = dig(page, "data", "cursor") or dig(page, "data", "nextCursor")
        if not cursor or not posts:
            break

    write_current_run(
        "facebook",
        {
            "run_dir": repo_relative(run_dir),
            "profile_path": repo_relative(run_dir / "profile.json"),
            "posts_path": repo_relative(posts_path),
            "comments_glob": repo_relative(run_dir / "comments_*.jsonl"),
        },
    )
    write_manifest(run_dir, platform="facebook", account=url, client=client)

    if ingest:
        run_ingest_sql("ingest_sociavault_facebook.sql")
        run_ingest_sql("ingest_sociavault_facebook_silver.sql")

    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape Facebook page via SociaVault")
    parser.add_argument("--url", required=True, help="Public Facebook page/profile URL")
    parser.add_argument("--max-posts", type=int, default=50, help="Max posts to fetch")
    parser.add_argument("--fetch-comments", action="store_true", help="Fetch comments per post")
    parser.add_argument("--ingest", action="store_true", help="Run bronze+silver SQL after scrape")
    args = parser.parse_args()

    try:
        run_dir = scrape_facebook(
            url=args.url,
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
