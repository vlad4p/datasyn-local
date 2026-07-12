-- Facebook bronze → silver: clean, normalize, join fanpage ↔ post ↔ comment ↔ classification
-- Uso: uv run python scripts/python/db.py run-sql --file scripts/sql/redes/ingest_fb_silver.sql

CREATE SCHEMA IF NOT EXISTS silver;

CREATE OR REPLACE TABLE silver.fb_fanpage AS
SELECT
    fanpage_id,
    TRIM(descripcion) AS descripcion,
    habilitado,
    orden,
    instagram_id,
    id_grupo,
    graph,
    datastudio,
    pts,
    figura,
    medio
FROM bronze.fb_fanpage;

CREATE OR REPLACE TABLE silver.fb_post AS
SELECT
    p.post_id,
    p.fanpage_id,
    TRIM(f.descripcion) AS fanpage_descripcion,
    p.tipo_post_id,
    CASE p.tipo_post_id
        WHEN 1 THEN 'link'
        WHEN 2 THEN 'status'
        WHEN 3 THEN 'photo'
        WHEN 4 THEN 'video'
        WHEN 5 THEN 'offer'
        WHEN 6 THEN 'event'
        WHEN 7 THEN 'other'
        WHEN 8 THEN 'note'
        ELSE 'unknown'
    END AS tipo_post,
    p.fecha_post,
    TRIM(p.mensaje) AS mensaje,
    p.reacciones,
    p.comentarios,
    p.compartidos,
    p.fecha_registro,
    p.likes,
    p.loves,
    p.wows,
    p.hahas,
    p.sads,
    p.angrys,
    p.cares,
    p.analizado,
    p.ultimo_link,
    p.anuncio,
    p.fecha_modificacion,
    p.esta_creciendo,
    p.ad,
    p.eliminado
FROM bronze.fb_post AS p
INNER JOIN silver.fb_fanpage AS f ON p.fanpage_id = f.fanpage_id;

CREATE OR REPLACE TABLE silver.fb_comment AS
SELECT
    c.comentario_id,
    c.respuesta_id,
    c.post_id,
    p.fanpage_id,
    p.fanpage_descripcion,
    c.user_id,
    NULLIF(TRIM(c.user_name), '') AS user_name,
    TRIM(c.comentario) AS comentario,
    c.fecha_comentario,
    c.like_count,
    c.comment_count,
    c.fecha_registro,
    c.respuesta_id > 0 AS es_respuesta
FROM bronze.fb_comment AS c
INNER JOIN silver.fb_post AS p ON c.post_id = p.post_id
WHERE c.comentario IS NOT NULL
  AND LENGTH(TRIM(c.comentario)) > 0;

CREATE OR REPLACE TABLE silver.fb_comment_classification AS
SELECT
    cl.id AS classification_id,
    cl.post_id,
    p.fanpage_id,
    p.fanpage_descripcion,
    cl.origen,
    cl.comment_id,
    cl.comment_id LIKE 'SIN_ID%' AS comment_id_sintetico,
    cl.free_criteria,
    CASE cl.free_criteria
        WHEN '1' THEN 'apoyo_izquierda'
        WHEN '2' THEN 'derecha_o_troll'
        WHEN '3' THEN 'neutral'
        WHEN '1,2' THEN 'ambiguo'
        WHEN 'INCLASIFICABLE' THEN 'inclasificable'
        ELSE 'otro'
    END AS criterio_label,
    TRIM(cl.resumen) AS resumen,
    cl.created_at,
    cl.updated_at,
    c.comentario_id IS NOT NULL AS has_comment_match,
    TRIM(c.comentario) AS comentario
FROM bronze.fb_comments_classification AS cl
INNER JOIN silver.fb_post AS p ON cl.post_id = p.post_id
LEFT JOIN bronze.fb_comment AS c ON cl.comment_id = CAST(c.comentario_id AS VARCHAR);
