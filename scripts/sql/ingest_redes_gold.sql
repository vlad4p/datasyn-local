-- Gold views for redes sociales: sentimiento, narrativa, trolls, grafo
-- Fuentes: silver.fb_* (Facebook only — Twitter vive en pipeline twikit tk_tw_*)
-- Uso: uv run python scripts/python/db.py mcp-stop
--      uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_redes_gold.sql

CREATE SCHEMA IF NOT EXISTS gold;

-- ---------------------------------------------------------------------------
-- Dimension: cuentas trackeadas del análisis (FB + handles TW de referencia)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_cuentas_trackeadas AS
SELECT *
FROM (
    VALUES
        ('myriambregman', 'Myriam Bregman', 'twitter', 'myriambregman', CAST(NULL AS VARCHAR)),
        ('myriambregman', 'Myriam Bregman', 'facebook', CAST(NULL AS VARCHAR), 'MyriamBregman.PTS'),
        ('nicolasdelcano', 'Nicolas del Caño', 'twitter', 'NicolasdelCano', CAST(NULL AS VARCHAR)),
        ('nicolasdelcano', 'Nicolas del Caño', 'facebook', CAST(NULL AS VARCHAR), 'NicolasDelCano.PTS'),
        ('cristiancastillo', 'Christian Castillo', 'facebook', CAST(NULL AS VARCHAR), 'ChristianCastillo.PTS'),
        ('ptsarg', 'PTS Argentina', 'twitter', 'PTSarg', CAST(NULL AS VARCHAR))
) AS t(cuenta_slug, cuenta_nombre, plataforma, tw_username, fb_fanpage);

-- ---------------------------------------------------------------------------
-- Base de comentarios clasificados (Facebook only)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_comentarios_clasificados AS
SELECT
    'facebook'::VARCHAR AS plataforma,
    cl.comment_id AS comentario_id,
    cl.post_id AS contenido_padre_id,
    cl.fanpage_descripcion AS cuenta_objetivo_raw,
    ct.cuenta_slug,
    ct.cuenta_nombre,
    c.fecha_comentario AS fecha,
    DATE_TRUNC('day', c.fecha_comentario)::DATE AS dia,
    DATE_TRUNC('week', c.fecha_comentario)::DATE AS semana,
    cl.criterio_label AS posicion,
    cl.free_criteria AS codigo_criterio,
    TRIM(cl.resumen) AS resumen,
    CAST(c.user_id AS VARCHAR) AS autor_id,
    c.user_name AS autor_nombre,
    CASE
        WHEN c.user_id IS NOT NULL THEN 'id:' || CAST(c.user_id AS VARCHAR)
        WHEN c.user_name IS NOT NULL AND TRIM(c.user_name) <> '' THEN 'name:' || LOWER(TRIM(c.user_name))
        ELSE 'anon:' || cl.comment_id
    END AS autor_key,
    cl.has_comment_match
FROM silver.fb_comment_classification AS cl
LEFT JOIN silver.fb_comment AS c
    ON CAST(c.comentario_id AS VARCHAR) = cl.comment_id
LEFT JOIN gold.v_cuentas_trackeadas AS ct
    ON ct.plataforma = 'facebook'
   AND ct.fb_fanpage = cl.fanpage_descripcion;

