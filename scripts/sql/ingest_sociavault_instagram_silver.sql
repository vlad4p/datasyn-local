-- SociaVault Instagram bronze → silver (MERGE upsert)
-- Uso: uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_instagram_silver.sql

CREATE SCHEMA IF NOT EXISTS silver;

CREATE OR REPLACE TEMP TABLE staging_sv_ig_profile AS
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
  ) AS BIGINT) AS media_count,
  'instagram' AS platform,
  current_timestamp AS ingested_at
FROM (SELECT to_json(p) AS j FROM bronze.sv_ig_profile AS p) AS raw
WHERE COALESCE(
  json_extract_string(j, '$.data.username'),
  json_extract_string(j, '$.data.data.username')
) IS NOT NULL;

CREATE TABLE IF NOT EXISTS silver.sv_ig_profile AS
SELECT * FROM staging_sv_ig_profile WHERE 1 = 0;

MERGE INTO silver.sv_ig_profile AS t
USING staging_sv_ig_profile AS s
ON t.user_id = s.user_id
WHEN MATCHED THEN UPDATE SET
  username = s.username,
  full_name = s.full_name,
  follower_count = s.follower_count,
  media_count = s.media_count,
  platform = s.platform,
  ingested_at = s.ingested_at
WHEN NOT MATCHED THEN INSERT *;

CREATE OR REPLACE TEMP TABLE staging_sv_ig_post AS
WITH posts AS (
  SELECT to_json(s.post) AS post_json FROM bronze.sv_ig_post_selected AS s
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
  COALESCE(
    json_extract_string(post_json, '$.user.id'),
    json_extract_string(post_json, '$.owner.id')
  ) AS author_id,
  COALESCE(
    json_extract_string(post_json, '$.user.username'),
    json_extract_string(post_json, '$.owner.username')
  ) AS author_username,
  TRY_CAST(json_extract_string(post_json, '$.like_count') AS BIGINT) AS like_count,
  TRY_CAST(json_extract_string(post_json, '$.comment_count') AS BIGINT) AS comment_count,
  json_extract_string(post_json, '$.taken_at') AS taken_at,
  CASE
    WHEN TRY_CAST(json_extract_string(post_json, '$.taken_at') AS BIGINT) IS NOT NULL
      THEN epoch(TRY_CAST(json_extract_string(post_json, '$.taken_at') AS BIGINT))
    ELSE NULL
  END AS taken_at_ts,
  json_extract_string(post_json, '$.url') AS url,
  'instagram' AS platform,
  current_timestamp AS ingested_at
FROM posts
WHERE COALESCE(
  json_extract_string(post_json, '$.id'),
  json_extract_string(post_json, '$.pk'),
  json_extract_string(post_json, '$.code')
) IS NOT NULL;

CREATE TABLE IF NOT EXISTS silver.sv_ig_post AS
SELECT * FROM staging_sv_ig_post WHERE 1 = 0;

MERGE INTO silver.sv_ig_post AS t
USING staging_sv_ig_post AS s
ON t.post_id = s.post_id
WHEN MATCHED THEN UPDATE SET
  shortcode = s.shortcode,
  caption = s.caption,
  author_id = s.author_id,
  author_username = s.author_username,
  like_count = s.like_count,
  comment_count = s.comment_count,
  taken_at = s.taken_at,
  taken_at_ts = s.taken_at_ts,
  url = s.url,
  platform = s.platform,
  ingested_at = s.ingested_at
WHEN NOT MATCHED THEN INSERT *;

CREATE OR REPLACE TEMP TABLE staging_sv_ig_comment AS
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
  COALESCE(
    json_extract_string(comment_json, '$.user.id'),
    json_extract_string(comment_json, '$.user.pk')
  ) AS user_id,
  COALESCE(
    json_extract_string(comment_json, '$.user.username'),
    json_extract_string(comment_json, '$.username')
  ) AS user_name,
  json_extract_string(comment_json, '$.user.profile_pic_url') AS user_url,
  TRY_CAST(json_extract_string(comment_json, '$.like_count') AS BIGINT) AS like_count,
  json_extract_string(comment_json, '$.created_at') AS fecha_comentario,
  CASE
    WHEN TRY_CAST(json_extract_string(comment_json, '$.created_at') AS BIGINT) IS NOT NULL
      THEN epoch(TRY_CAST(json_extract_string(comment_json, '$.created_at') AS BIGINT))
    ELSE TRY_CAST(json_extract_string(comment_json, '$.created_at') AS TIMESTAMP)
  END AS fecha_comentario_ts,
  'instagram' AS platform,
  current_timestamp AS ingested_at
FROM comments
WHERE COALESCE(
  json_extract_string(comment_json, '$.text'),
  json_extract_string(comment_json, '$.message')
) IS NOT NULL;

CREATE TABLE IF NOT EXISTS silver.sv_ig_comment AS
SELECT * FROM staging_sv_ig_comment WHERE 1 = 0;

MERGE INTO silver.sv_ig_comment AS t
USING staging_sv_ig_comment AS s
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
