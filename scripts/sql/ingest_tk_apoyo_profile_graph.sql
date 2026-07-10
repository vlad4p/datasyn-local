-- Gold graph for enriched top-supporter (apoyo) profiles (twikit follow edges).
-- Source: silver.tk_tw_*_apoyo tables
-- Profile-signal heuristics reused as neutral signals (not 'risk' of hostility).
-- Uso:
--   uv run python scripts/python/db.py mcp-stop
--   uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_tk_apoyo_profile_graph.sql

CREATE SCHEMA IF NOT EXISTS gold;

-- ---------------------------------------------------------------------------
-- Vertices: enriched supporters + neighbor accounts seen in follow edges
-- ---------------------------------------------------------------------------

CREATE OR REPLACE TABLE gold.tk_apoyo_grafo_vertices AS
WITH supporters AS (
  SELECT
    CAST(user_id AS VARCHAR) AS vertex_id,
    username AS label,
    'supporter' AS entity_type,
    display_name,
    followers_count,
    following_count,
    statuses_count,
    favourites_count,
    listed_count,
    bio,
    location,
    account_created_at,
    is_blue_verified,
    is_protected,
    profile_image_url
  FROM silver.tk_tw_profile_enriched_apoyo
),
neighbors AS (
  SELECT
    CAST(dst_user_id AS VARCHAR) AS vertex_id,
    COALESCE(NULLIF(TRIM(dst_username), ''), CAST(dst_user_id AS VARCHAR)) AS label,
    'neighbor' AS entity_type,
    dst_display_name AS display_name,
    dst_followers_count AS followers_count,
    dst_following_count AS following_count,
    CAST(NULL AS BIGINT) AS statuses_count,
    CAST(NULL AS BIGINT) AS favourites_count,
    CAST(NULL AS BIGINT) AS listed_count,
    CAST(NULL AS VARCHAR) AS bio,
    CAST(NULL AS VARCHAR) AS location,
    CAST(NULL AS VARCHAR) AS account_created_at,
    CAST(NULL AS BOOLEAN) AS is_blue_verified,
    CAST(NULL AS BOOLEAN) AS is_protected,
    CAST(NULL AS VARCHAR) AS profile_image_url
  FROM silver.tk_tw_follow_edge_apoyo
  WHERE dst_user_id IS NOT NULL
    AND CAST(dst_user_id AS VARCHAR) NOT IN (SELECT vertex_id FROM supporters)
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY dst_user_id
    ORDER BY dst_followers_count DESC NULLS LAST, dst_username
  ) = 1
)
SELECT * FROM supporters
UNION ALL BY NAME
SELECT * FROM neighbors;

-- ---------------------------------------------------------------------------
-- Raw directed edges (follow graph)
-- follower: neighbor → supporter
-- following: supporter → neighbor
-- ---------------------------------------------------------------------------

CREATE OR REPLACE TABLE gold.tk_apoyo_grafo_edges AS
SELECT
  CASE
    WHEN direction = 'follower' THEN CAST(dst_user_id AS VARCHAR)
    ELSE CAST(src_user_id AS VARCHAR)
  END AS source_id,
  CASE
    WHEN direction = 'follower' THEN CAST(src_user_id AS VARCHAR)
    ELSE CAST(dst_user_id AS VARCHAR)
  END AS target_id,
  CASE
    WHEN direction = 'follower' THEN 'follows_apoyo'
    WHEN direction = 'following' THEN 'apoyo_follows'
    ELSE direction
  END AS edge_type,
  1.0 AS weight,
  src_username AS apoyo_username,
  direction AS list_kind
FROM silver.tk_tw_follow_edge_apoyo
WHERE src_user_id IS NOT NULL
  AND dst_user_id IS NOT NULL;

CREATE OR REPLACE TABLE gold.tk_apoyo_grafo_edges_agg AS
SELECT
  source_id,
  target_id,
  edge_type,
  SUM(weight) AS peso_total,
  COUNT(*) AS edge_count
FROM gold.tk_apoyo_grafo_edges
GROUP BY 1, 2, 3;

-- ---------------------------------------------------------------------------
-- Co-follower pairs between supporters (shared audience)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE TABLE gold.tk_apoyo_grafo_co_followers AS
WITH fo AS (
  SELECT
    CAST(src_user_id AS VARCHAR) AS apoyo_id,
    CAST(dst_user_id AS VARCHAR) AS follower_id
  FROM silver.tk_tw_follow_edge_apoyo
  WHERE direction = 'follower'
)
SELECT
  a.apoyo_id AS apoyo_a_id,
  b.apoyo_id AS apoyo_b_id,
  COUNT(*) AS shared_followers
