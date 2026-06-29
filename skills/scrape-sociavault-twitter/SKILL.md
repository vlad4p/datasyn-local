---
name: scrape-sociavault-twitter
description: >-
  Scrape a public X/Twitter account via SociaVault API: profile, tweets,
  and replies. Saves JSON to data/landing/redes/sociavault/twitter/ and
  ingests to bronze.sv_tw_* / silver.sv_tw_* tables. Use when the user
  asks to scrape Twitter or X with SociaVault.
---

# Scrape Twitter / X (SociaVault)

**Platform:** X (Twitter) · **Source:** [SociaVault API](https://docs.sociavault.com/platforms/twitter) · **Schema:** parallel `sv_tw_*` (not legacy `tw_*` CSV dumps)

## Prerequisites

1. `SOCIAVAULT_API_KEY` in `.env`
2. Public handle (with or without `@`)
3. Follow **`data-privacy`**

## SociaVault endpoints

| Step | Endpoint | Credits |
|------|----------|---------|
| Profile | `GET /v1/scrape/twitter/profile?handle=` | ~1 |
| Tweets | `GET /v1/scrape/twitter/user-tweets?handle=` | ~1 |
| Replies | `GET /v1/scrape/twitter/tweet/replies?url=` | ~1/page |

Docs: [User Tweets](https://docs.sociavault.com/api-reference/twitter/user-tweets)

## Workflow

1. **Confirm** handle and whether to fetch replies (`--fetch-replies`)
2. **Scrape:**

```bash
uv run python scripts/python/scrape_sociavault_twitter.py \
  --handle levelsio \
  --fetch-replies
```

3. **Landing output:**

```
data/landing/redes/sociavault/twitter/{slug}_{YYYYMMDD}/
  profile.json
  tweets.json
  replies_{tweet_id}.jsonl
  manifest.json
```

4. **Ingest:**

```bash
uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_twitter.sql
uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_twitter_silver.sql
```

## DuckDB tables

| Zone | Tables |
|------|--------|
| Bronze | `bronze.sv_tw_profile`, `bronze.sv_tw_tweet`, `bronze.sv_tw_reply` |
| Silver | `silver.sv_tw_profile`, `silver.sv_tw_tweet`, `silver.sv_tw_reply` |

## Validation

```sql
SELECT COUNT(*) FROM silver.sv_tw_tweet;
SELECT COUNT(*) FROM silver.sv_tw_reply;
SELECT tweet_id, LEFT(text, 80) FROM silver.sv_tw_tweet LIMIT 3;
```

## Limits

- **Incomplete replies:** X APIs often return a subset of replies (same limitation documented in legacy [`data-tw` dictionary](../../data/landing/redes/data-tw/Diccionario%20de%20Datos%20y%20Aclaraciones.txt)). Document `reply_count` vs actual fetched rows in reports.
- `user-tweets` surfaces ~100 most popular tweets, not necessarily most recent
- Do not merge into legacy `bronze.tw_*` tables

## Related

- [`scrape-sociavault`](../scrape-sociavault/SKILL.md) · [`ingest-data-silver`](../ingest-data-silver/SKILL.md)
