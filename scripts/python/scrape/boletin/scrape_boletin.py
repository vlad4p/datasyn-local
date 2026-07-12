"""Scraper diario del Boletín Oficial — Sección Sociedades y Avisos Judiciales.

Uso:
    uv run python scripts/python/scrape/boletin/scrape_boletin.py --fecha 2026-06-03
    uv run python scripts/python/scrape/boletin/scrape_boletin.py  # hoy

Descarga avisos de "Sociedades Anónimas - Constitución SA", extrae
entidades/personas del texto y del PDF, y guarda JSON en data/landing/.
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
RUBRO_CONSTITUCION_SA = "SOCIEDADES ANONIMAS - CONSTITUCION SA"
RATE_LIMIT = 1.5  # seconds between requests


# ── Data models ─────────────────────────────────────────────────────
@dataclass
class Accionista:
    nombre: str = ""
    fecha_nacimiento: str = ""
    dni: str = ""
    cuit: str = ""
    domicilio: str = ""
    nacionalidad: str = ""
    estado_civil: str = ""
    profesion: str = ""
    acciones_suscritas: int = 0


@dataclass
class AvisoSA:
    id_aviso: str
    empresa: str
    fecha_publicacion: str
    url_detalle: str
    rubro: str
    fecha_scraping: str = ""

    texto_completo: str = ""
    texto_pdf: str = ""

    escritura: str = ""
    fecha_constitucion: str = ""
    domicilio_social: str = ""
    objeto_social: str = ""
    plazo: str = ""
    capital_social: float = 0.0
    valor_nominal_accion: float = 0.0
    total_acciones: int = 0
    administracion: str = ""
    presidente: str = ""
    presidente_suplente: str = ""
    sindicos: str = ""
    cierre_ejercicio: str = ""
    profesional_autorizante: str = ""
    accionistas: list[Accionista] = field(default_factory=list)


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


def _download_pdf_aviso(client: httpx.Client, aviso_id: str, seccion: str, fecha: str) -> bytes | None:
    """Download individual aviso PDF via the same POST endpoint the site uses."""
    try:
        data = _post_json(client, "/pdf/download_aviso", {
            "nombreSeccion": seccion,
            "idAviso": aviso_id,
            "fechaPublicacion": fecha,
        })
        b64 = data.get("pdfBase64")
        if b64:
            return base64.b64decode(b64)
    except Exception as e:
        print(f"  ⚠ PDF download failed for {aviso_id}: {e}", file=sys.stderr)
    return None


# ── PDF text extraction ────────────────────────────────────────────
def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using PyMuPDF."""
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text.strip()
    except Exception as e:
        print(f"  ⚠ PDF text extraction failed: {e}", file=sys.stderr)
        return ""


# ── HTML parsing ───────────────────────────────────────────────────
def parse_listing(html: str, fecha: str) -> list[dict]:
    """Extract aviso IDs and names from the listing page."""
    soup = BeautifulSoup(html, "lxml")
    avisos: list[dict] = []

    # Find all rows with rubro headings
    all_rows = soup.find_all("div", class_="row")
    rubro_start = None
    rubro_name = ""

    for i, row in enumerate(all_rows):
        h5 = row.find("h5", class_="seccion-rubro")
        if h5:
            rubro = h5.get_text(strip=True)
            if RUBRO_CONSTITUCION_SA in rubro:
                rubro_start = i
                rubro_name = rubro
            elif rubro_start is not None:
                # We reached the next rubro — stop
                break
        elif rubro_start is not None:
            # Inside our target rubro: look for avisos
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
            m = re.search(r"/detalleAviso/segunda/(A\d+)/", href)
            if not m:
                continue

            avisos.append({
                "id": m.group(1),
                "empresa": item_p.get_text(strip=True),
                "url": href,
                "fecha_publicacion": fecha,
                "rubro": rubro_name,
            })

    return avisos


def parse_detail(html: str) -> dict[str, Any]:
    """Extract company name and full text from detail page."""
    soup = BeautifulSoup(html, "lxml")

    nombre_el = soup.find("h1")
    nombre = nombre_el.get_text(strip=True) if nombre_el else ""

    cuerpo = soup.find("div", id="cuerpoDetalleAviso")
    texto = cuerpo.get_text(separator="\n", strip=True) if cuerpo else ""

    # Fecha de publicación
    fecha_p = soup.find("p", class_="text-muted")
    fecha_pub = ""
    if fecha_p and "Fecha de publicación" in fecha_p.get_text():
        m = re.search(r"(\d{2}/\d{2}/\d{4})", fecha_p.get_text())
        if m:
            fecha_pub = m.group(1)

    return {
        "empresa": nombre,
        "texto_completo": texto,
        "fecha_publicacion": fecha_pub,
    }


