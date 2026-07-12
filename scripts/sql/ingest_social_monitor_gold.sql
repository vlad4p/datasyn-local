-- Unified social monitoring gold layer keyed by persona_id + plataforma
-- Prereqs: silver.identidad / identidad_cuenta, gold redes FB views, twikit gold
-- Uso:
--   uv run python scripts/python/db.py mcp-stop
--   uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_identidades.sql
--   uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_social_monitor_gold.sql

CREATE SCHEMA IF NOT EXISTS gold;

-- ---------------------------------------------------------------------------
-- Map cuenta_slug (legacy) → persona_id
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_monitor_cuenta_map AS
SELECT DISTINCT
    i.persona_id,
    i.nombre_canonico,
    c.plataforma,
    c.handle,
    c.platform_user_id,
    c.fb_fanpage,
    CASE
        WHEN c.plataforma = 'facebook' AND c.fb_fanpage IS NOT NULL THEN
            CASE LOWER(c.fb_fanpage)
                WHEN 'myriambregman.pts' THEN 'myriambregman'
                WHEN 'nicolasdelcano.pts' THEN 'nicolasdelcano'
                WHEN 'christiancastillo.pts' THEN 'cristiancastillo'
                WHEN 'laizquierdadiario' THEN 'laizquierdadiario'
                ELSE LOWER(REGEXP_REPLACE(c.fb_fanpage, '\\.pts$', '', 'i'))
            END
        WHEN c.plataforma = 'twitter' AND c.handle IS NOT NULL THEN LOWER(c.handle)
        ELSE i.persona_id
    END AS cuenta_slug
FROM silver.identidad AS i
JOIN silver.identidad_cuenta AS c
    ON c.persona_id = i.persona_id
WHERE i.es_objetivo;

-- ---------------------------------------------------------------------------
-- Perfil: persona + cuentas + stats por plataforma
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_monitor_perfil AS
SELECT
    i.persona_id,
    i.nombre_canonico,
    i.tipo,
    i.rol,
    i.partido,
    i.es_objetivo,
    i.sitio_web,
    i.wikidata_id,
    i.genero,
    i.provincia,
    i.fuentes_osint,
    i.notas,
    c.plataforma,
    c.platform_user_id,
    c.handle,
    c.url,
    c.es_oficial,
    CASE
        WHEN c.plataforma = 'twitter' THEN COALESCE(enr.followers_count, tw.followers_count, twu.followers_count)
        WHEN c.plataforma = 'facebook' THEN CAST(np.facebook_page_total_likes AS BIGINT)
        ELSE NULL
    END AS followers_count,
    CASE
        WHEN c.plataforma = 'twitter' THEN COALESCE(enr.following_count, tw.following_count, twu.following_count)
        ELSE NULL
    END AS following_count,
    CASE
        WHEN c.plataforma = 'twitter' THEN COALESCE(enr.statuses_count, tw.statuses_count, twu.statuses_count)
        WHEN c.plataforma = 'facebook' THEN CAST(np.facebook_posts_in_period AS BIGINT)
        ELSE NULL
    END AS posts_count,
    CASE
        WHEN c.plataforma = 'twitter' THEN COALESCE(enr.is_blue_verified, enr.is_verified, twu.is_blue_verified, twu.is_verified, FALSE)
        ELSE FALSE
    END AS is_verified,
    CASE
        WHEN c.plataforma = 'twitter' THEN COALESCE(enr.bio, twu.bio, tw.description)
        WHEN c.plataforma = 'facebook' THEN np.display_name
        ELSE NULL
    END AS bio,
    CASE
        WHEN c.plataforma = 'twitter' THEN COALESCE(enr.location, twu.location)
        ELSE NULL
    END AS location,
    CASE
        WHEN c.plataforma = 'twitter' THEN COALESCE(enr.account_created_at, twu.account_created_at)
        ELSE NULL
    END AS account_created_at,
    m.cuenta_slug
FROM silver.identidad AS i
JOIN silver.identidad_cuenta AS c
    ON c.persona_id = i.persona_id
LEFT JOIN gold.v_monitor_cuenta_map AS m
    ON m.persona_id = i.persona_id
   AND m.plataforma = c.plataforma
   AND COALESCE(m.handle, '') = COALESCE(c.handle, '')
