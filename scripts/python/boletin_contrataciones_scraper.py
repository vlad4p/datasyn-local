"""
Scraper del Boletín Oficial — sección CONTRATACIONES → ADJUDICACIONES - ADJUDICACIONES.

Uso:
    uv run python scripts/python/boletin_contrataciones_scraper.py                     # hoy
    uv run python scripts/python/boletin_contrataciones_scraper.py --date 2026-06-05   # fecha específica

Flujo:
    1. Obtiene el listado de avisos de la sección tercera
    2. Filtra solo "ADJUDICACIONES - ADJUDICACIONES"
    3. Visita cada detalle, extrae contenido y número de página del PDF
    4. Descarga el PDF de la página correspondiente (/pdf/download_section)
    5. Guarda JSON en data/landing/boletin_oficial/contrataciones/
    6. Ingiere en DuckDB → schema bronze, tabla boletin_contrataciones_adjudicaciones
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

# ── paths ──────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path("scripts/python").resolve()))
import db

LANDING_DIR = db.get_landing_path() / "boletin_oficial" / "contrataciones"
PDF_DIR = db.get_landing_path() / "boletin_oficial" / "contrataciones_pdfs"
BASE_URL = "https://www.boletinoficial.gob.ar"
SECCION = "tercera"
SUBSECCION_BUSCADA = "ADJUDICACIONES - ADJUDICACIONES"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
}

TIMEOUT = httpx.Timeout(30.0)
REQUEST_DELAY = 0.5  # segundos entre requests al detalle


# ── helpers ────────────────────────────────────────────────────────────

def _parse_date_arg(d: str) -> date:
    try:
        return date.fromisoformat(d)
    except ValueError:
        print(f"❌ Fecha inválida: {d!r}. Usá formato YYYY-MM-DD.")
        sys.exit(1)


def _avisos_url(fecha: date) -> str:
    """URL del listado del día, ej. /seccion/tercera/20260605"""
    return f"{BASE_URL}/seccion/{SECCION}/{fecha.strftime('%Y%m%d')}"


def _detalle_url(aviso_id: str, fecha: date) -> str:
    return f"{BASE_URL}/detalleAviso/{SECCION}/{aviso_id}/{fecha.strftime('%Y%m%d')}"


def _pdf_url() -> str:
    """Endpoint POST para descargar página de la sección como PDF base64."""
    return f"{BASE_URL}/pdf/download_section"


def _get_soup(client: httpx.Client, url: str) -> BeautifulSoup:
    resp = client.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


# ── listado ────────────────────────────────────────────────────────────

def extraer_avisos(soup: BeautifulSoup) -> list[dict[str, str]]:
    """
    Busca el heading "ADJUDICACIONES - ADJUDICACIONES" y extrae
    todos los enlaces a detalle que le siguen (hasta el próximo heading).

    Estructura HTML real (tercera sección, basada en Bootstrap rows):
      <div class="row"><div class="col-md-12"><h5>ADJUDICACIONES - ADJUDICACIONES</h5></div></div>
      <div class="row"><a href="/detalleAviso/tercera/ID/FECHA"><p>ORG</p><p>TIPO</p></a></div>
      <div class="row"><a href="/detalleAviso/tercera/ID/FECHA"><p>ORG</p><p>TIPO</p></a></div>
      ...
      <div class="row"><div class="col-md-12"><h5>SIGUIENTE SUBSECCION</h5></div></div>
    """
    avisos: list[dict[str, str]] = []

    heading_h5 = soup.find(
        "h5", string=lambda t: t and t.strip() == SUBSECCION_BUSCADA
    )
    if not heading_h5:
        print(f"⚠️  No se encontró la sección '{SUBSECCION_BUSCADA}' en la página.")
        return avisos

    # La estructura usa div.row: el heading está en una row, los avisos en rows siguientes
    heading_row = heading_h5.find_parent("div", class_="row")
    if not heading_row:
        print("⚠️  No se encontró el contenedor row del heading.")
        return avisos

    # Recorrer las row siguientes hasta encontrar otra row con h5
    for row in heading_row.find_next_siblings("div", class_="row"):
        # Si esta row contiene un h5, es la siguiente subsección → terminamos
        if row.find("h5"):
            break

        # Buscar links a detalle dentro de esta row
        for link in row.find_all("a", href=lambda h: h and "/detalleAviso/" in h):
            href = link.get("href", "")
            aviso_id = href.rsplit("/", 2)[-2]
            ps = link.find_all("p")
            organismo = ps[0].get_text(strip=True) if len(ps) > 0 else ""
            tipo = ps[1].get_text(strip=True) if len(ps) > 1 else ""
            titulo = f"{organismo} — {tipo}" if organismo and tipo else link.get_text(strip=True)

            avisos.append({
                "id": aviso_id,
                "url": f"{BASE_URL}{href}",
                "organismo": organismo,
                "tipo_licitacion": tipo,
                "titulo": titulo,
            })

    return avisos


# ── detalle ────────────────────────────────────────────────────────────

def extraer_detalle(client: httpx.Client, aviso: dict[str, str], fecha: date) -> dict[str, Any]:
    """Visita la página de detalle: extrae contenido, nº de página PDF, y descarga el PDF."""
    url = aviso["url"]
    print(f"  → {aviso['titulo']}")

    try:
        soup = _get_soup(client, url)
    except Exception as e:
        print(f"    ⚠️  Error al obtener detalle: {e}")
        return {
            **aviso,
            "contenido": None,
            "pdf_page": None,
            "pdf_path": None,
            "error": str(e),
            "fecha_publicacion": fecha.isoformat(),
        }

    # ── Extraer número de página del botón "Ver páginas publicadas" ──
    pdf_page = None
    btn = soup.find("button", string=lambda t: t and "Ver páginas publicadas" in t)
    if btn:
        onclick = btn.get("onclick", "")
        # mostrarPdfSeccionPorPaginas("tercera","20260605","27","27",...)
        m = re.search(r'mostrarPdfSeccionPorPaginas\("tercera",\s*"[^"]+",\s*"(\d+)"', onclick)
        if m:
            pdf_page = m.group(1)
            print(f"    📄 Página PDF: {pdf_page}")

    # ── Extraer contenido del <article> ──
    article = soup.find("article")
    texto = ""
    if article:
        parrafos = article.find_all("p")
        texto = "\n\n".join(p.get_text(strip=True) for p in parrafos if p.get_text(strip=True))

    # ── Extraer fecha de publicación ──
    fecha_pub = fecha.isoformat()
    pie = soup.find(string=lambda t: t and "Fecha de publicación" in t)
    if pie:
        m = re.search(r"(\d{2})/(\d{2})/(\d{4})", pie)
        if m:
            fecha_pub = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

    # ── Descargar PDF ──
    pdf_path = None
    if pdf_page:
        pdf_path = _descargar_pdf(client, fecha, pdf_page, aviso["id"])

    return {
        "id": aviso["id"],
        "url": url,
        "organismo": aviso["organismo"],
        "tipo_licitacion": aviso["tipo_licitacion"],
        "titulo": aviso["titulo"],
        "contenido": texto,
        "pdf_page": pdf_page,
        "pdf_path": str(pdf_path) if pdf_path else None,
        "seccion": SECCION,
        "subseccion": SUBSECCION_BUSCADA,
        "fecha_publicacion": fecha_pub,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def _descargar_pdf(client: httpx.Client, fecha: date, pagina: str, aviso_id: str) -> Path | None:
    """Descarga el PDF de la página vía POST (retorna base64). Usa caché local."""
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    fecha_str = fecha.strftime('%Y%m%d')
    filename = f"{fecha_str}_pagina_{pagina}.pdf"
    filepath = PDF_DIR / filename

    if filepath.exists():
        print(f"    📎 PDF ya descargado: {filename}")
        return filepath

    try:
        resp = client.post(
            _pdf_url(),
            data={
                "nombreSeccion": SECCION,
                "fechaPublicacion": fecha_str,
                "paginaDesde": pagina,
                "paginaHasta": pagina,
            },
            headers={
                **HEADERS,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            },
            timeout=httpx.Timeout(60.0),
        )
        resp.raise_for_status()
        data = resp.json()
        pdf_base64 = data.get("pdfBase64")
        if not pdf_base64:
            print(f"    ⚠️  pdfBase64 vacío o nulo en la respuesta")
            return None

        import base64
        pdf_bytes = base64.b64decode(pdf_base64)
        filepath.write_bytes(pdf_bytes)
        print(f"    📎 PDF descargado: {filename} ({len(pdf_bytes)} bytes)")
        return filepath
    except Exception as e:
        print(f"    ⚠️  Error al descargar PDF: {e}")
        return None


# ── guardado ───────────────────────────────────────────────────────────

def guardar_json(fecha: date, datos: list[dict[str, Any]]) -> Path:
    """Guarda los datos como JSON en data/landing/boletin_oficial/contrataciones/."""
    LANDING_DIR.mkdir(parents=True, exist_ok=True)
    archivo = LANDING_DIR / f"{fecha.isoformat()}.json"
    payload = {
        "fecha": fecha.isoformat(),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "seccion": SECCION,
        "subseccion": SUBSECCION_BUSCADA,
        "total": len(datos),
        "avisos": datos,
    }
    archivo.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  💾 JSON guardado: {archivo}")
    return archivo


# ── ingest a DuckDB (vía db.py run-sql) ────────────────────────────────

def _run_sql(sql: str) -> int:
    """Ejecuta SQL usando db.py run-sql."""
    import subprocess
    cmd = [
        "uv", "run", "python",
        str(db.PROJECT_ROOT / "scripts" / "python" / "db.py"),
        "run-sql", sql,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=db.PROJECT_ROOT)
    if result.stdout:
        print(f"    {result.stdout.strip()}")
    if result.returncode != 0:
        print(f"    ❌ {result.stderr.strip()}")
    return result.returncode


def ingestar_en_duckdb(fecha: date, archivo: Path) -> None:
    """Crea schema bronze y tabla bronze.boletin_contrataciones_adjudicaciones usando CTE."""
    rel_path = archivo.relative_to(db.PROJECT_ROOT)

    # 1. Schema bronze
    print("  🗄️  Creando schema bronze...")
    if _run_sql("CREATE SCHEMA IF NOT EXISTS bronze;") != 0:
        return

    # 2. Crear tabla con schema plano usando CTE + UNNEST
    print("  🗄️  Creando tabla bronze.boletin_contrataciones_adjudicaciones...")
    exit_code = _run_sql(f"""
        CREATE OR REPLACE TABLE bronze.boletin_contrataciones_adjudicaciones AS
        WITH expanded AS (
            SELECT j.fecha, j.scraped_at, j.seccion, j.subseccion, j.total,
                   UNNEST(j.avisos) AS aviso
            FROM read_json_auto('{rel_path}') j
        )
        SELECT 
            fecha AS boletin_fecha,
            scraped_at AS boletin_scraped_at,
            seccion AS boletin_seccion,
            subseccion AS boletin_subseccion,
            total AS boletin_total,
            aviso.id,
            aviso.url,
            aviso.organismo,
            aviso.tipo_licitacion,
            aviso.titulo,
            aviso.contenido,
            aviso.pdf_page,
            aviso.pdf_path,
            aviso.fecha_publicacion,
            aviso.scraped_at AS aviso_scraped_at
        FROM expanded;
    """)
    if exit_code != 0:
        return

    # 3. Validar
    print("  📊 Total registros en tabla:")
    _run_sql("SELECT COUNT(*) AS total FROM bronze.boletin_contrataciones_adjudicaciones;")
    print("  📊 Muestra:")
    _run_sql("SELECT id, organismo, tipo_licitacion, pdf_page, pdf_path FROM bronze.boletin_contrataciones_adjudicaciones LIMIT 5;")


# ── main ───────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scraper del Boletín Oficial — ADJUDICACIONES - ADJUDICACIONES (tercera sección)"
    )
    parser.add_argument(
        "--date", "-d",
        type=str,
        default=date.today().isoformat(),
        help="Fecha en formato YYYY-MM-DD (default: hoy)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo scrapea y guarda JSON, no ingiere en DuckDB",
    )
    args = parser.parse_args(argv)

    fecha = _parse_date_arg(args.date)

    print(f"\n{'='*60}")
    print(f"📰 Boletín Oficial — Contrataciones / {SUBSECCION_BUSCADA}")
    print(f"📅 Fecha: {fecha.isoformat()}")
    print(f"{'='*60}\n")

    # ── 1. Obtener listado ──
    print("🔍 Obteniendo listado...")
    try:
        with httpx.Client() as client:
            soup = _get_soup(client, _avisos_url(fecha))
            avisos = extraer_avisos(soup)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 302:
            print(f"⚠️  No hay edición para {fecha.isoformat()} (día sin actividad).")
            return 0
        print(f"❌ Error HTTP {e.response.status_code}.")
        return 1

    if not avisos:
        print("❌ No se encontraron avisos para esta fecha.")
        return 1

    print(f"📋 {len(avisos)} avisos encontrados.\n")

    # ── 2. Visitar cada detalle + descargar PDFs ──
    print("📄 Descargando detalles y PDFs...")
    datos: list[dict[str, Any]] = []
    with httpx.Client() as client:
        for i, aviso in enumerate(avisos, 1):
            print(f"  [{i}/{len(avisos)}] ", end="")
            detalle = extraer_detalle(client, aviso, fecha)
            datos.append(detalle)
            if i < len(avisos):
                time.sleep(REQUEST_DELAY)

    # ── 3. Guardar JSON ──
    print(f"\n💾 Guardando datos...")
    archivo = guardar_json(fecha, datos)

    # ── 4. Ingestar en DuckDB ──
    if not args.dry_run:
        print(f"\n🗄️  Ingestando en DuckDB...")
        ingestar_en_duckdb(fecha, archivo)
    else:
        print(f"\n⏭️  Dry-run: omitiendo ingest en DuckDB.")

    # ── Resumen de PDFs ──
    pdfs_descargados = sum(1 for d in datos if d.get("pdf_path"))
    pdfs_unicos = len(set(d["pdf_path"] for d in datos if d.get("pdf_path")))
    print(f"\n{'='*60}")
    print(f"✅ Completado — {len(datos)} avisos procesados.")
    print(f"📎 {pdfs_descargados} referencias a PDF, {pdfs_unicos} archivos únicos.")
    print(f"{'='*60}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