# ── Text parsing for SA constitutions ─────────────────────────────
def parse_sa_text(texto: str) -> dict[str, Any]:
    """Extract structured fields from the standardized SA constitution text."""
    data: dict[str, Any] = {
        "accionistas": [],
    }

    # Remove HTML tags if any remain
    texto = re.sub(r"<[^>]+>", " ", texto)
    # Normalize whitespace
    texto = re.sub(r"\s+", " ", texto).strip()

    # Extract Escritura info
    m = re.search(r"Esc[^\s]*\s*([^)]*(?:\d{2}/\d{2}/\d{4}))", texto)
    if m:
        data["escritura"] = m.group(1).strip()

    # Split by numbered sections 1) through 10) or similar
    sections = re.split(r"\b(\d+)\)\s*", texto)
    section_map: dict[str, str] = {}
    current_num = None
    for part in sections:
        part = part.strip()
        if re.match(r"^\d+$", part):
            current_num = part
        elif current_num:
            section_map[current_num] = part
            current_num = None

    # 1) Accionistas / socios
    if "1" in section_map:
        raw = section_map["1"]
        data["accionistas_raw"] = raw
        data["accionistas"] = parse_accionistas(raw)

    # 2) Fecha de constitución
    if "2" in section_map:
        raw = section_map["2"]
        m2 = re.search(r"(\d{2}/\d{2}/\d{4})", raw)
        if m2:
            data["fecha_constitucion"] = m2.group(1)
        else:
            data["fecha_constitucion"] = raw.strip()

    # 3) Sometimes missing or merged with 4)

    # 4) Domicilio social
    if "4" in section_map:
        data["domicilio_social"] = section_map["4"].strip()

    # 5) Objeto social
    if "5" in section_map:
        raw = section_map["5"]
        # Remove leading lettered numbering (a), b), c) etc.)
        obj = re.sub(r"\b[a-z]\)\s*", "", raw).strip()
        # Remove trailing content that belongs to section 6+ (look for number followed by ))
        obj = re.split(r"\s+\d+\)\s", obj)[0].strip()
        data["objeto_social"] = obj

    # 6) Plazo
    if "6" in section_map:
        data["plazo"] = section_map["6"].strip()

    # 7) Capital social
    if "7" in section_map:
        raw = section_map["7"]
        m_cap = re.search(r"\$\s*([\d.]+)", raw)
        if m_cap:
            data["capital_social"] = float(m_cap.group(1).replace(".", ""))
        m_acc = re.search(r"(\d[\d.]*)\s*acciones", raw)
        if m_acc:
            data["total_acciones"] = int(m_acc.group(1).replace(".", ""))
        m_vn = re.search(r"V/N\s*\$\s*([\d.]+)", raw)
        if m_vn:
            data["valor_nominal_accion"] = float(m_vn.group(1).replace(".", ""))

        # Extract subscription per accionista
        for part in re.split(r"(?:Suscripción|y|\.)", raw):
            for acc in data["accionistas"]:
                name_part = acc["nombre"].split()[-1] if acc["nombre"] else ""
                if name_part and name_part.upper() in part.upper():
                    m_accs = re.search(r"(\d+)\s*acciones", part)
                    if m_accs:
                        acc["acciones_suscritas"] = int(m_accs.group(1))

    # 8) Administración
    if "8" in section_map:
        data["administracion"] = section_map["8"].strip()

    # 9) Presidente / representación
    if "9" in section_map:
        raw = section_map["9"]
        m_pres = re.search(r"Presidente\s+([A-Za-zÁÉÍÓÚÑáéíóúñ\s]+?)(?:\s+y\s+Suplente|\s+Suplente|$)", raw)
        if m_pres:
            data["presidente"] = m_pres.group(1).strip()
        m_sup = re.search(r"Suplente\s+([A-Za-zÁÉÍÓÚÑáéíóúñ\s]+?)(?:todos|con domicilio|$)", raw)
        if m_sup:
            data["presidente_suplente"] = m_sup.group(1).strip()

    # 10) Cierre del ejercicio
    if "10" in section_map:
        raw = section_map["10"]
        m_cierre = re.search(r"(\d{2}/\d{2})", raw)
        if m_cierre:
            data["cierre_ejercicio"] = m_cierre.group(1)
        else:
            data["cierre_ejercicio"] = raw.strip()

    # Profesional autorizante (al final del texto)
    m_prof = re.search(
        r"Autorizado según[^:]+?\s+([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ\s]+?)"
        r"(?:\s*-\s*T[°º:]|\s*T[°º:]|\s*e\.\s*\d{2}/\d{2}/\d{4}|$)",
        texto,
    )
    if m_prof:
        data["profesional_autorizante"] = m_prof.group(1).strip()

    return data