LEFT JOIN silver.tk_tw_profile AS tw
    ON c.plataforma = 'twitter'
   AND (
        tw.user_id = c.platform_user_id
        OR LOWER(tw.username) = LOWER(c.handle)
    )
LEFT JOIN silver.tk_tw_user AS twu
    ON c.plataforma = 'twitter'
   AND (
        twu.user_id = c.platform_user_id
        OR LOWER(twu.username) = LOWER(c.handle)
    )
LEFT JOIN silver.tk_tw_profile_enriched AS enr
    ON c.plataforma = 'twitter'
   AND (
        enr.user_id = c.platform_user_id
        OR LOWER(enr.username) = LOWER(c.handle)
    )
LEFT JOIN silver.network_profile AS np
    ON c.plataforma = 'facebook'
   AND (
        CAST(np.facebook_page_id AS VARCHAR) = c.platform_user_id
        OR np.facebook_page_name = c.fb_fanpage
        OR np.facebook_page_name = c.handle
    );

-- ---------------------------------------------------------------------------
-- Reacciones: desglose por persona / plataforma / post
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_monitor_reacciones AS
-- Facebook reaction breakdown
SELECT
    m.persona_id,
    m.nombre_canonico,
    'facebook'::VARCHAR AS plataforma,
    CAST(p.post_id AS VARCHAR) AS content_id,
    p.fecha_post AS published_at,
    DATE_TRUNC('day', p.fecha_post)::DATE AS dia,
    COALESCE(p.reacciones, 0) AS reacciones_total,
    COALESCE(p.likes, 0) AS likes,
    COALESCE(p.loves, 0) AS loves,
    COALESCE(p.wows, 0) AS wows,
    COALESCE(p.hahas, 0) AS hahas,
    COALESCE(p.sads, 0) AS sads,
    COALESCE(p.angrys, 0) AS angrys,
    COALESCE(p.cares, 0) AS cares,
    COALESCE(p.comentarios, 0) AS comentarios,
    COALESCE(p.compartidos, 0) AS compartidos,
    CAST(NULL AS BIGINT) AS retweets,
    CAST(NULL AS BIGINT) AS quotes,
    CAST(NULL AS BIGINT) AS views
FROM silver.fb_post AS p
JOIN gold.v_monitor_cuenta_map AS m
    ON m.plataforma = 'facebook'
   AND m.fb_fanpage = p.fanpage_descripcion

UNION ALL

-- Twitter engagement as "reactions"
SELECT
    m.persona_id,
    m.nombre_canonico,
    'twitter'::VARCHAR AS plataforma,
    t.tweet_id AS content_id,
    t.created_at_ts AS published_at,
    DATE_TRUNC('day', t.created_at_ts)::DATE AS dia,
    COALESCE(t.like_count, 0)
        + COALESCE(t.retweet_count, 0)
        + COALESCE(t.reply_count, 0)
        + COALESCE(t.quote_count, 0) AS reacciones_total,
    COALESCE(t.like_count, 0) AS likes,
    CAST(0 AS BIGINT) AS loves,
    CAST(0 AS BIGINT) AS wows,
    CAST(0 AS BIGINT) AS hahas,
    CAST(0 AS BIGINT) AS sads,
    CAST(0 AS BIGINT) AS angrys,
    CAST(0 AS BIGINT) AS cares,
    COALESCE(t.reply_count, 0) AS comentarios,
    CAST(0 AS BIGINT) AS compartidos,
    COALESCE(t.retweet_count, 0) AS retweets,
    COALESCE(t.quote_count, 0) AS quotes,
    COALESCE(t.view_count, 0) AS views
FROM silver.tk_tw_tweet AS t
JOIN gold.v_monitor_cuenta_map AS m
    ON m.plataforma = 'twitter'
   AND (
        t.author_id = m.platform_user_id
        OR LOWER(t.username) = LOWER(m.handle)
    );

