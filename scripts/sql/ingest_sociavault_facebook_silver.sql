-- SociaVault Facebook bronze → silver (MERGE upsert, author identity fields)
-- Uso: uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_facebook_silver.sql

CREATE SCHEMA IF NOT EXISTS silver;

-- Staging: profile
CREATE OR REPLACE TEMP TABLE staging_sv_fb_profile AS
SELECT DISTINCT
  COALESCE(
    json_extract_string(j, '$.data.id'),
    json_extract_string(j, '$.data.data.id')
  ) AS page_id,
  COALESCE(
    json_extract_string(j, '$.data.name'),
    json_extract_string(j, '$.data.data.name')
  ) AS name,
  COALESCE(
    json_extract_string(j, '$.data.url'),
    json_extract_string(j, '$.data.data.url')
  ) AS url,
  TRY_CAST(COALESCE(
    json_extract_string(j, '$.data.likeCount'),
    json_extract_string(j, '$.data.data.likeCount')
  ) AS BIGINT) AS like_count,
  TRY_CAST(COALESCE(
    json_extract_string(j, '$.data.followerCount'),
    json_extract_string(j, '$.data.data.followerCount')
  ) AS BIGINT) AS follower_count,
  COALESCE(
    json_extract_string(j, '$.data.category'),
    json_extract_string(j, '$.data.data.category')
  ) AS category,
  COALESCE(
    json_extract_string(j, '$.data.pageIntro'),
    json_extract_string(j, '$.data.data.pageIntro')
  ) AS page_intro,
  'facebook' AS platform,
  current_timestamp AS ingested_at
FROM (
  SELECT to_json(p) AS j FROM bronze.sv_fb_profile AS p
) AS raw
WHERE COALESCE(
  json_extract_string(j, '$.data.id'),
  json_extract_string(j, '$.data.data.id')
) IS NOT NULL;

CREATE TABLE IF NOT EXISTS silver.sv_fb_profile AS
SELECT * FROM staging_sv_fb_profile WHERE 1 = 0;

MERGE INTO silver.sv_fb_profile AS t
USING staging_sv_fb_profile AS s
ON t.page_id = s.page_id
WHEN MATCHED THEN UPDATE SET
  name = s.name,
  url = s.url,
  like_count = s.like_count,
  follower_count = s.follower_count,
  category = s.category,
  page_intro = s.page_intro,
  platform = s.platform,
  ingested_at = s.ingested_at
WHEN NOT MATCHED THEN INSERT *;

-- Staging: posts
CREATE OR REPLACE TEMP TABLE staging_sv_fb_post AS
WITH flat AS (
  SELECT to_json(s.post) AS post_json FROM bronze.sv_fb_post_selected AS s
)
SELECT DISTINCT
  json_extract_string(post_json, '$.id') AS post_id,
  json_extract_string(post_json, '$.url') AS url,
  TRIM(COALESCE(
    json_extract_string(post_json, '$.text'),
    json_extract_string(post_json, '$.message')
  )) AS mensaje,
  json_extract_string(post_json, '$.author.name') AS author_name,
  COALESCE(
    json_extract_string(post_json, '$.author.id'),
    json_extract_string(post_json, '$.author.userId')
  ) AS author_id,
  json_extract_string(post_json, '$.author.url') AS author_url,
  TRY_CAST(json_extract_string(post_json, '$.reactionCount') AS BIGINT) AS reacciones,
  TRY_CAST(json_extract_string(post_json, '$.commentCount') AS BIGINT) AS comentarios,
  TRY_CAST(json_extract_string(post_json, '$.shareCount') AS BIGINT) AS compartidos,
  TRY_CAST(json_extract_string(post_json, '$.publishTime') AS BIGINT) AS publish_time_unix,
  CASE
    WHEN TRY_CAST(json_extract_string(post_json, '$.publishTime') AS BIGINT) > 1000000000000
      THEN epoch_ms(TRY_CAST(json_extract_string(post_json, '$.publishTime') AS BIGINT))
    WHEN TRY_CAST(json_extract_string(post_json, '$.publishTime') AS BIGINT) IS NOT NULL
      THEN epoch(TRY_CAST(json_extract_string(post_json, '$.publishTime') AS BIGINT))
    ELSE NULL
  END AS publish_time,
  'facebook' AS platform,
  current_timestamp AS ingested_at
