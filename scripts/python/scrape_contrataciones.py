"""Scraper diario del Boletín Oficial — Sección Tercera (Contrataciones).

Uso:
    uv run python scripts/python/scrape_contrataciones.py --fecha 2026-06-11
    uv run python scripts/python/scrape_contrataciones.py  # hoy

Descarga licitaciones, concursos y contrataciones públicas del Estado,
extrae organismo, tipo, objeto, fechas clave, montos, y guarda JSON
en data/landing/. También descarga el PDF oficial de cada aviso.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path("scripts/python").resolve()))
import db


# ── Config ──────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "datasyn-local/0.1 (research; contact: local)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}
BASE_URL = "https://www.boletinoficial.gob.ar"
SECCION = "tercera"
RATE_LIMIT = 1.5


# ── Data model ──────────────────────────────────────────────────────
@dataclass
class Licitacion:
    id_aviso: str
    organismo: str
    tipo_contratacion: str
    fecha_publicacion: str
    url_detalle: str
    rubro: str
    fecha_scraping: str = ""

    texto_completo: str = ""
    texto_pdf: str = ""

    uoc: str = ""
    ejercicio: str = ""
    clase: str = ""
    modalidad: str = ""
    expediente: str = ""
    objeto: str = ""
    presupuesto_oficial: str = ""
    retiro_pliego_lugar: str = ""
    retiro_pliego_plazo: str = ""
    consulta_pliego_lugar: str = ""
    consulta_pliego_plazo: str = ""
    presentacion_ofertas_lugar: str = ""
    presentacion_ofertas_plazo: str = ""
    acto_apertura_lugar: str = ""
    acto_apertura_fecha: str = ""


# ── HTTP helpers ────────────────────────────────────────────────────
def _get(client: httpx.Client, path: str) -> str:
    time.sleep(RATE_LIMIT * 0.5)
    resp = client.get(f"{BASE_URL}{path}")
    resp.raise_for_status()
    return resp.text


def _post_json(client: httpx.Client, path: str, data: dict) -> dict:
    time.sleep(RATE_LIMIT * 0.5)
    resp = client.post(f"{BASE_URL}{path}", data=data)
    resp.raise_for_status()
    return resp.json()


def _download_pdf_aviso(client: httpx.Client, aviso_id: str, fecha: str) -> bytes | None:
    try:
        data = _post_json(client, "/pdf/download_aviso", {
            "nombreSeccion": SECCION,
            "idAviso": aviso_id,
            "fechaPublicacion": fecha,
        })
        b64 = data.get("pdfBase64")
        if b64:
            return base64.b64decode(b64)
    except Exception as e:
        print(f"  ⚠ PDF download failed: {e}", file=sys.stderr)
    return None


def extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text.strip()
    except Exception as e:
        print(f"  ⚠ PDF text extraction failed: {e}", file=sys.stderr)
        return ""


# ── Listing parser ──────────────────────────────────────────────────
def parse_listing(html: str, fecha: str) -> list[dict]:
    """Extract avisos from Sección Tercera listing page."""
    soup = BeautifulSoup(html, "lxml")
    avisos: list[dict] = []
    all_rows = soup.find_all("div", class_="row")
    in_rubro = False
    current_rubro = ""

    for row in all_rows:
        h5 = row.find("h5", class_="seccion-rubro")
        if h5:
            rubro = h5.get_text(strip=True)
            in_rubro = True
            current_rubro = rubro
            continue
        elif not in_rubro:
            continue

        linea = row.find("div", class_="linea-aviso")
        if not linea:
            continue
        link = row.find("a", href=True)
        if not link:
            continue
        item_p = linea.find("p", class_="item")
        if not item_p:
            continue

        href = link["href"]
        # aviso IDs in sección 3 are numeric
        m = re.search(r"/detalleAviso/tercera/(\d+)/", href)
        if not m:
            continue

        # Extract sub-type (e.g. "Licitación Pública 0002/2026")
        detalle_p = linea.find("p", class_="item-detalle")
        tipo = detalle_p.get_text(strip=True) if detalle_p else ""

        avisos.append({
            "id": m.group(1),
            "organismo": item_p.get_text(strip=True),
            "tipo_contratacion": tipo,
            "url": href,
            "fecha_publicacion": fecha,
            "rubro": current_rubro,
        })

    return avisos


# ── Detail parser ───────────────────────────────────────────────────
def parse_detail(html: str) -> dict[str, Any]:
    """Extract data from a contratación detail page."""
    soup = BeautifulSoup(html, "lxml")

    org_el = soup.find("h1")
    organismo = org_el.get_text(strip=True) if org_el else ""

    cuerpo = soup.find("div", id="cuerpoDetalleAviso")
    texto = cuerpo.get_text(separator="\n", strip=True) if cuerpo else ""

    # Fecha de publicación
    fecha_p = soup.find("p", class_="text-muted")
    fecha_pub = ""
    if fecha_p and "Fecha de publicación" in fecha_p.get_text():
        m = re.search(r"(\d{2}/\d{2}/\d{4})", fecha_p.get_text())
        if m:
            fecha_pub = m.group(1)

    # Extract structured fields from text
    datos = parse_contratacion_text(texto)

    return {
        "organismo": organismo,
        "texto_completo": texto,
        "fecha_publicacion": fecha_pub,
        **datos,
    }


def parse_contratacion_text(texto: str) -> dict[str, str]:
    """Extract structured fields from the contratación text."""
    data: dict[str, str] = {}

    # Remove HTML tags
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    # UOC
    m = re.search(r"UOC:\s*([^\n]+)", texto)
    if m:
        data["uoc"] = m.group(1).strip()

    # Ejercicio
    m = re.search(r"Ejercicio:\s*([^\s]+)", texto)
    if m:
        data["ejercicio"] = m.group(1).strip()

    # Clase
    m = re.search(r"Clase:\s*([^\n]+?)(?:\s+Modalidad:|$)", texto)
    if m:
        data["clase"] = m.group(1).strip()

    # Modalidad
    m = re.search(r"Modalidad:\s*([^\n]+?)(?:\s+Expediente|$)", texto)
    if m:
        data["modalidad"] = m.group(1).strip()

    # Expediente
    m = re.search(r"Expediente\s*N[°º]\s*:\s*([^\n]+)", texto)
    if m:
        data["expediente"] = m.group(1).strip()

    # Objeto
    m = re.search(r"Objeto:\s*(.+?)(?:\s+Presupuesto|Retiro del Pliego|Consulta del Pliego|Presentación de Ofertas|Acto de Apertura|$)", texto)
    if m:
        data["objeto"] = m.group(1).strip()

    # Presupuesto Oficial
    m = re.search(r"Presupuesto[^:]*:\s*([^\n]+)", texto)
    if m:
        data["presupuesto_oficial"] = m.group(1).strip()

    # Retiro del Pliego - lugar
    m = re.search(r"Retiro del Pliego[^:]*:\s*([^\n]+)", texto)
    if m:
        data["retiro_pliego_lugar"] = m.group(1).strip()
    m = re.search(r"Retiro del Pliego[^:]*:\s*[^\n]+\s+Plazo[^:]*:\s*([^\n]+)", texto)
    if m:
        data["retiro_pliego_plazo"] = m.group(1).strip()
    else:
        # Sometimes the plazo follows on the same line pattern
        m = re.search(r"Retiro del Pliego[^:]*:\s*[^\n]+(?:\s+)(?:Plazo|Plazo y horario)[^:]*:\s*([^\n]+)", texto)
        if m:
            data["retiro_pliego_plazo"] = m.group(1).strip()

    # Consulta del Pliego
    m = re.search(r"Consulta del Pliego[^:]*:\s*([^\n]+)", texto)
    if m:
        data["consulta_pliego_lugar"] = m.group(1).strip()
    m = re.search(r"Consulta del Pliego[^:]*:\s*[^\n]+\s+Plazo[^:]*:\s*([^\n]+)", texto)
    if m:
        data["consulta_pliego_plazo"] = m.group(1).strip()

    # Presentación de Ofertas
    m = re.search(r"Presentación de Ofertas[^:]*:\s*([^\n]+)", texto)
    if m:
        data["presentacion_ofertas_lugar"] = m.group(1).strip()
    m = re.search(r"Presentación de Ofertas[^:]*:\s*[^\n]+\s+Plazo[^:]*:\s*([^\n]+)", texto)
    if m:
        data["presentacion_ofertas_plazo"] = m.group(1).strip()

    # Acto de Apertura
    m = re.search(r"Acto de Apertura[^:]*:\s*([^\n]+)", texto)
    if m:
        data["acto_apertura_lugar"] = m.group(1).strip()
    m = re.search(r"Acto de Apertura[^:]*:\s*[^\n]+\s+Plazo[^:]*:\s*([^\n]+)", texto)
    if m:
        data["acto_apertura_fecha"] = m.group(1).strip()
    # Sometimes it's just the date after the place
    m = re.search(r"Acto de Apertura[^:]*:\s*[^\n]+\s+(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})", texto)
    if m and not data.get("acto_apertura_fecha"):
        data["acto_apertura_fecha"] = m.group(1).strip()

    return data


# ── Main scraping pipeline ─────────────────────────────────────────
def scrape_fecha(fecha_str: str) -> list[Licitacion]:
    """Scrape all avisos from Sección Tercera for a given date."""
    fmt_fecha = fecha_str
    fecha_obj = datetime.strptime(fmt_fecha, "%Y%m%d").date()

    print(f"\n📡 Scraping Contrataciones — {fecha_obj.strftime('%d/%m/%Y')}")

    with httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True) as client:
        print(f"  → {BASE_URL}/seccion/{SECCION}/{fmt_fecha}")
        html_listing = _get(client, f"/seccion/{SECCION}/{fmt_fecha}")

        raw_avisos = parse_listing(html_listing, fmt_fecha)
        if not raw_avisos:
            print("  ⚠ No se encontraron avisos.")
            return []

        print(f"  → {len(raw_avisos)} avisos encontrados")

        items: list[Licitacion] = []
        for i, raw in enumerate(raw_avisos, 1):
            aviso_id = raw["id"]
            organismo = raw["organismo"]
            tipo = raw["tipo_contratacion"]
            print(f"  [{i}/{len(raw_avisos)}] {organismo} — {tipo}")

            try:
                html_detail = _get(client, raw["url"])
                detail = parse_detail(html_detail)

                item = Licitacion(
                    id_aviso=aviso_id,
                    organismo=detail.get("organismo", organismo),
                    tipo_contratacion=tipo,
                    fecha_publicacion=detail.get("fecha_publicacion", ""),
                    url_detalle=raw["url"],
                    rubro=raw["rubro"],
                    fecha_scraping=datetime.now().isoformat(),
                    texto_completo=detail.get("texto_completo", ""),
                    uoc=detail.get("uoc", ""),
                    ejercicio=detail.get("ejercicio", ""),
                    clase=detail.get("clase", ""),
                    modalidad=detail.get("modalidad", ""),
                    expediente=detail.get("expediente", ""),
                    objeto=detail.get("objeto", ""),
                    presupuesto_oficial=detail.get("presupuesto_oficial", ""),
                    retiro_pliego_lugar=detail.get("retiro_pliego_lugar", ""),
                    retiro_pliego_plazo=detail.get("retiro_pliego_plazo", ""),
                    consulta_pliego_lugar=detail.get("consulta_pliego_lugar", ""),
                    consulta_pliego_plazo=detail.get("consulta_pliego_plazo", ""),
                    presentacion_ofertas_lugar=detail.get("presentacion_ofertas_lugar", ""),
                    presentacion_ofertas_plazo=detail.get("presentacion_ofertas_plazo", ""),
                    acto_apertura_lugar=detail.get("acto_apertura_lugar", ""),
                    acto_apertura_fecha=detail.get("acto_apertura_fecha", ""),
                )

                # Download PDF
                print(f"    → Descargando PDF...")
                pdf_bytes = _download_pdf_aviso(client, aviso_id, fmt_fecha)
                if pdf_bytes:
                    item.texto_pdf = extract_pdf_text(pdf_bytes)
                    print(f"    → PDF: {len(pdf_bytes)} bytes, {len(item.texto_pdf)} chars texto")

                items.append(item)

            except Exception as e:
                print(f"    ⚠ Error: {e}", file=sys.stderr)
                continue

    return items


def save_landing(items: list[Licitacion], fecha_str: str) -> Path:
    landing = db.get_landing_path()
    out_path = landing / f"contrataciones_{fecha_str}.json"

    data = {
        "fecha": fecha_str,
        "scraped_at": datetime.now().isoformat(),
        "fuente": "Boletín Oficial - Sección Tercera (Contrataciones)",
        "total_avisos": len(items),
        "avisos": [asdict(i) for i in items],
    }

    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"\n💾 Guardado: {out_path}")
    return out_path


# ── CLI ────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Scraper diario del Boletín Oficial — Contrataciones"
    )
    parser.add_argument(
        "--fecha",
        default=date.today().strftime("%Y-%m-%d"),
        help="Fecha en formato YYYY-MM-DD (default: hoy)",
    )
    args = parser.parse_args()

    try:
        fecha_obj = datetime.strptime(args.fecha, "%Y-%m-%d").date()
    except ValueError:
        print("Error: fecha debe ser YYYY-MM-DD", file=sys.stderr)
        sys.exit(1)

    fecha_str = fecha_obj.strftime("%Y%m%d")
    items = scrape_fecha(fecha_str)

    if items:
        save_landing(items, fecha_str)
        print(f"\n✅ {len(items)} contrataciones scrapeadas correctamente.")
    else:
        print("\n⚠ No se scrapearon avisos.")
        sys.exit(1)


if __name__ == "__main__":
    main()
