-- Twitter/X bronze → silver (clean, typed, joined)
-- Prereq: scripts/sql/ingest_twitter.sql
-- Optional enrich: silver.tk_tw_* + classification tables (twikit / LLM)
-- Uso: uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_twitter_silver.sql

CREATE SCHEMA IF NOT EXISTS silver;

-- Original tweets (no retweets in source), enriched with tracked-account flags
CREATE OR REPLACE TABLE silver.tw_tweets AS
SELECT
    t.id::BIGINT AS tweet_id,
    CAST(t.id_str AS VARCHAR) AS id_str,
    t.url,
    t.user_id::BIGINT AS user_id,
    TRIM(u.username) AS author_username,
    (u.is_diputado = 1) AS author_is_diputado,
    t.replyCount::INTEGER AS reply_count,
    t.retweetCount::INTEGER AS retweet_count,
    t.quoteCount::INTEGER AS quote_count,
    t.viewCount::BIGINT AS view_count,
    t.likeCount::INTEGER AS like_count,
    TRIM(t.text) AS text,
    t.date AS published_at,
    t.created_at AS scraped_at,
    t.updated_at,
    (t.estaCreciendo = 1) AS is_growing,
    TRY_CAST(NULLIF(TRIM(t.retweetedTweetId), '') AS BIGINT) AS retweeted_tweet_id,
    t.raw_data
FROM bronze.tw_tweets t
INNER JOIN bronze.tw_users u ON t.user_id = u.user_id;

-- Replies: fix INT32 overflow on inReplyToTweetId using inReplyToTweetIdStr
CREATE OR REPLACE TABLE silver.tw_tweets_replies AS
SELECT
    r.id::BIGINT AS tweet_id,
    CAST(r.id_str AS VARCHAR) AS id_str,
    r.url,
    r.user_id::BIGINT AS author_user_id,
    NULLIF(TRIM(json_extract_string(r.raw_data, '$.user.username')), '') AS author_username,
    TRIM(r.text) AS text,
    CAST(r.inReplyToTweetIdStr AS BIGINT) AS in_reply_to_tweet_id,
    CAST(r.inReplyToTweetIdStr AS VARCHAR) AS in_reply_to_tweet_id_str,
    p.user_id AS parent_author_user_id,
    TRIM(pu.username) AS parent_author_username,
    r.replyCount::INTEGER AS reply_count,
    r.retweetCount::INTEGER AS retweet_count,
    r.quoteCount::INTEGER AS quote_count,
    r.viewCount::BIGINT AS view_count,
    r.likeCount::INTEGER AS like_count,
    r.date AS published_at,
    r.created_at AS scraped_at,
    r.updated_at,
    (r.estaCreciendo = 1) AS is_growing,
    r.raw_data
FROM bronze.tw_tweets_replies r
INNER JOIN bronze.tw_tweets p
    ON CAST(r.inReplyToTweetIdStr AS BIGINT) = p.id
LEFT JOIN bronze.tw_users pu ON p.user_id = pu.user_id;

-- LLM classifications for top-10 tweets by reply volume
CREATE OR REPLACE TABLE silver.tw_comments_classification AS
SELECT
    c.id::INTEGER AS classification_id,
    c.post_id::BIGINT AS parent_tweet_id,
    c.origen AS source_platform,
    c.comment_id::BIGINT AS reply_tweet_id,
    TRIM(c.resumen) AS summary,
    c.created_at AS classified_at,
    c.updated_at,
    TRIM(c.free_criteria) AS criteria_code,
    CASE TRIM(c.free_criteria)
        WHEN '1' THEN 'apoyo_izquierda'
        WHEN '2' THEN 'derecha_o_troll'
        WHEN '3' THEN 'neutral'
        WHEN 'INCLASIFICABLE' THEN 'inclasificable'
        WHEN '1,2' THEN 'ambiguo'
        ELSE 'otro'
    END AS criteria_label,
    r.text AS reply_text,
    r.author_user_id AS reply_author_user_id,
    r.author_username AS reply_author_username,
    TRIM(pu.username) AS parent_author_username
FROM bronze.tw_comments_classification c
LEFT JOIN silver.tw_tweets_replies r ON c.comment_id = r.tweet_id
LEFT JOIN silver.tw_tweets pt ON c.post_id = pt.tweet_id
LEFT JOIN bronze.tw_users pu ON pt.user_id = pu.user_id;

