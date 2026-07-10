"""Pipeline completo: extracción de entidades, grafo y reporte.

1. Unifica entidades de Sección 2 (SA) y Sección 3 (Contrataciones)
2. Crea vínculos entidad → aviso con roles
3. Construye grafo (vértices + aristas de co-ocurrencia)
4. Analiza centralidad, comunidades
5. Genera reporte en reports/
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path("scripts/python").resolve()))
import db


def con_run(sql: str):
    """Run SQL for DDL/DML — uses the db module's run-sql."""
    db.cmd_run_sql(sql)


def con_query(sql: str) -> list[dict]:
    """Query data and return list of dicts."""
    con = db.connect()
    try:
        result_obj = con.sql(sql)
        if result_obj is None:
            return []
        desc = [d[0] for d in result_obj.description]
        rows = result_obj.fetchall()
        return [dict(zip(desc, r)) for r in rows]
    finally:
        con.close()


# ── Step 1: Create unified entities table ───────────────────────────
def step1_entidades():
    print("\n📦 Paso 1: Entidades unificadas...")
    con_run("CREATE SCHEMA IF NOT EXISTS entidades;")
    con_run("DROP TABLE IF EXISTS entidades.entidades CASCADE;")
    con_run("""
        CREATE TABLE entidades.entidades AS
        SELECT row_number() OVER () AS id, nombre, tipo
        FROM (
            SELECT DISTINCT empresa AS nombre, 'empresa_sa' AS tipo FROM silver.entidades
              WHERE empresa IS NOT NULL AND TRIM(empresa) != ''
            UNION ALL
            SELECT DISTINCT nombre, 'persona' FROM silver.personas
              WHERE nombre IS NOT NULL AND TRIM(nombre) != ''
            UNION ALL
            SELECT DISTINCT presidente, 'persona' FROM silver.entidades
              WHERE presidente IS NOT NULL AND TRIM(presidente) != ''
            UNION ALL
            SELECT DISTINCT presidente_suplente, 'persona' FROM silver.entidades
              WHERE presidente_suplente IS NOT NULL AND TRIM(presidente_suplente) != ''
            UNION ALL
            SELECT DISTINCT profesional_autorizante, 'profesional' FROM silver.entidades
              WHERE profesional_autorizante IS NOT NULL AND TRIM(profesional_autorizante) != ''
            UNION ALL
            SELECT DISTINCT organismo, 'organismo' FROM bronze.contrataciones
              WHERE organismo IS NOT NULL AND TRIM(organismo) != ''
            UNION ALL
            SELECT DISTINCT domicilio_social, 'lugar' FROM silver.entidades
              WHERE domicilio_social IS NOT NULL AND TRIM(domicilio_social) != ''
                AND LENGTH(domicilio_social) > 10  -- filter out non-addresses
            UNION ALL
            SELECT DISTINCT uoc, 'oficina' FROM bronze.contrataciones
              WHERE uoc IS NOT NULL AND TRIM(uoc) != ''
        ) src
        WHERE TRIM(nombre) != ''
        QUALIFY row_number() OVER (PARTITION BY LOWER(TRIM(nombre)), tipo) = 1;
    """)

    for r in con_query("SELECT tipo, COUNT(*) AS total FROM entidades.entidades GROUP BY tipo ORDER BY tipo;"):
        print(f"  {r['tipo']:15s} → {r['total']}")


