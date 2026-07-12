"""Scrape a public Instagram account via SociaVault → data/landing/redes/sociavault/instagram/.

Usage:
    uv run python scripts/python/scrape/sociavault/scrape_sociavault_instagram.py \\
        --handle instagram --last 10 --fetch-comments --ingest-full
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scrape.sociavault.sociavault_client import SociaVaultClient, SociaVaultCreditsError, SociaVaultError
from scrape.sociavault.sociavault_limits import (
    ScrapeLimits,
    add_limit_args,
    item_dedupe_key,
    page_cursor,
    paginate_collect_items,
    select_most_recent,
)
from scrape.sociavault.sociavault_scrape_common import (
    account_slug,
    append_jsonl,
    make_run_dir,
    repo_relative,
    run_ingest_full,
    run_ingest_sql,
    write_current_run,
    write_json,
    write_manifest,
    write_selected_snapshot,
)


def _post_url(post: dict) -> str | None:
    return post.get("url") or post.get("postUrl") or post.get("link") or post.get("code")


def _post_id(post: dict) -> str | None:
    return item_dedupe_key("instagram", post)


def _fetch_comments(
    client: SociaVaultClient,
    run_dir: Path,
    handle: str,
    post: dict,
) -> None:
    post_url = _post_url(post)
    post_id = _post_id(post)
    if not post_url:
        return
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
        comment_cursor = page_cursor(comments_page)
        if not comment_cursor:
            break


def scrape_instagram(
    *,
    handle: str,
    limits: ScrapeLimits,
    fetch_comments: bool,
    ingest: bool,
    ingest_full: bool,
    classify_limit: int,
) -> Path:
    handle = handle.lstrip("@")
    slug = account_slug(handle)
    run_dir = make_run_dir("instagram", slug)
    client = SociaVaultClient()

    profile = client.scrape("instagram", "profile", {"handle": handle})
    write_json(run_dir / "profile.json", profile)

    posts_path = run_dir / "posts.jsonl"
    pool = paginate_collect_items(
        client,
        platform="instagram",
        resource="posts",
        base_params={"handle": handle},
        raw_path=posts_path,
    )

    selected = select_most_recent(pool, "instagram", limits.last)
    write_selected_snapshot(run_dir, limits=limits, pool=pool, selected=selected)

    if fetch_comments:
        for post in selected:
            _fetch_comments(client, run_dir, handle, post)

    write_current_run(
        "instagram",
        {
            "run_dir": repo_relative(run_dir),
            "profile_path": repo_relative(run_dir / "profile.json"),
            "posts_path": repo_relative(posts_path),
            "selected_path": repo_relative(run_dir / "selected.json"),
            "comments_glob": repo_relative(run_dir / "comments_*.jsonl"),
            "limits": limits.to_manifest_dict(),
        },
    )
    write_manifest(
        run_dir,
        platform="instagram",
        account=handle,
        client=client,
        extra={
            "limits": limits.to_manifest_dict(),
            "api_pool_size": len(pool),
            "selected_count": len(selected),
        },
    )

    if ingest_full:
        rc = run_ingest_full("instagram", classify_limit=classify_limit)
        if rc != 0:
            raise SociaVaultError(f"Ingest full failed with exit code {rc}")
    elif ingest:
        run_ingest_sql("ingest_sociavault_instagram.sql")
        run_ingest_sql("ingest_sociavault_instagram_silver.sql")

    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape Instagram account via SociaVault")
    parser.add_argument("--handle", required=True, help="Instagram handle")
    add_limit_args(parser, alias_flag="max-posts")
    parser.add_argument("--fetch-comments", action="store_true")
    parser.add_argument("--ingest", action="store_true")
    parser.add_argument("--ingest-full", action="store_true")
    parser.add_argument("--classify-limit", type=int, default=500)
    args = parser.parse_args()

    try:
        limits = ScrapeLimits.from_args(args)
        run_dir = scrape_instagram(
            handle=args.handle,
            limits=limits,
            fetch_comments=args.fetch_comments,
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
