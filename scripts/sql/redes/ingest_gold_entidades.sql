-- Gold views: inferencia de persona detrás de cada cuenta y agrupación multicuenta.
-- Fuente: silver.network_profile (+ gold.v_cuentas_trackeadas para anclas PTS).
-- Prereq: ingest_network_profile.sql
-- Uso: uv run python scripts/python/db.py mcp-stop
--      uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/redes/ingest_gold_entidades.sql

CREATE SCHEMA IF NOT EXISTS gold;

-- ---------------------------------------------------------------------------
-- Helpers: limpieza de nombres y detección organización vs persona
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold._entidades_nombre_base AS
SELECT
    np.profile_id,
    np.canonical_key,
    np.display_name,
    np.twitter_display_name,
    np.twitter_username,
    np.twitter_bio,
    np.facebook_page_name,
    np.facebook_user_name,
    np.instagram_id,
    np.networks_found,
    np.entity_roles,
    np.is_pts,
    np.is_diputado,
    np.is_tracked,
    np.comments_count,
    np.tweets_count,
    np.replies_count,
    np.comentarios_clasificados,
    -- Fanpage PTS: MyriamBregman.PTS -> Myriam Bregman
    CASE
        WHEN np.facebook_page_name IS NOT NULL
             AND regexp_matches(np.facebook_page_name, '\.PTS$', 'i')
            THEN TRIM(
                REGEXP_REPLACE(
                    REGEXP_REPLACE(np.facebook_page_name, '\.PTS$', '', 'i'),
                    '([a-z])([A-Z])',
                    '\1 \2',
                    'g'
                )
            )
    END AS nombre_desde_fanpage_pts,
    -- Handle alfanumérico para cruce FB fanpage <-> TW username
    NULLIF(
        REGEXP_REPLACE(LOWER(COALESCE(np.facebook_page_name, '')), '[^a-z0-9]', '', 'g'),
        ''
    ) AS fb_page_handle_norm,
    NULLIF(
        REGEXP_REPLACE(LOWER(COALESCE(np.twitter_username, '')), '[^a-z0-9]', '', 'g'),
        ''
    ) AS tw_handle_norm,
    -- Slug manual de cuentas trackeadas
    ct.cuenta_trackeada_slug,
    ct.cuenta_trackeada_nombre
FROM silver.network_profile AS np
LEFT JOIN (
    SELECT
        np2.profile_id,
        MAX(ct.cuenta_slug) AS cuenta_trackeada_slug,
        MAX(ct.cuenta_nombre) AS cuenta_trackeada_nombre
    FROM silver.network_profile AS np2
    INNER JOIN gold.v_cuentas_trackeadas AS ct
        ON (
            ct.plataforma = 'twitter'
            AND np2.twitter_username IS NOT NULL
            AND LOWER(ct.tw_username) = np2.twitter_username
        )
        OR (
            ct.plataforma = 'facebook'
            AND np2.facebook_page_name IS NOT NULL
            AND ct.fb_fanpage = np2.facebook_page_name
        )
    GROUP BY np2.profile_id
) AS ct
    ON np.profile_id = ct.profile_id;

