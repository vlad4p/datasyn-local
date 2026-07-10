-- Twikit profile enrich → bronze + silver
-- Paths filled by enrich_twikit_profiles.py --ingest from
-- data/landing/redes/twikit/profiles/_current_batch.json

CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;

-- ---------------------------------------------------------------------------
-- Bronze (raw landing)
-- ---------------------------------------------------------------------------

CREATE OR REPLACE TABLE bronze.tk_tw_profile_enriched AS
SELECT * FROM read_json_auto(
  '{{profiles_glob}}',
  filename = true,
  union_by_name = true,
  ignore_errors = true
);

CREATE OR REPLACE TABLE bronze.tk_tw_profile_post AS
SELECT * FROM read_json_auto(
  '{{posts_glob}}',
  format = 'newline_delimited',
  filename = true,
  union_by_name = true,
  ignore_errors = true
);

-- Followers / following JSONL may be empty or ID-only rows.
CREATE OR REPLACE TABLE bronze.tk_tw_follow_edge_raw AS
SELECT
  'followers' AS direction,
  *
FROM read_json_auto(
  '{{followers_glob}}',
  format = 'newline_delimited',
  filename = true,
  union_by_name = true,
  ignore_errors = true
)
UNION ALL BY NAME
SELECT
  'following' AS direction,
  *
FROM read_json_auto(
  '{{following_glob}}',
  format = 'newline_delimited',
  filename = true,
  union_by_name = true,
  ignore_errors = true
);

-- ---------------------------------------------------------------------------
-- Silver: enriched profile snapshot
-- ---------------------------------------------------------------------------

CREATE OR REPLACE TEMP TABLE staging_tk_tw_profile_enriched AS
SELECT DISTINCT
  CAST(id AS VARCHAR) AS user_id,
  COALESCE(screen_name, scraped_handle) AS username,
  name AS display_name,
  description AS bio,
  location,
  TRY_CAST(followers_count AS BIGINT) AS followers_count,
  TRY_CAST(following_count AS BIGINT) AS following_count,
  TRY_CAST(statuses_count AS BIGINT) AS statuses_count,
  TRY_CAST(favourites_count AS BIGINT) AS favourites_count,
  TRY_CAST(listed_count AS BIGINT) AS listed_count,
  CAST(created_at AS VARCHAR) AS account_created_at,
  TRY_CAST(verified AS BOOLEAN) AS is_verified,
  TRY_CAST(is_blue_verified AS BOOLEAN) AS is_blue_verified,
  TRY_CAST(is_protected AS BOOLEAN) AS is_protected,
  profile_image_url,
  url AS profile_url,
  'twitter' AS platform,
  'twikit' AS source,
  current_timestamp AS ingested_at
FROM bronze.tk_tw_profile_enriched
WHERE id IS NOT NULL;

CREATE TABLE IF NOT EXISTS silver.tk_tw_profile_enriched AS
SELECT * FROM staging_tk_tw_profile_enriched WHERE 1 = 0;

MERGE INTO silver.tk_tw_profile_enriched AS t
USING staging_tk_tw_profile_enriched AS s
ON t.user_id = s.user_id
WHEN MATCHED THEN UPDATE SET
  username = s.username,
  display_name = s.display_name,
  bio = s.bio,
  location = s.location,
  followers_count = s.followers_count,
  following_count = s.following_count,
  statuses_count = s.statuses_count,
  favourites_count = s.favourites_count,
  listed_count = s.listed_count,
  account_created_at = s.account_created_at,
  is_verified = s.is_verified,
  is_blue_verified = s.is_blue_verified,
  is_protected = s.is_protected,
  profile_image_url = s.profile_image_url,
  profile_url = s.profile_url,
  platform = s.platform,
  source = s.source,
  ingested_at = s.ingested_at
WHEN NOT MATCHED THEN INSERT *;

-- Refresh metrics on the main profile table without wiping sparse reply authors.
CREATE TABLE IF NOT EXISTS silver.tk_tw_profile AS
SELECT
  CAST(NULL AS VARCHAR) AS user_id,
  CAST(NULL AS VARCHAR) AS username,
  CAST(NULL AS VARCHAR) AS display_name,
  CAST(NULL AS BIGINT) AS followers_count,
  CAST(NULL AS BIGINT) AS following_count,
  CAST(NULL AS BIGINT) AS statuses_count,
  CAST(NULL AS VARCHAR) AS description,
  CAST(NULL AS VARCHAR) AS platform,
  CAST(NULL AS VARCHAR) AS source,
  CAST(NULL AS TIMESTAMPTZ) AS ingested_at
WHERE 1 = 0;

