-- Silver + gold La Nación from remote Quack bronze.lanacion_*
-- Requires: db.py run-sql --ingest --attach-quack --file this.sql
-- Quack cannot CTAS with multiple .query() scans in one statement
-- (streaming limitation). Stage each remote table locally first, then silver.

CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- ---------------------------------------------------------------------------
-- Stage remote → local bronze (one .query() per statement)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE bronze.lanacion_noticias AS
SELECT *
FROM "datasyn-rlab".query(
    'SELECT tema, titulo, url, cuerpo_md, fecha_publicacion, scraped_at, landing_key
     FROM bronze.lanacion_noticias'
);

CREATE OR REPLACE TABLE bronze.lanacion_opinion_notas AS
SELECT *
FROM "datasyn-rlab".query(
    'SELECT columnista_id, titulo, url, cuerpo_md, fecha_publicacion, scraped_at, landing_key, tema
     FROM bronze.lanacion_opinion_notas'
);

CREATE OR REPLACE TABLE bronze.lanacion_opinion_columnistas AS
SELECT *
FROM "datasyn-rlab".query(
    'SELECT columnista_id, nombre, autor_url, slug, perfil_politico, scraped_at, landing_key
     FROM bronze.lanacion_opinion_columnistas'
);

-- ---------------------------------------------------------------------------
-- silver.lanacion_columnistas
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE silver.lanacion_columnistas AS
SELECT
    columnista_id,
    nombre_clean AS nombre,
    autor_url,
    slug,
    especialidad,
    perfil_politico,
    scraped_at,
    landing_key
FROM (
    SELECT
        columnista_id,
        TRIM(
            regexp_replace(
                COALESCE(nombre, ''),
                '(?i)\\s*:\\s*publicaciones\\s+para\\s+LA\\s+NACION\\s*$',
                ''
            )
        ) AS nombre_clean,
        autor_url,
        slug,
        NULLIF(
            TRIM(
                regexp_extract(
                    COALESCE(perfil_politico, ''),
                    '(?i)Columnista\\s+de\\s+([^.]+)',
                    1
                )
            ),
            ''
        ) AS especialidad,
        perfil_politico,
        scraped_at,
        landing_key
    FROM bronze.lanacion_opinion_columnistas
)
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY columnista_id
    ORDER BY scraped_at DESC NULLS LAST
) = 1;

-- ---------------------------------------------------------------------------
-- silver.lanacion_articulos (noticias + opinión, sin stubs paywall)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE silver.lanacion_articulos AS
WITH noticias AS (
    SELECT
        url,
        'noticia'::VARCHAR AS tipo,
        NULLIF(
            regexp_extract(url, 'lanacion[.]com[.]ar/([^/]+)/', 1),
            ''
        ) AS seccion,
        NULLIF(TRIM(tema), '') AS tema_raw,
        titulo,
        CAST(NULL AS VARCHAR) AS autor,
        CAST(NULL AS BIGINT) AS columnista_id,
        CAST(fecha_publicacion AS DATE) AS fecha,
        fecha_publicacion,
        cuerpo_md,
        CASE
            WHEN TRIM(COALESCE(cuerpo_md, '')) = '' THEN 0
            ELSE len(string_split(TRIM(cuerpo_md), ' '))
        END AS palabras,
        scraped_at,
        landing_key
    FROM bronze.lanacion_noticias
),
opinion AS (
    SELECT
        n.url,
        'opinion'::VARCHAR AS tipo,
        NULLIF(
            regexp_extract(n.url, 'lanacion[.]com[.]ar/([^/]+)/', 1),
            ''
        ) AS seccion,
        NULLIF(TRIM(n.tema), '') AS tema_raw,
        n.titulo,
        c.nombre AS autor,
        n.columnista_id,
        CAST(n.fecha_publicacion AS DATE) AS fecha,
        n.fecha_publicacion,
        n.cuerpo_md,
        CASE
            WHEN TRIM(COALESCE(n.cuerpo_md, '')) = '' THEN 0
            ELSE len(string_split(TRIM(n.cuerpo_md), ' '))
        END AS palabras,
        n.scraped_at,
        n.landing_key
    FROM bronze.lanacion_opinion_notas AS n
    LEFT JOIN silver.lanacion_columnistas AS c
        ON n.columnista_id = c.columnista_id
    WHERE n.titulo NOT ILIKE 'Suscribite a LA NACION%'
),
unidos AS (
    SELECT * FROM noticias
    UNION ALL BY NAME
    SELECT * FROM opinion
)
SELECT
    url,
    tipo,
    COALESCE(seccion, 'sin_seccion') AS seccion,
    tema_raw,
    titulo,
    autor,
    columnista_id,
    fecha,
    fecha_publicacion,
    cuerpo_md,
    palabras,
    scraped_at,
    landing_key
