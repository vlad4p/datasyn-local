-- Twitter/X bronze → silver (clean, typed, joined)
-- Prereq: scripts/sql/ingest_twitter.sql
-- Uso: uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_twitter_silver.sql

CREATE SCHEMA IF NOT EXISTS silver;

-- Users: 4 tracked accounts, boolean flags typed
CREATE OR REPLACE TABLE silver.tw_users AS
SELECT
    id::INTEGER AS id,
    TRIM(username) AS username,
    user_id::BIGINT AS user_id,
    (is_pts = 1) AS is_pts,
    (track = 1) AS track,
    (is_diputado = 1) AS is_diputado
FROM bronze.tw_users;

-- Original tweets (no retweets in source), enriched with author username
CREATE OR REPLACE TABLE silver.tw_tweets AS
SELECT
    t.id::BIGINT AS tweet_id,
    CAST(t.id_str AS VARCHAR) AS id_str,
    t.url,
    t.user_id::BIGINT AS user_id,
    u.username AS author_username,
    u.is_diputado AS author_is_diputado,
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
INNER JOIN silver.tw_users u ON t.user_id = u.user_id;

-- Replies: fix INT32 overflow on inReplyToTweetId using inReplyToTweetIdStr
CREATE OR REPLACE TABLE silver.tw_tweets_replies AS
SELECT
    r.id::BIGINT AS tweet_id,
    CAST(r.id_str AS VARCHAR) AS id_str,
    r.url,
    r.user_id::BIGINT AS author_user_id,
    TRIM(r.text) AS text,
    CAST(r.inReplyToTweetIdStr AS BIGINT) AS in_reply_to_tweet_id,
    CAST(r.inReplyToTweetIdStr AS VARCHAR) AS in_reply_to_tweet_id_str,
    p.user_id AS parent_author_user_id,
    pu.username AS parent_author_username,
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
LEFT JOIN silver.tw_users pu ON p.user_id = pu.user_id;

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
    pu.username AS parent_author_username
FROM bronze.tw_comments_classification c
LEFT JOIN silver.tw_tweets_replies r ON c.comment_id = r.tweet_id
LEFT JOIN silver.tw_tweets pt ON c.post_id = pt.tweet_id
LEFT JOIN silver.tw_users pu ON pt.user_id = pu.user_id;
