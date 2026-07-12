-- SociaVault Facebook → bronze (raw API responses)
-- Paths resolved from _current_run.json by sociavault_scrape_common.run_ingest_sql
-- Uso: uv run python scripts/python/db.py run-sql --file scripts/sql/sociavault/ingest_sociavault_facebook.sql

CREATE SCHEMA IF NOT EXISTS bronze;

CREATE OR REPLACE TABLE bronze.sv_fb_profile AS
SELECT * FROM read_json_auto('{{profile_path}}');

CREATE OR REPLACE TABLE bronze.sv_fb_post AS
SELECT * FROM read_json_auto('{{posts_path}}', format = 'newline_delimited', filename = true);

CREATE OR REPLACE TABLE bronze.sv_fb_post_selected AS
SELECT post.value AS post
FROM read_json_auto('{{selected_path}}') AS sel,
LATERAL json_each(sel.items) AS post;

CREATE OR REPLACE TABLE bronze.sv_fb_comment AS
SELECT * FROM read_json_auto('{{comments_glob}}', format = 'newline_delimited', filename = true);