FROM unidos
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY url
    ORDER BY length(COALESCE(cuerpo_md, '')) DESC, scraped_at DESC NULLS LAST
) = 1;

-- ---------------------------------------------------------------------------
-- silver.lanacion_diario (grano día)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TABLE silver.lanacion_diario AS
SELECT
    fecha,
    count(*)::BIGINT AS n_articulos,
    count(*) FILTER (WHERE tipo = 'noticia')::BIGINT AS n_noticias,
    count(*) FILTER (WHERE tipo = 'opinion')::BIGINT AS n_opinion,
    count(DISTINCT seccion)::BIGINT AS n_secciones,
    count(DISTINCT autor) FILTER (WHERE autor IS NOT NULL)::BIGINT AS n_autores,
    coalesce(sum(palabras), 0)::BIGINT AS palabras_total,
    round(avg(palabras), 1) AS palabras_prom,
    min(scraped_at) AS primer_scrape,
    max(scraped_at) AS ultimo_scrape
FROM silver.lanacion_articulos
WHERE fecha IS NOT NULL
GROUP BY fecha
ORDER BY fecha;

-- ---------------------------------------------------------------------------
-- gold.v_lanacion_que_ocurrio — resumen diario + desglose por sección
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_lanacion_que_ocurrio AS
WITH por_seccion AS (
    SELECT
        fecha,
        seccion,
        count(*)::BIGINT AS n
    FROM silver.lanacion_articulos
    WHERE fecha IS NOT NULL
    GROUP BY fecha, seccion
),
sec_agregado AS (
    SELECT
        fecha,
        coalesce(sum(n) FILTER (WHERE seccion = 'opinion'), 0)::BIGINT AS n_opinion_sec,
        coalesce(sum(n) FILTER (WHERE seccion = 'economia'), 0)::BIGINT AS n_economia,
        coalesce(sum(n) FILTER (WHERE seccion = 'politica'), 0)::BIGINT AS n_politica,
        coalesce(sum(n) FILTER (WHERE seccion = 'seguridad'), 0)::BIGINT AS n_seguridad,
        coalesce(sum(n) FILTER (WHERE seccion = 'editoriales'), 0)::BIGINT AS n_editoriales,
        coalesce(sum(n) FILTER (WHERE seccion NOT IN (
            'opinion', 'economia', 'politica', 'seguridad', 'editoriales'
        )), 0)::BIGINT AS n_otras,
        string_agg(seccion, ', ' ORDER BY n DESC, seccion) AS secciones_activas
    FROM por_seccion
    GROUP BY fecha
)
SELECT
    d.fecha,
    d.n_articulos,
    d.n_noticias,
    d.n_opinion,
    d.n_autores AS n_autores_opinion,
    d.n_secciones,
    d.palabras_total,
    d.palabras_prom,
    s.n_opinion_sec,
    s.n_economia,
    s.n_politica,
    s.n_seguridad,
    s.n_editoriales,
    s.n_otras,
    s.secciones_activas
FROM silver.lanacion_diario AS d
LEFT JOIN sec_agregado AS s USING (fecha)
ORDER BY d.fecha;

-- ---------------------------------------------------------------------------
-- gold.v_lanacion_top_dia — top 5 por día (proxy: palabras)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW gold.v_lanacion_top_dia AS
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
)
WHERE rank_dia <= 5
ORDER BY fecha DESC, rank_dia;