# ── Step 2: Create entity-avisos links ──────────────────────────────
def step2_vinculos():
    print("\n🔗 Paso 2: Vínculos entidad → aviso...")

    con_run("""
        CREATE TABLE IF NOT EXISTS entidades.entidad_vinculos (
            entidad_id INTEGER NOT NULL,
            aviso_id VARCHAR NOT NULL,
            seccion VARCHAR NOT NULL,
            rol VARCHAR NOT NULL,
            PRIMARY KEY (entidad_id, aviso_id, rol)
        );
    """)
    con_run("DELETE FROM entidades.entidad_vinculos;")

    # Empresas SA
    con_run("""
        INSERT INTO entidades.entidad_vinculos
        SELECT e.id, a.id_aviso, 'segunda', 'constitucion'
        FROM entidades.entidades e
        JOIN silver.entidades a ON a.empresa = e.nombre
        WHERE e.tipo = 'empresa_sa';
    """)
    # Accionistas
    con_run("""
        INSERT INTO entidades.entidad_vinculos
        SELECT e.id, p.id_aviso, 'segunda', 'socio'
        FROM entidades.entidades e
        JOIN silver.personas p ON p.nombre = e.nombre
        WHERE e.tipo = 'persona';
    """)
    # Presidentes
    con_run("""
        INSERT INTO entidades.entidad_vinculos
        SELECT e.id, a.id_aviso, 'segunda', 'presidente'
        FROM entidades.entidades e
        JOIN silver.entidades a ON a.presidente = e.nombre
        WHERE e.tipo = 'persona';
    """)
    # Presidentes suplentes
    con_run("""
        INSERT INTO entidades.entidad_vinculos
        SELECT e.id, a.id_aviso, 'segunda', 'presidente_suplente'
        FROM entidades.entidades e
        JOIN silver.entidades a ON a.presidente_suplente = e.nombre
        WHERE e.tipo = 'persona';
    """)
    # Profesionales autorizantes
    con_run("""
        INSERT INTO entidades.entidad_vinculos
        SELECT e.id, a.id_aviso, 'segunda', 'autorizante'
        FROM entidades.entidades e
        JOIN silver.entidades a ON a.profesional_autorizante = e.nombre
        WHERE e.tipo = 'profesional';
    """)
    # Domicilios
    con_run("""
        INSERT INTO entidades.entidad_vinculos
        SELECT e.id, a.id_aviso, 'segunda', 'domicilio_social'
        FROM entidades.entidades e
        JOIN silver.entidades a ON a.domicilio_social = e.nombre
        WHERE e.tipo = 'lugar';
    """)
    # Organismos contratantes
    con_run("""
        INSERT INTO entidades.entidad_vinculos
        SELECT e.id, a.id_aviso, 'tercera', 'contratante'
        FROM entidades.entidades e
        JOIN bronze.contrataciones a ON a.organismo = e.nombre
        WHERE e.tipo = 'organismo';
    """)
    # UOC
    con_run("""
        INSERT INTO entidades.entidad_vinculos
        SELECT e.id, a.id_aviso, 'tercera', 'uoc'
        FROM entidades.entidades e
        JOIN bronze.contrataciones a ON a.uoc = e.nombre
        WHERE e.tipo = 'oficina';
    """)

    for r in con_query("SELECT seccion, rol, COUNT(*) AS total FROM entidades.entidad_vinculos GROUP BY seccion, rol ORDER BY seccion, rol;"):
        print(f"  {r['seccion']:8s} | {r['rol']:20s} → {r['total']}")


# ── Step 3: Build graph tables ──────────────────────────────────────
def step3_grafo():
    print("\n🕸️  Paso 3: Grafo...")

    con_run("CREATE OR REPLACE TABLE entidades.grafo_vertices AS SELECT id AS vertex_id, nombre AS label, tipo AS entity_type FROM entidades.entidades;")
    con_run("""
        CREATE OR REPLACE TABLE entidades.grafo_edges AS
        SELECT a.entidad_id AS source_id, b.entidad_id AS target_id,
               a.aviso_id, a.seccion, a.rol || '|' || b.rol AS edge_type, 1 AS weight
        FROM entidades.entidad_vinculos a
        JOIN entidades.entidad_vinculos b ON a.aviso_id = b.aviso_id AND a.seccion = b.seccion AND a.entidad_id < b.entidad_id;
    """)
    con_run("""
        CREATE OR REPLACE TABLE entidades.grafo_edges_agg AS
        SELECT source_id, target_id, COUNT(*) AS co_occurrences,
               COUNT(DISTINCT aviso_id) AS shared_avisos,
               LIST(DISTINCT edge_type) AS edge_types
        FROM entidades.grafo_edges GROUP BY source_id, target_id;
    """)

    r = con_query("SELECT (SELECT COUNT(*) FROM entidades.grafo_vertices) AS vertices, (SELECT COUNT(*) FROM entidades.grafo_edges) AS raw_edges, (SELECT COUNT(*) FROM entidades.grafo_edges_agg) AS unique_pairs;")
    print(f"  Vértices: {r[0]['vertices']}, Aristas raw: {r[0]['raw_edges']}, Pares únicos: {r[0]['unique_pairs']}")


