# SociaVault sub-scope

Social media collection via [SociaVault](https://docs.sociavault.com) API.

**Router:** [`scrape-sociavault`](scrape-sociavault/SKILL.md)

## Platform skills

| Platform | Skill | Script |
|----------|-------|--------|
| Facebook | [`scrape-sociavault-facebook`](scrape-sociavault-facebook/SKILL.md) | `scrape_sociavault_facebook.py` |
| Twitter/X | [`scrape-sociavault-twitter`](scrape-sociavault-twitter/SKILL.md) | `scrape_sociavault_twitter.py` |
| Instagram | [`scrape-sociavault-instagram`](scrape-sociavault-instagram/SKILL.md) | `scrape_sociavault_instagram.py` |
| TikTok | [`scrape-sociavault-tiktok`](scrape-sociavault-tiktok/SKILL.md) | `scrape_sociavault_tiktok.py` |

## Key conventions

- Scrape by **count** (`--last N`), not date range
- Auth: `SOCIAVAULT_API_KEY` + `LLM_API_KEY` in `.env`
- Landing: `data/landing/redes/sociavault/<platform>/`
- Pipeline: bronze `sv_*` → silver `sv_*` (MERGE) → actors → LLM classify

## References

- [`references/count-limits.md`](references/count-limits.md) — `--last N` behavior
- [`references/infrastructure.md`](references/infrastructure.md) — shared Python/shell scripts
