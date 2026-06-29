-- SociaVault Twitter/X → bronze
-- Uso: uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_twitter.sql

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE OR REPLACE TABLE bronze.sv_tw_profile AS
WITH paths AS (
  SELECT * FROM read_json('data/landing/redes/sociavault/twitter/_current_run.json')
)
SELECT p.*
FROM paths,
LATERAL read_json_auto(paths.profile_path) AS p;

CREATE OR REPLACE TABLE bronze.sv_tw_tweet AS
WITH paths AS (
  SELECT * FROM read_json('data/landing/redes/sociavault/twitter/_current_run.json')
)
SELECT t.*
FROM paths,
LATERAL read_json_auto(paths.tweets_path) AS t;

CREATE OR REPLACE TABLE bronze.sv_tw_reply AS
WITH paths AS (
  SELECT * FROM read_json('data/landing/redes/sociavault/twitter/_current_run.json')
)
SELECT r.*
FROM paths,
LATERAL read_json_auto(
  paths.run_dir || '/replies_*.jsonl',
  format = 'newline_delimited',
  filename = true
) AS r;