def parse_accionistas(texto: str) -> list[dict]:
    """Extract individual accionistas from section 1) text."""
    accionistas = []

    # Split by "y" between accionistas (look for " y " followed by uppercase)
    partes = re.split(r"\s+y\s+(?=[A-ZÁÉÍÓÚÑa-z])", texto)

    for parte in partes:
        acc = {}

        # Nombre: capture everything up to the first date or DNI
        m_nom = re.search(r"^([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ\s]+?)(?:\d{2}/\d{2}/\d{4}|\bDNI\b)", parte)
        if m_nom:
            acc["nombre"] = m_nom.group(1).strip()
        else:
            acc["nombre"] = ""

        # Fecha de nacimiento
        m_fn = re.search(r"(\d{2}/\d{2}/\d{4})", parte)
        if m_fn:
            acc["fecha_nacimiento"] = m_fn.group(1)

        # DNI
        m_dni = re.search(r"DNI\s*([\d.]+)", parte)
        if m_dni:
            acc["dni"] = m_dni.group(1)

        # CUIT
        m_cuit = re.search(r"CUIT\s*([\d-]+)", parte)
        if m_cuit:
            acc["cuit"] = m_cuit.group(1)

        # Nacionalidad
        for nac in ["argentino", "argentina", "extranjero", "extranjera"]:
            if nac in parte.lower():
                acc["nacionalidad"] = nac
                break

        # Estado civil
        for ec in ["soltero", "soltera", "casado", "casada", "divorciado",
                     "divorciada", "viudo", "viuda"]:
            if ec in parte.lower():
                acc["estado_civil"] = ec
                break

        # Profesión
        for prof in ["comerciante", "empresario", "empresaria", "abogado", "abogada",
                     "contador", "contadora", "ingeniero", "ingeniera", "medico", "medica",
                     "docente", "empleado", "empleada", "profesional", "productor",
                     "arquitecto", "arquitecta", "economista", "licenciado", "licenciada"]:
            if prof in parte.lower():
                acc["profesion"] = prof
                break

        # Domicilio: text between CUIT/date and keywords like "ambos" or end
        m_addr = re.search(
            r"(?:(?:Av\.|Calle|Pasaje|Ruta|Boulevard|Hipólito|Maipú|Esmeralda)"
            r"\s[^,]+(?:,\s*[^,]+)*?(?:Prov\.\s*[^.]+|CABA))",
            parte,
        )
        if m_addr:
            acc["domicilio"] = m_addr.group(0).strip()
        else:
            # Fallback: grab text after CUIT until "ambos" or end
            m_cuit = re.search(r"CUIT\s*[\d-]+\s*", parte)
            if m_cuit:
                rest = parte[m_cuit.end():]
                end = re.search(r"\b(?:ambos|todos|argentino|soltero|casado)", rest)
                if end:
                    acc["domicilio"] = rest[:end.start()].strip()
                else:
                    acc["domicilio"] = rest.strip()

        if acc.get("nombre"):
            accionistas.append(acc)

    return accionistas


