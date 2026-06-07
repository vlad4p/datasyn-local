"""
Analiza los PDFs de contrataciones y extrae entidades + relaciones enriquecidas.
Los PDFs tienen formato tabular: Renglón | Oferente Adjudicado | Monto Total.

Uso:
    uv run python scripts/python/analizar_pdfs_contrataciones.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import fitz  # pymupdf

sys.path.insert(0, str(Path("scripts/python").resolve()))
import db


PDF_DIR = db.get_landing_path() / "boletin_oficial" / "contrataciones_pdfs"
OUTPUT_JSON = db.get_landing_path() / "boletin_oficial" / "contrataciones_pdf_extracciones.json"

# ── patrones de extracción ────────────────────────────────────────────

RE_EXPEDIENTE = re.compile(
    r'(?:EXPTE\.|Expediente)\s*(?:N[°º]\s*)?[:.]?\s*'
    r'(EX-\d{4}-\d+-?\s*-?\s*[A-Z0-9#_/-]+)',
    re.IGNORECASE,
)

RE_CUIT = re.compile(
    r'(?:CUIT[\s:]*N?[°º]?[\s.]*)?(\d{2}-\s*\d{7,8}-\s*\d)',
    re.IGNORECASE,
)

RE_MONTO = re.compile(
    r'(?:Total\s+Adjudicado\s*:\s*|Monto\s+Total\s+Adjudicado\s*|'
    r'importe\s+total\s+de\s+hasta\s+|'
    r'por\s+un\s+(?:importe|monto|total)\s+(?:total\s+)?(?:de\s+)?(?:hasta\s+)?'
    r'|IMPORTE\s+ADJUDICADO\s*:|ADJUDICADO\s*:|'
    r'por\s+la\s+suma\s+total\s+de\s+)'
    r'\$?\s*([\d\s.]+(?:,\d{2})?)',
    re.IGNORECASE,
)

RE_ADJUDICATARIO = re.compile(
    r'(?:Oferente\s+Adjudicado|Adjudicatario|ADJUDICATARIO)'
    r'[\s:]*'
    r'(?P<nombre>[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s.,&]+?)(?:\s*\.|\s*[,;]|\s*CUIT|\s*$)',
    re.IGNORECASE,
)

RE_OBJETO = re.compile(
    r'(?:OBJETO(?:\s+DE\s+LA\s+(?:LICITACIÓN|CONTRATACIÓN))?\s*[:.]?\s*|'
    r'Objeto(?:\s+de\s+la\s+(?:contratación|licitación))?\s*[:.]?\s*)'
    r'(?P<objeto>[^-]+?)(?:\s*\.\s*(?:CONSULTA|LUGAR|PLAZO|Renglón|Se\s+encuentra|$))',
    re.IGNORECASE,
)


def _run_sql(sql: str) -> int:
    """Ejecuta SQL via db.py run-sql."""
    cmd = [
        "uv", "run", "python",
        str(db.PROJECT_ROOT / "scripts" / "python" / "db.py"),
        "run-sql", sql,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=db.PROJECT_ROOT)
    if result.stdout and "✅" not in result.stdout:
        if "Error" in result.stdout:
            print(f"    ❌ {result.stdout.strip()[:200]}")
            return 1
    if result.returncode != 0:
        print(f"    ❌ {result.stderr.strip()[:200]}")
        return 1
    return 0


def extraer_de_pdf(pdf_path: Path) -> list[dict[str, Any]]:
    """Extrae entidades de un PDF."""
    resultados: list[dict[str, Any]] = []

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        print(f"    ⚠️  Error abriendo {pdf_path.name}: {e}")
        return resultados

    for page_num, page in enumerate(doc):
        text = page.get_text()

        # Dividir en bloques por aviso. Cada aviso empieza con organismo + tipo
        # Buscar líneas que parezcan un organismo (MAYÚSCULAS)
        bloque_actual = ""
        bloques: list[str] = []

        for line in text.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue
            # Detectar inicio de nuevo aviso: organismo en mayúsculas seguido de tipo
            if re.match(r'^[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\-.,&]{10,}$', stripped) and not stripped.startswith(('BOLETÍN', 'ADJUDICACIONES', 'Viernes', 'Renglón', 'OBJETO', 'CONSULTA', 'LUGAR', 'PLAZO')):
                if bloque_actual and any(kw in bloque_actual.upper() for kw in ['ADJUDICADO', 'ADJUDICATARIO', 'OFERENTE', 'RENGLÓN', 'EXPEDIENTE']):
                    bloques.append(bloque_actual.strip())
                bloque_actual = stripped + '\n'
            else:
                bloque_actual += stripped + '\n'

        if bloque_actual.strip():
            bloques.append(bloque_actual.strip())

        print(f"    Página {page_num+1}: {len(bloques)} bloques de aviso detectados")

        # Extraer de cada bloque
        for bloque in bloques:
            entidades = _extraer_de_bloque(bloque, pdf_path.name)
            resultados.extend(entidades)

    doc.close()
    return resultados


def _extraer_de_bloque(texto: str, pdf_filename: str) -> list[dict[str, Any]]:
    """Extrae adjudicatarios de un bloque de texto de aviso."""
    resultados: list[dict[str, Any]] = []

    # Expediente
    exp_match = RE_EXPEDIENTE.search(texto)
    expediente = exp_match.group(1).strip() if exp_match else None

    # Objeto
    obj_match = RE_OBJETO.search(texto)
    objeto = obj_match.group("objeto").strip() if obj_match else None

    # Buscar adjudicatarios en el bloque
    # Método 1: "Oferente Adjudicado" o "Adjudicatario"
    for m in RE_ADJUDICATARIO.finditer(texto):
        nombre = m.group("nombre").strip()
        # Limpiar nombre
        nombre = re.sub(r'\s+', ' ', nombre).strip()
        if len(nombre) < 4 or nombre.upper() in ('Nº', 'NRO', 'CUIT', 'SOLPED'):
            continue

        # Buscar CUIT cercano
        cuit = None
        pos = m.end()
        ctx = texto[pos:pos + 200]
        cuit_match = RE_CUIT.search(ctx)
        if cuit_match:
            cuit = cuit_match.group(1).replace(' ', '')

        # Buscar monto cercano
        monto = None
        monto_match = RE_MONTO.search(ctx)
        if monto_match:
            monto_str = monto_match.group(1).strip().replace(' ', '').replace('.', '').replace(',', '.')
            try:
                monto = float(monto_str)
            except ValueError:
                pass

        resultados.append({
            "nombre": nombre,
            "cuit": cuit,
            "monto": monto,
            "expediente": expediente,
            "objeto": objeto,
            "fuente_pdf": pdf_filename,
        })

    # Método 2: Si no encontró adjudicatarios por el nombre, buscar CUITs + montos
    if not resultados:
        cuits = [(m.group(1).replace(' ', ''), m.start()) for m in RE_CUIT.finditer(texto)]
        montos = []
        for m in RE_MONTO.finditer(texto):
            monto_str = m.group(1).strip().replace(' ', '').replace('.', '').replace(',', '.')
            try:
                montos.append((float(monto_str), m.start()))
            except ValueError:
                pass

        # Emparejar CUITs con montos por posición
        for i, (cuit, cuit_pos) in enumerate(cuits):
            monto = montos[i][0] if i < len(montos) else None
            resultados.append({
                "nombre": None,
                "cuit": cuit,
                "monto": monto,
                "expediente": expediente,
                "objeto": objeto,
                "fuente_pdf": pdf_filename,
            })

    return resultados


def main() -> int:
    print("📄 Analizando PDFs de contrataciones...")
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    print(f"  {len(pdfs)} PDFs encontrados")

    todas_extracciones: list[dict[str, Any]] = []

    for pdf_path in pdfs:
        print(f"📎 {pdf_path.name}")
        resultados = extraer_de_pdf(pdf_path)
        todas_extracciones.extend(resultados)
        print(f"    → {len(resultados)} adjudicatarios extraídos")

    print(f"\n📊 Total: {len(todas_extracciones)} extracciones de PDFs")

    # Guardar JSON
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(todas_extracciones, ensure_ascii=False, indent=2))
    print(f"💾 JSON guardado: {OUTPUT_JSON}")

    # ── Preparar inserts para DuckDB ──
    # Deduplicar adjudicatarios por (nombre, cuit)
    adjudicatarios_unicos: dict[str, dict[str, Any]] = {}
    for e in todas_extracciones:
        key = (e.get("nombre") or e.get("cuit") or "").strip().upper()
        if not key:
            continue
        if key not in adjudicatarios_unicos:
            cuit = e.get("cuit") or ""
            adjudicatarios_unicos[key] = {
                "nombre": e.get("nombre") or "",
                "cuit": cuit.replace(' ', ''),
                "tipo_persona": "JURIDICA" if cuit.startswith("30") or cuit.startswith("33") else "FISICA",
            }

    print(f"\n🔬 {len(adjudicatarios_unicos)} adjudicatarios únicos de PDFs")

    # Kill MCP y ejecutar inserts
    subprocess.run(
        "kill $(ps aux | grep 'db.py mcp-serve' | grep -v grep | awk '{print $2}') 2>/dev/null; sleep 1",
        shell=True,
    )

    # Insertar nuevos adjudicatarios (los que no existen)
    if adjudicatarios_unicos:
        # Obtener max ID actual
        con = db.connect()
        max_id_row = con.execute(
            "SELECT COALESCE(MAX(adjudicatario_id), 0) FROM silver.contrataciones_adjudicatarios"
        ).fetchone()
        max_id = max_id_row[0] if max_id_row else 0
        con.close()

        # Obtener nombres existentes
        con = db.connect()
        existentes = set(
            r[0].upper()
            for r in con.execute("SELECT UPPER(nombre) FROM silver.contrataciones_adjudicatarios").fetchall()
        )
        con.close()

        nuevos = []
        for key, info in adjudicatarios_unicos.items():
            if key not in existentes and info["nombre"]:
                max_id += 1
                nombre_esc = info["nombre"].replace("'", "''")
                cuit = (info["cuit"] or "").replace("'", "")
                nuevos.append(f"({max_id}, '{nombre_esc}', '{cuit}', '{info['tipo_persona']}')")

        if nuevos:
            print(f"  ➕ Insertando {len(nuevos)} nuevos adjudicatarios...")
            sql = f"""
                INSERT INTO silver.contrataciones_adjudicatarios (adjudicatario_id, nombre, cuit, tipo_persona)
                VALUES {','.join(nuevos)};
            """
            _run_sql(sql)
        else:
            print("  ✅ Todos los adjudicatarios ya existen en la tabla.")

    print("\n✅ Análisis de PDFs completado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
