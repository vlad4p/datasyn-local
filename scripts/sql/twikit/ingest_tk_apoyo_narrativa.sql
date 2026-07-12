-- Twikit apoyo (support) narrative clusters (gold) + analysis views
-- Prereq: silver.tk_tw_reply_classification populated
-- Clusters written by classify_tk_tw_replies.py with --cluster-apoyo
-- Uso: uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/twikit/ingest_tk_apoyo_narrativa.sql

CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.tk_apoyo_narrativa_cluster (
  cluster_id VARCHAR PRIMARY KEY,
  label VARCHAR NOT NULL,
  descripcion VARCHAR,
  n_replies BIGINT,
  ejemplo_textos VARCHAR,
  run_id VARCHAR,
  created_at TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS gold.tk_apoyo_narrativa_assignment (
  reply_id VARCHAR PRIMARY KEY,
  cluster_id VARCHAR NOT NULL,
  narrativa_raw VARCHAR,
  parent_tweet_id VARCHAR,
  username VARCHAR,
  run_id VARCHAR,
  assigned_at TIMESTAMP DEFAULT current_timestamp
);

-- Joined detail: apoyo reply + classification + cluster
CREATE OR REPLACE VIEW gold.v_tk_apoyo_narrativa_detalle AS
SELECT
  a.reply_id,
  a.cluster_id,
  c.label AS narrativa_cluster,
  c.descripcion AS narrativa_descripcion,
  a.narrativa_raw,
  a.parent_tweet_id,
  a.username AS reply_username,
  r.text AS reply_text,
  r.like_count,
  r.created_at_ts,
  DATE_TRUNC('day', r.created_at_ts)::DATE AS dia,
  cl.criterio_label,
  cl.resumen,
  cl.free_criteria
FROM gold.tk_apoyo_narrativa_assignment AS a
LEFT JOIN gold.tk_apoyo_narrativa_cluster AS c ON a.cluster_id = c.cluster_id
LEFT JOIN silver.tk_tw_reply AS r ON a.reply_id = r.reply_id
LEFT JOIN silver.tk_tw_reply_classification AS cl ON a.reply_id = cl.reply_id;

CREATE OR REPLACE VIEW gold.v_tk_apoyo_narrativa_resumen AS
SELECT
  c.cluster_id,
  c.label,
  c.descripcion,
  COUNT(a.reply_id) AS n_replies,
  COUNT(DISTINCT a.parent_tweet_id) AS n_tweets,
  COUNT(DISTINCT a.username) AS n_autores,
  ROUND(100.0 * COUNT(a.reply_id) / NULLIF(SUM(COUNT(a.reply_id)) OVER (), 0), 2) AS pct_apoyo
FROM gold.tk_apoyo_narrativa_cluster AS c
LEFT JOIN gold.tk_apoyo_narrativa_assignment AS a ON c.cluster_id = a.cluster_id
GROUP BY c.cluster_id, c.label, c.descripcion
ORDER BY n_replies DESC;

CREATE OR REPLACE VIEW gold.v_tk_apoyo_narrativa_por_tweet AS
SELECT
  a.parent_tweet_id,
  c.label AS narrativa_cluster,
  COUNT(*) AS n_replies,
  COUNT(DISTINCT a.username) AS n_autores
FROM gold.tk_apoyo_narrativa_assignment AS a
JOIN gold.tk_apoyo_narrativa_cluster AS c ON a.cluster_id = c.cluster_id
GROUP BY a.parent_tweet_id, c.label
ORDER BY a.parent_tweet_id, n_replies DESC;

CREATE OR REPLACE VIEW gold.v_tk_apoyo_narrativa_temporal AS
SELECT
  DATE_TRUNC('day', r.created_at_ts)::DATE AS dia,
  c.label AS narrativa_cluster,
  COUNT(*) AS n_replies
FROM gold.tk_apoyo_narrativa_assignment AS a
JOIN gold.tk_apoyo_narrativa_cluster AS c ON a.cluster_id = c.cluster_id
LEFT JOIN silver.tk_tw_reply AS r ON a.reply_id = r.reply_id
WHERE r.created_at_ts IS NOT NULL
GROUP BY 1, 2
ORDER BY 1, n_replies DESC;