-- ---------------------------------------------------------------------------
-- silver.tw_users — catalog of Twitter/X accounts (tracked + reply/post authors)
-- Sources: bronze.tw_users, legacy reply raw_data.user, twikit profile/tweets/replies
-- ---------------------------------------------------------------------------

CREATE OR REPLACE TEMP TABLE staging_tw_users_raw AS
-- Tracked accounts from legacy users.csv
SELECT
    TRY_CAST(u.user_id AS BIGINT) AS user_id,
    LOWER(TRIM(u.username)) AS username_key,
    TRIM(u.username) AS username,
    NULL::VARCHAR AS display_name,
    NULL::TIMESTAMP AS account_created_at,
    NULL::VARCHAR AS bio,
    NULL::VARCHAR AS location,
    NULL::BOOLEAN AS is_protected,
    NULL::BIGINT AS followers_count,
    NULL::BIGINT AS following_count,
    NULL::BIGINT AS statuses_count,
    NULL::BIGINT AS listed_count,
    NULL::BIGINT AS media_count,
    NULL::BIGINT AS favourites_count,
    NULL::BOOLEAN AS is_blue_verified,
    NULL::BOOLEAN AS is_verified,
    NULL::VARCHAR AS profile_image_url,
    (u.is_pts = 1) AS is_pts,
    (u.track = 1) AS track,
    (u.is_diputado = 1) AS is_diputado,
    TRUE AS from_tracked,
    FALSE AS from_legacy_reply,
    FALSE AS from_twikit,
    u.id::INTEGER AS legacy_row_id,
    0::BIGINT AS observed_replies,
    NULL::TIMESTAMP AS first_seen_at,
    NULL::TIMESTAMP AS last_seen_at
FROM bronze.tw_users u
WHERE TRIM(u.username) IS NOT NULL AND LENGTH(TRIM(u.username)) > 0

UNION ALL

-- Authors of legacy original tweets (usually same 4 tracked)
SELECT
    t.user_id::BIGINT AS user_id,
    LOWER(TRIM(u.username)) AS username_key,
    TRIM(u.username) AS username,
    NULL::VARCHAR AS display_name,
    NULL::TIMESTAMP AS account_created_at,
    NULL::VARCHAR AS bio,
    NULL::VARCHAR AS location,
    NULL::BOOLEAN AS is_protected,
    NULL::BIGINT AS followers_count,
    NULL::BIGINT AS following_count,
    NULL::BIGINT AS statuses_count,
    NULL::BIGINT AS listed_count,
    NULL::BIGINT AS media_count,
    NULL::BIGINT AS favourites_count,
    NULL::BOOLEAN AS is_blue_verified,
    NULL::BOOLEAN AS is_verified,
    NULL::VARCHAR AS profile_image_url,
    (u.is_pts = 1) AS is_pts,
    (u.track = 1) AS track,
    (u.is_diputado = 1) AS is_diputado,
    TRUE AS from_tracked,
    FALSE AS from_legacy_reply,
    FALSE AS from_twikit,
    u.id::INTEGER AS legacy_row_id,
    0::BIGINT AS observed_replies,
    MIN(t.date)::TIMESTAMP AS first_seen_at,
    MAX(t.date)::TIMESTAMP AS last_seen_at
FROM bronze.tw_tweets t
INNER JOIN bronze.tw_users u ON t.user_id = u.user_id
GROUP BY
    t.user_id, u.username, u.is_pts, u.track, u.is_diputado, u.id

UNION ALL

