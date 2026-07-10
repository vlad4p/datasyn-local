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

-- Flatten reply batches. Skip error-only JSONL rows (no "replies" field).
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

-- Sparse profiles from reply authors (id / username / name only).
-- WHEN MATCHED: refresh names only — do not null out full tracked metrics.
CREATE OR REPLACE TEMP TABLE staging_tk_tw_profile_from_replies AS
SELECT DISTINCT
  author_id AS user_id,
  username,
  author_name AS display_name,
  NULL::BIGINT AS followers_count,
  NULL::BIGINT AS following_count,
  NULL::BIGINT AS statuses_count,
  NULL::VARCHAR AS description,
  'twitter' AS platform,
  'twikit' AS source,
  current_timestamp AS ingested_at
FROM silver.tk_tw_reply
WHERE author_id IS NOT NULL AND username IS NOT NULL;

MERGE INTO silver.tk_tw_profile AS t
USING staging_tk_tw_profile_from_replies AS s
ON t.user_id = s.user_id
WHEN MATCHED THEN UPDATE SET
  username = s.username,
  display_name = COALESCE(s.display_name, t.display_name)
WHEN NOT MATCHED THEN INSERT *;

-- ---------------------------------------------------------------------------
-- Catalog: silver.tk_tw_user (twikit-only - replaces legacy silver.tw_users)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS silver.tk_tw_profile_enriched (
  user_id VARCHAR,
  username VARCHAR,
  display_name VARCHAR,
  bio VARCHAR,
  location VARCHAR,
  followers_count BIGINT,
  following_count BIGINT,
  statuses_count BIGINT,
  favourites_count BIGINT,
  listed_count BIGINT,
  account_created_at VARCHAR,
  is_verified BOOLEAN,
  is_blue_verified BOOLEAN,
  is_protected BOOLEAN,
  profile_image_url VARCHAR,
  profile_url VARCHAR,
  platform VARCHAR,
  source VARCHAR,
  ingested_at TIMESTAMP
);

CREATE OR REPLACE TEMP TABLE staging_tk_tw_user_hater AS
SELECT
  r.author_id AS user_id,
  COUNT(*) FILTER (WHERE c.criterio_label = 'derecha_o_troll') AS hater_replies_count,
  COUNT(*) AS replies_observed_count,
  MIN(r.created_at_ts) AS first_seen_at,
  MAX(r.created_at_ts) AS last_seen_at
FROM silver.tk_tw_reply AS r
LEFT JOIN silver.tk_tw_reply_classification AS c
  ON c.reply_id = r.reply_id
WHERE r.author_id IS NOT NULL
GROUP BY r.author_id;

CREATE OR REPLACE TABLE silver.tk_tw_user AS
WITH base AS (
  SELECT
    p.user_id,
    p.username,
    p.display_name,
    p.followers_count,
    p.following_count,
    p.statuses_count,
    p.description AS bio,
    CAST(NULL AS VARCHAR) AS location,
    CAST(NULL AS VARCHAR) AS account_created_at,
    CAST(NULL AS BOOLEAN) AS is_blue_verified,
    CAST(NULL AS BOOLEAN) AS is_verified,
    CAST(NULL AS BOOLEAN) AS is_protected,
    CAST(NULL AS VARCHAR) AS profile_image_url,
    'https://x.com/' || p.username AS profile_url,
    p.platform,
    p.source,
    p.ingested_at
  FROM silver.tk_tw_profile AS p
),
enriched AS (
  SELECT
    e.user_id,
    e.username,
    e.display_name,
    e.followers_count,
    e.following_count,
    e.statuses_count,
    e.bio,
    e.location,
    e.account_created_at,
    e.is_blue_verified,
    e.is_verified,
    e.is_protected,
    e.profile_image_url,
    e.profile_url,
    e.platform,
    e.source,
    e.ingested_at
  FROM silver.tk_tw_profile_enriched AS e
)
SELECT
  COALESCE(en.user_id, b.user_id) AS user_id,
  COALESCE(en.username, b.username) AS username,
  COALESCE(en.display_name, b.display_name) AS display_name,
  COALESCE(en.followers_count, b.followers_count) AS followers_count,
  COALESCE(en.following_count, b.following_count) AS following_count,
  COALESCE(en.statuses_count, b.statuses_count) AS statuses_count,
  COALESCE(en.bio, b.bio) AS bio,
  COALESCE(en.location, b.location) AS location,
  COALESCE(en.account_created_at, b.account_created_at) AS account_created_at,
  COALESCE(en.is_blue_verified, b.is_blue_verified) AS is_blue_verified,
  COALESCE(en.is_verified, b.is_verified) AS is_verified,
  COALESCE(en.is_protected, b.is_protected) AS is_protected,
  COALESCE(en.profile_image_url, b.profile_image_url) AS profile_image_url,
  COALESCE(en.profile_url, b.profile_url) AS profile_url,
  COALESCE(h.hater_replies_count, 0) AS hater_replies_count,
  COALESCE(h.replies_observed_count, 0) AS replies_observed_count,
  (COALESCE(h.hater_replies_count, 0) >= 1) AS is_hater,
  h.first_seen_at,
  h.last_seen_at,
  COALESCE(en.platform, b.platform, 'twitter') AS platform,
  'twikit' AS source,
  COALESCE(en.ingested_at, b.ingested_at, current_timestamp) AS ingested_at
FROM base AS b
FULL OUTER JOIN enriched AS en ON b.user_id = en.user_id
LEFT JOIN staging_tk_tw_user_hater AS h
  ON h.user_id = COALESCE(en.user_id, b.user_id);