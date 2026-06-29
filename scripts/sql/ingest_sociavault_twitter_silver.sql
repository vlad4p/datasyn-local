-- SociaVault Twitter/X bronze → silver
-- Uso: uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_twitter_silver.sql

CREATE SCHEMA IF NOT EXISTS silver;

CREATE OR REPLACE TABLE silver.sv_tw_profile AS
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
  ) AS BIGINT) AS followers_count
FROM (SELECT to_json(p) AS j FROM bronze.sv_tw_profile AS p) AS raw
WHERE COALESCE(
  json_extract_string(j, '$.data.legacy.screen_name'),
  json_extract_string(j, '$.data.core.screen_name')
) IS NOT NULL;

CREATE OR REPLACE TABLE silver.sv_tw_tweet AS
WITH raw AS (
  SELECT to_json(t) AS j FROM bronze.sv_tw_tweet AS t
),
tweets AS (
  SELECT tweet.value AS tweet_json
  FROM raw,
  LATERAL json_each(
    COALESCE(
      TRY_CAST(json_extract_string(j, '$.data.tweets') AS JSON),
      TRY_CAST(json_extract_string(j, '$.data.data.tweets') AS JSON)
    )
  ) AS tweet
  WHERE tweet.value IS NOT NULL
)
SELECT DISTINCT
  json_extract_string(tweet_json, '$.rest_id') AS tweet_id,
  json_extract_string(tweet_json, '$.legacy.id_str') AS id_str,
  json_extract_string(tweet_json, '$.url') AS url,
  TRIM(json_extract_string(tweet_json, '$.legacy.full_text')) AS text,
  json_extract_string(tweet_json, '$.core.user_results.result.core.screen_name') AS username,
  TRY_CAST(json_extract_string(tweet_json, '$.legacy.favorite_count') AS BIGINT) AS like_count,
  TRY_CAST(json_extract_string(tweet_json, '$.legacy.retweet_count') AS BIGINT) AS retweet_count,
  TRY_CAST(json_extract_string(tweet_json, '$.legacy.reply_count') AS BIGINT) AS reply_count,
  TRY_CAST(json_extract_string(tweet_json, '$.legacy.quote_count') AS BIGINT) AS quote_count,
  TRY_CAST(json_extract_string(tweet_json, '$.views.count') AS BIGINT) AS view_count,
  json_extract_string(tweet_json, '$.legacy.created_at') AS created_at,
  json_extract_string(tweet_json, '$.legacy.in_reply_to_status_id_str') AS in_reply_to_tweet_id_str
FROM tweets
WHERE json_extract_string(tweet_json, '$.rest_id') IS NOT NULL;

CREATE OR REPLACE TABLE silver.sv_tw_reply AS
WITH pages AS (
  SELECT to_json(r) AS j FROM bronze.sv_tw_reply AS r
),
replies AS (
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
)
SELECT DISTINCT
  json_extract_string(reply_json, '$.rest_id') AS reply_id,
  json_extract_string(reply_json, '$.legacy.in_reply_to_status_id_str') AS in_reply_to_tweet_id_str,
  TRIM(json_extract_string(reply_json, '$.legacy.full_text')) AS text,
  json_extract_string(reply_json, '$.core.user_results.result.core.screen_name') AS username,
  TRY_CAST(json_extract_string(reply_json, '$.legacy.favorite_count') AS BIGINT) AS like_count,
  json_extract_string(reply_json, '$.legacy.created_at') AS created_at
FROM replies
WHERE json_extract_string(reply_json, '$.rest_id') IS NOT NULL;