# ── Main scraping pipeline ─────────────────────────────────────────
def scrape_fecha(fecha_str: str) -> list[AvisoSA]:
    """Scrape all 'Constitucion SA' avisos for a given date (YYYYMMDD)."""
    fmt_fecha = fecha_str
    fecha_obj = datetime.strptime(fmt_fecha, "%Y%m%d").date()

    print(f"\n📡 Scraping Boletín Oficial — {fecha_obj.strftime('%d/%m/%Y')}")

    with httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True) as client:
        # 1. Fetch listing page
        print(f"  → Sección segunda: {BASE_URL}/seccion/segunda/{fmt_fecha}")
        html_listing = _get(client, f"/seccion/segunda/{fmt_fecha}")

        # 2. Parse avisos
        raw_avisos = parse_listing(html_listing, fmt_fecha)
        if not raw_avisos:
            print("  ⚠ No se encontraron avisos de Constitución SA.")
            return []

        print(f"  → {len(raw_avisos)} avisos encontrados")

        # 3. Fetch each detail
        avisos: list[AvisoSA] = []
        for i, raw in enumerate(raw_avisos, 1):
            aviso_id = raw["id"]
            empresa = raw["empresa"]
            print(f"  [{i}/{len(raw_avisos)}] {empresa} ({aviso_id})")

            try:
                html_detail = _get(client, raw["url"])
                detail = parse_detail(html_detail)

                aviso = AvisoSA(
                    id_aviso=aviso_id,
                    empresa=detail.get("empresa", empresa),
                    fecha_publicacion=detail.get("fecha_publicacion", ""),
                    url_detalle=raw["url"],
                    rubro=raw["rubro"],
                    fecha_scraping=datetime.now().isoformat(),
                    texto_completo=detail.get("texto_completo", ""),
                )

                # Parse structured data from text
                parsed = parse_sa_text(aviso.texto_completo)
                aviso.escritura = parsed.get("escritura", "")
                aviso.fecha_constitucion = parsed.get("fecha_constitucion", "")
                aviso.domicilio_social = parsed.get("domicilio_social", "")
                aviso.objeto_social = parsed.get("objeto_social", "")
                aviso.plazo = parsed.get("plazo", "")
                aviso.capital_social = parsed.get("capital_social", 0.0)
                aviso.valor_nominal_accion = parsed.get("valor_nominal_accion", 0.0)
                aviso.total_acciones = parsed.get("total_acciones", 0)
                aviso.administracion = parsed.get("administracion", "")
                aviso.presidente = parsed.get("presidente", "")
                aviso.presidente_suplente = parsed.get("presidente_suplente", "")
                aviso.sindicos = parsed.get("sindicos", "")
                aviso.cierre_ejercicio = parsed.get("cierre_ejercicio", "")
                aviso.profesional_autorizante = parsed.get("profesional_autorizante", "")
                for a in parsed.get("accionistas", []):
                    aviso.accionistas.append(Accionista(**a))

                # 4. Download PDF and extract text
                print(f"    → Descargando PDF...")
                pdf_bytes = _download_pdf_aviso(client, aviso_id, "segunda", fmt_fecha)
                if pdf_bytes:
                    aviso.texto_pdf = extract_pdf_text(pdf_bytes)
                    print(f"    → PDF: {len(pdf_bytes)} bytes, {len(aviso.texto_pdf)} chars texto")

                avisos.append(aviso)

            except Exception as e:
                print(f"    ⚠ Error: {e}", file=sys.stderr)
                continue

    return avisos


def aviso_to_dict(a: AvisoSA) -> dict:
    d = asdict(a)
    d["accionistas"] = [asdict(acc) for acc in a.accionistas]
    return d


def save_landing(avisos: list[AvisoSA], fecha_str: str) -> Path:
    """Save scraped data to data/landing/ as JSON."""
    landing = db.get_landing_path()
    out_path = landing / f"boletin_sa_{fecha_str}.json"

    data = {
        "fecha": fecha_str,
        "scraped_at": datetime.now().isoformat(),
        "fuente": "Boletín Oficial - Sección Segunda",
        "rubro": RUBRO_CONSTITUCION_SA,
        "total_avisos": len(avisos),
        "avisos": [aviso_to_dict(a) for a in avisos],
    }

    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"\n💾 Guardado: {out_path}")
    return out_path


# ── CLI ────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Scraper diario del Boletín Oficial — Constitución SA"
    )
    parser.add_argument(
        "--fecha",
        default=date.today().strftime("%Y-%m-%d"),
        help="Fecha en formato YYYY-MM-DD (default: hoy)",
    )
    args = parser.parse_args()

    # Normalize date
    try:
        fecha_obj = datetime.strptime(args.fecha, "%Y-%m-%d").date()
    except ValueError:
        print("Error: fecha debe ser YYYY-MM-DD", file=sys.stderr)
        sys.exit(1)

    fecha_str = fecha_obj.strftime("%Y%m%d")
    avisos = scrape_fecha(fecha_str)

    if avisos:
        save_landing(avisos, fecha_str)
        print(f"\n✅ {len(avisos)} avisos scrapeados correctamente.")
    else:
        print("\n⚠ No se scrapearon avisos.")
        sys.exit(1)


if __name__ == "__main__":
    main()