-- ---------------------------------------------------------------------------
-- Narrativa temática (heurística sobre resumen + posición)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_comentario_narrativa AS
SELECT
    cc.*,
    CASE
        WHEN LOWER(COALESCE(cc.resumen, '')) ~ '(sin texto|formato sin|comentario sin)' THEN 'sin_contenido'
        WHEN LOWER(COALESCE(cc.resumen, '')) ~ '(link|enlace|spam)' THEN 'spam_enlaces'
        WHEN LOWER(COALESCE(cc.resumen, '')) ~ '(conspir|sionis|antisemit|nuevo orden)' THEN 'conspiranoia'
        WHEN LOWER(COALESCE(cc.resumen, '')) ~ '(pedofil|violador|asesin)' THEN 'acusacion_grave'
        WHEN LOWER(COALESCE(cc.resumen, '')) ~ '(hipocres|falso|farisa)' THEN 'acusacion_hipocresia'
        WHEN LOWER(COALESCE(cc.resumen, '')) ~ '(boliv|rebeli|evo|masismo)' THEN 'bolivia_rebelion'
        WHEN LOWER(COALESCE(cc.resumen, '')) ~ '(feminis|agostina|niunamenos|mujer)' THEN 'feminismo_genero'
        WHEN LOWER(COALESCE(cc.resumen, '')) ~ 'milei' THEN 'referencia_milei'
        WHEN LOWER(COALESCE(cc.resumen, '')) ~ '(insulto|descalific|burla|provoc)' THEN 'insulto_descalificacion'
        WHEN LOWER(COALESCE(cc.resumen, '')) ~ '(apoyo|solidar|viva|fuerza)' THEN 'apoyo_movilizacion'
        WHEN cc.posicion = 'apoyo_izquierda' THEN 'apoyo_izquierda'
        WHEN cc.posicion = 'derecha_o_troll' THEN 'critica_antizurda'
        WHEN cc.posicion IN ('neutral', 'ambiguo', 'inclasificable') THEN 'neutral_ambiguo'
        ELSE 'otros'
    END AS narrativa,
    CASE cc.posicion
        WHEN 'apoyo_izquierda' THEN 'positivo'
        WHEN 'derecha_o_troll' THEN 'negativo'
        WHEN 'neutral' THEN 'neutral'
        WHEN 'ambiguo' THEN 'ambiguo'
        WHEN 'inclasificable' THEN 'inclasificable'
        ELSE 'desconocido'
    END AS sentimiento,
    cc.posicion = 'derecha_o_troll' AS es_troll
FROM gold.v_comentarios_clasificados AS cc;

-- ---------------------------------------------------------------------------
-- 1) Sentimiento / posición por cuenta trackeada
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_sentimiento_por_cuenta AS
SELECT
    cuenta_slug,
    cuenta_nombre,
    plataforma,
    posicion,
    sentimiento,
    COUNT(*) AS comentarios,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY cuenta_slug, plataforma), 2) AS pct_dentro_cuenta,
    MIN(fecha) AS primer_comentario,
    MAX(fecha) AS ultimo_comentario
FROM gold.v_comentario_narrativa
WHERE cuenta_slug IS NOT NULL
GROUP BY cuenta_slug, cuenta_nombre, plataforma, posicion, sentimiento;

CREATE OR REPLACE VIEW gold.v_sentimiento_resumen_cuenta AS
SELECT
    cuenta_slug,
    cuenta_nombre,
    COUNT(*) AS comentarios_clasificados,
    COUNT(*) FILTER (WHERE plataforma = 'facebook') AS fb_clasificados,
    COUNT(*) FILTER (WHERE plataforma = 'twitter') AS tw_clasificados,
    COUNT(*) FILTER (WHERE posicion = 'apoyo_izquierda') AS apoyo_izquierda,
    COUNT(*) FILTER (WHERE posicion = 'derecha_o_troll') AS derecha_o_troll,
    COUNT(*) FILTER (WHERE posicion = 'neutral') AS neutral,
    COUNT(*) FILTER (WHERE posicion IN ('ambiguo', 'inclasificable')) AS ambiguo_inclasificable,
    ROUND(100.0 * COUNT(*) FILTER (WHERE posicion = 'apoyo_izquierda') / COUNT(*), 1) AS pct_apoyo,
    ROUND(100.0 * COUNT(*) FILTER (WHERE posicion = 'derecha_o_troll') / COUNT(*), 1) AS pct_troll,
    MIN(fecha) AS primer_comentario,
    MAX(fecha) AS ultimo_comentario
FROM gold.v_comentario_narrativa
WHERE cuenta_slug IS NOT NULL
GROUP BY cuenta_slug, cuenta_nombre;

CREATE OR REPLACE VIEW gold.v_sentimiento_temporal AS
SELECT
    cuenta_slug,
    cuenta_nombre,
    plataforma,
    dia,
    semana,
    posicion,
    sentimiento,
    COUNT(*) AS comentarios
FROM gold.v_comentario_narrativa
WHERE cuenta_slug IS NOT NULL
  AND fecha IS NOT NULL
