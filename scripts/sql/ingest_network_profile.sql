-- Build silver.network_profile from legacy Facebook (fb_*) and Twitter (tw_*) tables.
-- One row per canonical identity with platform IDs/handles and networks_found[].
-- Uso: uv run python scripts/python/db.py mcp-stop
--      uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_network_profile.sql

CREATE SCHEMA IF NOT EXISTS silver;

CREATE OR REPLACE TEMP TABLE staging_network_identities AS
WITH fb_fanpages AS (
    SELECT
        'facebook'::VARCHAR AS platform,
        'page'::VARCHAR AS entity_type,
        'fanpage'::VARCHAR AS entity_role,
        CAST(f.fanpage_id AS VARCHAR) AS external_id,
        NULL::VARCHAR AS handle,
        TRIM(f.descripcion) AS display_name,
        'https://www.facebook.com/' || CAST(f.fanpage_id AS VARCHAR) AS profile_url,
        f.instagram_id,
        (f.pts = 1) AS is_pts,
        FALSE AS is_diputado,
        TRUE AS is_tracked,
        NULL::TIMESTAMP AS first_seen,
        NULL::TIMESTAMP AS last_seen,
        0::BIGINT AS comments_count,
        (SELECT COUNT(*) FROM silver.fb_post p WHERE p.fanpage_id = f.fanpage_id) AS posts_count,
        0::BIGINT AS tweets_count,
        0::BIGINT AS replies_count,
        ['silver.fb_fanpage', 'silver.fb_post']::VARCHAR[] AS source_tables
    FROM silver.fb_fanpage AS f
),
fb_commenters AS (
    SELECT
        'facebook'::VARCHAR AS platform,
        'person'::VARCHAR AS entity_type,
        'commenter'::VARCHAR AS entity_role,
        CAST(c.user_id AS VARCHAR) AS external_id,
        NULLIF(LOWER(TRIM(c.user_name)), '') AS handle,
        NULLIF(TRIM(c.user_name), '') AS display_name,
        CASE
            WHEN c.user_id IS NOT NULL
                THEN 'https://www.facebook.com/profile.php?id=' || CAST(c.user_id AS VARCHAR)
        END AS profile_url,
        NULL::BIGINT AS instagram_id,
        FALSE AS is_pts,
        FALSE AS is_diputado,
        FALSE AS is_tracked,
        MIN(c.fecha_comentario) AS first_seen,
        MAX(c.fecha_comentario) AS last_seen,
        COUNT(*) AS comments_count,
        0::BIGINT AS posts_count,
        0::BIGINT AS tweets_count,
        0::BIGINT AS replies_count,
        ['silver.fb_comment']::VARCHAR[] AS source_tables
    FROM silver.fb_comment AS c
    WHERE c.user_id IS NOT NULL
       OR (c.user_name IS NOT NULL AND LENGTH(TRIM(c.user_name)) > 0)
    GROUP BY
        c.user_id,
        NULLIF(LOWER(TRIM(c.user_name)), ''),
        NULLIF(TRIM(c.user_name), '')
),
tw_tracked AS (
    SELECT
        'twitter'::VARCHAR AS platform,
        'person'::VARCHAR AS entity_type,
        'tracked_account'::VARCHAR AS entity_role,
        CAST(u.user_id AS VARCHAR) AS external_id,
        LOWER(TRIM(u.username)) AS handle,
        TRIM(u.username) AS display_name,
        'https://x.com/' || TRIM(u.username) AS profile_url,
        NULL::BIGINT AS instagram_id,
        u.is_pts,
        u.is_diputado,
        u.track AS is_tracked,
        NULL::TIMESTAMP AS first_seen,
        NULL::TIMESTAMP AS last_seen,
        0::BIGINT AS comments_count,
        0::BIGINT AS posts_count,
        (SELECT COUNT(*) FROM silver.tw_tweets t WHERE t.user_id = u.user_id) AS tweets_count,
        0::BIGINT AS replies_count,
        ['silver.tw_users', 'silver.tw_tweets']::VARCHAR[] AS source_tables
    FROM silver.tw_users AS u
    WHERE u.track = TRUE
),
tw_reply_authors AS (
    SELECT
        'twitter'::VARCHAR AS platform,
        'person'::VARCHAR AS entity_type,
        'reply_author'::VARCHAR AS entity_role,
        CAST(r.author_user_id AS VARCHAR) AS external_id,
        LOWER(TRIM(r.author_username)) AS handle,
        TRIM(r.author_username) AS display_name,
        CASE
            WHEN TRIM(r.author_username) IS NOT NULL
                THEN 'https://x.com/' || TRIM(r.author_username)
        END AS profile_url,
        NULL::BIGINT AS instagram_id,
        COALESCE(tu.is_pts, FALSE) AS is_pts,
        COALESCE(tu.is_diputado, FALSE) AS is_diputado,
        COALESCE(tu.track, FALSE) AS is_tracked,
        MIN(r.published_at) AS first_seen,
        MAX(r.published_at) AS last_seen,
        0::BIGINT AS comments_count,
        0::BIGINT AS posts_count,
        0::BIGINT AS tweets_count,
        COUNT(*) AS replies_count,
        ['silver.tw_tweets_replies']::VARCHAR[] AS source_tables
    FROM silver.tw_tweets_replies AS r
    LEFT JOIN silver.tw_users AS tu ON r.author_user_id = tu.user_id
    WHERE r.author_user_id IS NOT NULL
       OR (r.author_username IS NOT NULL AND LENGTH(TRIM(r.author_username)) > 0)
    GROUP BY
        r.author_user_id,
        LOWER(TRIM(r.author_username)),
        TRIM(r.author_username),
        tu.is_pts,
        tu.is_diputado,
        tu.track
),
all_identities AS (
    SELECT * FROM fb_fanpages
    UNION ALL SELECT * FROM fb_commenters
    UNION ALL SELECT * FROM tw_tracked
    UNION ALL SELECT * FROM tw_reply_authors
),
normalized AS (
    SELECT
        ai.*,
        CASE
            WHEN ai.platform = 'twitter'
                 AND ai.handle IS NOT NULL
                THEN 'tw:' || ai.handle
            WHEN ai.platform = 'facebook'
                 AND ai.entity_type = 'page'
                 AND ai.handle IS NULL
                THEN COALESCE(
                    (
                        SELECT 'tw:' || LOWER(TRIM(u.username))
                        FROM silver.tw_users AS u
                        WHERE LOWER(REGEXP_REPLACE(ai.display_name, '\.PTS$', '', 'i')) = LOWER(u.username)
                           OR LOWER(REPLACE(ai.display_name, '.', '')) = LOWER(REPLACE(u.username, '.', ''))
                        LIMIT 1
                    ),
                    'fb_page:' || ai.external_id
                )
            WHEN ai.platform = 'facebook'
                 AND ai.entity_type = 'person'
                 AND ai.external_id IS NOT NULL
                THEN 'fb_user:' || ai.external_id
            WHEN ai.platform = 'facebook'
                 AND ai.entity_type = 'person'
                THEN 'fb_name:' || COALESCE(ai.handle, lower(COALESCE(ai.display_name, 'unknown')))
            WHEN ai.platform = 'twitter'
                 AND ai.external_id IS NOT NULL
                THEN 'tw_id:' || ai.external_id
            ELSE ai.platform || ':' || COALESCE(ai.external_id, ai.handle, 'unknown')
        END AS canonical_key
    FROM all_identities AS ai
    WHERE COALESCE(ai.external_id, ai.handle, ai.display_name) IS NOT NULL
)
SELECT * FROM normalized;

