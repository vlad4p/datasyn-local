-- Twikit reply classification schema (populated by classify_tk_tw_replies.py)
-- Uso: uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_tk_tw_classification.sql

CREATE SCHEMA IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS silver.tk_tw_reply_classification (
  classification_id VARCHAR PRIMARY KEY,
  reply_id VARCHAR NOT NULL,
  parent_tweet_id VARCHAR,
  platform VARCHAR DEFAULT 'twitter',
  origen VARCHAR DEFAULT 'TK_TW',
  free_criteria VARCHAR,
  criterio_label VARCHAR,
  resumen VARCHAR,
  narrativa_raw VARCHAR,
  created_at TIMESTAMP DEFAULT current_timestamp,
  updated_at TIMESTAMP DEFAULT current_timestamp
);

-- reply_id uniqueness enforced by application upsert (DELETE+INSERT).