MERGE INTO silver.tk_tw_profile AS t
USING staging_tk_tw_profile_enriched AS s
ON t.user_id = s.user_id
WHEN MATCHED THEN UPDATE SET
  username = COALESCE(s.username, t.username),
  display_name = COALESCE(s.display_name, t.display_name),
  followers_count = COALESCE(s.followers_count, t.followers_count),
  following_count = COALESCE(s.following_count, t.following_count),
  statuses_count = COALESCE(s.statuses_count, t.statuses_count),
  description = COALESCE(s.bio, t.description),
  platform = COALESCE(s.platform, t.platform),
  source = COALESCE(s.source, t.source),
  ingested_at = s.ingested_at
WHEN NOT MATCHED THEN INSERT (
  user_id, username, display_name, followers_count, following_count,
  statuses_count, description, platform, source, ingested_at
) VALUES (
  s.user_id, s.username, s.display_name, s.followers_count, s.following_count,
  s.statuses_count, s.bio, s.platform, s.source, s.ingested_at
);

-- ---------------------------------------------------------------------------
-- Silver: profile posts
-- ---------------------------------------------------------------------------

CREATE OR REPLACE TEMP TABLE staging_tk_tw_profile_post AS
SELECT DISTINCT
  CAST(id AS VARCHAR) AS tweet_id,
  TRIM(CAST(text AS VARCHAR)) AS text,
  CAST(lang AS VARCHAR) AS lang,
  CAST(created_at AS VARCHAR) AS created_at,
  TRY_CAST(created_at_iso AS TIMESTAMP) AS created_at_ts,
  CAST(in_reply_to AS VARCHAR) AS in_reply_to_tweet_id,
  TRY_CAST(reply_count AS BIGINT) AS reply_count,
  TRY_CAST(favorite_count AS BIGINT) AS like_count,
  TRY_CAST(retweet_count AS BIGINT) AS retweet_count,
  TRY_CAST(quote_count AS BIGINT) AS quote_count,
  TRY_CAST(view_count AS BIGINT) AS view_count,
  TRY_CAST(bookmark_count AS BIGINT) AS bookmark_count,
  CAST(user.id AS VARCHAR) AS author_id,
  CAST(user.screen_name AS VARCHAR) AS username,
  CAST(user.name AS VARCHAR) AS author_name,
  'twitter' AS platform,
  'twikit' AS source,
  current_timestamp AS ingested_at
FROM bronze.tk_tw_profile_post
WHERE id IS NOT NULL;

CREATE TABLE IF NOT EXISTS silver.tk_tw_profile_post AS
SELECT * FROM staging_tk_tw_profile_post WHERE 1 = 0;

MERGE INTO silver.tk_tw_profile_post AS t
USING staging_tk_tw_profile_post AS s
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

-- ---------------------------------------------------------------------------
-- Silver: follow edges
-- filename like .../profiles/<slug>_YYYYMMDD/followers.jsonl
-- ---------------------------------------------------------------------------

CREATE OR REPLACE TABLE silver.tk_tw_follow_edge AS
WITH raw AS (
  SELECT
    direction AS list_kind,
    CAST(id AS VARCHAR) AS other_user_id,
    CAST(screen_name AS VARCHAR) AS other_username,
    CAST(name AS VARCHAR) AS other_display_name,
    TRY_CAST(followers_count AS BIGINT) AS other_followers_count,
    TRY_CAST(following_count AS BIGINT) AS other_following_count,
    replace(filename, chr(92), '/') AS path_norm
  FROM bronze.tk_tw_follow_edge_raw
  WHERE id IS NOT NULL
),
parsed AS (
  SELECT
    r.*,
    -- path .../profiles/<slug>_YYYYMMDD/<file>.jsonl → slug
    regexp_extract(path_norm, 'profiles/([^/]+)_[0-9]{8}/', 1) AS profile_slug
  FROM raw r
),
joined AS (
  SELECT
    e.user_id AS src_user_id,
    e.username AS src_username,
    p.other_user_id AS dst_user_id,
    p.other_username AS dst_username,
    p.other_display_name AS dst_display_name,
    p.other_followers_count AS dst_followers_count,
    p.other_following_count AS dst_following_count,
    CASE
      WHEN p.list_kind = 'followers' THEN 'follower'
      WHEN p.list_kind = 'following' THEN 'following'
      ELSE p.list_kind
    END AS direction,
    'twitter' AS platform,
    'twikit' AS source,
    current_timestamp AS ingested_at
  FROM parsed p
  INNER JOIN silver.tk_tw_profile_enriched e
    ON lower(e.username) = lower(p.profile_slug)
)
SELECT DISTINCT *
FROM joined
WHERE src_user_id IS NOT NULL
  AND dst_user_id IS NOT NULL;
