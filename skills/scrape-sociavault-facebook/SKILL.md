---
name: scrape-sociavault-facebook
description: >-
  Scrape a public Facebook page via SociaVault API: last N posts by publish
  date, all comments per selected post. MERGEs sv_fb_*, actors, LLM classify.
---

# Scrape Facebook (SociaVault)

**Platform:** Facebook · **Source:** [SociaVault API](https://docs.sociavault.com/platforms/facebook) · **Schema:** parallel `sv_fb_*` (not legacy `fb_*` CSV dumps)

## Prerequisites

1. `SOCIAVAULT_API_KEY` in `.env` (copy from [`.env.example`](../../.env.example))
2. `LLM_API_KEY` in `.env` for comment classification (`uv sync --extra llm`)
3. Public Facebook **page** URL (personal profiles may fail)
4. Follow **`data-privacy`** — landing data and reports stay local

## Count flag

| Flag | Default | Meaning |
|------|---------|---------|
| `--last N` | 10 | N most recent posts (by `publishTime`) |
| `--max-posts N` | — | Alias for `--last` |

## SociaVault endpoints

| Step | Endpoint | Credits |
|------|----------|---------|
| Profile | `GET /v1/scrape/facebook/profile?url=` | ~1 |
| Posts | `GET /v1/scrape/facebook/profile/posts?url=` or `pageId=` | ~1/page (≤3 posts/page) |
| Comments | `GET /v1/scrape/facebook/post/comments?url=` | ~1/page |

## Workflow

1. **Confirm** URL, time window, and `--fetch-comments`
2. **Estimate credits:** 1 (profile) + post pages + comment pages per post
3. **Scrape + full pipeline:**

```bash
uv run python scripts/python/scrape_sociavault_facebook.py \
  --url "https://www.facebook.com/example" \
  --last 10 \
  --fetch-comments \
  --ingest-full

./scripts/sh/scrape_sociavault.sh facebook "https://www.facebook.com/example" --last 5
```

4. **Landing output** (gitignored):

```
data/landing/redes/sociavault/facebook/{slug}_{YYYYMMDD}/
  profile.json
  posts.jsonl
  comments_{post_id}.jsonl
  manifest.json   # includes window, posts_collected
```

5. **Manual ingest** (if not using `--ingest` / `--ingest-full`):

```bash
uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_facebook.sql
uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_facebook_silver.sql
uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_classification.sql
uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_entities.sql
uv run python scripts/python/classify_sv_comments.py --platform facebook --limit 500
```

## DuckDB tables

| Zone | Tables |
|------|--------|
| Bronze | `bronze.sv_fb_profile`, `bronze.sv_fb_post`, `bronze.sv_fb_comment` (current run) |
| Silver | `silver.sv_fb_*` (MERGE upsert by `post_id` / `comment_id`) |
| Actors | `silver.sv_actor`, `silver.sv_actor_activity`, `silver.sv_actor_stats` |
| Classification | `silver.sv_fb_comment_classification` (`free_criteria` legacy schema) |

Silver comments include `user_id`, `user_name`, `user_url`, `fecha_comentario_ts`.

## Validation

```sql
SELECT COUNT(*) FROM silver.sv_fb_post;
SELECT COUNT(*) FROM silver.sv_fb_comment;
SELECT COUNT(DISTINCT user_id) FROM silver.sv_fb_comment;

SELECT criterio_label, COUNT(*) AS n
FROM silver.sv_fb_comment_classification
GROUP BY 1 ORDER BY n DESC;

SELECT a.display_name, s.comment_count, s.troll_count
FROM silver.sv_actor_stats s
JOIN silver.sv_actor a USING (actor_id)
WHERE a.platform = 'facebook'
ORDER BY s.troll_count DESC LIMIT 10;
```

Redact PII in chat outputs.

## Limits

- Public pages only; private content returns errors
- Facebook returns up to ~3 posts per API page — pagination via `cursor`
- `user_id` depends on SociaVault response; fallback identity uses `name_only`
- Legacy CSV dumps in `data/landing/redes/data-fb/` are a **separate** pipeline

## Related

- Pipeline entry: [`scrape-sociavault`](../scrape-sociavault/SKILL.md)
- [`ingest-data-gold`](../ingest-data-gold/SKILL.md) · [`graph-ingest`](../graph-ingest/SKILL.md)
