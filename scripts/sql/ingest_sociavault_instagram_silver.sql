-- SociaVault Instagram bronze → silver
-- Uso: uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_instagram_silver.sql

CREATE SCHEMA IF NOT EXISTS silver;

CREATE OR REPLACE TABLE silver.sv_ig_profile AS
SELECT DISTINCT
  COALESCE(
    json_extract_string(j, '$.data.id'),
    json_extract_string(j, '$.data.data.id'),
    json_extract_string(j, '$.data.pk')
  ) AS user_id,
  COALESCE(
    json_extract_string(j, '$.data.username'),
    json_extract_string(j, '$.data.data.username')
  ) AS username,
  COALESCE(
    json_extract_string(j, '$.data.full_name'),
    json_extract_string(j, '$.data.data.full_name')
  ) AS full_name,
  TRY_CAST(COALESCE(
    json_extract_string(j, '$.data.follower_count'),
    json_extract_string(j, '$.data.data.follower_count')
  ) AS BIGINT) AS follower_count,
  TRY_CAST(COALESCE(
    json_extract_string(j, '$.data.media_count'),
    json_extract_string(j, '$.data.data.media_count')
  ) AS BIGINT) AS media_count
FROM (SELECT to_json(p) AS j FROM bronze.sv_ig_profile AS p) AS raw
WHERE COALESCE(
  json_extract_string(j, '$.data.username'),
  json_extract_string(j, '$.data.data.username')
) IS NOT NULL;

CREATE OR REPLACE TABLE silver.sv_ig_post AS
WITH pages AS (
  SELECT to_json(p) AS j FROM bronze.sv_ig_post AS p
),
posts AS (
  SELECT post.value AS post_json
  FROM pages,
  LATERAL json_each(
    COALESCE(
      TRY_CAST(json_extract_string(j, '$.data.posts') AS JSON),
      TRY_CAST(json_extract_string(j, '$.data.data.posts') AS JSON),
      TRY_CAST(json_extract_string(j, '$.data.items') AS JSON)
    )
  ) AS post
  WHERE post.value IS NOT NULL
)
SELECT DISTINCT
  COALESCE(
    json_extract_string(post_json, '$.id'),
    json_extract_string(post_json, '$.pk'),
    json_extract_string(post_json, '$.code')
  ) AS post_id,
  json_extract_string(post_json, '$.code') AS shortcode,
  TRIM(COALESCE(
    json_extract_string(post_json, '$.caption.text'),
    json_extract_string(post_json, '$.caption'),
    json_extract_string(post_json, '$.text')
  )) AS caption,
  TRY_CAST(json_extract_string(post_json, '$.like_count') AS BIGINT) AS like_count,
  TRY_CAST(json_extract_string(post_json, '$.comment_count') AS BIGINT) AS comment_count,
  json_extract_string(post_json, '$.taken_at') AS taken_at,
  json_extract_string(post_json, '$.url') AS url
FROM posts
WHERE COALESCE(
  json_extract_string(post_json, '$.id'),
  json_extract_string(post_json, '$.pk'),
  json_extract_string(post_json, '$.code')
) IS NOT NULL;

CREATE OR REPLACE TABLE silver.sv_ig_comment AS
WITH pages AS (
  SELECT to_json(c) AS j FROM bronze.sv_ig_comment AS c
),
comments AS (
  SELECT comment.value AS comment_json
  FROM pages,
  LATERAL json_each(
    COALESCE(
      TRY_CAST(json_extract_string(j, '$.data.comments') AS JSON),
      TRY_CAST(json_extract_string(j, '$.data.data.comments') AS JSON)
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
  json_extract_string(comment_json, '$.user.username') AS user_name,
  TRY_CAST(json_extract_string(comment_json, '$.like_count') AS BIGINT) AS like_count,
  json_extract_string(comment_json, '$.created_at') AS fecha_comentario
FROM comments
WHERE COALESCE(
  json_extract_string(comment_json, '$.text'),
  json_extract_string(comment_json, '$.message')
) IS NOT NULL;