-- Reply authors from legacy snscrape-style raw_data.user (rich profile fields)
SELECT
    r.user_id::BIGINT AS user_id,
    LOWER(TRIM(json_extract_string(r.raw_data, '$.user.username'))) AS username_key,
    TRIM(json_extract_string(r.raw_data, '$.user.username')) AS username,
    NULLIF(TRIM(json_extract_string(r.raw_data, '$.user.displayname')), '') AS display_name,
    TRY_CAST(json_extract_string(r.raw_data, '$.user.created') AS TIMESTAMP) AS account_created_at,
    NULLIF(TRIM(json_extract_string(r.raw_data, '$.user.rawDescription')), '') AS bio,
    NULLIF(TRIM(json_extract_string(r.raw_data, '$.user.location')), '') AS location,
    TRY_CAST(json_extract_string(r.raw_data, '$.user.protected') AS BOOLEAN) AS is_protected,
    TRY_CAST(json_extract_string(r.raw_data, '$.user.followersCount') AS BIGINT) AS followers_count,
    TRY_CAST(json_extract_string(r.raw_data, '$.user.friendsCount') AS BIGINT) AS following_count,
    TRY_CAST(json_extract_string(r.raw_data, '$.user.statusesCount') AS BIGINT) AS statuses_count,
    TRY_CAST(json_extract_string(r.raw_data, '$.user.listedCount') AS BIGINT) AS listed_count,
    TRY_CAST(json_extract_string(r.raw_data, '$.user.mediaCount') AS BIGINT) AS media_count,
    TRY_CAST(json_extract_string(r.raw_data, '$.user.favouritesCount') AS BIGINT) AS favourites_count,
    TRY_CAST(json_extract_string(r.raw_data, '$.user.blue') AS BOOLEAN) AS is_blue_verified,
    TRY_CAST(json_extract_string(r.raw_data, '$.user.verified') AS BOOLEAN) AS is_verified,
    NULLIF(TRIM(json_extract_string(r.raw_data, '$.user.profileImageUrl')), '') AS profile_image_url,
    FALSE AS is_pts,
    FALSE AS track,
    FALSE AS is_diputado,
    FALSE AS from_tracked,
    TRUE AS from_legacy_reply,
    FALSE AS from_twikit,
    NULL::INTEGER AS legacy_row_id,
    COUNT(*)::BIGINT AS observed_replies,
    MIN(r.date)::TIMESTAMP AS first_seen_at,
    MAX(r.date)::TIMESTAMP AS last_seen_at
FROM bronze.tw_tweets_replies r
WHERE NULLIF(TRIM(json_extract_string(r.raw_data, '$.user.username')), '') IS NOT NULL
GROUP BY
    r.user_id,
    LOWER(TRIM(json_extract_string(r.raw_data, '$.user.username'))),
    TRIM(json_extract_string(r.raw_data, '$.user.username')),
    NULLIF(TRIM(json_extract_string(r.raw_data, '$.user.displayname')), ''),
    TRY_CAST(json_extract_string(r.raw_data, '$.user.created') AS TIMESTAMP),
    NULLIF(TRIM(json_extract_string(r.raw_data, '$.user.rawDescription')), ''),
    NULLIF(TRIM(json_extract_string(r.raw_data, '$.user.location')), ''),
    TRY_CAST(json_extract_string(r.raw_data, '$.user.protected') AS BOOLEAN),
    TRY_CAST(json_extract_string(r.raw_data, '$.user.followersCount') AS BIGINT),
    TRY_CAST(json_extract_string(r.raw_data, '$.user.friendsCount') AS BIGINT),
    TRY_CAST(json_extract_string(r.raw_data, '$.user.statusesCount') AS BIGINT),
    TRY_CAST(json_extract_string(r.raw_data, '$.user.listedCount') AS BIGINT),
    TRY_CAST(json_extract_string(r.raw_data, '$.user.mediaCount') AS BIGINT),
    TRY_CAST(json_extract_string(r.raw_data, '$.user.favouritesCount') AS BIGINT),
    TRY_CAST(json_extract_string(r.raw_data, '$.user.blue') AS BOOLEAN),
    TRY_CAST(json_extract_string(r.raw_data, '$.user.verified') AS BOOLEAN),
    NULLIF(TRIM(json_extract_string(r.raw_data, '$.user.profileImageUrl')), '')
;

