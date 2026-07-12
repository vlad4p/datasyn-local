-- Contexto La Nación (política/sociedad) × Twitter Myriam Bregman
-- Requires: silver.lanacion_*, silver.tk_tw_*, gold.v_monitor_cuenta_map
-- Run: db.py mcp-stop && db.py run-sql --ingest --file scripts/sql/ingest_contexto_ln_tw.sql

CREATE SCHEMA IF NOT EXISTS gold;

-- ---------------------------------------------------------------------------
-- A. Hechos diarios política / sociedad (La Nación)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_contexto_ln_hechos_diario AS
SELECT
    fecha,
    count(*)::BIGINT AS n_hechos,
    count(*) FILTER (WHERE seccion = 'politica')::BIGINT AS n_politica,
    count(*) FILTER (WHERE seccion = 'seguridad')::BIGINT AS n_seguridad,
    count(*) FILTER (WHERE seccion = 'editoriales')::BIGINT AS n_editoriales,
    count(*) FILTER (WHERE seccion = 'opinion')::BIGINT AS n_opinion,
    round(avg(palabras), 1) AS palabras_prom
FROM silver.lanacion_articulos
WHERE fecha IS NOT NULL
  AND seccion IN ('politica', 'seguridad', 'editoriales', 'opinion')
GROUP BY fecha;

-- ---------------------------------------------------------------------------
-- B. Serie diaria LN × TW (persona myriambregman)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_contexto_ln_tw_diario AS
WITH persona AS (
    SELECT DISTINCT
        persona_id,
        nombre_canonico,
        lower(handle) AS handle
    FROM gold.v_monitor_cuenta_map
    WHERE persona_id = 'myriambregman'
      AND plataforma = 'twitter'
      AND handle IS NOT NULL
),
author AS (
    SELECT
        p.persona_id,
        p.nombre_canonico,
        p.handle,
        u.user_id AS author_id
    FROM persona AS p
    JOIN silver.tk_tw_user AS u
        ON lower(u.username) = p.handle
),
tweets_dia AS (
    SELECT
        a.persona_id,
        a.nombre_canonico,
        CAST(t.created_at_ts AS DATE) AS fecha,
        count(*)::BIGINT AS n_tweets,
        coalesce(sum(t.like_count), 0)::BIGINT AS likes,
        coalesce(sum(t.reply_count), 0)::BIGINT AS reply_count_posts,
        coalesce(sum(t.retweet_count), 0)::BIGINT AS retweets,
        coalesce(sum(t.view_count), 0)::BIGINT AS views
    FROM author AS a
    JOIN silver.tk_tw_tweet AS t
        ON t.author_id = a.author_id
        OR lower(t.username) = a.handle
    WHERE t.created_at_ts IS NOT NULL
    GROUP BY a.persona_id, a.nombre_canonico, CAST(t.created_at_ts AS DATE)
),
replies_dia AS (
    SELECT
        a.persona_id,
        a.nombre_canonico,
        CAST(COALESCE(r.created_at_ts, try_cast(r.created_at AS TIMESTAMP)) AS DATE) AS fecha,
        count(*)::BIGINT AS n_replies,
        count(*) FILTER (WHERE c.criterio_label = 'derecha_o_troll')::BIGINT AS n_hostil,
        count(*) FILTER (WHERE c.criterio_label = 'apoyo_izquierda')::BIGINT AS n_apoyo,
        count(*) FILTER (
            WHERE c.criterio_label IN ('neutral', 'ambiguo')
               OR c.criterio_label IS NULL
        )::BIGINT AS n_neutral
    FROM author AS a
    JOIN silver.tk_tw_tweet AS t
        ON t.author_id = a.author_id
        OR lower(t.username) = a.handle
    JOIN silver.tk_tw_reply AS r
        ON r.parent_tweet_id = t.tweet_id
    LEFT JOIN silver.tk_tw_reply_classification AS c
        ON c.reply_id = r.reply_id
    WHERE COALESCE(r.created_at_ts, try_cast(r.created_at AS TIMESTAMP)) IS NOT NULL
    GROUP BY 1, 2, 3
),
bounds AS (
    SELECT min(fecha) AS d0, max(fecha) AS d1
    FROM (
        SELECT fecha FROM gold.v_contexto_ln_hechos_diario
        UNION ALL
        SELECT fecha FROM tweets_dia
        UNION ALL
        SELECT fecha FROM replies_dia
    )
),
calendario AS (
    SELECT
        CAST(gs AS DATE) AS fecha,
        a.persona_id,
        a.nombre_canonico
    FROM bounds AS b
    CROSS JOIN author AS a
    CROSS JOIN generate_series(b.d0, b.d1, INTERVAL 1 DAY) AS t(gs)
    WHERE b.d0 IS NOT NULL AND b.d1 IS NOT NULL
)
SELECT
    cal.persona_id,
    cal.nombre_canonico,
    cal.fecha,
    coalesce(ln.n_hechos, 0)::BIGINT AS n_hechos,
    coalesce(ln.n_politica, 0)::BIGINT AS n_politica,
    coalesce(ln.n_seguridad, 0)::BIGINT AS n_seguridad,
    coalesce(ln.n_editoriales, 0)::BIGINT AS n_editoriales,
    coalesce(ln.n_opinion, 0)::BIGINT AS n_opinion,
    ln.palabras_prom,
    coalesce(tw.n_tweets, 0)::BIGINT AS n_tweets,
    coalesce(tw.likes, 0)::BIGINT AS likes,
    coalesce(tw.reply_count_posts, 0)::BIGINT AS reply_count_posts,
    coalesce(tw.retweets, 0)::BIGINT AS retweets,
    coalesce(tw.views, 0)::BIGINT AS views,
    coalesce(rp.n_replies, 0)::BIGINT AS n_replies,
    coalesce(rp.n_hostil, 0)::BIGINT AS n_hostil,
    coalesce(rp.n_apoyo, 0)::BIGINT AS n_apoyo,
    coalesce(rp.n_neutral, 0)::BIGINT AS n_neutral