FROM fo a
JOIN fo b
  ON a.follower_id = b.follower_id
 AND a.apoyo_id < b.apoyo_id
GROUP BY 1, 2;

-- ---------------------------------------------------------------------------
-- Co-following pairs (supporters follow the same accounts)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE TABLE gold.tk_apoyo_grafo_co_following AS
WITH fl AS (
  SELECT
    CAST(src_user_id AS VARCHAR) AS apoyo_id,
    CAST(dst_user_id AS VARCHAR) AS followed_id
  FROM silver.tk_tw_follow_edge_apoyo
  WHERE direction = 'following'
)
SELECT
  a.apoyo_id AS apoyo_a_id,
  b.apoyo_id AS apoyo_b_id,
  COUNT(*) AS shared_following
FROM fl a
JOIN fl b
  ON a.followed_id = b.followed_id
 AND a.apoyo_id < b.apoyo_id
GROUP BY 1, 2;

-- ---------------------------------------------------------------------------
-- Bridge / multi-supporter followers (follow >= 2 enriched supporters)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE TABLE gold.tk_apoyo_grafo_bridge_followers AS
SELECT
  CAST(dst_user_id AS VARCHAR) AS follower_id,
  COALESCE(NULLIF(TRIM(MAX(dst_username)), ''), CAST(dst_user_id AS VARCHAR)) AS follower_username,
  MAX(dst_display_name) AS follower_display_name,
  MAX(dst_followers_count) AS follower_followers_count,
  MAX(dst_following_count) AS follower_following_count,
  COUNT(DISTINCT src_user_id) AS apoyos_followed,
  LIST(DISTINCT src_username ORDER BY src_username) AS apoyo_usernames
FROM silver.tk_tw_follow_edge_apoyo
WHERE direction = 'follower'
GROUP BY dst_user_id
HAVING COUNT(DISTINCT src_user_id) >= 2;

