"""Scrape a public TikTok account via SociaVault → data/landing/redes/sociavault/tiktok/.

Usage:
    uv run python scripts/python/scrape/sociavault/scrape_sociavault_tiktok.py \\
        --handle tiktok --last 10 --fetch-comments --ingest-full
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


def _video_url(video: dict) -> str | None:
    return video.get("url") or video.get("videoUrl") or video.get("share_url")


def _video_id(video: dict) -> str | None:
    return item_dedupe_key("tiktok", video)


def _fetch_comments(client: SociaVaultClient, run_dir: Path, video: dict) -> None:
    video_url = _video_url(video)
    video_id = _video_id(video)
    if not video_url and not video_id:
        return
    comments_path = run_dir / f"comments_{video_id or 'unknown'}.jsonl"
    comment_cursor: str | None = None
    while True:
        cparams: dict = {}
        if video_url:
            cparams["url"] = video_url
        else:
            cparams["video_id"] = video_id
        if comment_cursor:
            cparams["cursor"] = comment_cursor
        try:
            comments_page = client.scrape("tiktok", "video/comments", cparams)
        except SociaVaultError as exc:
            append_jsonl(comments_path, {"error": str(exc), "video_id": video_id})
            break
        append_jsonl(comments_path, comments_page)
        comment_cursor = page_cursor(comments_page)
        if not comment_cursor:
            break


def scrape_tiktok(
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
    run_dir = make_run_dir("tiktok", slug)
    client = SociaVaultClient()

    profile = client.scrape("tiktok", "profile", {"handle": handle})
    write_json(run_dir / "profile.json", profile)

    videos_path = run_dir / "videos.jsonl"
    pool = paginate_collect_items(
        client,
        platform="tiktok",
        resource="videos",
        base_params={"handle": handle},
        raw_path=videos_path,
    )

    selected = select_most_recent(pool, "tiktok", limits.last)
    write_selected_snapshot(run_dir, limits=limits, pool=pool, selected=selected)

    if fetch_comments:
        for video in selected:
            _fetch_comments(client, run_dir, video)

    write_current_run(
        "tiktok",
        {
            "run_dir": repo_relative(run_dir),
            "profile_path": repo_relative(run_dir / "profile.json"),
            "videos_path": repo_relative(videos_path),
            "selected_path": repo_relative(run_dir / "selected.json"),
            "comments_glob": repo_relative(run_dir / "comments_*.jsonl"),
            "limits": limits.to_manifest_dict(),
        },
    )
    write_manifest(
        run_dir,
        platform="tiktok",
        account=handle,
        client=client,
        extra={
            "limits": limits.to_manifest_dict(),
            "api_pool_size": len(pool),
            "selected_count": len(selected),
        },
    )

    if ingest_full:
        rc = run_ingest_full("tiktok", classify_limit=classify_limit)
        if rc != 0:
            raise SociaVaultError(f"Ingest full failed with exit code {rc}")
    elif ingest:
        run_ingest_sql("ingest_sociavault_tiktok.sql")
        run_ingest_sql("ingest_sociavault_tiktok_silver.sql")

    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape TikTok account via SociaVault")
    parser.add_argument("--handle", required=True, help="TikTok handle")
    add_limit_args(parser, alias_flag="max-videos")
    parser.add_argument("--fetch-comments", action="store_true")
    parser.add_argument("--ingest", action="store_true")
    parser.add_argument("--ingest-full", action="store_true")
    parser.add_argument("--classify-limit", type=int, default=500)
    args = parser.parse_args()

    try:
        limits = ScrapeLimits.from_args(args)
        run_dir = scrape_tiktok(
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
