"""Scrape a public TikTok account via SociaVault → data/landing/redes/sociavault/tiktok/.

Usage:
    uv run python scripts/python/scrape_sociavault_tiktok.py \\
        --handle tiktok --max-videos 30 --fetch-comments
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


def _video_url(video: dict) -> str | None:
    return video.get("url") or video.get("videoUrl") or video.get("share_url")


def _video_id(video: dict) -> str | None:
    vid = video.get("id") or video.get("video_id") or video.get("aweme_id")
    return str(vid) if vid is not None else None


def scrape_tiktok(*, handle: str, max_videos: int, fetch_comments: bool, ingest: bool) -> Path:
    handle = handle.lstrip("@")
    slug = account_slug(handle)
    run_dir = make_run_dir("tiktok", slug)
    client = SociaVaultClient()

    profile = client.scrape("tiktok", "profile", {"handle": handle})
    write_json(run_dir / "profile.json", profile)

    videos_path = run_dir / "videos.jsonl"
    collected = 0
    cursor: str | None = None

    while collected < max_videos:
        params: dict = {"handle": handle}
        if cursor:
            params["cursor"] = cursor
        page = client.scrape("tiktok", "videos", params)
        append_jsonl(videos_path, page)

        videos = dig(page, "data", "videos") or dig(page, "data", "data", "videos") or []
        if isinstance(videos, dict):
            videos = list(videos.values())

        if fetch_comments:
            for video in videos:
                if not isinstance(video, dict):
                    continue
                video_url = _video_url(video)
                video_id = _video_id(video)
                if not video_url and not video_id:
                    continue
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
                    comment_cursor = dig(comments_page, "data", "cursor")
                    if not comment_cursor:
                        break

        collected += len(videos) if isinstance(videos, list) else 0
        cursor = dig(page, "data", "cursor") or dig(page, "data", "nextCursor")
        if not cursor or not videos:
            break

    write_current_run(
        "tiktok",
        {
            "run_dir": repo_relative(run_dir),
            "profile_path": repo_relative(run_dir / "profile.json"),
            "videos_path": repo_relative(videos_path),
            "comments_glob": repo_relative(run_dir / "comments_*.jsonl"),
        },
    )
    write_manifest(run_dir, platform="tiktok", account=handle, client=client)

    if ingest:
        run_ingest_sql("ingest_sociavault_tiktok.sql")
        run_ingest_sql("ingest_sociavault_tiktok_silver.sql")

    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape TikTok account via SociaVault")
    parser.add_argument("--handle", required=True, help="TikTok handle")
    parser.add_argument("--max-videos", type=int, default=30)
    parser.add_argument("--fetch-comments", action="store_true")
    parser.add_argument("--ingest", action="store_true")
    args = parser.parse_args()

    try:
        run_dir = scrape_tiktok(
            handle=args.handle,
            max_videos=args.max_videos,
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