-- ---------------------------------------------------------------------------
-- Heuristic profile-signal scores for enriched supporters (signals, not proof)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE TABLE gold.tk_apoyo_profile_risk AS
WITH posts AS (
  SELECT
    CAST(author_id AS VARCHAR) AS user_id,
    COUNT(*) AS posts_scraped,
    AVG(like_count) AS avg_likes,
    AVG(retweet_count) AS avg_rts,
    AVG(reply_count) AS avg_replies
  FROM silver.tk_tw_profile_post_apoyo
  GROUP BY 1
),
bridge AS (
  SELECT
    CAST(src_user_id AS VARCHAR) AS apoyo_id,
    COUNT(DISTINCT dst_user_id) AS bridge_followers_on_me
  FROM silver.tk_tw_follow_edge_apoyo e
  JOIN gold.tk_apoyo_grafo_bridge_followers b
    ON CAST(e.dst_user_id AS VARCHAR) = b.follower_id
  WHERE e.direction = 'follower'
  GROUP BY 1
),
base AS (
  SELECT
    e.user_id,
    e.username,
    e.display_name,
    e.followers_count,
    e.following_count,
    e.statuses_count,
    e.favourites_count,
    e.listed_count,
    e.bio,
    e.account_created_at,
    e.is_blue_verified,
    COALESCE(p.posts_scraped, 0) AS posts_scraped,
    p.avg_likes,
    p.avg_rts,
    p.avg_replies,
    COALESCE(b.bridge_followers_on_me, 0) AS bridge_followers_on_me,
    CASE
      WHEN e.followers_count IS NULL OR e.followers_count = 0 THEN NULL
      ELSE ROUND(e.following_count::DOUBLE / e.followers_count, 2)
    END AS following_followers_ratio,
    CASE
      WHEN e.followers_count IS NULL OR e.followers_count = 0 THEN NULL
      ELSE ROUND(e.statuses_count::DOUBLE / e.followers_count, 2)
    END AS statuses_per_follower,
    CASE
      WHEN TRY_STRPTIME(e.account_created_at, '%a %b %d %H:%M:%S %z %Y') IS NOT NULL
        THEN TRY_STRPTIME(e.account_created_at, '%a %b %d %H:%M:%S %z %Y')
      ELSE TRY_CAST(e.account_created_at AS TIMESTAMP)
    END AS account_created_ts
  FROM silver.tk_tw_profile_enriched_apoyo e
  LEFT JOIN posts p ON p.user_id = CAST(e.user_id AS VARCHAR)
  LEFT JOIN bridge b ON b.apoyo_id = CAST(e.user_id AS VARCHAR)
)
SELECT
  user_id,
  username,
  display_name,
  followers_count,
  following_count,
  statuses_count,
  favourites_count,
  listed_count,
  bio,
  account_created_at,
  account_created_ts,
  is_blue_verified,
  posts_scraped,
  avg_likes,
  avg_rts,
  avg_replies,
  bridge_followers_on_me,
  following_followers_ratio,
  statuses_per_follower,
  -- Heuristic flags
  (COALESCE(LENGTH(TRIM(bio)), 0) = 0) AS flag_empty_bio,
  (account_created_ts IS NOT NULL AND account_created_ts >= TIMESTAMP '2024-01-01') AS flag_new_account,
  (following_followers_ratio IS NOT NULL AND following_followers_ratio >= 5) AS flag_follow_ratio_high,
  (statuses_per_follower IS NOT NULL AND statuses_per_follower >= 100) AS flag_high_output_low_audience,
  (followers_count IS NOT NULL AND followers_count < 50 AND statuses_count >= 1000) AS flag_low_followers_high_status,
  (favourites_count IS NOT NULL AND favourites_count < 50 AND statuses_count >= 3000) AS flag_low_likes_high_status,
  (bridge_followers_on_me >= 3) AS flag_shared_audience,
  (
    (CASE WHEN COALESCE(LENGTH(TRIM(bio)), 0) = 0 THEN 1 ELSE 0 END)
    + (CASE WHEN account_created_ts IS NOT NULL AND account_created_ts >= TIMESTAMP '2024-01-01' THEN 2 ELSE 0 END)
    + (CASE WHEN following_followers_ratio IS NOT NULL AND following_followers_ratio >= 5 THEN 1 ELSE 0 END)
    + (CASE WHEN statuses_per_follower IS NOT NULL AND statuses_per_follower >= 100 THEN 2 ELSE 0 END)
    + (CASE WHEN followers_count IS NOT NULL AND followers_count < 50 AND statuses_count >= 1000 THEN 2 ELSE 0 END)
    + (CASE WHEN favourites_count IS NOT NULL AND favourites_count < 50 AND statuses_count >= 3000 THEN 1 ELSE 0 END)
    + (CASE WHEN bridge_followers_on_me >= 3 THEN 1 ELSE 0 END)
  ) AS risk_score,
  CASE
    WHEN (
      (CASE WHEN COALESCE(LENGTH(TRIM(bio)), 0) = 0 THEN 1 ELSE 0 END)
      + (CASE WHEN account_created_ts IS NOT NULL AND account_created_ts >= TIMESTAMP '2024-01-01' THEN 2 ELSE 0 END)
      + (CASE WHEN following_followers_ratio IS NOT NULL AND following_followers_ratio >= 5 THEN 1 ELSE 0 END)
      + (CASE WHEN statuses_per_follower IS NOT NULL AND statuses_per_follower >= 100 THEN 2 ELSE 0 END)
      + (CASE WHEN followers_count IS NOT NULL AND followers_count < 50 AND statuses_count >= 1000 THEN 2 ELSE 0 END)
      + (CASE WHEN favourites_count IS NOT NULL AND favourites_count < 50 AND statuses_count >= 3000 THEN 1 ELSE 0 END)
      + (CASE WHEN bridge_followers_on_me >= 3 THEN 1 ELSE 0 END)
    ) >= 6 THEN 'high'
    WHEN (
      (CASE WHEN COALESCE(LENGTH(TRIM(bio)), 0) = 0 THEN 1 ELSE 0 END)
      + (CASE WHEN account_created_ts IS NOT NULL AND account_created_ts >= TIMESTAMP '2024-01-01' THEN 2 ELSE 0 END)
      + (CASE WHEN following_followers_ratio IS NOT NULL AND following_followers_ratio >= 5 THEN 1 ELSE 0 END)
      + (CASE WHEN statuses_per_follower IS NOT NULL AND statuses_per_follower >= 100 THEN 2 ELSE 0 END)
      + (CASE WHEN followers_count IS NOT NULL AND followers_count < 50 AND statuses_count >= 1000 THEN 2 ELSE 0 END)
      + (CASE WHEN favourites_count IS NOT NULL AND favourites_count < 50 AND statuses_count >= 3000 THEN 1 ELSE 0 END)
      + (CASE WHEN bridge_followers_on_me >= 3 THEN 1 ELSE 0 END)
    ) >= 3 THEN 'medium'
    ELSE 'low'
  END AS risk_band,
  current_timestamp AS computed_at
FROM base;