FROM calendario AS cal
LEFT JOIN gold.v_contexto_ln_hechos_diario AS ln
    ON ln.fecha = cal.fecha
LEFT JOIN tweets_dia AS tw
    ON tw.fecha = cal.fecha
   AND tw.persona_id = cal.persona_id
LEFT JOIN replies_dia AS rp
    ON rp.fecha = cal.fecha
   AND rp.persona_id = cal.persona_id
ORDER BY cal.fecha;

-- ---------------------------------------------------------------------------
-- C. Top titulares LN del día (pol/soc)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_contexto_ln_titulares_dia AS
SELECT
    fecha,
    rank_dia,
    titulo,
    seccion,
    tipo,
    autor,
    palabras,
    url
FROM (
    SELECT
        fecha,
        titulo,
        seccion,
        tipo,
        autor,
        palabras,
        url,
        ROW_NUMBER() OVER (
            PARTITION BY fecha
            ORDER BY palabras DESC NULLS LAST, titulo
        ) AS rank_dia
    FROM silver.lanacion_articulos
    WHERE fecha IS NOT NULL
      AND seccion IN ('politica', 'seguridad', 'editoriales', 'opinion')
)
WHERE rank_dia <= 5
ORDER BY fecha DESC, rank_dia;

-- ---------------------------------------------------------------------------
-- D. Días pico (z-score hechos + hostil/replies)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_contexto_ln_tw_picos AS
WITH base AS (
    SELECT *
    FROM gold.v_contexto_ln_tw_diario
    WHERE n_hechos > 0 OR n_tweets > 0 OR n_replies > 0
),
stats AS (
    SELECT
        avg(n_hechos)::DOUBLE AS mu_h,
        stddev_samp(n_hechos)::DOUBLE AS sd_h,
        avg(n_hostil)::DOUBLE AS mu_x,
        stddev_samp(n_hostil)::DOUBLE AS sd_x,
        avg(n_replies)::DOUBLE AS mu_r,
        stddev_samp(n_replies)::DOUBLE AS sd_r
    FROM base
),
scored AS (
    SELECT
        b.*,
        CASE
            WHEN s.sd_h IS NULL OR s.sd_h = 0 THEN 0
            ELSE (b.n_hechos - s.mu_h) / s.sd_h
        END AS z_hechos,
        CASE
            WHEN b.n_hostil > 0 AND s.sd_x IS NOT NULL AND s.sd_x > 0
                THEN (b.n_hostil - s.mu_x) / s.sd_x
            WHEN s.sd_r IS NULL OR s.sd_r = 0 THEN 0
            ELSE (b.n_replies - s.mu_r) / s.sd_r
        END AS z_tw,
        (CASE
            WHEN s.sd_h IS NULL OR s.sd_h = 0 THEN 0
            ELSE (b.n_hechos - s.mu_h) / s.sd_h
        END)
        + (CASE
            WHEN b.n_hostil > 0 AND s.sd_x IS NOT NULL AND s.sd_x > 0
                THEN (b.n_hostil - s.mu_x) / s.sd_x
            WHEN s.sd_r IS NULL OR s.sd_r = 0 THEN 0
            ELSE (b.n_replies - s.mu_r) / s.sd_r
        END) AS score
    FROM base AS b
    CROSS JOIN stats AS s
),
ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (ORDER BY score DESC, fecha DESC) AS rank_pico,
        (z_hechos >= 1.0) AS pico_hechos,
        (z_tw >= 1.0) AS pico_hostil,
        (z_hechos >= 1.0 AND z_tw >= 1.0) AS pico_ambos
    FROM scored
)
SELECT
    persona_id,
    nombre_canonico,
    fecha,
    n_hechos,
    n_politica,
    n_seguridad,
    n_editoriales,
    n_opinion,
    n_tweets,
    n_replies,
    n_hostil,
    n_apoyo,
    round(z_hechos, 3) AS z_hechos,
    round(z_tw, 3) AS z_tw,
    round(score, 3) AS score,
    pico_hechos,
    pico_hostil,
    pico_ambos,
    rank_pico
FROM ranked
WHERE rank_pico <= 20
ORDER BY rank_pico;
