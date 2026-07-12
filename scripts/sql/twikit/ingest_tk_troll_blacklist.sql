-- Twikit-only troll blacklist (auditable block/watch list).
-- Sources: silver.tk_tw_reply, silver.tk_tw_reply_classification,
--          gold.tk_hater_profile_risk, gold.tk_hater_grafo_bridge_followers,
--          gold.tk_hater_narrativa_assignment, silver.tk_tw_tweet
-- Rules: skills/analyze/reports/troll-blacklist/references/blacklist-rules.md
-- Uso:
--   uv run python scripts/python/db.py mcp-stop
--   uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/twikit/ingest_tk_troll_blacklist.sql

CREATE SCHEMA IF NOT EXISTS gold;

-- ---------------------------------------------------------------------------
-- Per-author behaviour from twikit replies + classification
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TEMP TABLE staging_tk_bl_behaviour AS
SELECT
  r.author_id AS user_id,
  LOWER(TRIM(r.username)) AS username_norm,
  MAX(r.username) AS username,
  MAX(r.author_name) AS display_name,
  COUNT(*) AS replies_total,
  COUNT(*) FILTER (WHERE c.criterio_label = 'derecha_o_troll') AS hater_replies,
  COUNT(DISTINCT r.parent_tweet_id) AS parent_tweets,
  COUNT(DISTINCT LOWER(TRIM(t.username)))
    FILTER (WHERE t.username IS NOT NULL) AS target_accounts,
  COUNT(DISTINCT a.cluster_id) AS narrativas,
  MIN(r.created_at_ts) AS first_reply_at,
  MAX(r.created_at_ts) AS last_reply_at
FROM silver.tk_tw_reply AS r
LEFT JOIN silver.tk_tw_reply_classification AS c
  ON c.reply_id = r.reply_id
LEFT JOIN silver.tk_tw_tweet AS t
  ON t.tweet_id = r.parent_tweet_id
LEFT JOIN gold.tk_hater_narrativa_assignment AS a
  ON a.reply_id = r.reply_id
WHERE r.author_id IS NOT NULL
  AND r.username IS NOT NULL
  AND LENGTH(TRIM(r.username)) > 0
GROUP BY r.author_id, LOWER(TRIM(r.username));

-- ---------------------------------------------------------------------------
-- Co-burst: >=2 distinct hater authors on same parent within 30 min window
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TEMP TABLE staging_tk_bl_hater_replies AS
SELECT
  r.author_id AS user_id,
  r.parent_tweet_id,
  r.created_at_ts
FROM silver.tk_tw_reply AS r
INNER JOIN silver.tk_tw_reply_classification AS c
  ON c.reply_id = r.reply_id
WHERE c.criterio_label = 'derecha_o_troll'
  AND r.author_id IS NOT NULL
  AND r.created_at_ts IS NOT NULL
  AND r.parent_tweet_id IS NOT NULL;

CREATE OR REPLACE TEMP TABLE staging_tk_bl_co_burst AS
SELECT DISTINCT a.user_id
FROM staging_tk_bl_hater_replies AS a
INNER JOIN staging_tk_bl_hater_replies AS b
  ON a.parent_tweet_id = b.parent_tweet_id
 AND a.user_id <> b.user_id
 AND ABS(EPOCH(a.created_at_ts) - EPOCH(b.created_at_ts)) <= 1800;

-- ---------------------------------------------------------------------------
-- Bridge followers (multi-hater audience)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TEMP TABLE staging_tk_bl_bridge AS
SELECT DISTINCT
  CAST(follower_id AS VARCHAR) AS user_id,
  TRUE AS is_bridge_follower
