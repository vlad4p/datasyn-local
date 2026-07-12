---
name: scrape-sociavault-tiktok
description: >-
  Scrape a public TikTok account via SociaVault: last N videos by date,
  all comments per selected video. MERGEs silver sv_tt_*. Use when the user
  asks to scrape TikTok with SociaVault.
---

# Scrape TikTok (SociaVault)

**Platform:** TikTok · **Schema:** `sv_tt_*`

## Count flag

| Flag | Default | Meaning |
|------|---------|---------|
| `--last N` | 10 | N most recent videos |
| `--max-videos N` | — | Alias for `--last` |

## Workflow

```bash
uv run python scripts/python/scrape/sociavault/scrape_sociavault_tiktok.py \
  --handle tiktok \
  --last 10 \
  --fetch-comments \
  --ingest-full

./scripts/sh/scrape_sociavault.sh tiktok myhandle --last 5 --fetch-comments
```

## Related

- [`scrape-sociavault`](../scrape-sociavault/SKILL.md)