-- ---------------------------------------------------------------------------
-- Engagement diario por persona / plataforma
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_monitor_engagement AS
SELECT
    persona_id,
    nombre_canonico,
    plataforma,
    dia,
    COUNT(*) AS posts,
    SUM(reacciones_total) AS reacciones,
    SUM(comentarios) AS comentarios,
    SUM(compartidos) AS compartidos,
    SUM(COALESCE(retweets, 0)) AS retweets,
    SUM(COALESCE(quotes, 0)) AS quotes,
    SUM(COALESCE(views, 0)) AS views,
    SUM(likes) AS likes,
    CASE
        WHEN COUNT(*) = 0 THEN 0.0
        ELSE CAST(SUM(reacciones_total) + SUM(comentarios) + SUM(compartidos) AS DOUBLE)
             / COUNT(*)
    END AS engagement_por_post
FROM gold.v_monitor_reacciones
WHERE dia IS NOT NULL
GROUP BY persona_id, nombre_canonico, plataforma, dia;

-- ---------------------------------------------------------------------------
-- Audiencia: clasificación de comentaristas / repliers (+ bot heuristic TW)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_monitor_audiencia AS
-- Facebook classified comments
SELECT
    m.persona_id,
    m.nombre_canonico,
    'facebook'::VARCHAR AS plataforma,
    cc.autor_id AS actor_id,
    cc.autor_nombre AS actor_nombre,
    cc.autor_key,
    cc.posicion AS criterio_label,
    CASE
        WHEN cc.posicion = 'derecha_o_troll' THEN 'hater'
        WHEN cc.posicion = 'apoyo_izquierda' THEN 'apoyo'
        WHEN cc.posicion IN ('neutral', 'ambiguo') THEN 'neutral'
        ELSE 'otro'
    END AS audiencia_clase,
    FALSE AS es_bot_heuristico,
    CAST(NULL AS VARCHAR) AS risk_band,
    CAST(NULL AS DOUBLE) AS risk_score,
    cc.comentario_id AS content_id,
    cc.fecha AS occurred_at,
    cc.dia,
    cc.narrativa
FROM gold.v_comentario_narrativa AS cc
JOIN gold.v_monitor_cuenta_map AS m
    ON m.plataforma = 'facebook'
   AND m.cuenta_slug = cc.cuenta_slug

UNION ALL

-- Twitter classified replies
SELECT
    m.persona_id,
    m.nombre_canonico,
    'twitter'::VARCHAR AS plataforma,
    r.author_id AS actor_id,
    r.username AS actor_nombre,
    COALESCE('tw:' || r.author_id, 'twu:' || LOWER(r.username)) AS autor_key,
    cl.criterio_label,
    CASE
        WHEN cl.criterio_label = 'derecha_o_troll' THEN 'hater'
        WHEN cl.criterio_label = 'apoyo_izquierda' THEN 'apoyo'
        WHEN cl.criterio_label IN ('neutral', 'ambiguo') THEN 'neutral'
        ELSE 'otro'
    END AS audiencia_clase,
    COALESCE(
        risk.flag_new_account
        OR risk.flag_follow_ratio_high
        OR risk.flag_high_output_low_audience
        OR risk.flag_empty_bio
        OR risk_apoyo.flag_new_account
        OR risk_apoyo.flag_follow_ratio_high
        OR risk_apoyo.flag_high_output_low_audience
        OR risk_apoyo.flag_empty_bio,
        FALSE
    ) AS es_bot_heuristico,
    COALESCE(risk.risk_band, risk_apoyo.risk_band) AS risk_band,
    COALESCE(risk.risk_score, risk_apoyo.risk_score) AS risk_score,
    r.reply_id AS content_id,
    r.created_at_ts AS occurred_at,
    DATE_TRUNC('day', r.created_at_ts)::DATE AS dia,
    COALESCE(na.label, na_apoyo.label, cl.narrativa_raw, cl.resumen) AS narrativa
FROM silver.tk_tw_reply AS r
JOIN silver.tk_tw_reply_classification AS cl
    ON cl.reply_id = r.reply_id
JOIN silver.tk_tw_tweet AS t
    ON t.tweet_id = r.parent_tweet_id
JOIN gold.v_monitor_cuenta_map AS m
    ON m.plataforma = 'twitter'
   AND (
        t.author_id = m.platform_user_id
        OR LOWER(t.username) = LOWER(m.handle)
    )
LEFT JOIN gold.tk_hater_profile_risk AS risk
    ON risk.user_id = r.author_id
LEFT JOIN gold.tk_apoyo_profile_risk AS risk_apoyo
    ON risk_apoyo.user_id = r.author_id
