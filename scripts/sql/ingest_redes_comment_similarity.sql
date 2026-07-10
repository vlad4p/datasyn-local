-- Redes: unified comments, entity stats, and similarity clusters (text + LLM resumen).
-- Prereq: silver.fb_* + gold.v_comentarios_clasificados (run ingest_redes_gold.sql first).
-- Facebook only — Twitter vive en pipeline twikit (tk_tw_*).
-- Uso: uv run python scripts/python/db.py mcp-stop
--      uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_network_profile.sql
--      uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_redes_comment_similarity.sql

CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- Unified classified comments with normalized text (Facebook only)
CREATE OR REPLACE TABLE silver.redes_comentarios_unificados AS
SELECT
    'facebook'::VARCHAR AS plataforma,
    CAST(c.comentario_id AS VARCHAR) AS comentario_id,
    CAST(c.post_id AS VARCHAR) AS contenido_padre_id,
    p.fanpage_descripcion AS cuenta_nombre,
    c.fecha_comentario AS fecha,
    cl.criterio_label AS posicion,
    cl.resumen,
    CAST(c.user_id AS VARCHAR) AS autor_id,
    NULLIF(TRIM(c.user_name), '') AS autor_nombre,
    CASE
        WHEN c.user_id IS NOT NULL THEN 'fb_user:' || CAST(c.user_id AS VARCHAR)
        WHEN NULLIF(TRIM(c.user_name), '') IS NOT NULL THEN 'fb_name:' || LOWER(TRIM(c.user_name))
    END AS autor_key,
    TRIM(c.comentario) AS texto,
    REGEXP_REPLACE(LOWER(TRIM(c.comentario)), '\s+', ' ', 'g') AS texto_norm,
    LENGTH(REGEXP_REPLACE(LOWER(TRIM(c.comentario)), '\s+', ' ', 'g')) AS texto_len
FROM silver.fb_comment AS c
INNER JOIN silver.fb_comment_classification AS cl
    ON CAST(c.comentario_id AS VARCHAR) = cl.comment_id
INNER JOIN silver.fb_post AS p ON c.post_id = p.post_id
WHERE c.comentario IS NOT NULL
  AND LENGTH(TRIM(c.comentario)) > 0;

-- Exact duplicate text clusters (normalized), min 5 occurrences, min 10 chars
CREATE OR REPLACE VIEW gold.v_comentarios_clusters_texto AS
WITH clustered AS (
    SELECT
        texto_norm,
        MIN(texto) AS texto_ejemplo,
        MIN(texto_len) AS texto_len,
        COUNT(*) AS ocurrencias,
        COUNT(DISTINCT comentario_id) AS comentarios_distintos,
        COUNT(DISTINCT autor_key) AS autores_distintos,
        COUNT(DISTINCT plataforma) AS plataformas,
        COUNT(DISTINCT cuenta_nombre) AS cuentas_objetivo,
        MODE(posicion) AS posicion_modal,
        MODE(resumen) AS resumen_modal,
        MIN(fecha) AS primera_vez,
        MAX(fecha) AS ultima_vez
    FROM silver.redes_comentarios_unificados
    WHERE texto_len >= 10
      AND texto_norm NOT IN ('formato_sin_texto', 'sin texto', 'comentario sin texto')
    GROUP BY texto_norm
    HAVING COUNT(*) >= 5
)
SELECT
    md5(texto_norm) AS cluster_id,
    texto_norm,
    LEFT(texto_ejemplo, 120) AS texto_ejemplo,
    texto_len,
    ocurrencias,
    comentarios_distintos,
    autores_distintos,
    plataformas,
    cuentas_objetivo,
    posicion_modal,
    resumen_modal,
    primera_vez,
    ultima_vez,
    ROUND(100.0 * ocurrencias / SUM(ocurrencias) OVER (), 3) AS pct_del_total_clasificado
FROM clustered
ORDER BY ocurrencias DESC;

-- LLM resumen clusters (cross-post narrative templates)
CREATE OR REPLACE VIEW gold.v_comentarios_clusters_resumen AS
SELECT
    md5(TRIM(resumen)) AS cluster_id,
    TRIM(resumen) AS resumen,
    COUNT(*) AS ocurrencias,
    COUNT(DISTINCT comentario_id) AS comentarios_distintos,
    COUNT(DISTINCT autor_key) AS autores_distintos,
    COUNT(DISTINCT plataforma) AS plataformas,
    COUNT(DISTINCT cuenta_nombre) AS cuentas_objetivo,
    MODE(posicion) AS posicion_modal,
    MIN(fecha) AS primera_vez,
    MAX(fecha) AS ultima_vez
FROM silver.redes_comentarios_unificados
WHERE resumen IS NOT NULL
  AND LENGTH(TRIM(resumen)) > 3
  AND LOWER(TRIM(resumen)) NOT IN (
      'sin texto', 'comentario sin texto', 'formato sin texto',
      'sin texto en el comentario', 'sin texto o formato inválido'
  )
GROUP BY TRIM(resumen)
HAVING COUNT(*) >= 10
ORDER BY ocurrencias DESC;

-- Pairs of comments with high text similarity (short texts only, capped row count)
CREATE OR REPLACE VIEW gold.v_comentarios_pares_similares AS
WITH sample AS (
    SELECT *
    FROM silver.redes_comentarios_unificados
    WHERE texto_len BETWEEN 15 AND 80
      AND texto_norm NOT LIKE 'formato%'
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY texto_norm ORDER BY fecha DESC
    ) = 1
),
pairs AS (
    SELECT
        a.comentario_id AS id_a,
        b.comentario_id AS id_b,
        a.plataforma AS plataforma_a,
        b.plataforma AS plataforma_b,
        a.texto_norm AS texto_a,
        b.texto_norm AS texto_b,
        jaro_winkler_similarity(a.texto_norm, b.texto_norm) AS similitud,
        a.posicion AS posicion_a,
        b.posicion AS posicion_b,
        a.cuenta_nombre AS cuenta_a,
        b.cuenta_nombre AS cuenta_b
    FROM sample AS a
    INNER JOIN sample AS b
        ON a.comentario_id < b.comentario_id
       AND a.texto_norm <> b.texto_norm
       AND left(a.texto_norm, 8) = left(b.texto_norm, 8)
    WHERE jaro_winkler_similarity(a.texto_norm, b.texto_norm) >= 0.92
)
SELECT * FROM pairs
ORDER BY similitud DESC, id_a
LIMIT 500;
