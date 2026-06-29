-- SociaVault Facebook bronze → silver (flatten nested JSON)
-- Uso: uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_facebook_silver.sql

CREATE SCHEMA IF NOT EXISTS silver;

CREATE OR REPLACE TABLE silver.sv_fb_profile AS
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
  ) AS page_intro
FROM (
  SELECT to_json(p) AS j FROM bronze.sv_fb_profile AS p
) AS raw
WHERE COALESCE(
  json_extract_string(j, '$.data.id'),
  json_extract_string(j, '$.data.data.id')
) IS NOT NULL;

CREATE OR REPLACE TABLE silver.sv_fb_post AS
WITH pages AS (
  SELECT to_json(p) AS j FROM bronze.sv_fb_post AS p
),
posts AS (
  SELECT
    json_extract_string(j, '$.data.posts') AS posts_obj,
    json_extract_string(j, '$.data.data.posts') AS posts_nested
  FROM pages
),
flat AS (
  SELECT post.value AS post_json
  FROM posts,
  LATERAL json_each(
    COALESCE(
      TRY_CAST(posts_obj AS JSON),
      TRY_CAST(posts_nested AS JSON)
    )
  ) AS post
  WHERE post.value IS NOT NULL
)
SELECT DISTINCT
  json_extract_string(post_json, '$.id') AS post_id,
  json_extract_string(post_json, '$.url') AS url,
  TRIM(COALESCE(
    json_extract_string(post_json, '$.text'),
    json_extract_string(post_json, '$.message')
  )) AS mensaje,
  json_extract_string(post_json, '$.author.name') AS author_name,
  TRY_CAST(json_extract_string(post_json, '$.reactionCount') AS BIGINT) AS reacciones,
  TRY_CAST(json_extract_string(post_json, '$.commentCount') AS BIGINT) AS comentarios,
  TRY_CAST(json_extract_string(post_json, '$.shareCount') AS BIGINT) AS compartidos,
  TRY_CAST(json_extract_string(post_json, '$.publishTime') AS BIGINT) AS publish_time_unix
FROM flat
WHERE json_extract_string(post_json, '$.id') IS NOT NULL;

CREATE OR REPLACE TABLE silver.sv_fb_comment AS
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
  json_extract_string(comment_json, '$.author.name') AS user_name,
  TRY_CAST(json_extract_string(comment_json, '$.likes') AS BIGINT) AS like_count,
  json_extract_string(comment_json, '$.createdAt') AS fecha_comentario
FROM comments
WHERE COALESCE(
  json_extract_string(comment_json, '$.text'),
  json_extract_string(comment_json, '$.message')
) IS NOT NULL;
