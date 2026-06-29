-- SociaVault TikTok bronze → silver
-- Uso: uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_tiktok_silver.sql

CREATE SCHEMA IF NOT EXISTS silver;

CREATE OR REPLACE TABLE silver.sv_tt_profile AS
SELECT DISTINCT
  COALESCE(
    json_extract_string(j, '$.data.id'),
    json_extract_string(j, '$.data.data.id'),
    json_extract_string(j, '$.data.user.id')
  ) AS user_id,
  COALESCE(
    json_extract_string(j, '$.data.uniqueId'),
    json_extract_string(j, '$.data.data.uniqueId'),
    json_extract_string(j, '$.data.user.uniqueId')
  ) AS handle,
  COALESCE(
    json_extract_string(j, '$.data.nickname'),
    json_extract_string(j, '$.data.data.nickname')
  ) AS nickname,
  TRY_CAST(COALESCE(
    json_extract_string(j, '$.data.followerCount'),
    json_extract_string(j, '$.data.stats.followerCount')
  ) AS BIGINT) AS follower_count,
  TRY_CAST(COALESCE(
    json_extract_string(j, '$.data.videoCount'),
    json_extract_string(j, '$.data.stats.videoCount')
  ) AS BIGINT) AS video_count
FROM (SELECT to_json(p) AS j FROM bronze.sv_tt_profile AS p) AS raw
WHERE COALESCE(
  json_extract_string(j, '$.data.uniqueId'),
  json_extract_string(j, '$.data.user.uniqueId')
) IS NOT NULL;

CREATE OR REPLACE TABLE silver.sv_tt_video AS
WITH pages AS (
  SELECT to_json(v) AS j FROM bronze.sv_tt_video AS v
),
videos AS (
  SELECT video.value AS video_json
  FROM pages,
  LATERAL json_each(
    COALESCE(
      TRY_CAST(json_extract_string(j, '$.data.videos') AS JSON),
      TRY_CAST(json_extract_string(j, '$.data.data.videos') AS JSON),
      TRY_CAST(json_extract_string(j, '$.data.items') AS JSON)
    )
  ) AS video
  WHERE video.value IS NOT NULL
)
SELECT DISTINCT
  COALESCE(
    json_extract_string(video_json, '$.id'),
    json_extract_string(video_json, '$.aweme_id'),
    json_extract_string(video_json, '$.video_id')
  ) AS video_id,
  TRIM(COALESCE(
    json_extract_string(video_json, '$.desc'),
    json_extract_string(video_json, '$.title'),
    json_extract_string(video_json, '$.description')
  )) AS description,
  TRY_CAST(json_extract_string(video_json, '$.stats.playCount') AS BIGINT) AS play_count,
  TRY_CAST(json_extract_string(video_json, '$.stats.diggCount') AS BIGINT) AS like_count,
  TRY_CAST(json_extract_string(video_json, '$.stats.commentCount') AS BIGINT) AS comment_count,
  TRY_CAST(json_extract_string(video_json, '$.stats.shareCount') AS BIGINT) AS share_count,
  json_extract_string(video_json, '$.createTime') AS create_time,
  json_extract_string(video_json, '$.url') AS url
FROM videos
WHERE COALESCE(
  json_extract_string(video_json, '$.id'),
  json_extract_string(video_json, '$.aweme_id')
) IS NOT NULL;

CREATE OR REPLACE TABLE silver.sv_tt_comment AS
WITH pages AS (
  SELECT to_json(c) AS j FROM bronze.sv_tt_comment AS c
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
  json_extract_string(comment_json, '$.video_id') AS video_id,
  TRIM(COALESCE(
    json_extract_string(comment_json, '$.text'),
    json_extract_string(comment_json, '$.content')
  )) AS comentario,
  json_extract_string(comment_json, '$.user.uniqueId') AS user_name,
  TRY_CAST(json_extract_string(comment_json, '$.digg_count') AS BIGINT) AS like_count,
  json_extract_string(comment_json, '$.create_time') AS fecha_comentario
FROM comments
WHERE COALESCE(
  json_extract_string(comment_json, '$.text'),
  json_extract_string(comment_json, '$.content')
) IS NOT NULL;