-- Latest Twitter/X profile snapshot per user (from tweet + reply raw_data JSON)
CREATE OR REPLACE TEMP TABLE staging_tw_profile_snapshot AS
WITH raw_users AS (
    SELECT
        t.user_id,
        LOWER(TRIM(json_extract_string(t.raw_data, '$.user.username'))) AS username,
        t.published_at AS snapshot_at,
        t.raw_data
    FROM silver.tw_tweets AS t
    WHERE t.raw_data IS NOT NULL

    UNION ALL

    SELECT
        r.author_user_id,
        LOWER(TRIM(r.author_username)),
        r.published_at,
        r.raw_data
    FROM silver.tw_tweets_replies AS r
    WHERE r.raw_data IS NOT NULL
),
ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY COALESCE(CAST(user_id AS VARCHAR), username)
            ORDER BY snapshot_at DESC
        ) AS rn
    FROM raw_users
    WHERE user_id IS NOT NULL OR username IS NOT NULL
)
SELECT
    CAST(user_id AS VARCHAR) AS twitter_user_id,
    username AS twitter_username,
    NULLIF(TRIM(json_extract_string(raw_data, '$.user.displayname')), '') AS twitter_display_name,
    NULLIF(TRIM(json_extract_string(raw_data, '$.user.rawDescription')), '') AS twitter_bio,
    COALESCE(
        NULLIF(TRIM(json_extract_string(raw_data, '$.user.location.location')), ''),
        NULLIF(TRIM(CAST(json_extract(raw_data, '$.user.location') AS VARCHAR)), '')
    ) AS twitter_location,
    TRY_CAST(json_extract_string(raw_data, '$.user.followersCount') AS BIGINT) AS twitter_followers_count,
    TRY_CAST(json_extract_string(raw_data, '$.user.friendsCount') AS BIGINT) AS twitter_following_count,
    TRY_CAST(json_extract_string(raw_data, '$.user.statusesCount') AS BIGINT) AS twitter_statuses_count,
    TRY_CAST(json_extract_string(raw_data, '$.user.listedCount') AS BIGINT) AS twitter_listed_count,
    TRY_CAST(json_extract_string(raw_data, '$.user.mediaCount') AS BIGINT) AS twitter_media_count,
    TRY_CAST(json_extract_string(raw_data, '$.user.favouritesCount') AS BIGINT) AS twitter_favourites_count,
    COALESCE(
        TRY_CAST(json_extract_string(raw_data, '$.user.blue') AS BOOLEAN),
        FALSE
    ) AS twitter_is_blue_verified,
    TRY_CAST(json_extract_string(raw_data, '$.user.created') AS TIMESTAMPTZ) AS twitter_account_created_at,
    NULLIF(TRIM(json_extract_string(raw_data, '$.user.profileImageUrl')), '') AS twitter_profile_image_url,
    snapshot_at AS twitter_profile_snapshot_at