LEFT JOIN gold.tk_hater_narrativa_assignment AS asg
    ON asg.reply_id = r.reply_id
LEFT JOIN gold.tk_hater_narrativa_cluster AS na
    ON na.cluster_id = asg.cluster_id
LEFT JOIN gold.tk_apoyo_narrativa_assignment AS asg_apoyo
    ON asg_apoyo.reply_id = r.reply_id
LEFT JOIN gold.tk_apoyo_narrativa_cluster AS na_apoyo
    ON na_apoyo.cluster_id = asg_apoyo.cluster_id;

-- ---------------------------------------------------------------------------
-- Audiencia resumen (agregado)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_monitor_audiencia_resumen AS
SELECT
    persona_id,
    nombre_canonico,
    plataforma,
    audiencia_clase,
    COUNT(*) AS eventos,
    COUNT(DISTINCT autor_key) AS actores_distintos,
    SUM(CASE WHEN es_bot_heuristico THEN 1 ELSE 0 END) AS eventos_bot_heuristico,
    COUNT(DISTINCT CASE WHEN es_bot_heuristico THEN autor_key END) AS actores_bot_heuristico
FROM gold.v_monitor_audiencia
GROUP BY persona_id, nombre_canonico, plataforma, audiencia_clase;

-- ---------------------------------------------------------------------------
-- Haters top 10 por persona (FB trolls + TW blacklist)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_monitor_haters_top10 AS
WITH fb AS (
    SELECT
        m.persona_id,
        m.nombre_canonico,
        'facebook'::VARCHAR AS plataforma,
        t.autor_id AS actor_id,
        t.autor_nombre AS actor_nombre,
        t.comentarios_troll AS score_eventos,
        t.dias_activos,
        array_to_string(t.cuentas_slug, ',') AS cuentas_objetivo,
        array_to_string(t.narrativas, ',') AS narrativas,
        CAST(NULL AS VARCHAR) AS tier,
        CAST(NULL AS DOUBLE) AS risk_score,
        t.ranking AS ranking_src
    FROM gold.v_trolls_top10 AS t
    JOIN gold.v_monitor_cuenta_map AS m
        ON m.plataforma = 'facebook'
       AND list_contains(t.cuentas_slug, m.cuenta_slug)
),
-- Twikit blacklist is scoped to scraped TW targets (today: myriambregman)
tw_targets AS (
    SELECT DISTINCT persona_id, nombre_canonico
    FROM gold.v_monitor_cuenta_map
    WHERE plataforma = 'twitter'
      AND LOWER(handle) IN (
          SELECT DISTINCT LOWER(username)
          FROM silver.tk_tw_tweet
          WHERE username IS NOT NULL
      )
),
tw AS (
    SELECT
        tg.persona_id,
        tg.nombre_canonico,
        'twitter'::VARCHAR AS plataforma,
        b.user_id AS actor_id,
        COALESCE(b.username, b.display_name) AS actor_nombre,
        COALESCE(b.hater_replies, b.replies_total, 0) AS score_eventos,
        CAST(NULL AS BIGINT) AS dias_activos,
        CAST(b.target_accounts AS VARCHAR) AS cuentas_objetivo,
        CAST(b.narrativas AS VARCHAR) AS narrativas,
        b.tier,
        CAST(b.risk_score AS DOUBLE) AS risk_score,
        ROW_NUMBER() OVER (
            PARTITION BY tg.persona_id
            ORDER BY COALESCE(b.score, 0) DESC, COALESCE(b.hater_replies, 0) DESC
        ) AS ranking_src
    FROM gold.tk_troll_blacklist AS b
    CROSS JOIN tw_targets AS tg
),
unioned AS (
    SELECT * FROM fb
    UNION ALL
    SELECT * FROM tw WHERE ranking_src <= 50
),
ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY persona_id, plataforma
            ORDER BY score_eventos DESC, COALESCE(risk_score, 0) DESC
        ) AS ranking
    FROM unioned
)
SELECT *
FROM ranked
WHERE ranking <= 10;