-- ---------------------------------------------------------------------------
-- gold.v_entidades — una fila por perfil con nombre inferido
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_entidades AS
WITH scored AS (
    SELECT
        b.*,
        CASE
            WHEN b.cuenta_trackeada_nombre IS NOT NULL
                THEN b.cuenta_trackeada_nombre
            WHEN b.twitter_display_name IS NOT NULL
                 AND LENGTH(TRIM(b.twitter_display_name)) >= 3
                 AND LEFT(TRIM(b.twitter_display_name), 1) NOT IN ('#', '@', '!')
                 AND TRIM(b.twitter_display_name) NOT LIKE '%http%'
                THEN TRIM(b.twitter_display_name)
            WHEN b.nombre_desde_fanpage_pts IS NOT NULL
                THEN b.nombre_desde_fanpage_pts
            WHEN b.facebook_page_name IS NOT NULL
                 AND NOT regexp_matches(b.facebook_page_name, '\.PTS$', 'i')
                THEN TRIM(
                    REGEXP_REPLACE(
                        b.facebook_page_name,
                        '([a-z])([A-Z])',
                        '\1 \2',
                        'g'
                    )
                )
            WHEN NULLIF(TRIM(b.facebook_user_name), '') IS NOT NULL
                THEN TRIM(b.facebook_user_name)
            WHEN NULLIF(TRIM(b.display_name), '') IS NOT NULL
                THEN TRIM(b.display_name)
            WHEN b.twitter_username IS NOT NULL
                THEN b.twitter_username
            ELSE b.canonical_key
        END AS nombre_inferido,
        CASE
            WHEN b.cuenta_trackeada_nombre IS NOT NULL
                THEN 'cuenta_trackeada'
            WHEN b.twitter_display_name IS NOT NULL
                 AND LENGTH(TRIM(b.twitter_display_name)) >= 3
                 AND LEFT(TRIM(b.twitter_display_name), 1) NOT IN ('#', '@', '!')
                 AND TRIM(b.twitter_display_name) NOT LIKE '%http%'
                THEN 'twitter_display_name'
            WHEN b.nombre_desde_fanpage_pts IS NOT NULL
                THEN 'fanpage_pts'
            WHEN b.facebook_page_name IS NOT NULL
                 AND NOT regexp_matches(b.facebook_page_name, '\.PTS$', 'i')
                THEN 'facebook_page_name'
            WHEN NULLIF(TRIM(b.facebook_user_name), '') IS NOT NULL
                THEN 'facebook_user_name'
            WHEN NULLIF(TRIM(b.display_name), '') IS NOT NULL
                THEN 'display_name'
            WHEN b.twitter_username IS NOT NULL
                THEN 'twitter_username'
            ELSE 'canonical_key'
        END AS nombre_inferido_fuente,
        (
            'fanpage' = ANY (b.entity_roles)
            OR b.is_pts
            OR LOWER(COALESCE(b.display_name, '')) LIKE '%diario%'
            OR LOWER(COALESCE(b.display_name, '')) LIKE '%frente de izquierda%'
            OR LOWER(COALESCE(b.twitter_display_name, '')) LIKE '%pts%'
            OR LOWER(COALESCE(b.twitter_bio, '')) LIKE '%oficial%'
            OR LOWER(COALESCE(b.canonical_key, '')) LIKE 'fb_page:%'
        ) AS es_organizacion
    FROM gold._entidades_nombre_base AS b
)
SELECT
    s.profile_id,
    s.canonical_key,
    s.nombre_inferido,
    s.nombre_inferido_fuente,
    LOWER(
        REGEXP_REPLACE(
            REGEXP_REPLACE(TRIM(s.nombre_inferido), '\s+', ' ', 'g'),
            '[^a-z0-9áéíóúñü ]',
            '',
            'g'
        )
    ) AS nombre_normalizado,
    s.es_organizacion,
    CASE
        WHEN 'fanpage' = ANY (s.entity_roles) THEN 'fanpage'
        WHEN 'tracked_account' = ANY (s.entity_roles) THEN 'cuenta_trackeada'
        WHEN 'commenter' = ANY (s.entity_roles) THEN 'comentarista_fb'
        WHEN 'reply_author' = ANY (s.entity_roles) THEN 'autor_reply_tw'
        ELSE 'otro'
    END AS tipo_cuenta,
    s.networks_found AS redes,
    s.twitter_username,
    s.twitter_display_name,
    s.facebook_page_name,
    s.facebook_user_name,
    s.instagram_id,
    s.is_pts,
    s.is_diputado,
    s.is_tracked,
    s.cuenta_trackeada_slug,
    s.comments_count,
    s.tweets_count,
    s.replies_count,
    s.comentarios_clasificados,
    s.fb_page_handle_norm,
    s.tw_handle_norm,
    CASE
        WHEN s.cuenta_trackeada_nombre IS NOT NULL
             OR s.nombre_inferido_fuente IN ('twitter_display_name', 'fanpage_pts', 'cuenta_trackeada')
            THEN 'alta'
        WHEN s.nombre_inferido_fuente IN ('facebook_page_name', 'facebook_user_name', 'display_name')
            THEN 'media'
        ELSE 'baja'
    END AS confianza_nombre,
    len(s.networks_found) > 1 AS multicuenta_mismo_perfil
