-- Twikit Twitter/X → bronze
-- Paths from data/landing/redes/twikit/twitter/_current_run.json (filled by scrape script)
-- Uso: via scrape_twikit_twitter.py --ingest

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE OR REPLACE TABLE bronze.tk_tw_profile AS
SELECT * FROM read_json_auto('{{profile_path}}');

CREATE OR REPLACE TABLE bronze.tk_tw_tweet AS
SELECT * FROM read_json_auto('{{tweets_path}}', format = 'newline_delimited', filename = true);

CREATE OR REPLACE TABLE bronze.tk_tw_tweet_selected AS
SELECT * FROM read_json_auto('{{selected_path}}');

-- Reply JSONL mixes success rows ({replies,count,...}) and error rows ({error});
-- union_by_name + ignore_errors keeps both shapes readable.
CREATE OR REPLACE TABLE bronze.tk_tw_reply AS
SELECT * FROM read_json_auto(
  '{{replies_glob}}',
  format = 'newline_delimited',
  filename = true,
  union_by_name = true,
  ignore_errors = true
);

CREATE OR REPLACE TABLE bronze.tk_tw_manifest AS
SELECT * FROM read_json_auto('{{manifest_path}}');