-- ---------------------------------------------------------------------------
-- Apoyo / defensores top 10 por persona (TW supporters)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_monitor_apoyo_top10 AS
WITH tw_targets AS (
    SELECT DISTINCT persona_id, nombre_canonico
    FROM gold.v_monitor_cuenta_map
    WHERE plataforma = 'twitter'
      AND LOWER(handle) IN (
          SELECT DISTINCT LOWER(username)
          FROM silver.tk_tw_tweet
          WHERE username IS NOT NULL
      )
),
tw AS (
    SELECT
        tg.persona_id,
        tg.nombre_canonico,
        'twitter'::VARCHAR AS plataforma,
        u.user_id AS actor_id,
        COALESCE(u.username, u.display_name) AS actor_nombre,
        COALESCE(u.apoyo_replies_count, 0) AS score_eventos,
        CAST(NULL AS BIGINT) AS dias_activos,
        CAST(NULL AS VARCHAR) AS cuentas_objetivo,
        CAST(NULL AS VARCHAR) AS narrativas,
        risk.risk_band AS tier,
        CAST(risk.risk_score AS DOUBLE) AS risk_score,
        ROW_NUMBER() OVER (
            PARTITION BY tg.persona_id
            ORDER BY COALESCE(u.apoyo_replies_count, 0) DESC,
                     COALESCE(u.replies_observed_count, 0) DESC
        ) AS ranking_src
    FROM silver.tk_tw_user AS u
    CROSS JOIN tw_targets AS tg
    LEFT JOIN gold.tk_apoyo_profile_risk AS risk
        ON risk.user_id = u.user_id
    WHERE u.is_supporter
),
ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY persona_id, plataforma
            ORDER BY score_eventos DESC, COALESCE(risk_score, 0) DESC
        ) AS ranking
    FROM tw
    WHERE ranking_src <= 50
)
SELECT *
FROM ranked
WHERE ranking <= 10;

-- ---------------------------------------------------------------------------
-- Narrativas por persona
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_monitor_narrativa AS
SELECT
    m.persona_id,
    m.nombre_canonico,
    n.plataforma,
    n.narrativa,
    n.posicion,
    SUM(n.comentarios) AS comentarios,
    AVG(n.pct_narrativa) AS pct_narrativa
FROM gold.v_narrativa_distribucion AS n
JOIN gold.v_monitor_cuenta_map AS m
    ON m.plataforma = n.plataforma
   AND m.cuenta_slug = n.cuenta_slug
GROUP BY m.persona_id, m.nombre_canonico, n.plataforma, n.narrativa, n.posicion

UNION ALL

SELECT
    m.persona_id,
    m.nombre_canonico,
    'twitter'::VARCHAR AS plataforma,
    COALESCE(r.label, 'sin_cluster') AS narrativa,
    'derecha_o_troll'::VARCHAR AS posicion,
    SUM(r.n_replies) AS comentarios,
    AVG(r.pct_haters) AS pct_narrativa
FROM gold.v_tk_hater_narrativa_resumen AS r
JOIN (
    SELECT DISTINCT persona_id, nombre_canonico
    FROM gold.v_monitor_cuenta_map
    WHERE plataforma = 'twitter'
      AND LOWER(handle) IN (
          SELECT DISTINCT LOWER(username) FROM silver.tk_tw_tweet WHERE username IS NOT NULL
      )
) AS m ON TRUE
GROUP BY m.persona_id, m.nombre_canonico, COALESCE(r.label, 'sin_cluster')

UNION ALL

SELECT
    m.persona_id,
    m.nombre_canonico,
    'twitter'::VARCHAR AS plataforma,
    COALESCE(r.label, 'sin_cluster') AS narrativa,
    'apoyo_izquierda'::VARCHAR AS posicion,
    SUM(r.n_replies) AS comentarios,
    AVG(r.pct_apoyo) AS pct_narrativa
FROM gold.v_tk_apoyo_narrativa_resumen AS r
JOIN (
    SELECT DISTINCT persona_id, nombre_canonico
    FROM gold.v_monitor_cuenta_map
    WHERE plataforma = 'twitter'
      AND LOWER(handle) IN (
          SELECT DISTINCT LOWER(username) FROM silver.tk_tw_tweet WHERE username IS NOT NULL
      )
) AS m ON TRUE
GROUP BY m.persona_id, m.nombre_canonico, COALESCE(r.label, 'sin_cluster');