-- Twikit profile (scraped account) — only if table exists with rows
CREATE OR REPLACE TEMP TABLE staging_tw_users_twikit AS
SELECT * FROM (
    SELECT
        TRY_CAST(p.user_id AS BIGINT) AS user_id,
        LOWER(TRIM(p.username)) AS username_key,
        TRIM(p.username) AS username,
        NULLIF(TRIM(p.display_name), '') AS display_name,
        NULL::TIMESTAMP AS account_created_at,
        NULLIF(TRIM(p.description), '') AS bio,
        NULL::VARCHAR AS location,
        NULL::BOOLEAN AS is_protected,
        p.followers_count,
        p.following_count,
        p.statuses_count,
        NULL::BIGINT AS listed_count,
        NULL::BIGINT AS media_count,
        NULL::BIGINT AS favourites_count,
        NULL::BOOLEAN AS is_blue_verified,
        NULL::BOOLEAN AS is_verified,
        NULL::VARCHAR AS profile_image_url,
        FALSE AS is_pts,
        FALSE AS track,
        FALSE AS is_diputado,
        FALSE AS from_tracked,
        FALSE AS from_legacy_reply,
        TRUE AS from_twikit,
        NULL::INTEGER AS legacy_row_id,
        0::BIGINT AS observed_replies,
        p.ingested_at AS first_seen_at,
        p.ingested_at AS last_seen_at
    FROM silver.tk_tw_profile p
    WHERE TRIM(p.username) IS NOT NULL AND LENGTH(TRIM(p.username)) > 0
) _
WHERE EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'silver' AND table_name = 'tk_tw_profile'
);

-- Twikit reply authors (sparse profile: id / screen_name / name only)
INSERT INTO staging_tw_users_twikit
SELECT
    TRY_CAST(r.author_id AS BIGINT) AS user_id,
    LOWER(TRIM(r.username)) AS username_key,
    TRIM(r.username) AS username,
    NULLIF(TRIM(r.author_name), '') AS display_name,
    NULL::TIMESTAMP AS account_created_at,
    NULL::VARCHAR AS bio,
    NULL::VARCHAR AS location,
    NULL::BOOLEAN AS is_protected,
    NULL::BIGINT AS followers_count,
    NULL::BIGINT AS following_count,
    NULL::BIGINT AS statuses_count,
    NULL::BIGINT AS listed_count,
    NULL::BIGINT AS media_count,
    NULL::BIGINT AS favourites_count,
    NULL::BOOLEAN AS is_blue_verified,
    NULL::BOOLEAN AS is_verified,
    NULL::VARCHAR AS profile_image_url,
    FALSE AS is_pts,
    FALSE AS track,
    FALSE AS is_diputado,
    FALSE AS from_tracked,
    FALSE AS from_legacy_reply,
    TRUE AS from_twikit,
    NULL::INTEGER AS legacy_row_id,
    COUNT(*)::BIGINT AS observed_replies,
    MIN(COALESCE(r.created_at_ts, TRY_CAST(r.created_at AS TIMESTAMP))) AS first_seen_at,
    MAX(COALESCE(r.created_at_ts, TRY_CAST(r.created_at AS TIMESTAMP))) AS last_seen_at
FROM silver.tk_tw_reply r
WHERE EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'silver' AND table_name = 'tk_tw_reply'
)
  AND TRIM(r.username) IS NOT NULL AND LENGTH(TRIM(r.username)) > 0
GROUP BY
    TRY_CAST(r.author_id AS BIGINT),
    LOWER(TRIM(r.username)),
    TRIM(r.username),
    NULLIF(TRIM(r.author_name), '');

CREATE OR REPLACE TEMP TABLE staging_tw_users_all AS
SELECT * FROM staging_tw_users_raw
UNION ALL BY NAME
SELECT * FROM staging_tw_users_twikit;

-- Hater flags from legacy + twikit classifications (if present)
CREATE OR REPLACE TEMP TABLE staging_tw_hater AS
SELECT
    LOWER(TRIM(username)) AS username_key,
    SUM(hater_n)::BIGINT AS hater_replies_count
FROM (
    SELECT
        c.reply_author_username AS username,
        COUNT(*) AS hater_n
    FROM silver.tw_comments_classification c
    WHERE c.criteria_label = 'derecha_o_troll'
      AND c.reply_author_username IS NOT NULL
    GROUP BY 1

    UNION ALL

    SELECT
        a.username,
        COUNT(*) AS hater_n
    FROM gold.tk_hater_narrativa_assignment a
    WHERE EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'gold' AND table_name = 'tk_hater_narrativa_assignment'
    )
      AND a.username IS NOT NULL
    GROUP BY 1

    UNION ALL

    SELECT
        r.username,
        COUNT(*) AS hater_n
    FROM silver.tk_tw_reply_classification cl
    JOIN silver.tk_tw_reply r ON cl.reply_id = CAST(r.reply_id AS VARCHAR)
    WHERE EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'silver' AND table_name = 'tk_tw_reply_classification'
    )
      AND cl.criterio_label = 'derecha_o_troll'
      AND r.username IS NOT NULL
    GROUP BY 1
) h
GROUP BY 1;

