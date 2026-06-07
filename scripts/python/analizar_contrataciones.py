"""
Analiza bronze.boletin_contrataciones_adjudicaciones y extrae:
- Entidades (organismos, adjudicatarios)
- Relaciones (organismo → adjudicatario con montos)
- Estructura limpia en silver

Uso:
    uv run python scripts/python/analizar_contrataciones.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path("scripts/python").resolve()))
import db


# ── patrones de extracción ────────────────────────────────────────────

# Expediente: EX-2026-13554501- -APN-DCYC#PFA  o  EX-2025-123456-
RE_EXPEDIENTE = re.compile(
    r'(?:Expediente\s*(?:N[°º]\s*)?:\s*)?'
    r'(EX-\d{4}-\d+-?\s*-?\s*(?:[A-Z0-9#_-]+))',
    re.IGNORECASE,
)

# Monto en pesos
RE_MONTO = re.compile(
    r'(?:'
    r'por\s+(?:un\s+)?(?:importe|monto|suma)\s+total\s+(?:de\s+)?(?:hasta\s+)?'
    r'|Total\s+(?:Adjudicado)?\s*:\s*'
    r'|por\s+un\s+(?:importe|monto|total)\s+total\s+'
    r'|IMPORTE\s+ADJUDICADO:\s*'
    r'|monto\s+total\s+de\s+'
    r'|precio\s+total\s*:\s*'
    r')\s*'
    r'\$?\s*([\d\s.]+(?:,\d{2})?)',
    re.IGNORECASE,
)

# Adjudicatarios: extraer nombres de empresas/personas adjudicadas
RE_ADJUDICATARIO = re.compile(
    r'(?:adjudic[oó]\s*(?:a\s+)?(?:favor\s+de\s+)?(?:la\s+)?(?:firma|empresa)?\s*'
    r'["“]?(?P<n1>[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s./]+?)(?:\s*\(CUIT[\s:]*[\d-]+\))?)'
    r'|'
    r'(?:ADJUDICATARIO:\s*(?P<n2>[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s.]+?)\.)'
    r'|'
    r'(?:Adjudicar\s+(?:al\s+S[rra]\.?\s*)?(?P<n3>[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s.]+?)\s+(?:el\s+Renglón|CUIT))',
    re.IGNORECASE,
)

# CUIT
RE_CUIT = re.compile(
    r'(?:CUIT[\s:]*\s*)?(\d{2}-?\d{8}-?\d)',
    re.IGNORECASE,
)

# Objeto de la contratación
RE_OBJETO = re.compile(
    r'(?:Objeto|OBJETO)\s*(?:de\s+la\s+(?:contratación|licitación))?\s*:\s*'
    r'["“]?(?P<objeto>[^"“\n]+?)["”]?(?:\s*[.\n]|$)',
    re.IGNORECASE,
)

# Estado: fracasada, desierta, adjudicada
RE_ESTADO = re.compile(
    r'(?:DECLARA\s+)?(FRACASADA|DESIERT[OA]|ADJUDIC[OA]D[OA])\s*(?:la\s+)?(?:LICITACIÓN|CONTRATACIÓN)?',
    re.IGNORECASE,
)


def extraer_entidades(texto: str, organismo: str, tipo: str, aviso_id: str, fecha: str) -> list[dict[str, Any]]:
    """Extrae adjudicatarios y sus montos del texto del aviso."""
    resultados: list[dict[str, Any]] = []
    texto_clean = texto.replace('\n', ' ').replace('\r', ' ')

    # Si no hay texto, retornar vacío
    if not texto_clean.strip():
        return resultados

    # Extraer expediente
    expediente = None
    m_exp = RE_EXPEDIENTE.search(texto_clean)
    if m_exp:
        expediente = m_exp.group(1).strip()

    # Extraer objeto
    objeto = None
    m_obj = RE_OBJETO.search(texto_clean)
    if m_obj:
        objeto = m_obj.group("objeto").strip()

    # Extraer estado
    estado = None
    m_est = RE_ESTADO.search(texto_clean)
    if m_est:
        estado = m_est.group(1).strip().title()
    else:
        estado = "Adjudicado"  # default

    # Extraer adjudicatarios
    adjudicatarios: list[dict[str, Any]] = []

    # Método 1: patrón "a favor de la firma XXX"
    for m in RE_ADJUDICATARIO.finditer(texto_clean):
        nombre = (m.group("n1") or m.group("n2") or m.group("n3") or "").strip()
        if nombre and len(nombre) > 3:
            # Buscar CUIT cercano
            cuit = None
            start = max(0, m.start() - 50)
            end = min(len(texto_clean), m.end() + 100)
            ctx = texto_clean[start:end]
            m_cuit = RE_CUIT.search(ctx)
            if m_cuit:
                cuit = m_cuit.group(1).replace('-', '')
            adjudicatarios.append({"nombre": nombre, "cuit": cuit})

    # Método 2: buscar montos en el texto
    montos = []
    for m in RE_MONTO.finditer(texto_clean):
        monto_str = m.group(1).strip().replace(' ', '').replace('.', '').replace(',', '.')
        try:
            montos.append(float(monto_str))
        except ValueError:
            pass

    # Asociar adjudicatarios con montos
    for i, adj in enumerate(adjudicatarios):
        monto = montos[i] if i < len(montos) else None
        resultados.append({
            "aviso_id": aviso_id,
            "boletin_fecha": fecha,
            "organismo": organismo.strip(),
            "tipo_licitacion": tipo.strip(),
            "adjudicatario": adj["nombre"],
            "cuit": adj["cuit"],
            "monto": monto,
            "expediente": expediente,
            "objeto": objeto,
            "estado": estado,
        })

    # Si no se encontraron adjudicatarios pero hay texto, igual registrar
    if not adjudicatarios and texto_clean.strip():
        resultados.append({
            "aviso_id": aviso_id,
            "boletin_fecha": fecha,
            "organismo": organismo.strip(),
            "tipo_licitacion": tipo.strip(),
            "adjudicatario": None,
            "cuit": None,
            "monto": montos[0] if montos else None,
            "expediente": expediente,
            "objeto": objeto,
            "estado": estado or "Sin especificar",
        })

    return resultados


def generar_sql_creacion() -> str:
    """Genera el SQL DDL para crear las tablas silver."""
    return """
    CREATE SCHEMA IF NOT EXISTS silver;

    -- Organismos (entidades contratantes) normalizados
    CREATE TABLE IF NOT EXISTS silver.contrataciones_organismos (
        organismo_id INTEGER PRIMARY KEY,
        nombre VARCHAR NOT NULL UNIQUE,
        tipo VARCHAR,  -- Empresa del Estado, Ministerio, Universidad, etc.
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Adjudicatarios (empresas/personas que ganan licitaciones)
    CREATE TABLE IF NOT EXISTS silver.contrataciones_adjudicatarios (
        adjudicatario_id INTEGER PRIMARY KEY,
        nombre VARCHAR NOT NULL,
        cuit VARCHAR,
        tipo_persona VARCHAR,  -- FISICA / JURIDICA
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Detalle de cada adjudicación (estructurado)
    CREATE TABLE IF NOT EXISTS silver.contrataciones_adjudicaciones_detalle (
        id INTEGER PRIMARY KEY,
        aviso_id VARCHAR,
        boletin_fecha DATE,
        organismo_id INTEGER,
        adjudicatario_id INTEGER,
        tipo_licitacion VARCHAR,
        expediente VARCHAR,
        objeto VARCHAR,
        monto DOUBLE,
        estado VARCHAR,
        pdf_path VARCHAR,
        FOREIGN KEY (organismo_id) REFERENCES silver.contrataciones_organismos(organismo_id),
        FOREIGN KEY (adjudicatario_id) REFERENCES silver.contrataciones_adjudicatarios(adjudicatario_id)
    );

    -- Grafo de relaciones
    CREATE TABLE IF NOT EXISTS silver.contrataciones_edges (
        source_id INTEGER,
        target_id INTEGER,
        edge_type VARCHAR,
        aviso_id VARCHAR,
        monto DOUBLE,
        boletin_fecha DATE
    );
    """


def main() -> int:
    print("🔍 Conectando a DuckDB...")
    con = db.connect()

    # 1. Obtener todos los registros
    print("📥 Leyendo bronze.boletin_contrataciones_adjudicaciones...")
    rows = con.execute("""
        SELECT id, boletin_fecha, organismo, tipo_licitacion, contenido, pdf_path
        FROM bronze.boletin_contrataciones_adjudicaciones
        ORDER BY boletin_fecha, id
    """).fetchall()

    print(f"  {len(rows)} registros obtenidos.")

    # 2. Extraer entidades y relaciones
    print("🔬 Analizando contenido...")
    todas_entidades: dict[str, dict] = {}  # nombre -> {id, tipo}
    todos_adjudicatarios: dict[str, dict] = {}  # nombre -> {id, cuit}
    edges: list[dict] = []
    detalles: list[dict] = []

    for row in rows:
        aviso_id, fecha, organismo, tipo, contenido, pdf_path = row
        resultados = extraer_entidades(
            contenido or "", organismo, tipo, aviso_id, str(fecha)
        )

        for r in resultados:
            # Registrar organismo
            org_nombre = r["organismo"]
            if org_nombre not in todas_entidades:
                todas_entidades[org_nombre] = {
                    "nombre": org_nombre,
                    "tipo": "Organismo Público",
                }

            # Registrar adjudicatario
            adj_nombre = r["adjudicatario"]
            adj_id = None
            if adj_nombre and adj_nombre not in todos_adjudicatarios:
                cuit = r.get("cuit")
                tipo_persona = "JURIDICA" if cuit and cuit.startswith("30") else "FISICA"
                todos_adjudicatarios[adj_nombre] = {
                    "nombre": adj_nombre,
                    "cuit": cuit,
                    "tipo_persona": tipo_persona,
                }

            if adj_nombre:
                adj_id_val = hash(adj_nombre) % 1000000
            else:
                adj_id_val = None

            detalles.append({
                "aviso_id": aviso_id,
                "boletin_fecha": str(fecha),
                "organismo": org_nombre,
                "adjudicatario": adj_nombre,
                "tipo_licitacion": tipo,
                "expediente": r["expediente"],
                "objeto": r["objeto"],
                "monto": r["monto"],
                "estado": r["estado"],
                "pdf_path": str(pdf_path) if pdf_path else None,
            })

            # Edge: organismo → adjudicatario
            if adj_nombre:
                edges.append({
                    "source_name": org_nombre,
                    "target_name": adj_nombre,
                    "edge_type": "ADJUDICA_A",
                    "aviso_id": aviso_id,
                    "monto": r["monto"],
                    "boletin_fecha": str(fecha),
                })

    print(f"  {len(todas_entidades)} organismos únicos")
    print(f"  {len(todos_adjudicatarios)} adjudicatarios únicos")
    print(f"  {len(edges)} relaciones")
    print(f"  {len(detalles)} registros de detalle")

    # 3. Crear tablas silver via MCP (db.py run-sql)
    print("\n🗄️  Creando tablas silver...")
    import subprocess

    def run_sql(sql: str) -> int:
        cmd = ["uv", "run", "python", str(db.PROJECT_ROOT / "scripts" / "python" / "db.py"), "run-sql", sql]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=db.PROJECT_ROOT)
        if result.stdout and "Error" in result.stdout:
            print(f"    ❌ {result.stdout.strip()[:200]}")
            return 1
        if result.returncode != 0:
            print(f"    ❌ {result.stderr.strip()[:200]}")
            return 1
        return 0

    # Kill MCP processes if any
    subprocess.run(
        "kill $(ps aux | grep 'db.py mcp-serve' | grep -v grep | awk '{print $2}') 2>/dev/null; sleep 1",
        shell=True,
    )

    # Crear schema
    run_sql("CREATE SCHEMA IF NOT EXISTS silver;")

    # Tabla organismos
    if todas_entidades:
        values = []
        for i, (nombre, info) in enumerate(todas_entidades.items(), 1):
            nombre_esc = nombre.replace("'", "''")
            values.append(f"({i}, '{nombre_esc}', '{info['tipo']}')")
        run_sql(f"""
            CREATE OR REPLACE TABLE silver.contrataciones_organismos AS
            SELECT * FROM (VALUES {','.join(values)})
            AS t(organismo_id, nombre, tipo);
        """)

    # Tabla adjudicatarios
    if todos_adjudicatarios:
        values = []
        for i, (nombre, info) in enumerate(todos_adjudicatarios.items(), 1):
            nombre_esc = nombre.replace("'", "''")
            cuit = info["cuit"] or ""
            values.append(f"({i}, '{nombre_esc}', '{cuit}', '{info['tipo_persona']}')")
        run_sql(f"""
            CREATE OR REPLACE TABLE silver.contrataciones_adjudicatarios AS
            SELECT * FROM (VALUES {','.join(values)})
            AS t(adjudicatario_id, nombre, cuit, tipo_persona);
        """)

    # Tabla detalle
    if detalles:
        # Crear mapas de IDs
        org_map = {n: i+1 for i, n in enumerate(todas_entidades)}
        adj_map = {n: i+1 for i, n in enumerate(todos_adjudicatarios)}

        values = []
        for i, d in enumerate(detalles, 1):
            org_id = org_map.get(d["organismo"], "NULL")
            adj_id = adj_map.get(d["adjudicatario"]) if d["adjudicatario"] else "NULL"
            monto = d["monto"] if d["monto"] is not None else "NULL"
            exp = (d["expediente"] or "").replace("'", "''")
            obj = (d["objeto"] or "").replace("'", "''")
            estado = (d["estado"] or "").replace("'", "''")
            pdf = (d["pdf_path"] or "").replace("'", "''")
            tipo = d["tipo_licitacion"].replace("'", "''")
            fecha = d["boletin_fecha"]

            values.append(
                f"({i}, '{d['aviso_id']}', '{fecha}', {org_id}, {adj_id}, "
                f"'{tipo}', '{exp}', '{obj}', {monto}, '{estado}', '{pdf}')"
            )

        run_sql(f"""
            CREATE OR REPLACE TABLE silver.contrataciones_adjudicaciones_detalle AS
            SELECT * FROM (VALUES {','.join(values)})
            AS t(id, aviso_id, boletin_fecha, organismo_id, adjudicatario_id,
                 tipo_licitacion, expediente, objeto, monto, estado, pdf_path);
        """)

    # Tabla edges
    if edges:
        org_map = {n: i+1 for i, n in enumerate(todas_entidades)}
        adj_map = {n: i+1 for i, n in enumerate(todos_adjudicatarios)}

        values = []
        for e in edges:
            src = org_map.get(e["source_name"], "NULL")
            tgt = adj_map.get(e["target_name"], "NULL")
            monto = e["monto"] if e["monto"] is not None else "NULL"
            values.append(
                f"({src}, {tgt}, '{e['edge_type']}', '{e['aviso_id']}', {monto}, '{e['boletin_fecha']}')"
            )

        run_sql(f"""
            CREATE OR REPLACE TABLE silver.contrataciones_edges AS
            SELECT * FROM (VALUES {','.join(values)})
            AS t(source_id, target_id, edge_type, aviso_id, monto, boletin_fecha);
        """)

    print("\n✅ Tablas silver creadas exitosamente.")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