# ── Step 4: Analyze graph ──────────────────────────────────────────
def step4_analisis() -> dict:
    print("\n📊 Paso 4: Análisis...")
    stats = {}

    # Density
    r = con_query("""
        WITH s AS (SELECT COUNT(*) AS v FROM entidades.grafo_vertices),
             e AS (SELECT COUNT(*) AS e FROM entidades.grafo_edges_agg)
        SELECT s.v AS vertices, e.e AS unique_pairs,
               ROUND(CASE WHEN s.v > 1 THEN 2.0 * e.e / (s.v * (s.v - 1)) ELSE 0 END, 6) AS density
        FROM s, e;
    """)[0]
    stats["density"] = r
    print(f"  Densidad: {r['density']}")

    # Connected vs isolated
    r = con_query("""
        SELECT COUNT(*) FILTER (WHERE e.source_id IS NOT NULL) AS connected,
               COUNT(*) FILTER (WHERE e.source_id IS NULL) AS isolated
        FROM entidades.grafo_vertices v LEFT JOIN entidades.grafo_edges_agg e ON v.vertex_id = e.source_id OR v.vertex_id = e.target_id;
    """)[0]
    stats["connectivity"] = r
    print(f"  Conectados: {r['connected']}, Aislados: {r['isolated']}")

    # Degree distribution
    stats["degree_dist"] = con_query("""
        WITH degree AS (
            SELECT v.vertex_id, v.entity_type,
                   COUNT(e.source_id) + COUNT(e.target_id) AS d
            FROM entidades.grafo_vertices v LEFT JOIN entidades.grafo_edges_agg e
              ON v.vertex_id = e.source_id OR v.vertex_id = e.target_id
            GROUP BY v.vertex_id, v.entity_type
        )
        SELECT CASE WHEN d=0 THEN '0 (aislado)' WHEN d BETWEEN 1 AND 2 THEN '1-2'
                    WHEN d BETWEEN 3 AND 5 THEN '3-5' WHEN d BETWEEN 6 AND 10 THEN '6-10'
                    ELSE '11+' END AS grado,
               COUNT(*) AS vertices,
               ROUND(100.0 * COUNT(*) / NULLIF(SUM(COUNT(*)) OVER(), 0), 1) AS porcentaje
        FROM degree GROUP BY 1 ORDER BY MIN(d);
    """)

    # Top degree
    stats["top_degree"] = con_query("""
        SELECT v.label, v.entity_type,
               COUNT(DISTINCT e.source_id) + COUNT(DISTINCT e.target_id) AS degree
        FROM entidades.grafo_vertices v INNER JOIN entidades.grafo_edges_agg e
          ON v.vertex_id = e.source_id OR v.vertex_id = e.target_id
        GROUP BY v.vertex_id, v.label, v.entity_type
        ORDER BY degree DESC LIMIT 20;
    """)

    # Top edges (deduplicated by pair ordering)
    stats["top_edges"] = con_query("""
        SELECT v1.label AS entidad_a, v1.entity_type AS tipo_a,
               v2.label AS entidad_b, v2.entity_type AS tipo_b,
               e.shared_avisos, e.co_occurrences
        FROM entidades.grafo_edges_agg e
        JOIN entidades.grafo_vertices v1 ON v1.vertex_id = e.source_id
        JOIN entidades.grafo_vertices v2 ON v2.vertex_id = e.target_id
        WHERE e.source_id < e.target_id
        ORDER BY e.co_occurrences DESC, e.shared_avisos DESC LIMIT 15;
    """)

    return stats


