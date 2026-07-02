# Legacy redes CSV dumps (Facebook + Twitter)

External CSV exports under `data/landing/redes/`. **Separate** from SociaVault (`sv_*`).

| Platform | Landing path | Bronze SQL | Silver SQL |
|----------|--------------|------------|------------|
| Facebook | `data/landing/redes/data-fb/` | `scripts/sql/ingest_fb_redes.sql` | `scripts/sql/ingest_fb_silver.sql` |
| Twitter/X | `data/landing/redes/data-tw/` | `scripts/sql/ingest_twitter.sql` | `scripts/sql/ingest_twitter_silver.sql` |

```bash
uv run python scripts/python/db.py mcp-stop
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_twitter.sql
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_twitter_silver.sql
```

Dictionary files (`Diccionario de Datos y Aclaraciones.txt`) are **not** ingested.

---

## Twitter (`tw_*`)

### Bronze

| Table | Source CSV | Key columns |
|-------|------------|-------------|
| `bronze.tw_users` | `users.csv` | `username`, `user_id` — 4 tracked accounts |
| `bronze.tw_tweets` | `tweets.csv` | `user_id`, `text`, `raw_data` — originals only |
| `bronze.tw_tweets_replies` | `tweets_replies.csv` | `user_id`, `inReplyToTweetIdStr`, `raw_data` |
| `bronze.tw_comments_classification` | `comments_classification.csv` | `post_id`, `comment_id`, `free_criteria` |

Bronze replies have **no `username` column** — only `user_id` and `raw_data` JSON.

### Silver

| Table | Username / handle columns | Notes |
|-------|---------------------------|-------|
| `silver.tw_users` | **`username`** | Tracked accounts (Myriam, Del Caño, PTS, Izquierda Diario) |
| `silver.tw_tweets` | **`author_username`** | Join from `tw_users` on tweet `user_id` |
| `silver.tw_tweets_replies` | **`author_username`**, **`parent_author_username`** | Reply author from `raw_data → $.user.username`; parent from `tw_users` join |
| `silver.tw_comments_classification` | **`reply_author_username`**, **`parent_author_username`** | Joins to replies + parent tweet |

### Classification codes (`free_criteria`)

| Code | Label (`criteria_label`) |
|------|--------------------------|
| `1` | `apoyo_izquierda` |
| `2` | `derecha_o_troll` |
| `3` | `neutral` |
| `1,2` | `ambiguo` |
| `INCLASIFICABLE` | `inclasificable` |

Classifications cover replies on the **top-10 tweets by reply volume** per tracked account (partial sample).

### Example queries

```sql
-- Top troll accounts replying to Myriam (no raw_data parsing needed)
SELECT
  r.author_username,
  COUNT(*) AS comentarios_negativos,
  SUM(r.like_count) AS likes_totales
FROM silver.tw_comments_classification c
JOIN silver.tw_tweets_replies r ON c.reply_tweet_id = r.tweet_id
WHERE c.parent_author_username = 'myriambregman'
  AND c.criteria_label = 'derecha_o_troll'
GROUP BY 1
ORDER BY comentarios_negativos DESC, likes_totales DESC;
```

---

## Facebook (`fb_*`)

| Table | User handle column |
|-------|-------------------|
| `silver.fb_fanpage` | **`descripcion`** (page name, not user handle) |
| `silver.fb_comment` | **`user_name`** (comment author; often sparse in source) |
| `silver.fb_comment_classification` | no author column — join to `silver.fb_comment` |

Facebook does **not** use `username`; the equivalent is `user_name`.

---

## SociaVault vs legacy

| | Legacy `tw_*` / `fb_*` | SociaVault `sv_*` |
|--|------------------------|-------------------|
| Source | External CSV dump | Scrape via SociaVault API |
| Reply author | `silver.tw_tweets_replies.author_username` (from `raw_data`) | `silver.sv_tw_reply.username` |
| Actors graph | not built | `silver.sv_actor`, `silver.sv_actor_stats` |

Do not mix tables across pipelines without explicit joins on platform + user id.