GROUP BY cuenta_slug, cuenta_nombre, plataforma, dia, semana, posicion, sentimiento;

-- ---------------------------------------------------------------------------
-- 2) Narrativa
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_narrativa_distribucion AS
SELECT
    cuenta_slug,
    cuenta_nombre,
    plataforma,
    narrativa,
    posicion,
    COUNT(*) AS comentarios,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY cuenta_slug, plataforma), 2) AS pct_narrativa
FROM gold.v_comentario_narrativa
WHERE cuenta_slug IS NOT NULL
GROUP BY cuenta_slug, cuenta_nombre, plataforma, narrativa, posicion;

CREATE OR REPLACE VIEW gold.v_narrativa_temporal AS
SELECT
    cuenta_slug,
    cuenta_nombre,
    plataforma,
    semana,
    narrativa,
    COUNT(*) AS comentarios
FROM gold.v_comentario_narrativa
WHERE cuenta_slug IS NOT NULL
  AND semana IS NOT NULL
GROUP BY cuenta_slug, cuenta_nombre, plataforma, semana, narrativa;

CREATE OR REPLACE VIEW gold.v_narrativa_top_resumenes AS
SELECT
    cuenta_slug,
    plataforma,
    narrativa,
    resumen,
    posicion,
    COUNT(*) AS ocurrencias
FROM gold.v_comentario_narrativa
WHERE cuenta_slug IS NOT NULL
  AND resumen IS NOT NULL
GROUP BY cuenta_slug, plataforma, narrativa, resumen, posicion
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY cuenta_slug, plataforma, narrativa
    ORDER BY COUNT(*) DESC, resumen
) <= 5;

-- ---------------------------------------------------------------------------
-- 3) Trolls: ranking, temporalidad, grupos
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_trolls_actividad AS
SELECT
    plataforma,
    autor_key,
    autor_id,
    autor_nombre,
    cuenta_slug,
    cuenta_objetivo_raw,
    contenido_padre_id,
    comentario_id,
    fecha,
    dia,
    semana,
    narrativa,
    resumen
FROM gold.v_comentario_narrativa
WHERE es_troll
  AND autor_key NOT LIKE 'anon:%';

CREATE OR REPLACE VIEW gold.v_trolls_top10 AS
SELECT
    plataforma,
    autor_key,
    MAX(autor_nombre) AS autor_nombre,
    MAX(autor_id) AS autor_id,
    COUNT(*) AS comentarios_troll,
    COUNT(DISTINCT dia) AS dias_activos,
    MIN(fecha) AS primer_comentario,
    MAX(fecha) AS ultimo_comentario,
    DATE_DIFF('day', MIN(fecha), MAX(fecha)) AS span_dias,
    COUNT(DISTINCT cuenta_slug) AS cuentas_objetivo,
    LIST(DISTINCT cuenta_slug ORDER BY cuenta_slug) AS cuentas_slug,
    LIST(DISTINCT narrativa ORDER BY narrativa) AS narrativas,
    ROW_NUMBER() OVER (PARTITION BY plataforma ORDER BY COUNT(*) DESC, MIN(fecha)) AS ranking
FROM gold.v_trolls_actividad
WHERE autor_nombre IS NOT NULL OR autor_id IS NOT NULL
GROUP BY plataforma, autor_key
QUALIFY ranking <= 10;

CREATE OR REPLACE VIEW gold.v_trolls_temporal AS
SELECT
    plataforma,
    dia,
    semana,
    cuenta_slug,
    COUNT(*) AS comentarios_troll,
    COUNT(DISTINCT autor_key) AS autores_troll,
    COUNT(*) FILTER (WHERE narrativa = 'spam_enlaces') AS spam_enlaces,
    COUNT(*) FILTER (WHERE narrativa = 'insulto_descalificacion') AS insultos,
    COUNT(*) FILTER (WHERE narrativa = 'conspiranoia') AS conspiranoia,
    COUNT(*) FILTER (WHERE narrativa = 'acusacion_grave') AS acusaciones_graves
FROM gold.v_trolls_actividad
GROUP BY plataforma, dia, semana, cuenta_slug;

