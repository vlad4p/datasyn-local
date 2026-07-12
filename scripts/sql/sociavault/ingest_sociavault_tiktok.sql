-- SociaVault TikTok → bronze
-- Paths resolved from _current_run.json by sociavault_scrape_common.run_ingest_sql
-- Uso: uv run python scripts/python/db.py run-sql --file scripts/sql/sociavault/ingest_sociavault_tiktok.sql

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE OR REPLACE TABLE bronze.sv_tt_profile AS
SELECT * FROM read_json_auto('{{profile_path}}');

CREATE OR REPLACE TABLE bronze.sv_tt_video AS
SELECT * FROM read_json_auto('{{videos_path}}', format = 'newline_delimited', filename = true);

CREATE OR REPLACE TABLE bronze.sv_tt_video_selected AS
SELECT video.value AS video
FROM read_json_auto('{{selected_path}}') AS sel,
LATERAL json_each(sel.items) AS video;

CREATE OR REPLACE TABLE bronze.sv_tt_comment AS
SELECT * FROM read_json_auto('{{comments_glob}}', format = 'newline_delimited', filename = true);
