-- SociaVault TikTok → bronze
-- Uso: uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_tiktok.sql

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE OR REPLACE TABLE bronze.sv_tt_profile AS
WITH paths AS (
  SELECT * FROM read_json('data/landing/redes/sociavault/tiktok/_current_run.json')
)
SELECT p.*
FROM paths,
LATERAL read_json_auto(paths.profile_path) AS p;

CREATE OR REPLACE TABLE bronze.sv_tt_video AS
WITH paths AS (
  SELECT * FROM read_json('data/landing/redes/sociavault/tiktok/_current_run.json')
)
SELECT v.*
FROM paths,
LATERAL read_json_auto(paths.videos_path, format = 'newline_delimited', filename = true) AS v;

CREATE OR REPLACE TABLE bronze.sv_tt_video_selected AS
WITH paths AS (
  SELECT * FROM read_json('data/landing/redes/sociavault/tiktok/_current_run.json')
)
SELECT video.value AS video
FROM paths,
LATERAL read_json_auto(paths.selected_path) AS sel,
LATERAL json_each(sel.items) AS video;

CREATE OR REPLACE TABLE bronze.sv_tt_comment AS
WITH paths AS (
  SELECT * FROM read_json('data/landing/redes/sociavault/tiktok/_current_run.json')
)
SELECT c.*
FROM paths,
LATERAL read_json_auto(
  paths.run_dir || '/comments_*.jsonl',
  format = 'newline_delimited',
  filename = true
) AS c;
