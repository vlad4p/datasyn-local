"""
Scraper del Boletín Oficial — sección SOCIEDADES ANONIMAS - CONSTITUCION SA.

Uso:
    uv run python scripts/python/boletin_scraper.py                     # hoy
    uv run python scripts/python/boletin_scraper.py --date 2026-06-05   # fecha específica

Flujo:
    1. Obtiene el listado de avisos de la sección segunda
    2. Filtra solo "SOCIEDADES ANONIMAS - CONSTITUCION SA"
    3. Visita cada detalle y extrae contenido
    4. Guarda JSON en data/landing/boletin_oficial/
    5. Ingiere en DuckDB → schema bronze, tabla boletin_sa_constitucion
"""

from __future__ import annotations

import argparse
import json
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

LANDING_DIR = db.get_landing_path() / "boletin_oficial"
BASE_URL = "https://www.boletinoficial.gob.ar"
LIST_URL = f"{BASE_URL}/seccion/segunda"
SECCION_BUSCADA = "SOCIEDADES ANONIMAS - CONSTITUCION SA"

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
    """URL del listado del día, ej. /seccion/segunda/20260605"""
    return f"{BASE_URL}/seccion/segunda/{fecha.strftime('%Y%m%d')}"


def _detalle_url(aviso_id: str, fecha: date) -> str:
    return f"{BASE_URL}/detalleAviso/segunda/{aviso_id}/{fecha.strftime('%Y%m%d')}"


def _get_soup(client: httpx.Client, url: str) -> BeautifulSoup:
    resp = client.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


# ── listado ────────────────────────────────────────────────────────────

def extraer_avisos(soup: BeautifulSoup) -> list[dict[str, str]]:
    """
    Busca el heading "SOCIEDADES ANONIMAS - CONSTITUCION SA" y extrae
    todos los enlaces a detalle que le siguen (hasta el próximo heading).

    Estructura HTML real (cada aviso está en su propio <div class="row">):
      <div class="row"><div class="col-md-12"><h5>SECCION</h5></div></div>
      <div class="row"><a href="/detalleAviso/...">EMPRESA S.A.</a></div>
      <div class="row"><a href="/detalleAviso/...">OTRA S.A.</a></div>
      <div class="row"><div class="col-md-12"><h5>SIGUIENTE SECCION</h5></div></div>
    """
    avisos: list[dict[str, str]] = []

    # Buscar el heading exacto (texto completo, no substring)
    heading_h5 = soup.find(
        "h5", string=lambda t: t and t.strip() == SECCION_BUSCADA
    )
    if not heading_h5:
        print(f"⚠️  No se encontró la sección '{SECCION_BUSCADA}' en la página.")
        return avisos

    heading_row = heading_h5.find_parent("div", class_="row")
    if not heading_row:
        print(f"⚠️  No se encontró el contenedor row para el heading.")
        return avisos

    # Recorrer las filas siguientes hasta encontrar otro heading
    for row in heading_row.find_next_siblings("div", class_="row"):
        # Si la fila contiene un heading, terminó la sección
        if row.find("h5"):
            break

        # Buscar links a detalle dentro de la fila
        link = row.find("a", href=lambda h: h and h.startswith("/detalleAviso/"))
        if link and isinstance(link, Tag):
            href = link.get("href", "")
            aviso_id = href.rsplit("/", 2)[-2]
            avisos.append({
                "id": aviso_id,
                "url": f"{BASE_URL}{href}",
                "titulo": link.get_text(strip=True),
            })

    return avisos


# ── detalle ────────────────────────────────────────────────────────────

