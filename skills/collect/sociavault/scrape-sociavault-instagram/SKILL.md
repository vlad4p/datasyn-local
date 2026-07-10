---
name: scrape-sociavault-instagram
description: >-
  Scrape a public Instagram account via SociaVault: last N posts by date,
  all comments per selected post. MERGEs silver sv_ig_*. Use when the user
  asks to scrape Instagram with SociaVault.
---

# Scrape Instagram (SociaVault)

**Platform:** Instagram · **Schema:** `sv_ig_*`

## Count flag

| Flag | Default | Meaning |
|------|---------|---------|
| `--last N` | 10 | N most recent posts |
| `--max-posts N` | — | Alias for `--last` |

## Workflow

```bash
uv run python scripts/python/scrape_sociavault_instagram.py \
  --handle instagram \
  --last 10 \
  --fetch-comments \
  --ingest-full

./scripts/sh/scrape_sociavault.sh instagram myhandle --last 5 --fetch-comments
```

## Related

- [`scrape-sociavault`](../scrape-sociavault/SKILL.md)
