# Legacy Twitter (`tw_*`) → twikit (`tk_tw_*`)

Legacy CSV dumps (`data/landing/redes/data-tw/`) are **retired**.  
Twitter/X data now lives only in the **twikit** pipeline.

| Legacy | Twikit equivalent | Notes |
|--------|-------------------|-------|
| `bronze/silver.tw_tweets` | `bronze/silver.tk_tw_tweet` | Posts of tracked accounts |
| `bronze/silver.tw_tweets_replies` | `bronze/silver.tk_tw_reply` | Replies under selected tweets |
| `bronze/silver.tw_users` | `silver.tk_tw_user` (+ `tk_tw_profile`, `tk_tw_profile_enriched`) | Catalog twikit-only |
| `bronze/silver.tw_comments_classification` | `silver.tk_tw_reply_classification` | LLM labels (`criterio_label`) |

## Column coverage

### Profiles / users

| Legacy `tw_users` | Twikit | Covered? |
|-------------------|--------|----------|
| `user_id`, `username`, `display_name` | `tk_tw_profile` / `tk_tw_user` | Yes |
| `followers_count`, `following_count`, `statuses_count` | profile / enriched | Yes (full on tracked + enriched) |
| `bio` / `description` | `description` / `bio` | Yes |
| `location`, `account_created_at`, verified flags | `tk_tw_profile_enriched` | Yes (enriched subset) |
| `is_hater`, `hater_replies_count` | `tk_tw_user` from classification | Yes (twikit-only signal) |
| `is_pts`, `track`, `is_diputado` | — | **No** (legacy flags; use `gold.v_cuentas_trackeadas` for PTS handles) |
| `listed_count`, `media_count`, `favourites_count` | enriched | Partial (enriched only) |
| `source` mix (`legacy_reply` / `twikit`) | always `twikit` | N/A |

### Tweets / replies

| Legacy | Twikit | Covered? |
|--------|--------|----------|
| tweet text, metrics, timestamps | `tk_tw_tweet` | Yes |
| reply text, author, parent id | `tk_tw_reply` | Yes |
| `raw_data` JSON blob | landing JSONL | Yes (landing), not mirrored as silver JSON column |
| classification labels | `tk_tw_reply_classification` | Yes (`criterio_label`, `resumen`, `narrativa_raw`) |

### Not in twikit (by design)

- Legacy snscrape-style full `raw_data.user` on every reply (sparse authors get id/username/name only until enrich).
- Cross-platform `network_profile` Twitter half (retired; FB-only).
- Gold redes `v_comentarios_clasificados` Twitter half (retired; use `gold.v_tk_hater_*` / `gold.tk_troll_blacklist`).

## Pipelines

| Task | Script / skill |
|------|----------------|
| Scrape + silver | `scrape-twikit-twitter` → `ingest_twikit_twitter_silver.sql` |
| Classify replies | `classify_tk_tw_replies.py` + `ingest_tk_tw_classification.sql` |
| Enrich profiles | `enrich_twikit_profiles.py` + `ingest_twikit_profiles.sql` |
| Hater narrativa | `ingest_tk_hater_narrativa.sql` |
| Troll blacklist | `ingest_tk_troll_blacklist.sql` + skill `troll-blacklist` |
| Drop legacy tables | `scripts/sql/ops/drop_legacy_twitter.sql` |