def extraer_detalle(client: httpx.Client, aviso: dict[str, str], fecha: date) -> dict[str, Any]:
    """Visita la página de detalle y extrae el contenido del artículo."""
    url = aviso["url"]
    print(f"  → {aviso['titulo']}")

    try:
        soup = _get_soup(client, url)
    except Exception as e:
        print(f"    ⚠️  Error al obtener detalle: {e}")
        return {
            **aviso,
            "contenido": None,
            "error": str(e),
            "fecha_publicacion": fecha.isoformat(),
        }

    # Buscar el <article>
    article = soup.find("article")
    texto = ""
    if article:
        # Extraer texto plano de todos los párrafos del article
        parrafos = article.find_all("p")
        texto = "\n\n".join(p.get_text(strip=True) for p in parrafos if p.get_text(strip=True))

    # Extraer la fecha de publicación del pie
    fecha_pub = fecha.isoformat()
    pie = soup.find(string=lambda t: t and "Fecha de publicación" in t)
    if pie:
        # "Fecha de publicación 05/06/2026"
        import re
        m = re.search(r"(\d{2})/(\d{2})/(\d{4})", pie)
        if m:
            fecha_pub = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

    return {
        "id": aviso["id"],
        "url": url,
        "titulo": aviso["titulo"],
        "contenido": texto,
        "seccion": SECCION_BUSCADA,
        "fecha_publicacion": fecha_pub,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


# ── guardado ───────────────────────────────────────────────────────────

def guardar_json(fecha: date, datos: list[dict[str, Any]]) -> Path:
    """Guarda los datos como JSON en data/landing/boletin_oficial/."""
    LANDING_DIR.mkdir(parents=True, exist_ok=True)
    archivo = LANDING_DIR / f"{fecha.isoformat()}.json"
    payload = {
        "fecha": fecha.isoformat(),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "total": len(datos),
        "avisos": datos,
    }
    archivo.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  💾 JSON guardado: {archivo}")
    return archivo


# ── ingest a DuckDB (vía MCP ─> db.py run-sql) ─────────────────────────

def _run_sql(sql: str) -> int:
    """Ejecuta SQL usando db.py run-sql (MCP)."""
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
    """
    Crea el schema bronze y la tabla bronze.boletin_sa_constitucion,
    luego inserta los datos del JSON — todo vía MCP (db.py run-sql).
    """
    rel_path = archivo.relative_to(db.PROJECT_ROOT)

    # 1. Schema bronze
    print("  🗄️  Creando schema bronze...")
    exit_code = _run_sql("CREATE SCHEMA IF NOT EXISTS bronze;")
    if exit_code != 0:
        return

    # 2. Crear tabla
    print("  🗄️  Creando tabla bronze.boletin_sa_constitucion...")
    exit_code = _run_sql("""
        CREATE TABLE IF NOT EXISTS bronze.boletin_sa_constitucion (
            id VARCHAR PRIMARY KEY,
            url VARCHAR,
            titulo VARCHAR,
            contenido TEXT,
            seccion VARCHAR,
            fecha_publicacion DATE,
            scraped_at TIMESTAMP WITH TIME ZONE
        );
    """)
    if exit_code != 0:
        return

    # 3. Insertar datos desde el JSON guardado
    print("  🗄️  Insertando datos desde JSON...")
    exit_code = _run_sql(f"""
        INSERT OR REPLACE INTO bronze.boletin_sa_constitucion
            (id, url, titulo, contenido, seccion, fecha_publicacion, scraped_at)
        SELECT
            (UNNEST(avisos)).id,
            (UNNEST(avisos)).url,
            (UNNEST(avisos)).titulo,
            (UNNEST(avisos)).contenido,
            (UNNEST(avisos)).seccion,
            (UNNEST(avisos)).fecha_publicacion::DATE,
            (UNNEST(avisos)).scraped_at::TIMESTAMP WITH TIME ZONE
        FROM read_json_auto('{rel_path}');
    """)
    if exit_code != 0:
        return

    # 4. Validar
    print("  📊 Total registros en tabla:")
    _run_sql("SELECT COUNT(*) AS total FROM bronze.boletin_sa_constitucion;")


# ── main ───────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scraper del Boletín Oficial — CONSTITUCIÓN DE SA"
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
    print(f"📰 Boletín Oficial — {SECCION_BUSCADA}")
    print(f"📅 Fecha: {fecha.isoformat()}")
    print(f"{'='*60}\n")

    # ── 1. Obtener listado ──
    print("🔍 Obteniendo listado...")
    with httpx.Client() as client:
        soup = _get_soup(client, _avisos_url(fecha))
        avisos = extraer_avisos(soup)

    if not avisos:
        print("❌ No se encontraron avisos para esta fecha.")
        return 1

    print(f"📋 {len(avisos)} avisos encontrados.\n")

    # ── 2. Visitar cada detalle ──
    print("📄 Descargando detalles...")
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

    print(f"\n{'='*60}")
    print(f"✅ Completado — {len(datos)} avisos procesados.")
    print(f"{'='*60}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