CREATE OR REPLACE VIEW gold.v_trolls_grupos_multobjetivo AS
SELECT
    plataforma,
    autor_key,
    MAX(autor_nombre) AS autor_nombre,
    COUNT(*) AS comentarios_troll,
    COUNT(DISTINCT cuenta_slug) AS cuentas_distintas,
    LIST(DISTINCT cuenta_slug ORDER BY cuenta_slug) AS cuentas_objetivo,
    MIN(fecha) AS primer_comentario,
    MAX(fecha) AS ultimo_comentario,
    LIST(DISTINCT narrativa ORDER BY narrativa) AS narrativas
FROM gold.v_trolls_actividad
WHERE cuenta_slug IS NOT NULL
GROUP BY plataforma, autor_key
HAVING COUNT(DISTINCT cuenta_slug) >= 2;

CREATE OR REPLACE VIEW gold.v_trolls_cohortes_dia AS
SELECT
    plataforma,
    cuenta_slug,
    dia,
    COUNT(DISTINCT autor_key) AS autores_troll,
    COUNT(*) AS comentarios_troll,
    ROUND(COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT autor_key), 0), 2) AS comentarios_por_autor,
    LIST(DISTINCT autor_nombre ORDER BY autor_nombre) FILTER (WHERE autor_nombre IS NOT NULL) AS autores_muestra
FROM gold.v_trolls_actividad
WHERE cuenta_slug IS NOT NULL
GROUP BY plataforma, cuenta_slug, dia
HAVING COUNT(DISTINCT autor_key) >= 3
ORDER BY comentarios_troll DESC;

CREATE OR REPLACE VIEW gold.v_trolls_rafagas AS
SELECT
    plataforma,
    autor_key,
    MAX(autor_nombre) AS autor_nombre,
    cuenta_slug,
    dia,
    COUNT(*) AS comentarios_en_dia,
    MIN(fecha) AS inicio_ráfaga,
    MAX(fecha) AS fin_ráfaga,
    DATE_DIFF('minute', MIN(fecha), MAX(fecha)) AS minutos_span,
    LIST(DISTINCT narrativa ORDER BY narrativa) AS narrativas
FROM gold.v_trolls_actividad
GROUP BY plataforma, autor_key, cuenta_slug, dia
HAVING COUNT(*) >= 3
ORDER BY comentarios_en_dia DESC, minutos_span ASC;

-- Autores distintos con ráfaga por día y cuenta objetivo
CREATE OR REPLACE VIEW gold.v_trolls_rafagas_dia AS
SELECT
    plataforma,
    cuenta_slug,
    dia,
    COUNT(DISTINCT autor_key) AS autores_con_rafaga,
    COUNT(*) AS eventos_rafaga,
    SUM(comentarios_en_dia) AS comentarios_en_rafagas,
    ROUND(SUM(comentarios_en_dia) * 1.0 / NULLIF(COUNT(DISTINCT autor_key), 0), 1) AS comentarios_por_autor,
    MAX(comentarios_en_dia) AS max_comentarios_un_autor,
    MIN(minutos_span) AS rafaga_mas_intensa_min
FROM gold.v_trolls_rafagas
WHERE cuenta_slug IS NOT NULL
GROUP BY plataforma, cuenta_slug, dia;

-- Resumen global de ráfagas
CREATE OR REPLACE VIEW gold.v_trolls_rafagas_resumen AS
SELECT
    COUNT(DISTINCT autor_key) AS autores_distintos_con_rafaga,
    COUNT(*) AS eventos_rafaga_total,
    SUM(comentarios_en_dia) AS comentarios_en_rafagas_total,
    COUNT(DISTINCT cuenta_slug) AS cuentas_objetivo_afectadas,
    MIN(dia) AS primer_dia_rafaga,
    MAX(dia) AS ultimo_dia_rafaga
FROM gold.v_trolls_rafagas;