FROM scored AS s;

-- ---------------------------------------------------------------------------
-- gold.v_entidades_vinculos — pares de perfiles con evidencia de misma persona/org
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_entidades_vinculos AS
WITH perfiles AS (
    SELECT * FROM gold.v_entidades
),
pares AS (
    -- Ya fusionados en network_profile (FB+TW en una fila)
    SELECT
        p.canonical_key AS canonical_key_a,
        p.canonical_key AS canonical_key_b,
        'multired_en_perfil'::VARCHAR AS tipo_vinculo,
        'alta'::VARCHAR AS confianza,
        'Varias redes en canonical_key: ' || array_to_string(p.redes, ', ') AS detalle
    FROM perfiles AS p
    WHERE len(p.redes) > 1

    UNION ALL

    -- Fanpage .PTS cuyo stem coincide con username TW (regla de ingest_network_profile)
    SELECT
        fb.canonical_key,
        tw.canonical_key,
        'fanpage_pts_username',
        'alta',
        'FB ' || fb.facebook_page_name || ' ↔ TW @' || tw.twitter_username
    FROM perfiles AS fb
    INNER JOIN perfiles AS tw
        ON fb.facebook_page_name IS NOT NULL
       AND regexp_matches(fb.facebook_page_name, '\.PTS$', 'i')
       AND LOWER(REGEXP_REPLACE(fb.facebook_page_name, '\.PTS$', '', 'i')) = tw.twitter_username
       AND fb.canonical_key <> tw.canonical_key

    UNION ALL

    -- Fanpage y TW con handle alfanumérico coincidente o sufijo (ej. LaIzquierdaDiario / izquierdadiario)
    SELECT
        fb.canonical_key,
        tw.canonical_key,
        'handle_alphanum',
        'media',
        'Norm alfanum FB=' || fb.fb_page_handle_norm || ' TW=' || tw.tw_handle_norm
    FROM perfiles AS fb
    INNER JOIN perfiles AS tw
        ON fb.fb_page_handle_norm IS NOT NULL
       AND tw.tw_handle_norm IS NOT NULL
       AND fb.canonical_key <> tw.canonical_key
       AND fb.facebook_page_name IS NOT NULL
       AND tw.twitter_username IS NOT NULL
       AND LENGTH(LEAST(fb.fb_page_handle_norm, tw.tw_handle_norm)) >= 6
       AND (
           fb.fb_page_handle_norm = tw.tw_handle_norm
           OR RIGHT(fb.fb_page_handle_norm, LENGTH(tw.tw_handle_norm)) = tw.tw_handle_norm
           OR RIGHT(tw.tw_handle_norm, LENGTH(fb.fb_page_handle_norm)) = fb.fb_page_handle_norm
       )

    UNION ALL

    -- Mismo instagram_id en perfiles distintos
    SELECT
        a.canonical_key,
        b.canonical_key,
        'mismo_instagram_id',
        'alta',
        'instagram_id=' || CAST(a.instagram_id AS VARCHAR)
    FROM perfiles AS a
    INNER JOIN perfiles AS b
        ON a.instagram_id IS NOT NULL
       AND a.instagram_id = b.instagram_id
       AND a.canonical_key < b.canonical_key

    UNION ALL

    -- Mismo slug de cuenta trackeada manual
    SELECT
        a.canonical_key,
        b.canonical_key,
        'cuenta_trackeada_slug',
        'alta',
        'slug=' || a.cuenta_trackeada_slug
    FROM perfiles AS a
    INNER JOIN perfiles AS b
        ON a.cuenta_trackeada_slug IS NOT NULL
       AND a.cuenta_trackeada_slug = b.cuenta_trackeada_slug
       AND a.canonical_key < b.canonical_key

    UNION ALL

    -- Candidato débil: mismo nombre normalizado (solo personas, nombre largo)
    SELECT
        a.canonical_key,
        b.canonical_key,
        'nombre_normalizado_igual',
        'baja',
        'nombre=' || a.nombre_normalizado
    FROM perfiles AS a
    INNER JOIN perfiles AS b
        ON NOT a.es_organizacion
       AND NOT b.es_organizacion
       AND a.nombre_normalizado = b.nombre_normalizado
       AND LENGTH(a.nombre_normalizado) >= 10
       AND a.canonical_key < b.canonical_key
)
SELECT DISTINCT
    canonical_key_a,
    canonical_key_b,
    tipo_vinculo,
    confianza,
    detalle
