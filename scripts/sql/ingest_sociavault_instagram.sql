-- SociaVault Instagram → bronze
-- Uso: uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_instagram.sql

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE OR REPLACE TABLE bronze.sv_ig_profile AS
WITH paths AS (
  SELECT * FROM read_json('data/landing/redes/sociavault/instagram/_current_run.json')
)
SELECT p.*
FROM paths,
LATERAL read_json_auto(paths.profile_path) AS p;

CREATE OR REPLACE TABLE bronze.sv_ig_post AS
WITH paths AS (
  SELECT * FROM read_json('data/landing/redes/sociavault/instagram/_current_run.json')
)
SELECT p.*
FROM paths,
LATERAL read_json_auto(paths.posts_path, format = 'newline_delimited', filename = true) AS p;

CREATE OR REPLACE TABLE bronze.sv_ig_comment AS
WITH paths AS (
  SELECT * FROM read_json('data/landing/redes/sociavault/instagram/_current_run.json')
)
SELECT c.*
FROM paths,
LATERAL read_json_auto(
  paths.run_dir || '/comments_*.jsonl',
  format = 'newline_delimited',
  filename = true
) AS c;