-- Por autor: cuántos días tuvo ráfaga y volumen
CREATE OR REPLACE VIEW gold.v_trolls_rafagas_por_autor AS
SELECT
    plataforma,
    autor_key,
    MAX(autor_nombre) AS autor_nombre,
    COUNT(*) AS dias_con_rafaga,
    SUM(comentarios_en_dia) AS comentarios_rafaga,
    COUNT(DISTINCT cuenta_slug) AS cuentas_objetivo,
    LIST(DISTINCT cuenta_slug ORDER BY cuenta_slug) AS cuentas_slug,
    MIN(dia) AS primera_rafaga,
    MAX(dia) AS ultima_rafaga,
    ROUND(AVG(comentarios_en_dia), 1) AS promedio_comentarios_rafaga
FROM gold.v_trolls_rafagas
GROUP BY plataforma, autor_key;

-- Grafo de interacciones troll (autores, cuentas, narrativas, co-ráfagas)
CREATE OR REPLACE VIEW gold.grafo_vertices_trolls AS
SELECT DISTINCT
    'autor:' || autor_key AS vertex_id,
    COALESCE(autor_nombre, autor_key) AS label,
    'autor'::VARCHAR AS tipo,
    plataforma,
    SUM(comentarios_en_dia) OVER (PARTITION BY autor_key) AS peso_actividad
FROM gold.v_trolls_rafagas

UNION

SELECT DISTINCT
    'cuenta:' || cuenta_slug AS vertex_id,
    cuenta_slug AS label,
    'cuenta_objetivo'::VARCHAR AS tipo,
    CAST(NULL AS VARCHAR) AS plataforma,
    NULL::BIGINT AS peso_actividad
FROM gold.v_trolls_rafagas
WHERE cuenta_slug IS NOT NULL

UNION

SELECT DISTINCT
    'narrativa:' || unnest AS vertex_id,
    unnest AS label,
    'narrativa'::VARCHAR AS tipo,
    CAST(NULL AS VARCHAR) AS plataforma,
    NULL::BIGINT AS peso_actividad
FROM gold.v_trolls_rafagas, unnest(narrativas)

UNION

SELECT DISTINCT
    'cohorte:' || CAST(dia AS VARCHAR) || ':' || cuenta_slug AS vertex_id,
    CAST(dia AS DATE)::VARCHAR || ' · ' || cuenta_slug AS label,
    'cohorte_dia'::VARCHAR AS tipo,
    plataforma,
    autores_con_rafaga AS peso_actividad
FROM gold.v_trolls_rafagas_dia
WHERE autores_con_rafaga >= 2;

CREATE OR REPLACE VIEW gold.grafo_edges_trolls AS
-- autor ataca cuenta (desde ráfagas)
SELECT
    'autor:' || autor_key AS source_id,
    'cuenta:' || cuenta_slug AS target_id,
    'ataca'::VARCHAR AS edge_type,
    SUM(comentarios_en_dia) AS peso,
    CAST(NULL AS VARCHAR) AS metadata
FROM gold.v_trolls_rafagas
WHERE cuenta_slug IS NOT NULL
GROUP BY 1, 2

UNION ALL

-- autor usa narrativa en ráfaga
SELECT
    'autor:' || r.autor_key,
    'narrativa:' || n.narrativa,
    'usa_narrativa',
    COUNT(*),
    r.cuenta_slug
FROM gold.v_trolls_rafagas AS r
CROSS JOIN UNNEST(r.narrativas) AS n(narrativa)
GROUP BY 1, 2, 5

UNION ALL

-- co-ráfaga: dos autores el mismo día contra la misma cuenta
SELECT
    'autor:' || a.autor_key,
    'autor:' || b.autor_key,
    'co_rafaga',
    1 + LEAST(a.comentarios_en_dia, b.comentarios_en_dia),
    a.cuenta_slug || ' · ' || CAST(a.dia AS DATE)
FROM gold.v_trolls_rafagas AS a
INNER JOIN gold.v_trolls_rafagas AS b
    ON a.cuenta_slug = b.cuenta_slug
   AND a.dia = b.dia
   AND a.autor_key < b.autor_key

UNION ALL

-- autor participa en cohorte diaria
SELECT
    'autor:' || autor_key,
    'cohorte:' || CAST(dia AS VARCHAR) || ':' || cuenta_slug,
    'en_cohorte',
    comentarios_en_dia,
    cuenta_slug
FROM gold.v_trolls_rafagas
WHERE cuenta_slug IS NOT NULL;