-- ---------------------------------------------------------------------------
-- Serie temporal comparable (para comparativa multi-persona)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_monitor_temporal AS
-- FB sentimiento temporal
SELECT
    m.persona_id,
    m.nombre_canonico,
    s.plataforma,
    s.dia,
    s.posicion,
    s.sentimiento,
    SUM(s.comentarios) AS comentarios,
    CAST(NULL AS VARCHAR) AS narrativa
FROM gold.v_sentimiento_temporal AS s
JOIN gold.v_monitor_cuenta_map AS m
    ON m.plataforma = s.plataforma
   AND m.cuenta_slug = s.cuenta_slug
WHERE s.dia IS NOT NULL
GROUP BY m.persona_id, m.nombre_canonico, s.plataforma, s.dia, s.posicion, s.sentimiento

UNION ALL

-- TW hater narrativa temporal (as hostile signal)
SELECT
    m.persona_id,
    m.nombre_canonico,
    'twitter'::VARCHAR AS plataforma,
    t.dia,
    'derecha_o_troll'::VARCHAR AS posicion,
    'negativo'::VARCHAR AS sentimiento,
    SUM(t.n_replies) AS comentarios,
    t.narrativa_cluster AS narrativa
FROM gold.v_tk_hater_narrativa_temporal AS t
JOIN (
    SELECT DISTINCT persona_id, nombre_canonico
    FROM gold.v_monitor_cuenta_map
    WHERE plataforma = 'twitter'
      AND LOWER(handle) IN (
          SELECT DISTINCT LOWER(username) FROM silver.tk_tw_tweet WHERE username IS NOT NULL
      )
) AS m ON TRUE
WHERE t.dia IS NOT NULL
GROUP BY m.persona_id, m.nombre_canonico, t.dia, t.narrativa_cluster

UNION ALL

-- TW apoyo narrativa temporal (as support signal)
SELECT
    m.persona_id,
    m.nombre_canonico,
    'twitter'::VARCHAR AS plataforma,
    t.dia,
    'apoyo_izquierda'::VARCHAR AS posicion,
    'positivo'::VARCHAR AS sentimiento,
    SUM(t.n_replies) AS comentarios,
    t.narrativa_cluster AS narrativa
FROM gold.v_tk_apoyo_narrativa_temporal AS t
JOIN (
    SELECT DISTINCT persona_id, nombre_canonico
    FROM gold.v_monitor_cuenta_map
    WHERE plataforma = 'twitter'
      AND LOWER(handle) IN (
          SELECT DISTINCT LOWER(username) FROM silver.tk_tw_tweet WHERE username IS NOT NULL
      )
) AS m ON TRUE
WHERE t.dia IS NOT NULL
GROUP BY m.persona_id, m.nombre_canonico, t.dia, t.narrativa_cluster;

-- ---------------------------------------------------------------------------
-- Engagement temporal agregado (comparativa)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_monitor_temporal_engagement AS
SELECT
    persona_id,
    nombre_canonico,
    plataforma,
    dia,
    SUM(posts) AS posts,
    SUM(reacciones) AS reacciones,
    SUM(comentarios) AS comentarios,
    SUM(engagement_por_post * posts) / NULLIF(SUM(posts), 0) AS engagement_por_post
FROM gold.v_monitor_engagement
GROUP BY persona_id, nombre_canonico, plataforma, dia;

-- ---------------------------------------------------------------------------
-- Grafos: comportamiento (FB trolls) mapeado a persona
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_monitor_grafo_comportamiento_vertices AS
SELECT
    v.vertex_id,
    v.label,
    v.tipo,
    v.plataforma,
    v.peso_actividad,
    m.persona_id,
    m.nombre_canonico
FROM gold.grafo_vertices_trolls AS v
LEFT JOIN gold.v_monitor_cuenta_map AS m
    ON m.plataforma = COALESCE(v.plataforma, 'facebook')
   AND (
        v.tipo = 'cuenta_objetivo'
        AND (
            v.vertex_id = 'cuenta:' || m.cuenta_slug
            OR v.label = m.nombre_canonico
            OR LOWER(v.label) = LOWER(m.handle)
            OR v.vertex_id LIKE '%' || m.cuenta_slug || '%'
        )
    );

