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

-- Raw paginated API pages (audit)
CREATE OR REPLACE TABLE bronze.sv_tw_tweet AS
WITH paths AS (
  SELECT * FROM read_json('data/landing/redes/sociavault/twitter/_current_run.json')
)
SELECT t.*
FROM paths,
LATERAL read_json_auto(paths.tweets_path, format = 'newline_delimited', filename = true) AS t;

-- Selected most-recent tweets (count-based scrape)
CREATE OR REPLACE TABLE bronze.sv_tw_tweet_selected AS
WITH paths AS (
  SELECT * FROM read_json('data/landing/redes/sociavault/twitter/_current_run.json')
)
SELECT tweet.value AS tweet
FROM paths,
LATERAL read_json_auto(paths.selected_path) AS sel,
LATERAL json_each(sel.items) AS tweet;

-- Per-tweet enrich payloads (twitter/tweet endpoint)
CREATE OR REPLACE TABLE bronze.sv_tw_tweet_detail AS
WITH paths AS (
  SELECT * FROM read_json('data/landing/redes/sociavault/twitter/_current_run.json')
)
SELECT d.*
FROM paths,
LATERAL read_json_auto(
  paths.run_dir || '/tweet_detail_*.json',
  filename = true
) AS d;

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