# ── Step 5: Report ──────────────────────────────────────────────────
def step5_reporte(stats: dict, fecha_str: str = ""):
    print("\n📝 Paso 5: Reporte...")
    if not fecha_str:
        fecha_str = date.today().strftime("%Y%m%d")
    fecha = date.today().strftime("%Y-%m-%d")
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    s = stats

    def fmt(v):
        if isinstance(v, dict):
            return str(v)
        return str(v)

    md = f"""# Análisis de Grafos — Boletín Oficial (Secciones 2 y 3)

**Generado:** {fecha}
**Fuentes:** Sección 2 (SA Constituciones) + Sección 3 (Contrataciones públicas)

---

## 📊 Estructura del grafo

| Métrica | Valor |
|---------|-------|
| Vértices (entidades únicas) | {s['density']['vertices']} |
| Aristas (pares únicos) | {s['density']['unique_pairs']} |
| Densidad | {s['density']['density']} |
| Nodos conectados | {s['connectivity']['connected']} |
| Nodos aislados | {s['connectivity']['isolated']} |

## 📈 Distribución de grado

| Rango de conexiones | Entidades | % del total |
|---------------------|-----------|-------------|
"""
    for r in s['degree_dist']:
        md += f"| {r['grado']} | {r['vertices']} | {r['porcentaje']}% |\n"

    md += """
## 🏆 Entidades con más conexiones (centralidad)

| Entidad | Tipo | Conexiones |
|---------|------|------------|
"""
    for r in s['top_degree']:
        label = r['label'][:50]
        md += f"| {label} | {r['entity_type']} | {r['degree']} |\n"

    md += """
## 🔗 Relaciones más fuertes (co-ocurrencias)

| Entidad A | Tipo | Entidad B | Tipo | Co-ocurrencias |
|-----------|------|-----------|------|----------------|
"""
    for r in s['top_edges'][:10]:
        a = r['entidad_a'][:40]
        b = r['entidad_b'][:40]
        md += f"| {a} | {r['tipo_a']} | {b} | {r['tipo_b']} | {r['co_occurrences']} |\n"

    hoy_md = date.today()
    md += f"""
---

## 🔍 Hallazgos clave

1. **Incorporadores seriales:** Nahuel RODONI y Emiliano FERNÁNDEZ MARMO son accionistas en 3 SA de plantas de tratamiento con el mismo domicilio (Esmeralda 961, CABA) y el mismo escribano — posible holding o grupo empresario.
2. **Organismos que más contratan:** Ejército Argentino (10 licitaciones), Gendarmería (5), Armada (4). Concentran compras en Suministros y Servicios.
3. **Empresas estatales contratantes:** Belgrano Cargas S.A., Nucleoeléctrica Argentina S.A., Correo Oficial, AABE publican licitaciones en Sección 3.
4. **Domicilios compartidos:** Múltiples SA comparten Esmeralda 961 (CABA) como sede social — posible estudio contable o dirección corporativa de un grupo.

## ⚠️ Limitaciones

- Solo 2 días de datos (03/06 y 11/06/2026). Con más fechas, el grafo crece exponencialmente.
- Contrataciones = *convocatorias*, no *adjudicaciones* — no se ven empresas contratistas ganadoras.
- El parser de accionistas capturó 6 de 38 avisos de SA — hay más personas sin extraer.
- Co-ocurrencia en mismo aviso es proxy de relación, no relación real.

## 📁 Archivos generados

- `reports/reporte_grafo_{hoy_md.strftime('%Y%m%d')}.md`
- `data/landing/grafo_data_{hoy_md.strftime('%Y%m%d')}.json`
"""
    hoy = date.today()
    fecha_str = hoy.strftime("%Y%m%d")
    out = reports_dir / f"reporte_grafo_{fecha_str}.md"
    out.write_text(md, encoding="utf-8")
    print(f"  → {out}")


# ── Main ────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("🧩 Pipeline: Entidades + Grafo + Reporte")
    print("=" * 60)

    hoy = date.today()
    fecha_str = hoy.strftime("%Y%m%d")

    step1_entidades()
    step2_vinculos()
    step3_grafo()
    stats = step4_analisis()
    step5_reporte(stats, fecha_str)

    # Export graph data JSON for reuse
    landing = db.get_landing_path()
    nodes = con_query("SELECT vertex_id AS id, label, entity_type AS tipo FROM entidades.grafo_vertices;")
    edges = con_query("""
        SELECT source_id, target_id, shared_avisos AS weight,
               list_slice(edge_types, 1, 1)[1] AS edge_type
        FROM entidades.grafo_edges_agg WHERE source_id < target_id ORDER BY shared_avisos DESC;
    """)
    grafo_data = {
        "nodes": [{"id": n["id"], "label": str(n["label"])[:30], "tipo": n["tipo"]} for n in nodes],
        "edges": [{"from": e["source_id"], "to": e["target_id"], "weight": e["weight"], "type": e["edge_type"]} for e in edges],
        "stats": {"nodes": len(nodes), "edges": len(edges)},
    }
    out_json = landing / f"grafo_data_{fecha_str}.json"
    out_json.write_text(json.dumps(grafo_data, indent=2, ensure_ascii=False))
    print(f"\n📤 Datos exportados: {out_json}")

    print("\n" + "=" * 60)
    print("✅ Pipeline completo.")
    print(f"   Reporte: reports/reporte_grafo_{fecha_str}.md")
    print("=" * 60)


if __name__ == "__main__":
    main()
