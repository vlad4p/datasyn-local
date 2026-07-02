-- SociaVault comment classification tables - schema only
-- Populated by classify_sv_comments.py
-- Uso: uv run python scripts/python/db.py run-sql --file scripts/sql/ingest_sociavault_classification.sql

CREATE SCHEMA IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS silver.sv_fb_comment_classification (
  classification_id VARCHAR PRIMARY KEY,
  post_id VARCHAR,
  platform VARCHAR DEFAULT 'facebook',
  comment_id VARCHAR NOT NULL,
  origen VARCHAR DEFAULT 'SV_FB',
  free_criteria VARCHAR,
  criterio_label VARCHAR,
  resumen VARCHAR,
  created_at TIMESTAMP DEFAULT current_timestamp,
  updated_at TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS silver.sv_ig_comment_classification (
  classification_id VARCHAR PRIMARY KEY,
  post_id VARCHAR,
  platform VARCHAR DEFAULT 'instagram',
  comment_id VARCHAR NOT NULL,
  origen VARCHAR DEFAULT 'SV_IG',
  free_criteria VARCHAR,
  criterio_label VARCHAR,
  resumen VARCHAR,
  created_at TIMESTAMP DEFAULT current_timestamp,
  updated_at TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS silver.sv_tt_comment_classification (
  classification_id VARCHAR PRIMARY KEY,
  video_id VARCHAR,
  platform VARCHAR DEFAULT 'tiktok',
  comment_id VARCHAR NOT NULL,
  origen VARCHAR DEFAULT 'SV_TT',
  free_criteria VARCHAR,
  criterio_label VARCHAR,
  resumen VARCHAR,
  created_at TIMESTAMP DEFAULT current_timestamp,
  updated_at TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS silver.sv_tw_reply_classification (
  classification_id VARCHAR PRIMARY KEY,
  tweet_id VARCHAR,
  platform VARCHAR DEFAULT 'twitter',
  reply_id VARCHAR NOT NULL,
  origen VARCHAR DEFAULT 'SV_TW',
  free_criteria VARCHAR,
  criterio_label VARCHAR,
  resumen VARCHAR,
  created_at TIMESTAMP DEFAULT current_timestamp,
  updated_at TIMESTAMP DEFAULT current_timestamp
);

-- View: unified classification label mapping (legacy compatible)
CREATE OR REPLACE VIEW silver.sv_comment_classification_all AS
SELECT classification_id, post_id AS parent_id, platform, comment_id AS content_id,
       origen, free_criteria, criterio_label, resumen, created_at, updated_at
FROM silver.sv_fb_comment_classification
UNION ALL
SELECT classification_id, post_id, platform, comment_id, origen, free_criteria, criterio_label, resumen, created_at, updated_at
FROM silver.sv_ig_comment_classification
UNION ALL
SELECT classification_id, video_id, platform, comment_id, origen, free_criteria, criterio_label, resumen, created_at, updated_at
FROM silver.sv_tt_comment_classification
UNION ALL
SELECT classification_id, tweet_id, platform, reply_id, origen, free_criteria, criterio_label, resumen, created_at, updated_at
FROM silver.sv_tw_reply_classification;