FROM ranked
WHERE rn = 1;

-- Facebook page engagement proxy (no page follower count in legacy CSV)
CREATE OR REPLACE TEMP TABLE staging_fb_page_engagement AS
SELECT
    CAST(p.fanpage_id AS VARCHAR) AS facebook_page_id,
    COUNT(*) AS facebook_posts_in_period,
    SUM(p.reacciones) AS facebook_page_total_reactions,
    SUM(p.comentarios) AS facebook_page_total_comments_on_posts,
    SUM(p.compartidos) AS facebook_page_total_shares,
    SUM(p.likes) AS facebook_page_total_likes,
    ROUND(AVG(p.reacciones), 1) AS facebook_page_avg_reactions_per_post,
    MAX(p.fecha_post) AS facebook_page_last_post_at,
    MIN(p.fecha_post) AS facebook_page_first_post_at
FROM silver.fb_post AS p
GROUP BY p.fanpage_id;

-- Classified-comment activity per author (FB + TW legacy sample)
CREATE OR REPLACE TEMP TABLE staging_author_classification_stats AS
WITH unified AS (
    SELECT
        CASE
            WHEN c.user_id IS NOT NULL THEN 'fb_user:' || CAST(c.user_id AS VARCHAR)
            WHEN NULLIF(TRIM(c.user_name), '') IS NOT NULL
                THEN 'fb_name:' || LOWER(TRIM(c.user_name))
        END AS autor_key,
        cl.criterio_label AS posicion,
        cl.resumen,
        c.fecha_comentario AS fecha
    FROM silver.fb_comment AS c
    INNER JOIN silver.fb_comment_classification AS cl
        ON CAST(c.comentario_id AS VARCHAR) = cl.comment_id

    UNION ALL

    SELECT
        CASE
            WHEN tc.reply_author_user_id IS NOT NULL
                THEN 'tw_id:' || CAST(tc.reply_author_user_id AS VARCHAR)
            WHEN tc.reply_author_username IS NOT NULL
                THEN 'tw:' || LOWER(TRIM(tc.reply_author_username))
        END,
        tc.criteria_label,
        tc.summary,
        tc.classified_at
    FROM silver.tw_comments_classification AS tc
)
SELECT
    autor_key,
    COUNT(*) AS comentarios_clasificados,
    COUNT(*) FILTER (WHERE posicion = 'derecha_o_troll') AS comentarios_troll,
    COUNT(*) FILTER (WHERE posicion = 'apoyo_izquierda') AS comentarios_apoyo,
    COUNT(*) FILTER (WHERE posicion = 'neutral') AS comentarios_neutral,
    MIN(fecha) AS primer_comentario_clasificado,
    MAX(fecha) AS ultimo_comentario_clasificado,
    MODE(resumen) AS resumen_modal
