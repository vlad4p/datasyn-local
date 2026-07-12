-- SociaVault Twitter/X bronze → silver (MERGE upsert)
-- Uso: uv run python scripts/python/db.py run-sql --file scripts/sql/sociavault/ingest_sociavault_twitter_silver.sql

CREATE SCHEMA IF NOT EXISTS silver;

CREATE OR REPLACE TEMP TABLE staging_sv_tw_profile AS
SELECT DISTINCT
  COALESCE(
    json_extract_string(j, '$.data.rest_id'),
    json_extract_string(j, '$.data.data.rest_id'),
    json_extract_string(j, '$.data.legacy.screen_name')
  ) AS user_id,
  COALESCE(
    json_extract_string(j, '$.data.legacy.screen_name'),
    json_extract_string(j, '$.data.core.screen_name')
  ) AS username,
  COALESCE(
    json_extract_string(j, '$.data.legacy.name'),
    json_extract_string(j, '$.data.core.name')
  ) AS display_name,
  TRY_CAST(COALESCE(
    json_extract_string(j, '$.data.legacy.followers_count'),
    json_extract_string(j, '$.data.legacy.followers_count')
  ) AS BIGINT) AS followers_count,
  'twitter' AS platform,
  current_timestamp AS ingested_at
FROM (SELECT to_json(p) AS j FROM bronze.sv_tw_profile AS p) AS raw
WHERE COALESCE(
  json_extract_string(j, '$.data.legacy.screen_name'),
  json_extract_string(j, '$.data.core.screen_name')
) IS NOT NULL;

CREATE TABLE IF NOT EXISTS silver.sv_tw_profile AS
SELECT * FROM staging_sv_tw_profile WHERE 1 = 0;

MERGE INTO silver.sv_tw_profile AS t
USING staging_sv_tw_profile AS s
ON t.user_id = s.user_id
WHEN MATCHED THEN UPDATE SET
  username = s.username,
  display_name = s.display_name,
  followers_count = s.followers_count,
  platform = s.platform,
  ingested_at = s.ingested_at
WHEN NOT MATCHED THEN INSERT *;

CREATE OR REPLACE TEMP TABLE staging_sv_tw_tweet AS
WITH raw AS (
  SELECT to_json(t.tweet) AS tweet_json FROM bronze.sv_tw_tweet_selected AS t
),
tweets AS (
  SELECT tweet_json FROM raw WHERE tweet_json IS NOT NULL
)
SELECT DISTINCT
  json_extract_string(tweet_json, '$.rest_id') AS tweet_id,
  json_extract_string(tweet_json, '$.legacy.id_str') AS id_str,
  json_extract_string(tweet_json, '$.url') AS url,
  TRIM(json_extract_string(tweet_json, '$.legacy.full_text')) AS text,
  json_extract_string(tweet_json, '$.core.user_results.result.core.screen_name') AS username,
  COALESCE(
    json_extract_string(tweet_json, '$.core.user_results.result.rest_id'),
    json_extract_string(tweet_json, '$.legacy.user_id_str')
  ) AS author_id,
  json_extract_string(tweet_json, '$.core.user_results.result.core.name') AS author_name,
  TRY_CAST(json_extract_string(tweet_json, '$.legacy.favorite_count') AS BIGINT) AS like_count,
  TRY_CAST(json_extract_string(tweet_json, '$.legacy.retweet_count') AS BIGINT) AS retweet_count,
  TRY_CAST(json_extract_string(tweet_json, '$.legacy.reply_count') AS BIGINT) AS reply_count,
  TRY_CAST(json_extract_string(tweet_json, '$.legacy.quote_count') AS BIGINT) AS quote_count,
  TRY_CAST(json_extract_string(tweet_json, '$.views.count') AS BIGINT) AS view_count,
  json_extract_string(tweet_json, '$.legacy.created_at') AS created_at,
  TRY_CAST(json_extract_string(tweet_json, '$.legacy.created_at') AS TIMESTAMP) AS created_at_ts,
  json_extract_string(tweet_json, '$.legacy.in_reply_to_status_id_str') AS in_reply_to_tweet_id_str,
  'twitter' AS platform,
  current_timestamp AS ingested_at
FROM tweets
WHERE json_extract_string(tweet_json, '$.rest_id') IS NOT NULL;

CREATE TABLE IF NOT EXISTS silver.sv_tw_tweet AS
SELECT * FROM staging_sv_tw_tweet WHERE 1 = 0;

MERGE INTO silver.sv_tw_tweet AS t
USING staging_sv_tw_tweet AS s
ON t.tweet_id = s.tweet_id
WHEN MATCHED THEN UPDATE SET
  id_str = s.id_str,
  url = s.url,
  text = s.text,
  username = s.username,
  author_id = s.author_id,
  author_name = s.author_name,
  like_count = s.like_count,
  retweet_count = s.retweet_count,
  reply_count = s.reply_count,
  quote_count = s.quote_count,
  view_count = s.view_count,
  created_at = s.created_at,
  created_at_ts = s.created_at_ts,
  in_reply_to_tweet_id_str = s.in_reply_to_tweet_id_str,
  platform = s.platform,
  ingested_at = s.ingested_at
WHEN NOT MATCHED THEN INSERT *;

