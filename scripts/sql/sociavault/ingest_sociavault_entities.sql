-- SociaVault social actors - extract identities from silver sv_* tables MERGE
-- Requires silver ingest first
-- Uso: uv run python scripts/python/db.py run-sql --file scripts/sql/sociavault/ingest_sociavault_entities.sql

CREATE SCHEMA IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS silver.sv_fb_comment (
  comment_id VARCHAR, post_id VARCHAR, user_id VARCHAR, user_name VARCHAR,
  user_url VARCHAR, comentario VARCHAR, like_count BIGINT, fecha_comentario VARCHAR,
  fecha_comentario_ts TIMESTAMP, platform VARCHAR, ingested_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS silver.sv_fb_profile (
  page_id VARCHAR, name VARCHAR, url VARCHAR, like_count BIGINT, follower_count BIGINT,
  category VARCHAR, page_intro VARCHAR, platform VARCHAR, ingested_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS silver.sv_ig_comment (
  comment_id VARCHAR, post_id VARCHAR, user_id VARCHAR, user_name VARCHAR,
  user_url VARCHAR, comentario VARCHAR, like_count BIGINT, fecha_comentario VARCHAR,
  fecha_comentario_ts TIMESTAMP, platform VARCHAR, ingested_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS silver.sv_ig_profile (
  user_id VARCHAR, username VARCHAR, full_name VARCHAR, follower_count BIGINT,
  media_count BIGINT, platform VARCHAR, ingested_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS silver.sv_tt_comment (
  comment_id VARCHAR, video_id VARCHAR, user_id VARCHAR, user_name VARCHAR,
  comentario VARCHAR, like_count BIGINT, fecha_comentario VARCHAR,
  fecha_comentario_ts TIMESTAMP, platform VARCHAR, ingested_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS silver.sv_tt_profile (
  user_id VARCHAR, handle VARCHAR, nickname VARCHAR, follower_count BIGINT,
  video_count BIGINT, platform VARCHAR, ingested_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS silver.sv_tw_reply (
  reply_id VARCHAR, in_reply_to_tweet_id_str VARCHAR, text VARCHAR, username VARCHAR,
  user_id VARCHAR, user_name VARCHAR, like_count BIGINT, created_at VARCHAR,
  created_at_ts TIMESTAMP, platform VARCHAR, ingested_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS silver.sv_tw_profile (
  user_id VARCHAR, username VARCHAR, display_name VARCHAR, followers_count BIGINT,
  platform VARCHAR, ingested_at TIMESTAMP
);

-- Unified actor staging from all platforms
CREATE OR REPLACE TEMP TABLE staging_sv_actor AS
WITH sources AS (
  -- Facebook comment authors
  SELECT
    'facebook' AS platform,
    user_id AS external_user_id,
    user_name AS display_name,
    NULL AS handle,
    user_url AS profile_url,
    CASE WHEN user_id IS NOT NULL AND TRIM(user_id) != '' THEN 'id' ELSE 'name_only' END AS identity_confidence,
    COALESCE(fecha_comentario_ts, ingested_at) AS seen_at
  FROM silver.sv_fb_comment
  WHERE user_id IS NOT NULL OR user_name IS NOT NULL

  UNION ALL

  -- Facebook page profiles
  SELECT
    'facebook' AS platform,
    page_id AS external_user_id,
    name AS display_name,
    NULL AS handle,
    url AS profile_url,
    'id' AS identity_confidence,
    ingested_at AS seen_at
  FROM silver.sv_fb_profile

  UNION ALL

  -- Instagram comment authors
  SELECT
    'instagram' AS platform,
    user_id AS external_user_id,
    user_name AS display_name,
    user_name AS handle,
    user_url AS profile_url,
    CASE WHEN user_id IS NOT NULL AND TRIM(user_id) != '' THEN 'id' ELSE 'name_only' END AS identity_confidence,
    COALESCE(fecha_comentario_ts, ingested_at) AS seen_at
  FROM silver.sv_ig_comment
  WHERE user_id IS NOT NULL OR user_name IS NOT NULL

  UNION ALL

  SELECT
    'instagram' AS platform,
    user_id AS external_user_id,
    full_name AS display_name,
    username AS handle,
    NULL AS profile_url,
    'id' AS identity_confidence,
    ingested_at AS seen_at
  FROM silver.sv_ig_profile

  UNION ALL

  -- TikTok comment authors
  SELECT
    'tiktok' AS platform,
    user_id AS external_user_id,
    user_name AS display_name,
    user_name AS handle,
    NULL AS profile_url,
    CASE WHEN user_id IS NOT NULL AND TRIM(user_id) != '' THEN 'id' ELSE 'name_only' END AS identity_confidence,
    COALESCE(fecha_comentario_ts, ingested_at) AS seen_at
  FROM silver.sv_tt_comment
  WHERE user_id IS NOT NULL OR user_name IS NOT NULL

  UNION ALL

  SELECT
    'tiktok' AS platform,
    user_id AS external_user_id,
    nickname AS display_name,
    handle AS handle,
    NULL AS profile_url,
    'id' AS identity_confidence,
    ingested_at AS seen_at
  FROM silver.sv_tt_profile

  UNION ALL

  -- Twitter reply authors
  SELECT
    'twitter' AS platform,
    user_id AS external_user_id,
    COALESCE(user_name, username) AS display_name,
    username AS handle,
    NULL AS profile_url,
    CASE WHEN user_id IS NOT NULL AND TRIM(user_id) != '' THEN 'id' ELSE 'name_only' END AS identity_confidence,
    COALESCE(created_at_ts, ingested_at) AS seen_at
  FROM silver.sv_tw_reply
  WHERE user_id IS NOT NULL OR username IS NOT NULL OR user_name IS NOT NULL

  UNION ALL

  SELECT
    'twitter' AS platform,
    user_id AS external_user_id,
    display_name AS display_name,
    username AS handle,
    NULL AS profile_url,
    'id' AS identity_confidence,
    ingested_at AS seen_at
  FROM silver.sv_tw_profile
),
normalized AS (
  SELECT
    platform,
    NULLIF(TRIM(external_user_id), '') AS external_user_id,
    NULLIF(TRIM(display_name), '') AS display_name,
    NULLIF(TRIM(handle), '') AS handle,
    NULLIF(TRIM(profile_url), '') AS profile_url,
    identity_confidence,
    seen_at,
    md5(
      platform || ':' ||
      COALESCE(NULLIF(TRIM(external_user_id), ''), 'name:' || lower(COALESCE(NULLIF(TRIM(display_name), ''), NULLIF(TRIM(handle), ''), 'unknown')))
    ) AS actor_id
  FROM sources
  WHERE COALESCE(NULLIF(TRIM(external_user_id), ''), NULLIF(TRIM(display_name), ''), NULLIF(TRIM(handle), '')) IS NOT NULL
),
aggregated AS (
  SELECT
    actor_id,
    platform,
    external_user_id,
    max(display_name) AS display_name,
    max(handle) AS handle,
    max(profile_url) AS profile_url,
    max(identity_confidence) AS identity_confidence,
    min(seen_at) AS first_seen,
    max(seen_at) AS last_seen
  FROM normalized
  GROUP BY actor_id, platform, external_user_id
)
SELECT * FROM aggregated;

CREATE TABLE IF NOT EXISTS silver.sv_actor AS
SELECT * FROM staging_sv_actor WHERE 1 = 0;

MERGE INTO silver.sv_actor AS t
USING staging_sv_actor AS s
ON t.actor_id = s.actor_id
WHEN MATCHED THEN UPDATE SET
  display_name = COALESCE(s.display_name, t.display_name),
  handle = COALESCE(s.handle, t.handle),
  profile_url = COALESCE(s.profile_url, t.profile_url),
  identity_confidence = CASE
    WHEN s.identity_confidence = 'id' OR t.identity_confidence = 'id' THEN 'id'
    ELSE 'name_only'
  END,
  first_seen = LEAST(t.first_seen, s.first_seen),
  last_seen = GREATEST(t.last_seen, s.last_seen)
WHEN NOT MATCHED THEN INSERT *;

-- Activity facts
CREATE OR REPLACE TEMP TABLE staging_sv_actor_activity AS
SELECT
  md5('facebook' || ':' || COALESCE(NULLIF(TRIM(c.user_id), ''), 'name:' || lower(COALESCE(NULLIF(TRIM(c.user_name), ''), 'unknown')))) AS actor_id,
  'comment' AS content_type,
  c.comment_id AS content_id,
  c.post_id AS parent_content_id,
  (SELECT name FROM silver.sv_fb_profile ORDER BY ingested_at DESC LIMIT 1) AS account_scraped,
  COALESCE(c.fecha_comentario_ts, c.ingested_at) AS occurred_at,
  'facebook' AS platform
FROM silver.sv_fb_comment c
WHERE c.user_id IS NOT NULL OR c.user_name IS NOT NULL

UNION ALL

SELECT
  md5('instagram' || ':' || COALESCE(NULLIF(TRIM(c.user_id), ''), 'name:' || lower(COALESCE(NULLIF(TRIM(c.user_name), ''), 'unknown')))) AS actor_id,
  'comment' AS content_type,
  c.comment_id AS content_id,
  c.post_id AS parent_content_id,
  (SELECT username FROM silver.sv_ig_profile ORDER BY ingested_at DESC LIMIT 1) AS account_scraped,
  COALESCE(c.fecha_comentario_ts, c.ingested_at) AS occurred_at,
  'instagram' AS platform
FROM silver.sv_ig_comment c
WHERE c.user_id IS NOT NULL OR c.user_name IS NOT NULL

UNION ALL

SELECT
  md5('tiktok' || ':' || COALESCE(NULLIF(TRIM(c.user_id), ''), 'name:' || lower(COALESCE(NULLIF(TRIM(c.user_name), ''), 'unknown')))) AS actor_id,
  'comment' AS content_type,
  c.comment_id AS content_id,
  c.video_id AS parent_content_id,
  (SELECT handle FROM silver.sv_tt_profile ORDER BY ingested_at DESC LIMIT 1) AS account_scraped,
  COALESCE(c.fecha_comentario_ts, c.ingested_at) AS occurred_at,
  'tiktok' AS platform
FROM silver.sv_tt_comment c
WHERE c.user_id IS NOT NULL OR c.user_name IS NOT NULL

UNION ALL

SELECT
  md5('twitter' || ':' || COALESCE(NULLIF(TRIM(r.user_id), ''), 'name:' || lower(COALESCE(NULLIF(TRIM(r.username), ''), NULLIF(TRIM(r.user_name), ''), 'unknown')))) AS actor_id,
  'reply' AS content_type,
  r.reply_id AS content_id,
  r.in_reply_to_tweet_id_str AS parent_content_id,
  (SELECT username FROM silver.sv_tw_profile ORDER BY ingested_at DESC LIMIT 1) AS account_scraped,
  COALESCE(r.created_at_ts, r.ingested_at) AS occurred_at,
  'twitter' AS platform
FROM silver.sv_tw_reply r
WHERE r.user_id IS NOT NULL OR r.username IS NOT NULL OR r.user_name IS NOT NULL;

CREATE TABLE IF NOT EXISTS silver.sv_actor_activity AS
SELECT * FROM staging_sv_actor_activity WHERE 1 = 0;

MERGE INTO silver.sv_actor_activity AS t
USING staging_sv_actor_activity AS s
ON t.content_id = s.content_id AND t.platform = s.platform AND t.content_type = s.content_type
WHEN MATCHED THEN UPDATE SET
  actor_id = s.actor_id,
  parent_content_id = s.parent_content_id,
  account_scraped = s.account_scraped,
  occurred_at = s.occurred_at
WHEN NOT MATCHED THEN INSERT *;

-- Actor stats (rebuilt each run from activity + classification)
CREATE OR REPLACE TABLE silver.sv_actor_stats AS
WITH comment_counts AS (
  SELECT
    actor_id,
    platform,
    COUNT(*) AS comment_count,
    COUNT(DISTINCT account_scraped) AS accounts_commented,
    COUNT(DISTINCT parent_content_id) AS posts_commented
  FROM silver.sv_actor_activity
  GROUP BY actor_id, platform
),
troll_counts AS (
  SELECT
    a.actor_id,
    COUNT(*) FILTER (WHERE cl.criterio_label = 'derecha_o_troll') AS troll_count,
    COUNT(*) FILTER (WHERE cl.criterio_label = 'apoyo_izquierda') AS apoyo_count,
    COUNT(*) FILTER (WHERE cl.criterio_label = 'neutral') AS neutral_count
  FROM silver.sv_actor_activity a
  LEFT JOIN silver.sv_fb_comment_classification cl
    ON a.content_id = cl.comment_id AND a.platform = 'facebook'
  GROUP BY a.actor_id

  UNION ALL

  SELECT
    a.actor_id,
    COUNT(*) FILTER (WHERE cl.criterio_label = 'derecha_o_troll'),
    COUNT(*) FILTER (WHERE cl.criterio_label = 'apoyo_izquierda'),
    COUNT(*) FILTER (WHERE cl.criterio_label = 'neutral')
  FROM silver.sv_actor_activity a
  LEFT JOIN silver.sv_ig_comment_classification cl
    ON a.content_id = cl.comment_id AND a.platform = 'instagram'
  GROUP BY a.actor_id

  UNION ALL

  SELECT
    a.actor_id,
    COUNT(*) FILTER (WHERE cl.criterio_label = 'derecha_o_troll'),
    COUNT(*) FILTER (WHERE cl.criterio_label = 'apoyo_izquierda'),
    COUNT(*) FILTER (WHERE cl.criterio_label = 'neutral')
  FROM silver.sv_actor_activity a
  LEFT JOIN silver.sv_tt_comment_classification cl
    ON a.content_id = cl.comment_id AND a.platform = 'tiktok'
  GROUP BY a.actor_id

  UNION ALL

  SELECT
    a.actor_id,
    COUNT(*) FILTER (WHERE cl.criterio_label = 'derecha_o_troll'),
    COUNT(*) FILTER (WHERE cl.criterio_label = 'apoyo_izquierda'),
    COUNT(*) FILTER (WHERE cl.criterio_label = 'neutral')
  FROM silver.sv_actor_activity a
  LEFT JOIN silver.sv_tw_reply_classification cl
    ON a.content_id = cl.reply_id AND a.platform = 'twitter'
  GROUP BY a.actor_id
),
troll_agg AS (
  SELECT
    actor_id,
    SUM(troll_count) AS troll_count,
    SUM(apoyo_count) AS apoyo_count,
    SUM(neutral_count) AS neutral_count
  FROM troll_counts
  GROUP BY actor_id
)
SELECT
  cc.actor_id,
  cc.platform,
  cc.comment_count,
  cc.accounts_commented,
  cc.posts_commented,
  COALESCE(ta.troll_count, 0) AS troll_count,
  COALESCE(ta.apoyo_count, 0) AS apoyo_count,
  COALESCE(ta.neutral_count, 0) AS neutral_count,
  current_timestamp AS computed_at
FROM comment_counts cc
LEFT JOIN troll_agg ta ON cc.actor_id = ta.actor_id;
