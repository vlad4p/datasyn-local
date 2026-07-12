-- Curated identity dimension: persona ↔ platform accounts + OSINT fields
-- Seed: config/identidades.seed.csv + config/identidad_cuentas.seed.csv
-- Uso:
--   uv run python scripts/python/db.py mcp-stop
--   uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/monitor/ingest_identidades.sql

CREATE SCHEMA IF NOT EXISTS silver;

-- ---------------------------------------------------------------------------
-- silver.identidad — canonical person / org / media dimension
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE silver.identidad AS
SELECT
    persona_id,
    nombre_canonico,
    CASE
        WHEN alias IS NULL OR TRIM(alias) = '' THEN CAST([] AS VARCHAR[])
        ELSE list_transform(string_split(alias, '|'), x -> TRIM(x))
    END AS alias,
    tipo,
    rol,
    partido,
    CAST(es_objetivo AS BOOLEAN) AS es_objetivo,
    NULLIF(TRIM(sitio_web), '') AS sitio_web,
    NULLIF(TRIM(wikidata_id), '') AS wikidata_id,
    NULLIF(TRIM(genero), '') AS genero,
    NULLIF(TRIM(provincia), '') AS provincia,
    CASE
        WHEN fuentes_osint IS NULL OR TRIM(fuentes_osint) = '' THEN CAST([] AS VARCHAR[])
        ELSE list_transform(string_split(fuentes_osint, '|'), x -> TRIM(x))
    END AS fuentes_osint,
    NULLIF(TRIM(notas), '') AS notas,
    CURRENT_TIMESTAMP AS built_at
FROM read_csv_auto(
    'config/identidades.seed.csv',
    header = true,
    all_varchar = true
);

-- ---------------------------------------------------------------------------
-- silver.identidad_cuenta — bridge persona → platform account
-- Resolves platform_user_id against live silver catalogs when seed is empty.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE silver.identidad_cuenta AS
WITH seed AS (
    SELECT
        persona_id,
        LOWER(TRIM(plataforma)) AS plataforma,
        NULLIF(TRIM(platform_user_id), '') AS platform_user_id_seed,
        NULLIF(TRIM(handle), '') AS handle,
        NULLIF(TRIM(url), '') AS url,
        CAST(es_oficial AS BOOLEAN) AS es_oficial,
        NULLIF(TRIM(fuente), '') AS fuente
    FROM read_csv_auto(
        'config/identidad_cuentas.seed.csv',
        header = true,
        all_varchar = true
    )
),
fb_resolved AS (
    SELECT
        s.persona_id,
        s.plataforma,
        COALESCE(s.platform_user_id_seed, CAST(f.fanpage_id AS VARCHAR)) AS platform_user_id,
        COALESCE(s.handle, f.descripcion) AS handle,
        COALESCE(
            s.url,
            CASE WHEN f.fanpage_id IS NOT NULL
                THEN 'https://www.facebook.com/' || COALESCE(f.descripcion, CAST(f.fanpage_id AS VARCHAR))
            END
        ) AS url,
        s.es_oficial,
        s.fuente,
        f.descripcion AS fb_fanpage,
        f.instagram_id AS fb_instagram_id
    FROM seed AS s
    LEFT JOIN silver.fb_fanpage AS f
        ON s.plataforma = 'facebook'
       AND (
            CAST(f.fanpage_id AS VARCHAR) = s.platform_user_id_seed
            OR LOWER(f.descripcion) = LOWER(s.handle)
        )
    WHERE s.plataforma = 'facebook'
),
tw_resolved AS (
    SELECT
        s.persona_id,
        s.plataforma,
        COALESCE(s.platform_user_id_seed, p.user_id) AS platform_user_id,
        COALESCE(s.handle, p.username) AS handle,
        COALESCE(
            s.url,
            CASE WHEN COALESCE(s.handle, p.username) IS NOT NULL
                THEN 'https://x.com/' || COALESCE(s.handle, p.username)
            END
        ) AS url,
        s.es_oficial,
        s.fuente,
        CAST(NULL AS VARCHAR) AS fb_fanpage,
        CAST(NULL AS BIGINT) AS fb_instagram_id
    FROM seed AS s
    LEFT JOIN silver.tk_tw_profile AS p
        ON s.plataforma = 'twitter'
       AND (
            p.user_id = s.platform_user_id_seed
            OR LOWER(p.username) = LOWER(s.handle)
        )
    WHERE s.plataforma = 'twitter'
),
other_platforms AS (
    SELECT
        s.persona_id,
        s.plataforma,
        s.platform_user_id_seed AS platform_user_id,
        s.handle,
        s.url,
        s.es_oficial,
        s.fuente,
        CAST(NULL AS VARCHAR) AS fb_fanpage,
        CAST(NULL AS BIGINT) AS fb_instagram_id
    FROM seed AS s
    WHERE s.plataforma NOT IN ('facebook', 'twitter')
)
SELECT
    persona_id,
    plataforma,
    platform_user_id,
    handle,
    url,
    es_oficial,
    fuente,
    fb_fanpage,
    fb_instagram_id,
    CURRENT_TIMESTAMP AS built_at
FROM fb_resolved
UNION ALL
SELECT
    persona_id,
    plataforma,
    platform_user_id,
    handle,
    url,
    es_oficial,
    fuente,
    fb_fanpage,
    fb_instagram_id,
    CURRENT_TIMESTAMP AS built_at
FROM tw_resolved
UNION ALL
SELECT
    persona_id,
    plataforma,
    platform_user_id,
    handle,
    url,
    es_oficial,
    fuente,
    fb_fanpage,
    fb_instagram_id,
    CURRENT_TIMESTAMP AS built_at
FROM other_platforms;
