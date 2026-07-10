---
name: scrape-twikit-twitter
description: >-
  Scrape a public X/Twitter account via twikit (session login/cookies): last N
  tweets, optional reply threads. Saves JSON/JSONL under
  data/landing/redes/twikit/twitter/. Use when the user asks to scrape Twitter/X
  with twikit (not SociaVault).
---

# Scrape Twitter / X (twikit)

**Library:** [twikit](https://twikit.readthedocs.io/en/latest/twikit.html) · **Landing:** `data/landing/redes/twikit/twitter/`

Alternative to SociaVault (`scrape-sociavault-twitter`). Uses a logged-in X session (cookies), not an API key.

## Auth

1. Copy vars from [`.env.example`](../../../../.env.example) into `.env` (never commit `.env`):

| Variable | Role |
|----------|------|
| `TWITTER_USERNAME` | Username / phone / email (`auth_info_1`) |
| `TWITTER_EMAIL` | Optional second factor (`auth_info_2`) |
| `TWITTER_PASSWORD` | Password |
| `TWITTER_TOTP_SECRET` | Optional 2FA TOTP secret |
| `TWITTER_COOKIES_PATH` | Cookies JSON (default `.data/twikit_cookies.json`) |

2. First run logs in and saves cookies; later runs load cookies and skip login when possible.

**Google-only accounts / Cloudflare 403:** programmatic login often fails. Export cookies from a browser session already logged into x.com into `.data/twikit_cookies.json`, then re-run the scraper (it loads cookies first and skips password login).

**Never commit** cookies, `.env`, or landing files — see [`data-privacy`](../../../engineering/data-privacy/SKILL.md).

## Known twikit breakage (Mar 2026)

datasyn uses the private fork [`rlyehlab/twikit-`](https://github.com/rlyehlab/twikit-) (`2.3.4`) with KEY_BYTE / User / tweet-detail fixes (see that repo’s `FORK.md`). Stock PyPI `twikit==2.3.3` is broken against current X.

## Flags

| Flag | Default | Meaning |
|------|---------|---------|
| `--last N` | 10 | Keep N most recent (when no date range) |
| `--since` / `--until` | — | Date window (`until` exclusive). July 2026: `--since 2026-07-01 --until 2026-08-01` |
| `--tweet-type` | `Tweets` | Timeline tab if `--no-search` |
| `--fetch-replies` | off | Fetch replies per tweet |
| `--max-replies` | 100 | Keep top N replies by likes after collecting |
| `--concurrency` | 3 | `asyncio.Semaphore` for reply fetches |
| `--ingest` | off | Bronze+silver → `bronze.tk_tw_*` / `silver.tk_tw_*` |

Date ranges use `search_tweet` (`from:handle since: until:`) by default; `--no-search` forces timeline pagination.

## Workflow

```bash
uv sync
# July 2026 + top ~100 replies + ingest
uv run python scripts/python/scrape_twikit_twitter.py \
  --handle myriambregman \
  --since 2026-07-01 --until 2026-08-01 \
  --fetch-replies --max-replies 100 --concurrency 3 \
  --ingest
```

**Landing:**

```
data/landing/redes/twikit/twitter/{slug}_{YYYYMMDD}/
  profile.json
  tweets.jsonl
  selected.json
  replies_{tweet_id}.jsonl   # if --fetch-replies
  manifest.json
```

**DuckDB:** `bronze.tk_tw_*` / `silver.tk_tw_profile|tweet|reply`

## Classify + hater narrative clusters

After ingest, batch-classify replies (efficient multi-comment LLM calls) and cluster haters:

```bash
uv sync --extra llm
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_tk_tw_classification.sql
uv run python scripts/python/classify_tk_tw_replies.py --batch-size 50 --cluster-haters
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_tk_hater_narrativa.sql
# Refresh silver.tw_users catalog (profile fields + is_hater) and HTML report
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_twitter_silver.sql
uv run python scripts/python/generate_tk_hater_clusters_report.py
```

| Table / view | Role |
|--------------|------|
| `silver.tk_tw_reply_classification` | Posición + resumen + `narrativa_raw` por reply |
| `gold.tk_hater_narrativa_cluster` | Catálogo de narrativas canónicas |
| `gold.tk_hater_narrativa_assignment` | reply → cluster |
| `gold.v_tk_hater_narrativa_*` | Resumen / por tweet / temporal |
| `silver.tw_users` | Catálogo de cuentas X (tracked + autores) con `is_hater` |
| `reports/twikit-myriam/hater-clusters/` | HTML interactivo (gitignored) |

Model: `CHAT_MODEL` or `LLM_MODEL` in `.env`.

## Limits

- Requires a real X account; rate limits / locks — ~1.2s + jitter between requests; concurrency ≤ 3 recommended
- Search/timeline may be incomplete vs full history
- “Top 100” replies = ranked among replies X returned, not guaranteed UI Top
- Never commit `.env`, cookies, or landing files

## Related

- [`scrape-sociavault-twitter`](../../sociavault/scrape-sociavault-twitter/SKILL.md) — paid API alternative
- [`web-scraping`](../../web-scraping/SKILL.md) — generic landing conventions
- [`data-privacy`](../../../engineering/data-privacy/SKILL.md)
