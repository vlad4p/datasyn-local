# Collect

Fetch external data into `data/landing/` before ingest.

## Model-invoked

| Skill | When to use |
|-------|-------------|
| [`web-scraping`](web-scraping/SKILL.md) | Generic web fetch — HTML, APIs, files to landing |
| [`scrape-sociavault`](sociavault/scrape-sociavault/SKILL.md) | SociaVault pipeline entry — route by platform |
| [`scrape-twikit-twitter`](twikit/scrape-twikit-twitter/SKILL.md) | X/Twitter via twikit session (cookies/login) |

## Sub-scope: SociaVault

See [`sociavault/README.md`](sociavault/README.md).

| Platform | Skill |
|----------|-------|
| Facebook | [`scrape-sociavault-facebook`](sociavault/scrape-sociavault-facebook/SKILL.md) |
| Twitter/X | [`scrape-sociavault-twitter`](sociavault/scrape-sociavault-twitter/SKILL.md) |
| Instagram | [`scrape-sociavault-instagram`](sociavault/scrape-sociavault-instagram/SKILL.md) |
| TikTok | [`scrape-sociavault-tiktok`](sociavault/scrape-sociavault-tiktok/SKILL.md) |

## Sub-scope: Twikit

See [`twikit/README.md`](twikit/README.md).

| Platform | Skill |
|----------|-------|
| Twitter/X | [`scrape-twikit-twitter`](twikit/scrape-twikit-twitter/SKILL.md) |

## References

- [`references/landing-paths.md`](references/landing-paths.md) — landing folder conventions

After collect → use [`ingest-data`](../ingest/ingest-data/SKILL.md).
