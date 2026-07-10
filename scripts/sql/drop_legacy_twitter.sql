-- Drop legacy Twitter tables (bronze + silver tw_*).
-- Twitter/X now lives only in the twikit pipeline (tk_tw_*).
-- Prereq: rewire FB-only gold/network_profile first (ingest_redes_gold.sql,
--         ingest_network_profile.sql, ingest_redes_comment_similarity.sql).
-- Uso:
--   uv run python scripts/python/db.py mcp-stop
--   uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/drop_legacy_twitter.sql

DROP TABLE IF EXISTS silver.tw_comments_classification;
DROP TABLE IF EXISTS silver.tw_tweets_replies;
DROP TABLE IF EXISTS silver.tw_tweets;
DROP TABLE IF EXISTS silver.tw_users;

DROP TABLE IF EXISTS bronze.tw_comments_classification;
DROP TABLE IF EXISTS bronze.tw_tweets_replies;
DROP TABLE IF EXISTS bronze.tw_tweets;
DROP TABLE IF EXISTS bronze.tw_users;
