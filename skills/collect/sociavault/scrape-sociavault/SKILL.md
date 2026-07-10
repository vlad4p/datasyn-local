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

Sub-scope index: [`../README.md`](../README.md)

## Platform skills

| Platform | Skill | Script |
|----------|-------|--------|
| Facebook | [`scrape-sociavault-facebook`](../scrape-sociavault-facebook/SKILL.md) | `scrape_sociavault_facebook.py` |
| Twitter/X | [`scrape-sociavault-twitter`](../scrape-sociavault-twitter/SKILL.md) | `scrape_sociavault_twitter.py` |
| Instagram | [`scrape-sociavault-instagram`](../scrape-sociavault-instagram/SKILL.md) | `scrape_sociavault_instagram.py` |
| TikTok | [`scrape-sociavault-tiktok`](../scrape-sociavault-tiktok/SKILL.md) | `scrape_sociavault_tiktok.py` |

## References

- [`references/count-limits.md`](references/count-limits.md) — `--last N` behavior
- [`references/infrastructure.md`](references/infrastructure.md) — shared scripts and examples

## Decision flow

1. **Auth** — `SOCIAVAULT_API_KEY` + `LLM_API_KEY` in `.env`
2. **Credits** — estimate: profile + pagination + enrich (Twitter) + comments
3. **Route** — pick platform skill
4. **Collect** — handle/URL, `--last N`, fetch comments/replies
5. **Execute** with `--ingest-full` or shell wrapper
6. **Validate** via MCP

## Related

- [`web-scraping`](../../web-scraping/SKILL.md) · [`ingest-data`](../../../ingest/ingest-data/SKILL.md)