CREATE OR REPLACE VIEW gold.grafo_edges_agg_trolls AS
SELECT
    source_id,
    target_id,
    edge_type,
    SUM(peso) AS peso_total,
    COUNT(*) AS eventos,
    MAX(metadata) AS metadata_ejemplo
FROM gold.grafo_edges_trolls
GROUP BY source_id, target_id, edge_type;

-- ---------------------------------------------------------------------------
-- 4) Grafo por narrativa (vértices + aristas)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.grafo_vertices_narrativa AS
SELECT DISTINCT
    'autor:' || autor_key AS vertex_id,
    COALESCE(autor_nombre, autor_id, autor_key) AS label,
    'autor'::VARCHAR AS tipo,
    plataforma
FROM gold.v_comentario_narrativa
WHERE cuenta_slug IS NOT NULL

UNION

SELECT DISTINCT
    'narrativa:' || narrativa AS vertex_id,
    narrativa AS label,
    'narrativa'::VARCHAR AS tipo,
    CAST(NULL AS VARCHAR) AS plataforma
FROM gold.v_comentario_narrativa
WHERE cuenta_slug IS NOT NULL

UNION

SELECT DISTINCT
    'cuenta:' || cuenta_slug AS vertex_id,
    cuenta_nombre AS label,
    'cuenta_objetivo'::VARCHAR AS tipo,
    CAST(NULL AS VARCHAR) AS plataforma
FROM gold.v_comentario_narrativa
WHERE cuenta_slug IS NOT NULL;

CREATE OR REPLACE VIEW gold.grafo_edges_narrativa AS
-- autor -> narrativa
SELECT
    'autor:' || autor_key AS source_id,
    'narrativa:' || narrativa AS target_id,
    'autor_narrativa'::VARCHAR AS edge_type,
    plataforma,
    cuenta_slug,
    contenido_padre_id,
    COUNT(*) AS peso
FROM gold.v_comentario_narrativa
WHERE cuenta_slug IS NOT NULL
GROUP BY 1, 2, 3, 4, 5, 6

UNION ALL

-- autor -> cuenta objetivo
SELECT
    'autor:' || autor_key,
    'cuenta:' || cuenta_slug,
    'autor_cuenta',
    plataforma,
    cuenta_slug,
    contenido_padre_id,
    COUNT(*)
FROM gold.v_comentario_narrativa
WHERE cuenta_slug IS NOT NULL
GROUP BY 1, 2, 3, 4, 5, 6

UNION ALL

-- narrativa -> cuenta objetivo
SELECT
    'narrativa:' || narrativa,
    'cuenta:' || cuenta_slug,
    'narrativa_cuenta',
    plataforma,
    cuenta_slug,
    contenido_padre_id,
    COUNT(*)
FROM gold.v_comentario_narrativa
WHERE cuenta_slug IS NOT NULL
GROUP BY 1, 2, 3, 4, 5, 6

UNION ALL

-- co-ocurrencia narrativa-narrativa en mismo post/tweet
SELECT
    'narrativa:' || LEAST(a.narrativa, b.narrativa),
    'narrativa:' || GREATEST(a.narrativa, b.narrativa),
    'narrativa_coocurrencia',
    a.plataforma,
    a.cuenta_slug,
    a.contenido_padre_id,
    COUNT(*) AS peso
FROM gold.v_comentario_narrativa AS a
INNER JOIN gold.v_comentario_narrativa AS b
    ON a.plataforma = b.plataforma
   AND a.contenido_padre_id = b.contenido_padre_id
   AND a.narrativa < b.narrativa
WHERE a.cuenta_slug IS NOT NULL
GROUP BY 1, 2, 3, 4, 5, 6;

CREATE OR REPLACE VIEW gold.grafo_edges_agg_narrativa AS
SELECT
    source_id,
    target_id,
    edge_type,
    plataforma,
    cuenta_slug,
    SUM(peso) AS peso_total,
    COUNT(DISTINCT contenido_padre_id) AS contenidos_distintos
FROM gold.grafo_edges_narrativa
GROUP BY source_id, target_id, edge_type, plataforma, cuenta_slug;
