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

**Never commit** cookies, `.env`, or landing files — see [`data-privacy`](../../../engineering/data-privacy/SKILL.md).

## Count flag

| Flag | Default | Meaning |
|------|---------|---------|
| `--last N` | 10 | Keep N most recent tweets (by `created_at`) from timeline pages |
| `--tweet-type` | `Tweets` | `Tweets` / `Replies` / `Media` / `Likes` |
| `--fetch-replies` | off | Paginate replies per selected tweet via `get_tweet_by_id` |

## Workflow

```bash
uv sync
uv run python scripts/python/scrape_twikit_twitter.py \
  --handle myriambregman \
  --last 10 \
  --fetch-replies
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

## Limits

- Requires a real X account; risk of rate limits / locks — sleep ~1s between pages
- Timeline pagination is best-effort; pinned tweets / RTs may appear in the pool
- Replies via tweet detail are incomplete vs `reply_count` (X UI limitation)
- Landing only — bronze/silver ingest for twikit is a separate follow-up (SociaVault uses `sv_tw_*`)

## Related

- [`scrape-sociavault-twitter`](../../sociavault/scrape-sociavault-twitter/SKILL.md) — paid API alternative
- [`web-scraping`](../../web-scraping/SKILL.md) — generic landing conventions
- [`data-privacy`](../../../engineering/data-privacy/SKILL.md)