FROM gold.tk_hater_grafo_bridge_followers
WHERE haters_followed >= 2
  AND follower_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Score + reasons + tier
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE gold.tk_troll_blacklist AS
WITH base AS (
  SELECT
    b.user_id,
    b.username,
    b.display_name,
    b.replies_total,
    b.hater_replies,
    CASE
      WHEN b.replies_total > 0
        THEN ROUND(b.hater_replies::DOUBLE / b.replies_total, 4)
      ELSE 0.0
    END AS hater_ratio,
    b.parent_tweets,
    b.target_accounts,
    b.narrativas,
    b.first_reply_at,
    b.last_reply_at,
    (cb.user_id IS NOT NULL) AS in_co_burst,
    r.risk_band,
    r.risk_score,
    COALESCE(r.flag_empty_bio, FALSE) AS flag_empty_bio,
    COALESCE(r.flag_new_account, FALSE) AS flag_new_account,
    COALESCE(r.flag_high_output_low_audience, FALSE) AS flag_high_output_low_audience,
    COALESCE(r.flag_shared_audience, FALSE) AS flag_shared_audience,
    COALESCE(br.is_bridge_follower, FALSE) AS is_bridge_follower,
    (COALESCE(r.flag_shared_audience, FALSE) OR COALESCE(br.is_bridge_follower, FALSE)) AS is_bridge
  FROM staging_tk_bl_behaviour AS b
  LEFT JOIN staging_tk_bl_co_burst AS cb ON cb.user_id = b.user_id
  LEFT JOIN gold.tk_hater_profile_risk AS r ON r.user_id = b.user_id
  LEFT JOIN staging_tk_bl_bridge AS br ON br.user_id = b.user_id
),
scored AS (
  SELECT
    *,
    (hater_replies >= 5) AS rule_hater_replies_ge5,
    (hater_replies >= 3 AND hater_replies < 5) AS rule_hater_replies_ge3,
    (hater_ratio >= 0.6 AND replies_total >= 3) AS rule_hater_ratio_high,
    (target_accounts >= 3) AS rule_multi_target,
    in_co_burst AS rule_co_burst,
    (risk_band = 'high') AS rule_risk_high,
    (risk_band = 'medium') AS rule_risk_medium,
    is_bridge AS rule_bridge
  FROM base
),
with_score AS (
  SELECT
    *,
    (
      CASE WHEN rule_hater_replies_ge5 THEN 2 ELSE 0 END
      + CASE WHEN rule_hater_replies_ge3 THEN 1 ELSE 0 END
      + CASE WHEN rule_hater_ratio_high THEN 1 ELSE 0 END
      + CASE WHEN rule_multi_target THEN 1 ELSE 0 END
      + CASE WHEN rule_co_burst THEN 1 ELSE 0 END
      + CASE WHEN rule_risk_high THEN 3 ELSE 0 END
      + CASE WHEN rule_risk_medium THEN 1 ELSE 0 END
      + CASE WHEN rule_bridge THEN 1 ELSE 0 END
    ) AS score,
    NULLIF(
      TRIM(
        CONCAT_WS(
          ' | ',
          CASE WHEN rule_hater_replies_ge5 THEN 'hater_replies_ge5' END,
          CASE WHEN rule_hater_replies_ge3 THEN 'hater_replies_ge3' END,
          CASE WHEN rule_hater_ratio_high THEN 'hater_ratio_high' END,
          CASE WHEN rule_multi_target THEN 'multi_target' END,
          CASE WHEN rule_co_burst THEN 'co_burst' END,
          CASE WHEN rule_risk_high THEN 'risk_high' END,
          CASE WHEN rule_risk_medium THEN 'risk_medium' END,
          CASE WHEN rule_bridge THEN 'bridge' END
        )
      ),
      ''
    ) AS reasons
  FROM scored
)
SELECT
  user_id,
  username,
  display_name,
  score,
  reasons,
  CASE
    WHEN score >= 4
      OR risk_band = 'high'
      OR (hater_replies >= 5 AND hater_ratio >= 0.6)
      THEN 'block'
    WHEN score >= 2 OR hater_replies >= 3
      THEN 'watch'
    ELSE NULL
  END AS tier,
  replies_total,
  hater_replies,
  hater_ratio,
  parent_tweets,
  target_accounts,
  narrativas,
  in_co_burst,
  risk_band,
  risk_score,
  flag_empty_bio,
  flag_new_account,
  flag_high_output_low_audience,
  is_bridge,
  first_reply_at,
  last_reply_at,
  current_timestamp AS computed_at
FROM with_score
WHERE
  score >= 4
  OR risk_band = 'high'
  OR (hater_replies >= 5 AND hater_ratio >= 0.6)
  OR score >= 2
  OR hater_replies >= 3
ORDER BY
  CASE WHEN tier = 'block' THEN 0 ELSE 1 END,
  score DESC,
  hater_replies DESC,
  username;