FROM pares;

-- ---------------------------------------------------------------------------
-- gold.v_entidades_grupos — componentes conectados (vínculos alta + media)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_entidades_grupos AS
WITH RECURSIVE
aristas_fuertes AS (
    SELECT canonical_key_a AS n1, canonical_key_b AS n2
    FROM gold.v_entidades_vinculos
    WHERE confianza IN ('alta', 'media')
      AND canonical_key_a <> canonical_key_b

    UNION

    SELECT canonical_key_b, canonical_key_a
    FROM gold.v_entidades_vinculos
    WHERE confianza IN ('alta', 'media')
      AND canonical_key_a <> canonical_key_b
),
recursivo AS (
    SELECT
        e.canonical_key AS nodo,
        e.canonical_key AS grupo_raiz
    FROM gold.v_entidades AS e

    UNION

    SELECT
        a.n2 AS nodo,
        r.grupo_raiz
    FROM recursivo AS r
    INNER JOIN aristas_fuertes AS a ON r.nodo = a.n1
),
grupos AS (
    SELECT
        nodo,
        MIN(grupo_raiz) AS persona_grupo_id
    FROM recursivo
    GROUP BY nodo
),
miembros AS (
    SELECT
        g.persona_grupo_id,
        e.canonical_key,
        e.nombre_inferido,
        e.nombre_normalizado,
        e.es_organizacion,
        e.redes,
        e.confianza_nombre,
        e.multicuenta_mismo_perfil,
        e.is_tracked,
        e.is_pts
    FROM grupos AS g
    INNER JOIN gold.v_entidades AS e ON g.nodo = e.canonical_key
)
SELECT
    m.persona_grupo_id,
    COUNT(DISTINCT m.canonical_key) AS n_perfiles,
    COUNT(DISTINCT unnest_red) AS n_redes_distintas,
    BOOL_OR(m.multicuenta_mismo_perfil) AS incluye_multired_en_perfil,
    BOOL_OR(m.is_tracked) AS incluye_trackeada,
    BOOL_OR(m.is_pts) AS incluye_pts,
    BOOL_OR(m.es_organizacion) AS es_organizacion,
    MODE(m.nombre_inferido) AS nombre_persona_inferido,
    MODE(m.nombre_normalizado) AS nombre_normalizado,
    LIST(DISTINCT m.canonical_key ORDER BY m.canonical_key) AS canonical_keys,
    LIST(DISTINCT unnest_red ORDER BY unnest_red) AS redes_en_grupo,
    CASE
        WHEN COUNT(DISTINCT m.canonical_key) = 1
             AND BOOL_OR(m.multicuenta_mismo_perfil)
            THEN 'alta'
        WHEN COUNT(DISTINCT m.canonical_key) > 1
            THEN 'media'
        ELSE 'unica'
    END AS confianza_grupo,
    CASE
        WHEN COUNT(DISTINCT m.canonical_key) > 1
            THEN 'varios_perfiles_vinculados'
        WHEN BOOL_OR(m.multicuenta_mismo_perfil)
            THEN 'multired_mismo_perfil'
        ELSE 'cuenta_unica'
    END AS tipo_grupo
