#!/bin/sh
# Scraper diario del Boletín Oficial + ingesta a DuckDB
# Uso: ./scripts/sh/scrape_boletin_diario.sh [YYYY-MM-DD]
#   Si no se pasa fecha, usa hoy

set -e

FECHA="${1:-$(date +%Y-%m-%d)}"
FECHA_YMD=$(echo "$FECHA" | tr -d '-')

echo "================================================"
echo "📰 Scraper diario — Boletín Oficial"
echo "   Fecha: $FECHA"
echo "================================================"

# 1. Scrapear
uv run python scripts/python/scrape/boletin/scrape_boletin.py --fecha "$FECHA"

# 2. Ingestar a DuckDB
echo ""
echo "📦 Ingestionando a la base de datos..."
TMP_SQL="/tmp/ingest_boletin_${FECHA_YMD}.sql"
sed "s/{FECHA}/$FECHA_YMD/g" scripts/sql/boletin/ingest_boletin.sql > "$TMP_SQL"
uv run python scripts/python/db.py run-sql --file "$TMP_SQL"
rm -f "$TMP_SQL"

# 3. Validar
echo ""
echo "✅ Tablas actualizadas:"
uv run python scripts/python/db.py run-sql "
    SELECT 'bronze.boletin_avisos' AS tabla, COUNT(*) AS total FROM bronze.boletin_avisos
    UNION ALL
    SELECT 'silver.entidades', COUNT(*) FROM silver.entidades
    UNION ALL
    SELECT 'silver.personas', COUNT(*) FROM silver.personas;
"

echo ""
echo "🎉 Listo! Datos del $FECHA disponibles."
echo "   Landing: data/landing/boletin_sa_${FECHA_YMD}.json"
echo "   Bronce:  bronze.boletin_avisos"
echo "   Silver:  silver.entidades — una fila por empresa"
echo "   Silver:  silver.personas  — una fila por accionista"