CREATE OR REPLACE TEMP TABLE staging_sv_tw_reply AS
WITH pages AS (
  SELECT to_json(r) AS j FROM bronze.sv_tw_reply AS r
),
legacy_replies AS (
  SELECT reply.value AS reply_json
  FROM pages,
  LATERAL json_each(
    COALESCE(
      TRY_CAST(json_extract_string(j, '$.data.replies') AS JSON),
      TRY_CAST(json_extract_string(j, '$.data.tweets') AS JSON),
      TRY_CAST(json_extract_string(j, '$.data.data.tweets') AS JSON)
    )
  ) AS reply
  WHERE reply.value IS NOT NULL
),
from_legacy AS (
  SELECT DISTINCT
    json_extract_string(reply_json, '$.rest_id') AS reply_id,
    json_extract_string(reply_json, '$.legacy.in_reply_to_status_id_str') AS in_reply_to_tweet_id_str,
    TRIM(json_extract_string(reply_json, '$.legacy.full_text')) AS text,
    COALESCE(
      json_extract_string(reply_json, '$.core.user_results.result.legacy.screen_name'),
      json_extract_string(reply_json, '$.core.user_results.result.core.screen_name')
    ) AS username,
    COALESCE(
      json_extract_string(reply_json, '$.core.user_results.result.rest_id'),
      json_extract_string(reply_json, '$.legacy.user_id_str')
    ) AS user_id,
    COALESCE(
      json_extract_string(reply_json, '$.core.user_results.result.legacy.name'),
      json_extract_string(reply_json, '$.core.user_results.result.core.name')
    ) AS user_name,
    TRY_CAST(json_extract_string(reply_json, '$.legacy.favorite_count') AS BIGINT) AS like_count,
    json_extract_string(reply_json, '$.legacy.created_at') AS created_at,
    TRY_CAST(json_extract_string(reply_json, '$.legacy.created_at') AS TIMESTAMP) AS created_at_ts,
    'twitter' AS platform,
    current_timestamp AS ingested_at
  FROM legacy_replies
  WHERE json_extract_string(reply_json, '$.rest_id') IS NOT NULL
),
from_comments AS (
  SELECT DISTINCT
    json_extract_string(to_json(item.item.itemContent.tweet_results.result), '$.rest_id') AS reply_id,
    json_extract_string(to_json(item.item.itemContent.tweet_results.result), '$.legacy.in_reply_to_status_id_str') AS in_reply_to_tweet_id_str,
    TRIM(json_extract_string(to_json(item.item.itemContent.tweet_results.result), '$.legacy.full_text')) AS text,
    COALESCE(
      json_extract_string(to_json(item.item.itemContent.tweet_results.result), '$.core.user_results.result.legacy.screen_name'),
      json_extract_string(to_json(item.item.itemContent.tweet_results.result), '$.core.user_results.result.core.screen_name')
    ) AS username,
    COALESCE(
      json_extract_string(to_json(item.item.itemContent.tweet_results.result), '$.core.user_results.result.rest_id'),
      json_extract_string(to_json(item.item.itemContent.tweet_results.result), '$.legacy.user_id_str')
    ) AS user_id,
    COALESCE(
      json_extract_string(to_json(item.item.itemContent.tweet_results.result), '$.core.user_results.result.legacy.name'),
      json_extract_string(to_json(item.item.itemContent.tweet_results.result), '$.core.user_results.result.core.name')
    ) AS user_name,
    TRY_CAST(json_extract_string(to_json(item.item.itemContent.tweet_results.result), '$.legacy.favorite_count') AS BIGINT) AS like_count,
    json_extract_string(to_json(item.item.itemContent.tweet_results.result), '$.legacy.created_at') AS created_at,
    TRY_CAST(json_extract_string(to_json(item.item.itemContent.tweet_results.result), '$.legacy.created_at') AS TIMESTAMP) AS created_at_ts,
    'twitter' AS platform,
    current_timestamp AS ingested_at
  FROM bronze.sv_tw_reply AS r,
  LATERAL unnest(r.data.result.instructions[1].entries) AS t(entry),
  LATERAL unnest(entry.content.items) AS u(item)
  WHERE r.success = true
    AND json_extract_string(to_json(item.item.itemContent.tweet_results.result), '$.rest_id') IS NOT NULL
    AND json_extract_string(to_json(item.item.itemContent.tweet_results.result), '$.legacy.in_reply_to_status_id_str') IS NOT NULL
)
SELECT * FROM from_legacy
UNION ALL
SELECT * FROM from_comments;

CREATE TABLE IF NOT EXISTS silver.sv_tw_reply AS
SELECT * FROM staging_sv_tw_reply WHERE 1 = 0;

MERGE INTO silver.sv_tw_reply AS t
USING staging_sv_tw_reply AS s
ON t.reply_id = s.reply_id AND t.platform = s.platform
WHEN MATCHED THEN UPDATE SET
  in_reply_to_tweet_id_str = s.in_reply_to_tweet_id_str,
  text = s.text,
  username = s.username,
  user_id = s.user_id,
  user_name = s.user_name,
  like_count = s.like_count,
  created_at = s.created_at,
  created_at_ts = s.created_at_ts,
  ingested_at = s.ingested_at
WHEN NOT MATCHED THEN INSERT *;