FROM unified
WHERE autor_key IS NOT NULL
GROUP BY autor_key;

CREATE OR REPLACE TABLE silver.network_profile AS
WITH aggregated AS (
    SELECT
        canonical_key,
        MAX(display_name) FILTER (WHERE display_name IS NOT NULL) AS display_name,
        MAX(profile_url) FILTER (WHERE profile_url IS NOT NULL) AS primary_profile_url,
        MAX(instagram_id) FILTER (WHERE instagram_id IS NOT NULL) AS instagram_id,
        BOOL_OR(is_pts) AS is_pts,
        BOOL_OR(is_diputado) AS is_diputado,
        BOOL_OR(is_tracked) AS is_tracked,
        MIN(first_seen) AS first_seen,
        MAX(last_seen) AS last_seen,
        SUM(comments_count) AS comments_count,
        SUM(posts_count) AS posts_count,
        SUM(tweets_count) AS tweets_count,
        SUM(replies_count) AS replies_count,
        LIST(DISTINCT platform ORDER BY platform) AS networks_found,
        LIST(DISTINCT entity_type ORDER BY entity_type) AS entity_types,
        LIST(DISTINCT entity_role ORDER BY entity_role) AS entity_roles
    FROM staging_network_identities
    GROUP BY canonical_key
),
source_tables_agg AS (
    SELECT
        canonical_key,
        LIST(DISTINCT st ORDER BY st) AS source_tables
    FROM staging_network_identities
    CROSS JOIN UNNEST(source_tables) AS t(st)
    GROUP BY canonical_key
),
platform_ids AS (
    SELECT
        canonical_key,
        MAX(external_id) FILTER (WHERE platform = 'facebook' AND entity_type = 'page') AS facebook_page_id,
        MAX(display_name) FILTER (WHERE platform = 'facebook' AND entity_type = 'page') AS facebook_page_name,
        MAX(external_id) FILTER (WHERE platform = 'facebook' AND entity_type = 'person') AS facebook_user_id,
        MAX(display_name) FILTER (WHERE platform = 'facebook' AND entity_type = 'person') AS facebook_user_name,
        MAX(external_id) FILTER (WHERE platform = 'twitter') AS twitter_user_id,
        MAX(handle) FILTER (WHERE platform = 'twitter') AS twitter_username,
        MAX(profile_url) FILTER (WHERE platform = 'twitter') AS twitter_profile_url,
        MAX(profile_url) FILTER (WHERE platform = 'facebook' AND entity_type = 'page') AS facebook_page_url,
        MAX(profile_url) FILTER (WHERE platform = 'facebook' AND entity_type = 'person') AS facebook_user_url
    FROM staging_network_identities
    GROUP BY canonical_key
)
SELECT
    md5(a.canonical_key) AS profile_id,
    a.canonical_key,
    COALESCE(tw.twitter_display_name, a.display_name) AS display_name,
    a.primary_profile_url,
    p.facebook_page_id,
    p.facebook_page_name,
    p.facebook_page_url,
    p.facebook_user_id,
    p.facebook_user_name,
    p.facebook_user_url,
    COALESCE(p.twitter_user_id, tw.twitter_user_id) AS twitter_user_id,
    COALESCE(p.twitter_username, tw.twitter_username) AS twitter_username,
    COALESCE(p.twitter_profile_url, CASE WHEN tw.twitter_username IS NOT NULL
        THEN 'https://x.com/' || tw.twitter_username END) AS twitter_profile_url,
    a.instagram_id,
    NULL::VARCHAR AS instagram_profile_url,
    CASE WHEN a.instagram_id IS NOT NULL THEN 'instagram' END AS instagram_linked,
    a.networks_found,
    a.entity_types,
    a.entity_roles,
    st.source_tables,
    a.is_pts,
    a.is_diputado,
    a.is_tracked,
    a.comments_count,
    a.posts_count,
    a.tweets_count,
    a.replies_count,
    a.first_seen,
    a.last_seen,
    -- Twitter/X profile snapshot (from raw_data, latest tweet or reply)
    tw.twitter_display_name,
    tw.twitter_bio,
    tw.twitter_location,
    tw.twitter_followers_count,
    tw.twitter_following_count,
    tw.twitter_statuses_count,
    tw.twitter_listed_count,
    tw.twitter_media_count,
    tw.twitter_favourites_count,
    tw.twitter_is_blue_verified,
    tw.twitter_account_created_at,
    tw.twitter_profile_image_url,
    tw.twitter_profile_snapshot_at,
    -- Facebook page engagement (legacy dump — not page followers)
    fb.facebook_posts_in_period,
    fb.facebook_page_total_reactions,
    fb.facebook_page_total_comments_on_posts,
    fb.facebook_page_total_shares,
    fb.facebook_page_total_likes,
    fb.facebook_page_avg_reactions_per_post,
    fb.facebook_page_first_post_at,
    fb.facebook_page_last_post_at,
    -- Classified-comment activity (when author can be linked)
    COALESCE(cs.comentarios_clasificados, 0) AS comentarios_clasificados,
    COALESCE(cs.comentarios_troll, 0) AS comentarios_troll,
    COALESCE(cs.comentarios_apoyo, 0) AS comentarios_apoyo,
    COALESCE(cs.comentarios_neutral, 0) AS comentarios_neutral,
    cs.primer_comentario_clasificado,
    cs.ultimo_comentario_clasificado,
    cs.resumen_modal,
    current_timestamp AS built_at
