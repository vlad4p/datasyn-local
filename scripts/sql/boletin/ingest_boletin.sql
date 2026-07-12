-- Ingest diario Boletín Oficial → bronze + silver
-- Acumula datos día a día (no reemplaza).
-- Uso: sed "s/{FECHA}/20260611/g" scripts/sql/boletin/ingest_boletin.sql > /tmp/q.sql && uv run python scripts/python/db.py run-sql --file /tmp/q.sql

CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;

-- Bronce
CREATE TABLE IF NOT EXISTS bronze.boletin_avisos (
    id_aviso VARCHAR,
    empresa VARCHAR,
    fecha_publicacion VARCHAR,
    url_detalle VARCHAR,
    rubro VARCHAR,
    fecha_scraping VARCHAR,
    texto_completo VARCHAR,
    texto_pdf VARCHAR,
    escritura VARCHAR,
    fecha_constitucion VARCHAR,
    domicilio_social VARCHAR,
    objeto_social VARCHAR,
    plazo VARCHAR,
    capital_social DOUBLE,
    valor_nominal_accion DOUBLE,
    total_acciones BIGINT,
    administracion VARCHAR,
    presidente VARCHAR,
    presidente_suplente VARCHAR,
    cierre_ejercicio VARCHAR,
    profesional_autorizante VARCHAR
);

INSERT INTO bronze.boletin_avisos BY NAME
SELECT
    unnest.id_aviso,
    unnest.empresa,
    unnest.fecha_publicacion,
    unnest.url_detalle,
    unnest.rubro,
    unnest.fecha_scraping,
    unnest.texto_completo,
    unnest.texto_pdf,
    unnest.escritura,
    unnest.fecha_constitucion,
    unnest.domicilio_social,
    unnest.objeto_social,
    unnest.plazo,
    unnest.capital_social,
    unnest.valor_nominal_accion,
    unnest.total_acciones,
    unnest.administracion,
    unnest.presidente,
    unnest.presidente_suplente,
    unnest.cierre_ejercicio,
    unnest.profesional_autorizante
FROM read_json_auto('data/landing/boletin_sa_{FECHA}.json') AS j,
LATERAL UNNEST(j.avisos);

-- Silver entidades
CREATE TABLE IF NOT EXISTS silver.entidades AS
SELECT
    unnest.id_aviso,
    unnest.empresa,
    unnest.fecha_publicacion,
    unnest.url_detalle,
    unnest.escritura,
    unnest.fecha_constitucion,
    unnest.domicilio_social,
    unnest.objeto_social,
    unnest.plazo,
    unnest.capital_social,
    unnest.valor_nominal_accion,
    unnest.total_acciones,
    unnest.administracion,
    unnest.presidente,
    unnest.presidente_suplente,
    unnest.cierre_ejercicio,
    unnest.profesional_autorizante,
    unnest.fecha_scraping
FROM read_json_auto('data/landing/boletin_sa_{FECHA}.json') AS j,
LATERAL UNNEST(j.avisos)
WHERE 1=0;

INSERT INTO silver.entidades BY NAME
SELECT
    unnest.id_aviso,
    unnest.empresa,
    unnest.fecha_publicacion,
    unnest.url_detalle,
    unnest.escritura,
    unnest.fecha_constitucion,
    unnest.domicilio_social,
    unnest.objeto_social,
    unnest.plazo,
    unnest.capital_social,
    unnest.valor_nominal_accion,
    unnest.total_acciones,
    unnest.administracion,
    unnest.presidente,
    unnest.presidente_suplente,
    unnest.cierre_ejercicio,
    unnest.profesional_autorizante,
    unnest.fecha_scraping
FROM read_json_auto('data/landing/boletin_sa_{FECHA}.json') AS j,
LATERAL UNNEST(j.avisos);

-- Silver personas (accionistas)
CREATE TABLE IF NOT EXISTS silver.personas (
    id_aviso VARCHAR,
    empresa_relacionada VARCHAR,
    nombre VARCHAR,
    fecha_nacimiento VARCHAR,
    dni VARCHAR,
    cuit VARCHAR,
    domicilio VARCHAR,
    nacionalidad VARCHAR,
    estado_civil VARCHAR,
    profesion VARCHAR,
    acciones_suscritas BIGINT,
    capital_social DOUBLE
);

INSERT INTO silver.personas BY NAME
WITH avisos_flat AS (
    SELECT unnest AS a
    FROM read_json_auto('data/landing/boletin_sa_{FECHA}.json') AS j,
    LATERAL UNNEST(j.avisos)
)
SELECT
    a.id_aviso,
    a.empresa AS empresa_relacionada,
    unnest.nombre,
    unnest.fecha_nacimiento,
    unnest.dni,
    unnest.cuit,
    unnest.domicilio,
    unnest.nacionalidad,
    unnest.estado_civil,
    unnest.profesion,
    unnest.acciones_suscritas,
    a.capital_social
FROM avisos_flat,
LATERAL UNNEST(a.accionistas)
WHERE unnest.nombre IS NOT NULL AND unnest.nombre != '';
