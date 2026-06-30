-- SociaVault TikTok bronze → silver (MERGE upsert)
-- Uso: uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_tiktok_silver.sql

CREATE SCHEMA IF NOT EXISTS silver;

CREATE OR REPLACE TEMP TABLE staging_sv_tt_profile AS
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
  ) AS BIGINT) AS video_count,
  'tiktok' AS platform,
  current_timestamp AS ingested_at
FROM (SELECT to_json(p) AS j FROM bronze.sv_tt_profile AS p) AS raw
WHERE COALESCE(
  json_extract_string(j, '$.data.uniqueId'),
  json_extract_string(j, '$.data.user.uniqueId')
) IS NOT NULL;

CREATE TABLE IF NOT EXISTS silver.sv_tt_profile AS
SELECT * FROM staging_sv_tt_profile WHERE 1 = 0;

MERGE INTO silver.sv_tt_profile AS t
USING staging_sv_tt_profile AS s
ON t.user_id = s.user_id
WHEN MATCHED THEN UPDATE SET
  handle = s.handle,
  nickname = s.nickname,
  follower_count = s.follower_count,
  video_count = s.video_count,
  platform = s.platform,
  ingested_at = s.ingested_at
WHEN NOT MATCHED THEN INSERT *;

CREATE OR REPLACE TEMP TABLE staging_sv_tt_video AS
WITH videos AS (
  SELECT to_json(s.video) AS video_json FROM bronze.sv_tt_video_selected AS s
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
  CASE
    WHEN TRY_CAST(json_extract_string(video_json, '$.createTime') AS BIGINT) IS NOT NULL
      THEN epoch(TRY_CAST(json_extract_string(video_json, '$.createTime') AS BIGINT))
    ELSE NULL
  END AS create_time_ts,
  json_extract_string(video_json, '$.url') AS url,
  'tiktok' AS platform,
  current_timestamp AS ingested_at
FROM videos
WHERE COALESCE(
  json_extract_string(video_json, '$.id'),
  json_extract_string(video_json, '$.aweme_id')
) IS NOT NULL;

CREATE TABLE IF NOT EXISTS silver.sv_tt_video AS
SELECT * FROM staging_sv_tt_video WHERE 1 = 0;

MERGE INTO silver.sv_tt_video AS t
USING staging_sv_tt_video AS s
ON t.video_id = s.video_id
WHEN MATCHED THEN UPDATE SET
  description = s.description,
  play_count = s.play_count,
  like_count = s.like_count,
  comment_count = s.comment_count,
  share_count = s.share_count,
  create_time = s.create_time,
  create_time_ts = s.create_time_ts,
  url = s.url,
  platform = s.platform,
  ingested_at = s.ingested_at
WHEN NOT MATCHED THEN INSERT *;

CREATE OR REPLACE TEMP TABLE staging_sv_tt_comment AS
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
  COALESCE(
    json_extract_string(comment_json, '$.user.id'),
    json_extract_string(comment_json, '$.user.uid')
  ) AS user_id,
  COALESCE(
    json_extract_string(comment_json, '$.user.uniqueId'),
    json_extract_string(comment_json, '$.user.nickname')
  ) AS user_name,
  TRY_CAST(json_extract_string(comment_json, '$.digg_count') AS BIGINT) AS like_count,
  json_extract_string(comment_json, '$.create_time') AS fecha_comentario,
  CASE
    WHEN TRY_CAST(json_extract_string(comment_json, '$.create_time') AS BIGINT) IS NOT NULL
      THEN epoch(TRY_CAST(json_extract_string(comment_json, '$.create_time') AS BIGINT))
    ELSE NULL
  END AS fecha_comentario_ts,
  'tiktok' AS platform,
  current_timestamp AS ingested_at
FROM comments
WHERE COALESCE(
  json_extract_string(comment_json, '$.text'),
  json_extract_string(comment_json, '$.content')
) IS NOT NULL;

CREATE TABLE IF NOT EXISTS silver.sv_tt_comment AS
SELECT * FROM staging_sv_tt_comment WHERE 1 = 0;

MERGE INTO silver.sv_tt_comment AS t
USING staging_sv_tt_comment AS s
ON t.comment_id = s.comment_id AND t.platform = s.platform
WHEN MATCHED THEN UPDATE SET
  video_id = s.video_id,
  comentario = s.comentario,
  user_id = s.user_id,
  user_name = s.user_name,
  like_count = s.like_count,
  fecha_comentario = s.fecha_comentario,
  fecha_comentario_ts = s.fecha_comentario_ts,
  ingested_at = s.ingested_at
WHEN NOT MATCHED THEN INSERT *;
