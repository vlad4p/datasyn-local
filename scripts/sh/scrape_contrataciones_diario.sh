#!/bin/sh
# Scraper diario de Contrataciones (Sección Tercera) + ingesta
# Uso: ./scripts/sh/scrape_contrataciones_diario.sh [YYYY-MM-DD]

set -e
FECHA="${1:-$(date +%Y-%m-%d)}"
FECHA_YMD=$(echo "$FECHA" | tr -d '-')

echo "================================================"
echo "📰 Scraper diario — Contrataciones Públicas"
echo "   Fecha: $FECHA"
echo "================================================"

uv run python scripts/python/scrape_contrataciones.py --fecha "$FECHA"

echo ""
echo "📦 Ingestionando a la base de datos..."

SQL=$(cat <<ENDSQL
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE TABLE IF NOT EXISTS bronze.contrataciones (
    id_aviso VARCHAR, organismo VARCHAR, tipo_contratacion VARCHAR,
    fecha_publicacion VARCHAR, url_detalle VARCHAR, rubro VARCHAR,
    fecha_scraping VARCHAR, texto_completo VARCHAR, texto_pdf VARCHAR,
    uoc VARCHAR, ejercicio VARCHAR, clase VARCHAR, modalidad VARCHAR,
    expediente VARCHAR, objeto VARCHAR, presupuesto_oficial VARCHAR,
    retiro_pliego_lugar VARCHAR, retiro_pliego_plazo VARCHAR,
    consulta_pliego_lugar VARCHAR, consulta_pliego_plazo VARCHAR,
    presentacion_ofertas_lugar VARCHAR, presentacion_ofertas_plazo VARCHAR,
    acto_apertura_lugar VARCHAR, acto_apertura_fecha VARCHAR
);
INSERT INTO bronze.contrataciones BY NAME
SELECT unnest.* FROM read_json_auto('data/landing/contrataciones_${FECHA_YMD}.json') AS j,
LATERAL UNNEST(j.avisos);

CREATE SCHEMA IF NOT EXISTS silver;
CREATE TABLE IF NOT EXISTS silver.licitaciones AS SELECT * FROM bronze.contrataciones WHERE 1=0;
INSERT INTO silver.licitaciones BY NAME
SELECT id_aviso, organismo, tipo_contratacion, fecha_publicacion, rubro,
       uoc, ejercicio, clase, modalidad, expediente, objeto,
       presupuesto_oficial, retiro_pliego_plazo, presentacion_ofertas_plazo,
       acto_apertura_fecha, fecha_scraping
FROM bronze.contrataciones;
ENDSQL
)

echo "$SQL" > /tmp/ingest_contrataciones.sql
uv run python scripts/python/db.py run-sql --file /tmp/ingest_contrataciones.sql
rm -f /tmp/ingest_contrataciones.sql

echo ""
echo "✅ Validación:"
uv run python scripts/python/db.py run-sql "
    SELECT 'bronze.contrataciones' AS tabla, COUNT(*) FROM bronze.contrataciones
    UNION ALL
    SELECT 'silver.licitaciones', COUNT(*) FROM silver.licitaciones;
"

echo ""
echo "🎯 Organismos que más contratan hoy:"
uv run python scripts/python/db.py run-sql "
    SELECT organismo, COUNT(*) AS avisos
    FROM silver.licitaciones
    WHERE fecha_publicacion LIKE '%${FECHA_YMD:6}%'
    GROUP BY organismo ORDER BY avisos DESC LIMIT 5;
"
echo ""
echo "🎉 Listo."
