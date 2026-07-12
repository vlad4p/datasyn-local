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
uv run python scripts/python/scrape/twikit/scrape_twikit_twitter.py \
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

## Enrich profiles (bio, metrics, posts, followers/following)

For top haters **or** top supporters (apoyo), fetch full profile + recent posts + follower/following lists with conservative rate limits:

```bash
uv run python scripts/python/db.py mcp-stop
# Haters (default role)
uv run python scripts/python/scrape/twikit/enrich_twikit_profiles.py --top-haters 10 \
  --max-posts 100 --max-follows 2000 --ingest
# Scoped to one target (avoids mixing multi-account tops):
uv run python scripts/python/scrape/twikit/enrich_twikit_profiles.py --top-haters 75 \
  --target-username NicolasdelCano --max-posts 100 --max-follows 2000 --ingest
# Apoyo / defensores (separate landing + silver tables)
uv run python scripts/python/scrape/twikit/enrich_twikit_profiles.py --role apoyo --top-supporters 30 \
  --max-posts 100 --max-follows 2000 --ingest
# or: --handles capibara_mood,CCDeville88
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--role` | `hater` | `hater` or `apoyo` (landing + ingest target) |
| `--top-haters N` | — | Rank from `silver.tk_tw_user` by `hater_replies_count` |
| `--top-supporters N` | — | Rank by `apoyo_replies_count` (forces `role=apoyo`) |
| `--target-username` | — | Scope top-N to replies on this target account (e.g. `NicolasdelCano`) |
| `--handles a,b` | — | Explicit list (overrides top-N) |
| `--max-posts` | 100 | Recent tweets per profile |
| `--max-follows` | 2000 | Cap per followers/following list (over → IDs-only) |
| `--min-delay` | 3 | Seconds between API calls (+ jitter) |
| `--profile-pause` | 35 | Pause between profiles |
| `--ingest` | off | Bronze+silver via role-specific SQL |

**Landing (haters):** `data/landing/redes/twikit/profiles/{slug}_{YYYYMMDD}/`  
**Landing (apoyo):** `data/landing/redes/twikit/profiles/apoyo/{slug}_{YYYYMMDD}/`

| Role | Tables |
|------|--------|
| hater | `silver.tk_tw_profile_enriched`, `tk_tw_profile_post`, `tk_tw_follow_edge` |
| apoyo | `silver.tk_tw_profile_enriched_apoyo`, `tk_tw_profile_post_apoyo`, `tk_tw_follow_edge_apoyo` |

Checkpoint: if a profile folder already has all five files for today, that handle is skipped (safe resume).

After apoyo enrich:

```bash
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/twikit/ingest_tk_apoyo_profile_graph.sql
```

## Classify + narrative clusters (haters and apoyo)

After ingest, batch-classify replies (efficient multi-comment LLM calls) and cluster narratives:

```bash
uv sync --extra llm
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/twikit/ingest_tk_tw_classification.sql
uv run python scripts/python/classify/classify_tk_tw_replies.py --batch-size 50 --cluster-haters
uv run python scripts/python/classify/classify_tk_tw_replies.py --cluster-only --cluster-apoyo
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/twikit/ingest_tk_hater_narrativa.sql
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/twikit/ingest_tk_apoyo_narrativa.sql
# Refresh silver.tk_tw_user catalog (is_hater + is_supporter)
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/twikit/ingest_twikit_twitter_silver.sql
uv run python scripts/python/reports/generate_tk_hater_clusters_report.py
```

| Table / view | Role |
|--------------|------|
| `silver.tk_tw_reply_classification` | Posición + resumen + `narrativa_raw` por reply |
| `gold.tk_hater_narrativa_*` / `v_tk_hater_narrativa_*` | Clusters hostiles (`derecha_o_troll`) |
| `gold.tk_apoyo_narrativa_*` / `v_tk_apoyo_narrativa_*` | Clusters de apoyo (`apoyo_izquierda`) |
| `silver.tk_tw_user` | Catálogo con `is_hater` + `is_supporter` |
| `reports/twikit-myriam/hater-clusters/` | HTML interactivo (gitignored) |

## Troll blacklist (manual block list)

Auditable `block` / `watch` list from reply behaviour + enriched risk (no auto-block on X):

```bash
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/twikit/ingest_tk_troll_blacklist.sql
uv run python scripts/python/reports/generate_tk_troll_blacklist_report.py
```

See skill [`troll-blacklist`](../../../analyze/reports/troll-blacklist/SKILL.md).

Model: `CHAT_MODEL` or `LLM_MODEL` in `.env`.

## Limits

- Requires a real X account; rate limits / locks — ~1.2s + jitter between requests; concurrency ≤ 3 recommended
- Search/timeline may be incomplete vs full history
- “Top 100” replies = ranked among replies X returned, not guaranteed UI Top
- Never commit `.env`, cookies, or landing files

## Related

- [`troll-blacklist`](../../../analyze/reports/troll-blacklist/SKILL.md) — block/watch export
- [`twitter-legacy-to-twikit.md`](../../../ingest/references/twitter-legacy-to-twikit.md) — legacy mapping
- [`web-scraping`](../../web-scraping/SKILL.md) — generic landing conventions
- [`data-privacy`](../../../engineering/data-privacy/SKILL.md)
