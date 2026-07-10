-- Twikit Twitter/X bronze → silver (MERGE upsert)
-- Uso: via scrape_twikit_twitter.py --ingest

CREATE SCHEMA IF NOT EXISTS silver;

CREATE OR REPLACE TEMP TABLE staging_tk_tw_profile AS
SELECT DISTINCT
  CAST(id AS VARCHAR) AS user_id,
  screen_name AS username,
  name AS display_name,
  TRY_CAST(followers_count AS BIGINT) AS followers_count,
  TRY_CAST(following_count AS BIGINT) AS following_count,
  TRY_CAST(statuses_count AS BIGINT) AS statuses_count,
  description,
  'twitter' AS platform,
  'twikit' AS source,
  current_timestamp AS ingested_at
FROM bronze.tk_tw_profile
WHERE screen_name IS NOT NULL;

CREATE TABLE IF NOT EXISTS silver.tk_tw_profile AS
SELECT * FROM staging_tk_tw_profile WHERE 1 = 0;

MERGE INTO silver.tk_tw_profile AS t
USING staging_tk_tw_profile AS s
ON t.user_id = s.user_id
WHEN MATCHED THEN UPDATE SET
  username = s.username,
  display_name = s.display_name,
  followers_count = s.followers_count,
  following_count = s.following_count,
  statuses_count = s.statuses_count,
  description = s.description,
  platform = s.platform,
  source = s.source,
  ingested_at = s.ingested_at
WHEN NOT MATCHED THEN INSERT *;

CREATE OR REPLACE TEMP TABLE staging_tk_tw_tweet AS
SELECT DISTINCT
  CAST(id AS VARCHAR) AS tweet_id,
  TRIM(text) AS text,
  lang,
  created_at,
  TRY_CAST(created_at_iso AS TIMESTAMP) AS created_at_ts,
  CAST(in_reply_to AS VARCHAR) AS in_reply_to_tweet_id,
  TRY_CAST(reply_count AS BIGINT) AS reply_count,
  TRY_CAST(favorite_count AS BIGINT) AS like_count,
  TRY_CAST(retweet_count AS BIGINT) AS retweet_count,
  TRY_CAST(quote_count AS BIGINT) AS quote_count,
  TRY_CAST(view_count AS BIGINT) AS view_count,
  TRY_CAST(bookmark_count AS BIGINT) AS bookmark_count,
  CAST(user.id AS VARCHAR) AS author_id,
  user.screen_name AS username,
  user.name AS author_name,
  'twitter' AS platform,
  'twikit' AS source,
  current_timestamp AS ingested_at
FROM bronze.tk_tw_tweet
WHERE id IS NOT NULL;

CREATE TABLE IF NOT EXISTS silver.tk_tw_tweet AS
SELECT * FROM staging_tk_tw_tweet WHERE 1 = 0;

MERGE INTO silver.tk_tw_tweet AS t
USING staging_tk_tw_tweet AS s
ON t.tweet_id = s.tweet_id
WHEN MATCHED THEN UPDATE SET
  text = s.text,
  lang = s.lang,
  created_at = s.created_at,
  created_at_ts = s.created_at_ts,
  in_reply_to_tweet_id = s.in_reply_to_tweet_id,
  reply_count = s.reply_count,
  like_count = s.like_count,
  retweet_count = s.retweet_count,
  quote_count = s.quote_count,
  view_count = s.view_count,
  bookmark_count = s.bookmark_count,
  author_id = s.author_id,
  username = s.username,
  author_name = s.author_name,
  platform = s.platform,
  source = s.source,
  ingested_at = s.ingested_at
WHEN NOT MATCHED THEN INSERT *;

-- Flatten reply batches; skip error-only JSONL rows (no "replies" field).
CREATE OR REPLACE TEMP TABLE staging_tk_tw_reply AS
WITH raw AS (
  SELECT
    CAST(tweet_id AS VARCHAR) AS parent_tweet_id,
    replies
  FROM bronze.tk_tw_reply
  WHERE replies IS NOT NULL
),
flat AS (
  SELECT
    parent_tweet_id,
    unnest(replies) AS reply
  FROM raw
)
SELECT DISTINCT
  parent_tweet_id,
  CAST(reply.id AS VARCHAR) AS reply_id,
  TRIM(CAST(reply.text AS VARCHAR)) AS text,
  CAST(reply.lang AS VARCHAR) AS lang,
  CAST(reply.created_at AS VARCHAR) AS created_at,
  TRY_CAST(reply.created_at_iso AS TIMESTAMP) AS created_at_ts,
  TRY_CAST(reply.favorite_count AS BIGINT) AS like_count,
  TRY_CAST(reply.retweet_count AS BIGINT) AS retweet_count,
  TRY_CAST(reply.reply_count AS BIGINT) AS reply_count,
  CAST(reply.user.id AS VARCHAR) AS author_id,
  CAST(reply.user.screen_name AS VARCHAR) AS username,
  CAST(reply.user.name AS VARCHAR) AS author_name,
  'twitter' AS platform,
  'twikit' AS source,
  current_timestamp AS ingested_at
FROM flat
WHERE reply.id IS NOT NULL;

CREATE TABLE IF NOT EXISTS silver.tk_tw_reply AS
SELECT * FROM staging_tk_tw_reply WHERE 1 = 0;

MERGE INTO silver.tk_tw_reply AS t
USING staging_tk_tw_reply AS s
ON t.reply_id = s.reply_id
WHEN MATCHED THEN UPDATE SET
  parent_tweet_id = s.parent_tweet_id,
  text = s.text,
  lang = s.lang,
  created_at = s.created_at,
  created_at_ts = s.created_at_ts,
  like_count = s.like_count,
  retweet_count = s.retweet_count,
  reply_count = s.reply_count,
  author_id = s.author_id,
  username = s.username,
  author_name = s.author_name,
  platform = s.platform,
  source = s.source,
  ingested_at = s.ingested_at
WHEN NOT MATCHED THEN INSERT *;