FROM flat
WHERE json_extract_string(post_json, '$.id') IS NOT NULL;

CREATE TABLE IF NOT EXISTS silver.sv_fb_post AS
SELECT * FROM staging_sv_fb_post WHERE 1 = 0;

MERGE INTO silver.sv_fb_post AS t
USING staging_sv_fb_post AS s
ON t.post_id = s.post_id
WHEN MATCHED THEN UPDATE SET
  url = s.url,
  mensaje = s.mensaje,
  author_name = s.author_name,
  author_id = s.author_id,
  author_url = s.author_url,
  reacciones = s.reacciones,
  comentarios = s.comentarios,
  compartidos = s.compartidos,
  publish_time_unix = s.publish_time_unix,
  publish_time = s.publish_time,
  platform = s.platform,
  ingested_at = s.ingested_at
WHEN NOT MATCHED THEN INSERT *;

-- Staging: comments
CREATE OR REPLACE TEMP TABLE staging_sv_fb_comment AS
WITH pages AS (
  SELECT to_json(c) AS j FROM bronze.sv_fb_comment AS c
),
comments AS (
  SELECT comment.value AS comment_json
  FROM pages,
  LATERAL json_each(
    COALESCE(
      TRY_CAST(json_extract_string(j, '$.data.comments') AS JSON),
      TRY_CAST(json_extract_string(j, '$.data.data.comments') AS JSON),
      TRY_CAST(json_extract_string(j, '$.comments') AS JSON)
    )
  ) AS comment
  WHERE comment.value IS NOT NULL
)
SELECT DISTINCT
  json_extract_string(comment_json, '$.id') AS comment_id,
  json_extract_string(comment_json, '$.post_id') AS post_id,
  TRIM(COALESCE(
    json_extract_string(comment_json, '$.text'),
    json_extract_string(comment_json, '$.message')
  )) AS comentario,
  COALESCE(
    json_extract_string(comment_json, '$.author.id'),
    json_extract_string(comment_json, '$.author.userId'),
    json_extract_string(comment_json, '$.user.id')
  ) AS user_id,
  COALESCE(
    json_extract_string(comment_json, '$.author.name'),
    json_extract_string(comment_json, '$.user.name')
  ) AS user_name,
  COALESCE(
    json_extract_string(comment_json, '$.author.url'),
    json_extract_string(comment_json, '$.user.url')
  ) AS user_url,
  TRY_CAST(json_extract_string(comment_json, '$.likes') AS BIGINT) AS like_count,
  json_extract_string(comment_json, '$.createdAt') AS fecha_comentario,
  TRY_CAST(json_extract_string(comment_json, '$.createdAt') AS TIMESTAMP) AS fecha_comentario_ts,
  'facebook' AS platform,
  current_timestamp AS ingested_at
FROM comments
WHERE COALESCE(
  json_extract_string(comment_json, '$.text'),
  json_extract_string(comment_json, '$.message')
) IS NOT NULL;

CREATE TABLE IF NOT EXISTS silver.sv_fb_comment AS
SELECT * FROM staging_sv_fb_comment WHERE 1 = 0;

MERGE INTO silver.sv_fb_comment AS t
USING staging_sv_fb_comment AS s
ON t.comment_id = s.comment_id AND t.platform = s.platform
WHEN MATCHED THEN UPDATE SET
  post_id = s.post_id,
  comentario = s.comentario,
  user_id = s.user_id,
  user_name = s.user_name,
  user_url = s.user_url,
  like_count = s.like_count,
  fecha_comentario = s.fecha_comentario,
  fecha_comentario_ts = s.fecha_comentario_ts,
  ingested_at = s.ingested_at
WHEN NOT MATCHED THEN INSERT *;
