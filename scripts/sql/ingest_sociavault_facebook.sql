-- SociaVault Facebook → bronze (raw API responses)
-- Requires: scrape run wrote data/landing/redes/sociavault/facebook/_current_run.json
-- Uso: uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_facebook.sql

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE OR REPLACE TABLE bronze.sv_fb_profile AS
WITH paths AS (
  SELECT * FROM read_json('data/landing/redes/sociavault/facebook/_current_run.json')
)
SELECT p.*
FROM paths,
LATERAL read_json_auto(paths.profile_path) AS p;

CREATE OR REPLACE TABLE bronze.sv_fb_post AS
WITH paths AS (
  SELECT * FROM read_json('data/landing/redes/sociavault/facebook/_current_run.json')
)
SELECT p.*
FROM paths,
LATERAL read_json_auto(paths.posts_path, format = 'newline_delimited', filename = true) AS p;

CREATE OR REPLACE TABLE bronze.sv_fb_post_selected AS
WITH paths AS (
  SELECT * FROM read_json('data/landing/redes/sociavault/facebook/_current_run.json')
)
SELECT post.value AS post
FROM paths,
LATERAL read_json_auto(paths.selected_path) AS sel,
LATERAL json_each(sel.items) AS post;

CREATE OR REPLACE TABLE bronze.sv_fb_comment AS
WITH paths AS (
  SELECT * FROM read_json('data/landing/redes/sociavault/facebook/_current_run.json')
)
SELECT c.*
FROM paths,
LATERAL read_json_auto(
  paths.run_dir || '/comments_*.jsonl',
  format = 'newline_delimited',
  filename = true
) AS c;
