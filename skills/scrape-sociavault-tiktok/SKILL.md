---
name: scrape-sociavault-tiktok
description: >-
  Scrape a public TikTok account via SociaVault API: profile, videos,
  and comments. Saves JSON to data/landing/redes/sociavault/tiktok/ and
  ingests to bronze.sv_tt_* / silver.sv_tt_* tables. Use when the user
  asks to scrape TikTok with SociaVault.
---

# Scrape TikTok (SociaVault)

**Platform:** TikTok · **Source:** [SociaVault API](https://docs.sociavault.com/platforms/tiktok) · **Schema:** `sv_tt_*`

## Prerequisites

1. `SOCIAVAULT_API_KEY` in `.env`
2. Public TikTok handle
3. Follow **`data-privacy`**

## SociaVault endpoints

| Step | Endpoint | Credits |
|------|----------|---------|
| Profile | `GET /v1/scrape/tiktok/profile?handle=` | ~1 |
| Videos | `GET /v1/scrape/tiktok/videos?handle=` | ~1/page |
| Comments | `GET /v1/scrape/tiktok/video/comments` | ~1/page |

## Workflow

```bash
uv run python scripts/python/scrape_sociavault_tiktok.py \
  --handle tiktok \
  --max-videos 30 \
  --fetch-comments
```

**Landing:**

```
data/landing/redes/sociavault/tiktok/{slug}_{YYYYMMDD}/
  profile.json
  videos.jsonl
  comments_{video_id}.jsonl
  manifest.json
```

**Ingest:**

```bash
uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_tiktok.sql
uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_tiktok_silver.sql
```

## DuckDB tables

| Zone | Tables |
|------|--------|
| Bronze | `bronze.sv_tt_profile`, `bronze.sv_tt_video`, `bronze.sv_tt_comment` |
| Silver | `silver.sv_tt_profile`, `silver.sv_tt_video`, `silver.sv_tt_comment` |

## Validation

```sql
SELECT COUNT(*) FROM silver.sv_tt_video;
SELECT COUNT(*) FROM silver.sv_tt_comment;
SELECT video_id, LEFT(description, 80) FROM silver.sv_tt_video LIMIT 3;
```

## Limits

- Public profiles only
- Comment fetch requires video URL or ID from the videos response
- Credits scale with `--max-videos` and `--fetch-comments`

## Related

- [`scrape-sociavault`](../scrape-sociavault/SKILL.md)