FROM miembros AS m
CROSS JOIN UNNEST(m.redes) AS t(unnest_red)
GROUP BY m.persona_grupo_id;

-- ---------------------------------------------------------------------------
-- gold.v_entidades_resumen — perfil + grupo + señales multicuenta
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_entidades_resumen AS
WITH grupo_map AS (
    SELECT
        g.persona_grupo_id,
        unnest_key AS canonical_key
    FROM gold.v_entidades_grupos AS g
    CROSS JOIN UNNEST(g.canonical_keys) AS t(unnest_key)
),
vinculos_agg AS (
    SELECT
        canonical_key_a AS canonical_key,
        COUNT(*) AS n_vinculos_salientes,
        COUNT(*) FILTER (WHERE confianza = 'baja') AS n_vinculos_debiles,
        LIST(DISTINCT tipo_vinculo ORDER BY tipo_vinculo) AS tipos_vinculo
    FROM gold.v_entidades_vinculos
    WHERE canonical_key_a <> canonical_key_b
    GROUP BY canonical_key_a

    UNION ALL

    SELECT
        canonical_key_b,
        COUNT(*),
        COUNT(*) FILTER (WHERE confianza = 'baja'),
        LIST(DISTINCT tipo_vinculo ORDER BY tipo_vinculo)
    FROM gold.v_entidades_vinculos
    WHERE canonical_key_a <> canonical_key_b
    GROUP BY canonical_key_b
),
vinculos_sum AS (
    SELECT
        canonical_key,
        SUM(n_vinculos_salientes) AS n_vinculos,
        SUM(n_vinculos_debiles) AS n_vinculos_debiles,
        LIST(DISTINCT unnest_tipo ORDER BY unnest_tipo) AS tipos_vinculo
    FROM vinculos_agg
    CROSS JOIN UNNEST(tipos_vinculo) AS u(unnest_tipo)
    GROUP BY canonical_key
)
SELECT
    e.*,
    gm.persona_grupo_id,
    g.n_perfiles AS perfiles_en_grupo,
    g.nombre_persona_inferido AS nombre_grupo,
    g.confianza_grupo,
    g.tipo_grupo,
    g.canonical_keys AS perfiles_mismo_grupo,
    COALESCE(v.n_vinculos, 0) AS n_vinculos_con_otros_perfiles,
    COALESCE(v.n_vinculos_debiles, 0) AS n_vinculos_debiles,
    v.tipos_vinculo,
    (
        e.multicuenta_mismo_perfil
        OR COALESCE(g.n_perfiles, 1) > 1
        OR COALESCE(v.n_vinculos, 0) > 0
    ) AS posible_multicuenta,
    CASE
        WHEN e.multicuenta_mismo_perfil
            THEN 'confirmado_multired_en_perfil'
        WHEN COALESCE(g.n_perfiles, 1) > 1
            THEN 'probable_misma_persona_grupo'
        WHEN COALESCE(v.n_vinculos_debiles, 0) > 0
             AND COALESCE(v.n_vinculos, 0) = COALESCE(v.n_vinculos_debiles, 0)
            THEN 'solo_coincidencia_nombre_debil'
        WHEN COALESCE(v.n_vinculos, 0) > 0
            THEN 'vinculo_entre_perfiles'
        ELSE 'sin_evidencia_multicuenta'
    END AS evaluacion_multicuenta
FROM gold.v_entidades AS e
LEFT JOIN grupo_map AS gm ON e.canonical_key = gm.canonical_key
LEFT JOIN gold.v_entidades_grupos AS g ON gm.persona_grupo_id = g.persona_grupo_id
LEFT JOIN vinculos_sum AS v ON e.canonical_key = v.canonical_key;