FROM aggregated AS a
INNER JOIN platform_ids AS p USING (canonical_key)
INNER JOIN source_tables_agg AS st USING (canonical_key)
LEFT JOIN staging_tw_profile_snapshot AS tw
    ON a.canonical_key = 'tw:' || tw.twitter_username
    OR a.canonical_key = 'tw_id:' || tw.twitter_user_id
    OR (p.twitter_user_id IS NOT NULL AND p.twitter_user_id = tw.twitter_user_id)
    OR (p.twitter_username IS NOT NULL AND p.twitter_username = tw.twitter_username)
LEFT JOIN staging_fb_page_engagement AS fb
    ON p.facebook_page_id = fb.facebook_page_id
LEFT JOIN staging_author_classification_stats AS cs
    ON a.canonical_key = cs.autor_key
ORDER BY
    len(a.networks_found) DESC,
    COALESCE(a.comments_count, 0) + COALESCE(a.replies_count, 0)
        + COALESCE(a.tweets_count, 0) + COALESCE(a.posts_count, 0) DESC,
    a.display_name;

-- Backward-compatible view (subset of enriched columns)
DROP TABLE IF EXISTS silver.network_profile_comment_stats;
DROP VIEW IF EXISTS silver.network_profile_comment_stats;
CREATE OR REPLACE VIEW silver.network_profile_comment_stats AS
SELECT
    profile_id,
    canonical_key,
    display_name,
    networks_found,
    twitter_username,
    facebook_user_name,
    is_tracked,
    is_pts,
    comentarios_clasificados,
    comentarios_troll,
    comentarios_apoyo,
    primer_comentario_clasificado AS primer_comentario,
    ultimo_comentario_clasificado AS ultimo_comentario,
    resumen_modal,
    built_at
FROM silver.network_profile;
