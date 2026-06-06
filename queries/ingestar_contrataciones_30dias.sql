
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE OR REPLACE TABLE bronze.boletin_contrataciones_adjudicaciones AS
WITH all_avisos AS (

            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-04-27.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-04-28.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-04-29.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-04-30.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-05-04.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-05-05.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-05-06.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-05-08.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-05-11.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-05-12.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-05-13.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-05-14.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-05-15.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-05-18.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-05-19.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-05-20.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-05-21.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-05-22.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-05-26.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-05-27.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-05-28.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-05-29.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-06-01.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-06-02.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-06-03.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-06-04.json') j,
            UNNEST(j.avisos) AS t(a)
         UNION ALL 
            SELECT 
                j.fecha AS boletin_fecha,
                j.scraped_at AS boletin_scraped_at,
                j.seccion,
                j.subseccion,
                j.total AS boletin_total,
                a AS aviso_struct
            FROM read_json_auto('data/landing/boletin_oficial/contrataciones/2026-06-05.json') j,
            UNNEST(j.avisos) AS t(a)
        
)
SELECT 
    boletin_fecha,
    boletin_scraped_at,
    seccion,
    subseccion,
    boletin_total,
    aviso_struct.id,
    aviso_struct.url,
    aviso_struct.organismo,
    aviso_struct.tipo_licitacion,
    aviso_struct.titulo,
    aviso_struct.contenido,
    aviso_struct.pdf_page,
    aviso_struct.pdf_path,
    aviso_struct.fecha_publicacion,
    aviso_struct.scraped_at AS aviso_scraped_at
FROM all_avisos;

SELECT 'Ingesta completa' AS status, COUNT(*) AS total, COUNT(DISTINCT boletin_fecha) AS dias 
FROM bronze.boletin_contrataciones_adjudicaciones;
