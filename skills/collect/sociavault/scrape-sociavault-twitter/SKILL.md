---
name: scrape-sociavault-twitter
description: >-
  DEPRECATED for Twitter/X. Prefer scrape-twikit-twitter. Historical SociaVault
  Twitter scrape docs (sv_tw_*). Use only if explicitly asked for SociaVault Twitter.
---

# Scrape Twitter / X (SociaVault) — DEPRECATED

> **Deprecated.** Canonical Twitter/X pipeline is **twikit**:
> [`scrape-twikit-twitter`](../../twikit/scrape-twikit-twitter/SKILL.md).
> Legacy CSV `tw_*` tables are also retired — see
> [`twitter-legacy-to-twikit.md`](../../../ingest/references/twitter-legacy-to-twikit.md).

**Platform:** X (Twitter) · **Schema:** `sv_tw_*` (historical; may not exist in DB)

## Count flag

| Flag | Default | Meaning |
|------|---------|---------|
| `--last N` | 10 | Keep N most recent tweets (sorted by `created_at` from API pool) |
| `--max-tweets N` | — | Alias for `--last` |

## SociaVault endpoints

| Step | Endpoint | Credits |
|------|----------|---------|
| Profile | `twitter/profile?handle=` | ~1 |
| Tweets pool | `twitter/user-tweets?handle=&trim=false` | ~1/page |
| Tweet detail | `twitter/tweet?url=` | ~1/tweet (default `--enrich`) |
| Replies | `twitter/comments?pid=` | ~1/page (all pages) |

## Workflow

```bash
uv run python scripts/python/scrape_sociavault_twitter.py \
  --handle myriambregman \
  --last 10 \
  --fetch-replies \
  --ingest-full

./scripts/sh/scrape_sociavault.sh twitter myriambregman --last 10 --fetch-replies
```

**Landing:**

```
data/landing/redes/sociavault/twitter/{slug}_{YYYYMMDD}/
  profile.json
  tweets.jsonl          # raw API pages
  selected.json         # last N tweets after sort
  tweet_detail_{id}.json
  replies_{tweet_id}.jsonl
  manifest.json         # api_pool_size, selected_count, reply_stats
```

## DuckDB tables

| Zone | Tables |
|------|--------|
| Bronze | `sv_tw_profile`, `sv_tw_tweet`, `sv_tw_tweet_selected`, `sv_tw_tweet_detail`, `sv_tw_reply` |
| Silver | `silver.sv_tw_*` (MERGE) |

## Validation

```sql
SELECT COUNT(*) FROM silver.sv_tw_tweet;
SELECT tweet_id, created_at, reply_count
FROM silver.sv_tw_tweet ORDER BY created_at_ts DESC LIMIT 10;
SELECT COUNT(*) FROM silver.sv_tw_reply;
```

## Limits

- **`user-tweets` returns ~100 popular tweets**, not full history — "last N" is best-effort among that pool
- Replies often incomplete vs `reply_count` (X API limitation)
- Use `--no-enrich` to skip per-tweet detail calls (saves credits)
- Prefer **twikit** for Twitter/X: [`scrape-twikit-twitter`](../../twikit/scrape-twikit-twitter/SKILL.md)
- Legacy CSV `tw_*` tables are **retired**

## Related

- [`scrape-twikit-twitter`](../../twikit/scrape-twikit-twitter/SKILL.md) — canonical Twitter pipeline
- [`scrape-sociavault`](../scrape-sociavault/SKILL.md)
