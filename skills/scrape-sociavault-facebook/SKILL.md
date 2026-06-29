---
name: scrape-sociavault-facebook
description: >-
  Scrape a public Facebook page via SociaVault API: profile, posts, and
  comments. Saves JSON to data/landing/redes/sociavault/facebook/ and
  ingests to bronze.sv_fb_* / silver.sv_fb_* tables. Use when the user
  asks to scrape a Facebook account, fanpage, or page with SociaVault.
---

# Scrape Facebook (SociaVault)

**Platform:** Facebook · **Source:** [SociaVault API](https://docs.sociavault.com/platforms/facebook) · **Schema:** parallel `sv_fb_*` (not legacy `fb_*` CSV dumps)

## Prerequisites

1. `SOCIAVAULT_API_KEY` in `.env` (copy from [`.env.example`](../../.env.example))
2. Public Facebook **page** URL (personal profiles may fail)
3. Follow **`data-privacy`** — landing data and reports stay local

## SociaVault endpoints

| Step | Endpoint | Credits |
|------|----------|---------|
| Profile | `GET /v1/scrape/facebook/profile?url=` | ~1 |
| Posts | `GET /v1/scrape/facebook/profile/posts?url=` or `pageId=` | ~1/page (≤3 posts/page) |
| Comments | `GET /v1/scrape/facebook/post/comments?url=` | ~1/page |

Docs: [Profile](https://docs.sociavault.com/api-reference/facebook/profile) · [Profile Posts](https://docs.sociavault.com/api-reference/facebook/profile-posts) · [Post Comments](https://docs.sociavault.com/api-reference/facebook/post-comments)

## Workflow

1. **Confirm** public page URL and `--max-posts` / `--fetch-comments`
2. **Estimate credits:** 1 (profile) + pages for posts + 1 per post comment page
3. **Scrape:**

```bash
uv run python scripts/python/scrape_sociavault_facebook.py \
  --url "https://www.facebook.com/example" \
  --max-posts 50 \
  --fetch-comments
```

4. **Landing output** (gitignored):

```
data/landing/redes/sociavault/facebook/{slug}_{YYYYMMDD}/
  profile.json
  posts.jsonl
  comments_{post_id}.jsonl
  manifest.json
```

5. **Ingest bronze:**

```bash
uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_facebook.sql
```

6. **Ingest silver:**

```bash
uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_facebook_silver.sql
```

Or pass `--ingest` to the scrape script to run both SQL files automatically.

## DuckDB tables

| Zone | Tables |
|------|--------|
| Bronze | `bronze.sv_fb_profile`, `bronze.sv_fb_post`, `bronze.sv_fb_comment` |
| Silver | `silver.sv_fb_profile`, `silver.sv_fb_post`, `silver.sv_fb_comment` |

Silver column names align with legacy [`silver.fb_post`](../../scripts/sql/ingest_fb_silver.sql) where possible (`post_id`, `mensaje`, `comentarios`).

## Validation

```sql
SELECT COUNT(*) FROM bronze.sv_fb_profile;
SELECT COUNT(*) FROM silver.sv_fb_post;
SELECT COUNT(*) FROM silver.sv_fb_comment;
SELECT post_id, LEFT(mensaje, 80) FROM silver.sv_fb_post LIMIT 3;
```

Redact PII in chat outputs.

## Limits

- Public pages only; private content returns errors
- Facebook returns up to ~3 posts per API page — pagination via `cursor`
- Legacy CSV dumps in `data/landing/redes/data-fb/` are a **separate** pipeline — do not merge into `fb_*` tables

## Related

- Pipeline entry: [`scrape-sociavault`](../scrape-sociavault/SKILL.md)
- After silver: [`ingest-data-gold`](../ingest-data-gold/SKILL.md), [`sentiment-analysis`](../sentiment-analysis/SKILL.md)
