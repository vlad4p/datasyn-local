-- SociaVault Twitter/X → bronze
-- Paths resolved from _current_run.json by sociavault_scrape_common.run_ingest_sql
-- Uso: uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_twitter.sql

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE OR REPLACE TABLE bronze.sv_tw_profile AS
SELECT * FROM read_json_auto('{{profile_path}}');

-- Raw paginated API pages (audit)
CREATE OR REPLACE TABLE bronze.sv_tw_tweet AS
SELECT * FROM read_json_auto('{{tweets_path}}', format = 'newline_delimited', filename = true);

-- Selected most-recent tweets (count-based scrape)
CREATE OR REPLACE TABLE bronze.sv_tw_tweet_selected AS
SELECT tweet.value AS tweet
FROM read_json_auto('{{selected_path}}') AS sel,
LATERAL json_each(sel.items) AS tweet;

-- Per-tweet enrich payloads (twitter/tweet endpoint)
CREATE OR REPLACE TABLE bronze.sv_tw_tweet_detail AS
SELECT * FROM read_json_auto('{{tweet_detail_glob}}', filename = true);

CREATE OR REPLACE TABLE bronze.sv_tw_reply AS
SELECT * FROM read_json_auto('{{replies_glob}}', format = 'newline_delimited', filename = true);