CREATE OR REPLACE TABLE silver.tw_users AS
WITH ranked AS (
    SELECT
        s.*,
        ROW_NUMBER() OVER (
            PARTITION BY COALESCE(CAST(s.user_id AS VARCHAR), 'u:' || s.username_key)
            ORDER BY
                s.from_tracked DESC,
                (s.followers_count IS NOT NULL) DESC,
                s.observed_replies DESC,
                s.from_legacy_reply DESC,
                s.from_twikit DESC
        ) AS rn
    FROM staging_tw_users_all s
    WHERE s.username_key IS NOT NULL AND LENGTH(s.username_key) > 0
),
agg AS (
    SELECT
        COALESCE(CAST(user_id AS VARCHAR), 'u:' || username_key) AS merge_key,
        MAX(user_id) AS user_id,
        MAX(username_key) AS username_key,
        MAX(username) AS username,
        MAX(display_name) AS display_name,
        MAX(account_created_at) AS account_created_at,
        MAX(bio) AS bio,
        MAX(location) AS location,
        MAX(is_protected) AS is_protected,
        MAX(followers_count) AS followers_count,
        MAX(following_count) AS following_count,
        MAX(statuses_count) AS statuses_count,
        MAX(listed_count) AS listed_count,
        MAX(media_count) AS media_count,
        MAX(favourites_count) AS favourites_count,
        MAX(is_blue_verified) AS is_blue_verified,
        MAX(is_verified) AS is_verified,
        MAX(profile_image_url) AS profile_image_url,
        BOOL_OR(is_pts) AS is_pts,
        BOOL_OR(track) AS track,
        BOOL_OR(is_diputado) AS is_diputado,
        BOOL_OR(from_tracked) AS from_tracked,
        BOOL_OR(from_legacy_reply) AS from_legacy_reply,
        BOOL_OR(from_twikit) AS from_twikit,
        MAX(legacy_row_id) AS legacy_row_id,
        SUM(observed_replies) AS replies_observed_count,
        MIN(first_seen_at) AS first_seen_at,
        MAX(last_seen_at) AS last_seen_at
    FROM ranked
    GROUP BY COALESCE(CAST(user_id AS VARCHAR), 'u:' || username_key)
)
SELECT
    a.user_id,
    a.username,
    a.display_name,
    CASE
        WHEN a.username IS NOT NULL THEN 'https://x.com/' || a.username
    END AS profile_url,
    a.account_created_at,
    a.bio,
    a.location,
    a.is_protected,
    a.followers_count,
    a.following_count,
    a.statuses_count,
    a.listed_count,
    a.media_count,
    a.favourites_count,
    a.is_blue_verified,
    a.is_verified,
    a.profile_image_url,
    COALESCE(a.is_pts, FALSE) AS is_pts,
    COALESCE(a.track, FALSE) AS track,
    COALESCE(a.is_diputado, FALSE) AS is_diputado,
    COALESCE(h.hater_replies_count, 0) > 0 AS is_hater,
    COALESCE(h.hater_replies_count, 0) AS hater_replies_count,
    COALESCE(a.replies_observed_count, 0) AS replies_observed_count,
    a.first_seen_at,
    a.last_seen_at,
    CASE
        WHEN a.from_tracked AND (a.from_legacy_reply OR a.from_twikit) THEN 'tracked+observed'
        WHEN a.from_tracked THEN 'tracked'
        WHEN a.from_legacy_reply AND a.from_twikit THEN 'legacy+twikit'
        WHEN a.from_legacy_reply THEN 'legacy_reply'
        WHEN a.from_twikit THEN 'twikit'
        ELSE 'unknown'
    END AS source,
    a.legacy_row_id AS id,
    current_timestamp AS ingested_at
FROM agg a
LEFT JOIN staging_tw_hater h ON a.username_key = h.username_key
ORDER BY
    COALESCE(a.track, FALSE) DESC,
    (COALESCE(h.hater_replies_count, 0) > 0) DESC,
    COALESCE(a.replies_observed_count, 0) DESC,
    a.username;
