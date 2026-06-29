---
name: scrape-sociavault
description: >-
  SociaVault social-scrape pipeline entry point. Routes to platform skills
  (Facebook, Twitter/X, Instagram, TikTok), checks API key and credits,
  saves raw JSON to landing, and ingests bronze/silver sv_* tables. Use
  when the user asks to scrape redes sociales, SociaVault, or multi-platform
  social media collection.
---

# SociaVault scrape pipeline

Unified pipeline for collecting public social media data via [SociaVault](https://docs.sociavault.com) into DuckDB. Raw JSON lands in `data/landing/redes/sociavault/`; parallel `sv_*` schemas keep SociaVault data separate from legacy CSV dumps.

```
account URL/handle
       │
       ▼
┌──────────────────┐
│ scrape-sociavault│  ← this skill (route + validate)
└────────┬─────────┘
         │
    ┌────┴────┬─────────┬─────────┐
    ▼         ▼         ▼         ▼
 facebook  twitter  instagram  tiktok   ← platform skills
    │         │         │         │
    ▼         ▼         ▼         ▼
 landing/  landing/  landing/  landing/
    │         │         │         │
    ▼         ▼         ▼         ▼
 bronze.sv_*  →  silver.sv_*  →  gold / reports
```

## Platform skills

| Platform | Skill | Script |
|----------|-------|--------|
| Facebook | [`scrape-sociavault-facebook`](../scrape-sociavault-facebook/SKILL.md) | `scrape_sociavault_facebook.py` |
| Twitter/X | [`scrape-sociavault-twitter`](../scrape-sociavault-twitter/SKILL.md) | `scrape_sociavault_twitter.py` |
| Instagram | [`scrape-sociavault-instagram`](../scrape-sociavault-instagram/SKILL.md) | `scrape_sociavault_instagram.py` |
| TikTok | [`scrape-sociavault-tiktok`](../scrape-sociavault-tiktok/SKILL.md) | `scrape_sociavault_tiktok.py` |

## Decision flow

1. **Auth** — verify `SOCIAVAULT_API_KEY` in `.env` (see [`.env.example`](../../.env.example)). Never commit `.env`.
2. **Credits** (optional) — check balance before large runs:

```bash
# via Python
uv run python -c "
from scripts.python.sociavault_client import SociaVaultClient
print(SociaVaultClient().get_credits())
"
```

3. **Route** — pick platform skill from user request
4. **Collect inputs** — URL/handle, `--max-posts` / `--max-videos`, fetch comments/replies flag
5. **Estimate cost** — profile (1) + pagination pages + comments per post/tweet/video
6. **Execute** platform scrape script
7. **Ingest** — bronze SQL then silver SQL (or `--ingest` flag on script)
8. **Validate** via MCP:

```sql
SELECT 'sv_fb_post' AS t, COUNT(*) FROM silver.sv_fb_post
UNION ALL SELECT 'sv_tw_tweet', COUNT(*) FROM silver.sv_tw_tweet
UNION ALL SELECT 'sv_ig_post', COUNT(*) FROM silver.sv_ig_post
UNION ALL SELECT 'sv_tt_video', COUNT(*) FROM silver.sv_tt_video;
```

## Shared infrastructure

| Component | Path |
|-----------|------|
| API client | [`scripts/python/sociavault_client.py`](../../scripts/python/sociavault_client.py) |
| Scrape helpers | [`scripts/python/sociavault_scrape_common.py`](../../scripts/python/sociavault_scrape_common.py) |
| Run pointer | `data/landing/redes/sociavault/{platform}/_current_run.json` |
| Bronze SQL | `scripts/sql/ingest_sociavault_{platform}.sql` |
| Silver SQL | `scripts/sql/ingest_sociavault_{platform}_silver.sql` |

## Multi-platform run

Run each platform separately (separate credits and landing folders):

```bash
uv run python scripts/python/scrape_sociavault_facebook.py --url "..." --fetch-comments
uv run python scripts/python/scrape_sociavault_twitter.py --handle "..." --fetch-replies
uv run python scripts/python/scrape_sociavault_instagram.py --handle "..." --fetch-comments
uv run python scripts/python/scrape_sociavault_tiktok.py --handle "..." --fetch-comments
```

Then ingest each platform's SQL pair.

## Default scrape depth

Per plan: **profile + posts/tweets/videos + comments/replies**. Pass `--fetch-comments` or `--fetch-replies` on platform scripts.

## Privacy and git safety

- Landing JSON, manifest, and DuckDB stay **gitignored** — see **`data-privacy`**
- Commit only skills, SQL, and Python helpers
- Chat: aggregates + `LIMIT 3` samples with PII redaction

## Legacy vs SociaVault data

| Source | Landing | Bronze prefix |
|--------|---------|---------------|
| Internal CSV dumps | `data/landing/redes/data-fb/`, `data-tw/` | `fb_*`, `tw_*` |
| SociaVault API | `data/landing/redes/sociavault/` | `sv_*` |

Do **not** merge into legacy tables in v1. Cross-source analysis can join in gold layer later.

## After silver

- [`ingest-data-gold`](../ingest-data-gold/SKILL.md) — KPIs, daily summaries
- [`sentiment-analysis`](../sentiment-analysis/SKILL.md) — text on `mensaje`/`text`/`caption` columns
- [`graph-ingest`](../graph-ingest/SKILL.md) — co-occurrence from entity links

## Errors

| HTTP | Action |
|------|--------|
| 401 | Fix `SOCIAVAULT_API_KEY` in `.env` |
| 402 | Stop run; report required vs available credits |
| 400 | Check URL/handle format; page may be private |

## Related

- Generic web scrape (non-API): [`web-scraping`](../web-scraping/SKILL.md)
- Medallion ingest: [`ingest-data`](../ingest-data/SKILL.md)
