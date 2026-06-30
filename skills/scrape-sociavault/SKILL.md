---
name: scrape-sociavault
description: >-
  SociaVault social-scrape pipeline entry point. Routes to platform skills
  (Facebook, Twitter/X, Instagram, TikTok), scrapes by count (--last N),
  MERGE silver ingest, actor extraction, and LLM comment classification.
  Use when the user asks to scrape redes sociales or SociaVault accounts.
---

# SociaVault scrape pipeline

Unified pipeline for collecting public social media data via [SociaVault](https://docs.sociavault.com) into DuckDB. Scrapes by **count** (last N posts/tweets/videos), not by date range.

```
account URL/handle + --last N
       │
       ▼
┌──────────────────┐
│ scrape-sociavault│  ← route + validate
└────────┬─────────┘
         │
    ┌────┴────┬─────────┬─────────┐
    ▼         ▼         ▼         ▼
 facebook  twitter  instagram  tiktok
    │         │         │         │
    ▼         ▼         ▼         ▼
 paginate → sort by date → take N → fetch all comments/replies
    │         │         │         │
    ▼         ▼         ▼         ▼
 bronze.sv_*  →  silver.sv_* (MERGE)  →  sv_actor  →  LLM classify
```

## Platform skills

| Platform | Skill | Script |
|----------|-------|--------|
| Facebook | [`scrape-sociavault-facebook`](../scrape-sociavault-facebook/SKILL.md) | `scrape_sociavault_facebook.py` |
| Twitter/X | [`scrape-sociavault-twitter`](../scrape-sociavault-twitter/SKILL.md) | `scrape_sociavault_twitter.py` |
| Instagram | [`scrape-sociavault-instagram`](../scrape-sociavault-instagram/SKILL.md) | `scrape_sociavault_instagram.py` |
| TikTok | [`scrape-sociavault-tiktok`](../scrape-sociavault-tiktok/SKILL.md) | `scrape_sociavault_tiktok.py` |

## Count limits (`--last N`)

| User request | CLI |
|--------------|-----|
| últimos 10 tweets | `--last 10` (default if omitted: 10) |
| últimos 3 posts de FB | `--last 3` or `--max-posts 3` |
| últimos 20 videos TikTok | `--last 20` or `--max-videos 20` |

Implemented in [`scripts/python/sociavault_limits.py`](../../scripts/python/sociavault_limits.py):

1. Paginate API until no cursor
2. Dedupe by platform ID
3. Sort by publish timestamp DESC
4. Take first N → `selected.json`
5. Fetch **all** comments/replies for selected items only

## Decision flow

1. **Auth** — `SOCIAVAULT_API_KEY` + `LLM_API_KEY` in `.env`
2. **Credits** — estimate: profile + pagination + enrich (Twitter) + comments
3. **Route** — pick platform skill
4. **Collect** — handle/URL, `--last N`, fetch comments/replies
5. **Execute** with `--ingest-full` or shell wrapper
6. **Validate** via MCP

## Example

```bash
uv run python scripts/python/scrape_sociavault_twitter.py \
  --handle myriambregman \
  --last 10 \
  --fetch-replies \
  --ingest-full
```

Shell wrapper (default `--last 10`):

```bash
./scripts/sh/scrape_sociavault.sh twitter myriambregman --last 10 --fetch-replies
```

## Shared infrastructure

| Component | Path |
|-----------|------|
| API client | [`scripts/python/sociavault_client.py`](../../scripts/python/sociavault_client.py) |
| Count limits | [`scripts/python/sociavault_limits.py`](../../scripts/python/sociavault_limits.py) |
| Scrape helpers | [`scripts/python/sociavault_scrape_common.py`](../../scripts/python/sociavault_scrape_common.py) |
| Orchestrator | [`scripts/sh/scrape_sociavault.sh`](../../scripts/sh/scrape_sociavault.sh) |

## Related

- [`web-scraping`](../web-scraping/SKILL.md) · [`ingest-data`](../ingest-data/SKILL.md)
