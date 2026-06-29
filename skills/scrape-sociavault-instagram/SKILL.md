---
name: scrape-sociavault-instagram
description: >-
  Scrape a public Instagram account via SociaVault API: profile, posts,
  and comments. Saves JSON to data/landing/redes/sociavault/instagram/
  and ingests to bronze.sv_ig_* / silver.sv_ig_* tables. Use when the
  user asks to scrape Instagram with SociaVault.
---

# Scrape Instagram (SociaVault)

**Platform:** Instagram · **Source:** [SociaVault API](https://docs.sociavault.com/platforms/instagram) · **Schema:** `sv_ig_*`

## Prerequisites

1. `SOCIAVAULT_API_KEY` in `.env`
2. Public Instagram handle
3. Follow **`data-privacy`**

## SociaVault endpoints

| Step | Endpoint | Credits |
|------|----------|---------|
| Profile | `GET /v1/scrape/instagram/profile?handle=` | ~1 |
| Posts | `GET /v1/scrape/instagram/posts?handle=` | ~1/page |
| Comments | `GET /v1/scrape/instagram/post/comments` | ~1/page |

## Workflow

```bash
uv run python scripts/python/scrape_sociavault_instagram.py \
  --handle instagram \
  --max-posts 30 \
  --fetch-comments
```

**Landing:**

```
data/landing/redes/sociavault/instagram/{slug}_{YYYYMMDD}/
  profile.json
  posts.jsonl
  comments_{post_id}.jsonl
  manifest.json
```

**Ingest:**

```bash
uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_instagram.sql
uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_instagram_silver.sql
```

## DuckDB tables

| Zone | Tables |
|------|--------|
| Bronze | `bronze.sv_ig_profile`, `bronze.sv_ig_post`, `bronze.sv_ig_comment` |
| Silver | `silver.sv_ig_profile`, `silver.sv_ig_post`, `silver.sv_ig_comment` |

## Validation

```sql
SELECT COUNT(*) FROM silver.sv_ig_post;
SELECT COUNT(*) FROM silver.sv_ig_comment;
SELECT post_id, LEFT(caption, 80) FROM silver.sv_ig_post LIMIT 3;
```

## Limits

- Public profiles only
- Private accounts and restricted posts fail with API errors
- Rate limit: ≥1s between paginated calls (handled by client)

## Related

- [`scrape-sociavault`](../scrape-sociavault/SKILL.md)
