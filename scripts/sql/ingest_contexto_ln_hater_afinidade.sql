-- Views: La Nación articles assigned to hater narrative clusters
-- Prereq: gold.ln_hecho_hater_cluster (classify_lanacion_to_hater_clusters.py)
--         gold.tk_hater_narrativa_cluster / v_tk_hater_narrativa_temporal
-- Uso: uv run python scripts/python/db.py run-sql --ingest \
--        --file scripts/sql/ingest_contexto_ln_hater_afinidade.sql

CREATE SCHEMA IF NOT EXISTS gold;

CREATE TABLE IF NOT EXISTS gold.ln_hecho_hater_cluster (
  url VARCHAR PRIMARY KEY,
  fecha DATE,
  seccion VARCHAR,
  titulo VARCHAR,
  cluster_id VARCHAR,
  cluster_label VARCHAR,
  score DOUBLE,
  run_id VARCHAR,
  assigned_at TIMESTAMP DEFAULT current_timestamp
);

CREATE OR REPLACE VIEW gold.v_contexto_ln_por_cluster AS
SELECT
  a.url,
  a.fecha,
  a.seccion,
  a.titulo,
  a.cluster_id,
  a.cluster_label,
  a.score,
  c.descripcion AS cluster_descripcion,
  c.n_replies AS cluster_n_replies_global,
  a.run_id,
  a.assigned_at
FROM gold.ln_hecho_hater_cluster AS a
LEFT JOIN gold.tk_hater_narrativa_cluster AS c
  ON a.cluster_id = c.cluster_id
ORDER BY a.fecha DESC, a.score DESC;