CREATE OR REPLACE VIEW gold.v_monitor_grafo_comportamiento_edges AS
SELECT
    e.source_id,
    e.target_id,
    e.edge_type,
    e.peso_total,
    e.eventos,
    e.metadata_ejemplo,
    'comportamiento'::VARCHAR AS grafo_tipo
FROM gold.grafo_edges_agg_trolls AS e;

-- ---------------------------------------------------------------------------
-- Grafos: clusters de narrativa (FB)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_monitor_grafo_narrativa_vertices AS
SELECT
    v.vertex_id,
    v.label,
    v.tipo,
    v.plataforma,
    CAST(NULL AS DOUBLE) AS peso_actividad
FROM gold.grafo_vertices_narrativa AS v;

CREATE OR REPLACE VIEW gold.v_monitor_grafo_narrativa_edges AS
SELECT
    e.source_id,
    e.target_id,
    e.edge_type,
    e.peso_total,
    e.contenidos_distintos AS eventos,
    e.cuenta_slug,
    'narrativa'::VARCHAR AS grafo_tipo
FROM gold.grafo_edges_agg_narrativa AS e;

-- ---------------------------------------------------------------------------
-- Grafos: cuentas coordinadas (TW co-followers / bridges)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_monitor_grafo_coordinacion_edges AS
SELECT
    CAST(hater_a_id AS VARCHAR) AS source_id,
    CAST(hater_b_id AS VARCHAR) AS target_id,
    'co_followers'::VARCHAR AS edge_type,
    CAST(shared_followers AS DOUBLE) AS peso_total,
    'coordinacion'::VARCHAR AS grafo_tipo
FROM gold.tk_hater_grafo_co_followers

UNION ALL

SELECT
    CAST(follower_id AS VARCHAR) AS source_id,
    CAST(hater_username AS VARCHAR) AS target_id,
    'bridge_follower'::VARCHAR AS edge_type,
    CAST(haters_followed AS DOUBLE) AS peso_total,
    'coordinacion'::VARCHAR AS grafo_tipo
FROM gold.tk_hater_grafo_bridge_followers AS b,
     UNNEST(b.hater_usernames) AS u(hater_username)

UNION ALL

SELECT
    CAST(source_id AS VARCHAR),
    CAST(target_id AS VARCHAR),
    edge_type,
    CAST(peso_total AS DOUBLE),
    'coordinacion'::VARCHAR AS grafo_tipo
FROM gold.grafo_edges_agg_trolls
WHERE edge_type = 'co_rafaga';

CREATE OR REPLACE VIEW gold.v_monitor_grafo_coordinacion_vertices AS
SELECT DISTINCT
    v.vertex_id,
    COALESCE(v.label, v.display_name, v.vertex_id) AS label,
    COALESCE(v.entity_type, 'neighbor') AS tipo,
    'twitter'::VARCHAR AS plataforma,
    COALESCE(v.followers_count, 0) AS peso_actividad
FROM gold.tk_hater_grafo_vertices AS v

UNION ALL

SELECT DISTINCT
    v.vertex_id,
    v.label,
    v.tipo,
    COALESCE(v.plataforma, 'facebook'),
    COALESCE(v.peso_actividad, 0)
FROM gold.grafo_vertices_trolls AS v
WHERE v.tipo IN ('autor', 'cuenta_objetivo');

-- ---------------------------------------------------------------------------
-- KPIs globales del monitor
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_monitor_kpis AS
SELECT
    (SELECT COUNT(*) FROM silver.identidad WHERE es_objetivo) AS personas_objetivo,
    (SELECT COUNT(*) FROM silver.identidad_cuenta) AS cuentas_vinculadas,
    (SELECT COUNT(DISTINCT plataforma) FROM silver.identidad_cuenta) AS plataformas,
    (SELECT COUNT(*) FROM gold.v_monitor_reacciones) AS posts_con_metricas,
    (SELECT COUNT(*) FROM gold.v_monitor_audiencia) AS eventos_audiencia,
    (SELECT COUNT(*) FROM gold.v_monitor_audiencia WHERE audiencia_clase = 'hater') AS eventos_hater,
    (SELECT COUNT(DISTINCT autor_key) FROM gold.v_monitor_audiencia WHERE es_bot_heuristico) AS actores_bot_heuristico;
