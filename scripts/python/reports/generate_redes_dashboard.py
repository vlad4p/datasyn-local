#!/usr/bin/env python3
"""Generate unified redes dashboard: CSV datasets + HTML shell."""

from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import db  # noqa: E402

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "redes_dashboard.html"

NODE_STYLE = {
    "autor": {"color": "#f07178", "shape": "dot", "size": 18},
    "cuenta_objetivo": {"color": "#3dd68c", "shape": "box", "size": 28},
    "narrativa": {"color": "#a78bfa", "shape": "diamond", "size": 22},
    "cohorte_dia": {"color": "#60a5fa", "shape": "hexagon", "size": 24},
}

EDGE_STYLE = {
    "ataca": {"color": "#f0717866", "dashes": False, "width_factor": 0.15},
    "co_rafaga": {"color": "#fbbf2488", "dashes": True, "width_factor": 2},
    "usa_narrativa": {"color": "#a78bfa55", "dashes": True, "width_factor": 0.5},
    "en_cohorte": {"color": "#60a5fa66", "dashes": True, "width_factor": 0.3},
}

# (filename, sql) — exported to data/<filename>
SQL_EXPORTS: list[tuple[str, str]] = [
    (
        "sentimiento_resumen.csv",
        "SELECT * FROM gold.v_sentimiento_resumen_cuenta ORDER BY cuenta_slug",
    ),
    (
        "sentimiento_por_cuenta.csv",
        """
        SELECT cuenta_slug, cuenta_nombre, plataforma, posicion, comentarios, pct_dentro_cuenta
        FROM gold.v_sentimiento_por_cuenta
        ORDER BY cuenta_slug, plataforma, comentarios DESC
        """,
    ),
    (
        "sentimiento_temporal.csv",
        """
        SELECT cuenta_slug, CAST(dia AS VARCHAR) AS dia, posicion, comentarios
        FROM gold.v_sentimiento_temporal
        WHERE cuenta_slug IS NOT NULL AND dia IS NOT NULL
        ORDER BY dia, cuenta_slug
        """,
    ),
    (
        "narrativa_distribucion.csv",
        """
        SELECT cuenta_slug, plataforma, narrativa, comentarios, pct_narrativa
        FROM gold.v_narrativa_distribucion
        ORDER BY cuenta_slug, comentarios DESC
        """,
    ),
    (
        "narrativa_temporal.csv",
        """
        SELECT cuenta_slug, CAST(semana AS VARCHAR) AS semana, narrativa, comentarios
        FROM gold.v_narrativa_temporal
        WHERE cuenta_slug IS NOT NULL
        ORDER BY semana, cuenta_slug
        """,
    ),
    (
        "grafo_coocurrencia.csv",
        """
        SELECT source_id, target_id, cuenta_slug, peso_total, contenidos_distintos
        FROM gold.grafo_edges_agg_narrativa
        WHERE edge_type = 'narrativa_coocurrencia'
        ORDER BY peso_total DESC
        LIMIT 20
        """,
    ),
    (
        "grafo_narrativa_cuenta.csv",
        """
        SELECT source_id, target_id, cuenta_slug, peso_total
        FROM gold.grafo_edges_agg_narrativa
        WHERE edge_type = 'narrativa_cuenta'
        ORDER BY peso_total DESC
        """,
    ),
    (
        "trolls_top10.csv",
        """
        SELECT plataforma, ranking, autor_nombre, autor_id, comentarios_troll,
               dias_activos, CAST(cuentas_slug AS VARCHAR) AS cuentas_slug
        FROM gold.v_trolls_top10
        ORDER BY plataforma, ranking
        """,
    ),
    (
        "trolls_temporal.csv",
        """
        SELECT plataforma, CAST(dia AS VARCHAR) AS dia, cuenta_slug,
               comentarios_troll, autores_troll, spam_enlaces, insultos, conspiranoia
        FROM gold.v_trolls_temporal
        WHERE cuenta_slug IS NOT NULL
        ORDER BY dia
        """,
    ),
    (
        "trolls_grupos.csv",
        """
        SELECT plataforma, autor_nombre, comentarios_troll, cuentas_distintas,
               CAST(cuentas_objetivo AS VARCHAR) AS cuentas_objetivo
        FROM gold.v_trolls_grupos_multobjetivo
        ORDER BY comentarios_troll DESC
        LIMIT 15
        """,
    ),
    (
        "trolls_rafagas.csv",
        """
        SELECT plataforma, autor_nombre, cuenta_slug, CAST(dia AS VARCHAR) AS dia,
               comentarios_en_dia, minutos_span
        FROM gold.v_trolls_rafagas
        ORDER BY comentarios_en_dia DESC
        LIMIT 15
        """,
    ),
    (
        "trolls_rafagas_dia.csv",
        """
        SELECT plataforma, cuenta_slug, CAST(dia AS VARCHAR) AS dia,
               autores_con_rafaga, eventos_rafaga, comentarios_en_rafagas,
               comentarios_por_autor, max_comentarios_un_autor, rafaga_mas_intensa_min
        FROM gold.v_trolls_rafagas_dia
        ORDER BY autores_con_rafaga DESC, comentarios_en_rafagas DESC
        LIMIT 30
        """,
    ),
    (
        "trolls_rafagas_por_autor.csv",
        """
        SELECT plataforma, autor_nombre, dias_con_rafaga, comentarios_rafaga,
               cuentas_objetivo, CAST(cuentas_slug AS VARCHAR) AS cuentas_slug,
               CAST(primera_rafaga AS VARCHAR) AS primera_rafaga,
               CAST(ultima_rafaga AS VARCHAR) AS ultima_rafaga,
               promedio_comentarios_rafaga
        FROM gold.v_trolls_rafagas_por_autor
        ORDER BY comentarios_rafaga DESC
        LIMIT 20
        """,
    ),
    (
        "trolls_rafagas_resumen.csv",
        "SELECT * FROM gold.v_trolls_rafagas_resumen",
    ),
    (
        "trolls_rafagas_dia_temporal.csv",
        """
        SELECT CAST(dia AS VARCHAR) AS dia, plataforma,
               SUM(autores_con_rafaga) AS autores_con_rafaga,
               SUM(comentarios_en_rafagas) AS comentarios_en_rafagas
        FROM gold.v_trolls_rafagas_dia
        GROUP BY dia, plataforma
        ORDER BY dia
        """,
    ),
    (
        "entidades_tipo_cuenta.csv",
        """
        SELECT tipo_cuenta, COUNT(*) AS n
        FROM gold.v_entidades_resumen
        GROUP BY tipo_cuenta
        ORDER BY n DESC
        """,
    ),
    (
        "entidades_confianza.csv",
        """
        SELECT confianza_nombre, COUNT(*) AS n
        FROM gold.v_entidades_resumen
        GROUP BY confianza_nombre
        ORDER BY n DESC
        """,
    ),
    (
        "entidades_nombre_fuente.csv",
        """
        SELECT nombre_inferido_fuente, COUNT(*) AS n
        FROM gold.v_entidades_resumen
        GROUP BY nombre_inferido_fuente
        ORDER BY n DESC
        """,
    ),
    (
        "entidades_evaluacion.csv",
        """
        SELECT evaluacion_multicuenta, COUNT(*) AS n
        FROM gold.v_entidades_resumen
        GROUP BY evaluacion_multicuenta
        ORDER BY n DESC
        """,
    ),
    (
        "entidades_trackeadas.csv",
        """
        SELECT canonical_key, nombre_inferido, tipo_cuenta,
               array_to_string(redes, ', ') AS redes,
               evaluacion_multicuenta, perfiles_en_grupo, persona_grupo_id,
               is_pts, is_tracked
        FROM gold.v_entidades_resumen
        WHERE is_tracked OR is_pts
        ORDER BY canonical_key
        """,
    ),
    (
        "entidades_grupos.csv",
        """
        SELECT persona_grupo_id, n_perfiles, nombre_persona_inferido,
               tipo_grupo, confianza_grupo,
               array_to_string(canonical_keys, ' | ') AS canonical_keys,
               array_to_string(redes_en_grupo, ', ') AS redes_en_grupo
        FROM gold.v_entidades_grupos
        WHERE n_perfiles > 1 OR tipo_grupo != 'cuenta_unica'
        ORDER BY n_perfiles DESC
        """,
    ),
    (
        "entidades_vinculos.csv",
        """
        SELECT canonical_key_a, canonical_key_b, tipo_vinculo, confianza, detalle
        FROM gold.v_entidades_vinculos
        WHERE canonical_key_a <> canonical_key_b
        ORDER BY confianza, tipo_vinculo
        LIMIT 20
        """,
    ),
    (
        "entidades_nombres_frecuentes.csv",
        """
        SELECT nombre_inferido AS nombre, COUNT(*) AS n_cuentas
        FROM gold.v_entidades_resumen
        WHERE NOT es_organizacion AND confianza_nombre = 'alta'
        GROUP BY nombre_inferido
        HAVING COUNT(*) >= 3
        ORDER BY n_cuentas DESC
        LIMIT 20
        """,
    ),
    (
        "comentarios_posicion_plataforma.csv",
        """
        SELECT plataforma, posicion, COUNT(*) AS n
        FROM gold.v_comentarios_clasificados
        GROUP BY plataforma, posicion
        ORDER BY plataforma, n DESC
        """,
    ),
    (
        "comentarios_clusters_texto.csv",
        """
        SELECT ocurrencias, posicion_modal, LEFT(texto_ejemplo, 120) AS muestra
        FROM gold.v_comentarios_clusters_texto
        WHERE texto_norm NOT LIKE 'formato%'
        ORDER BY ocurrencias DESC
        LIMIT 15
        """,
    ),
    (
        "comentarios_clusters_resumen.csv",
        """
        SELECT resumen, ocurrencias, plataformas
        FROM gold.v_comentarios_clusters_resumen
        ORDER BY ocurrencias DESC
        LIMIT 15
        """,
    ),
    (
        "volumenes_cuenta.csv",
        """
        SELECT cuenta_slug, cuenta_nombre, plataforma, posicion, comentarios
        FROM gold.v_sentimiento_por_cuenta
        ORDER BY cuenta_slug, plataforma, comentarios DESC
        """,
    ),
]

# Maps exported CSV filename → JS DATA key in redes_dashboard.html
CSV_KEY_MAP: dict[str, str] = {
    "kpis.csv": "kpis",
    "sentimiento_resumen.csv": "sentimiento_resumen",
    "sentimiento_por_cuenta.csv": "sentimiento_por_cuenta",
    "sentimiento_temporal.csv": "sentimiento_temporal",
    "narrativa_distribucion.csv": "narrativa_distribucion",
    "narrativa_temporal.csv": "narrativa_temporal",
    "grafo_coocurrencia.csv": "grafo_coocurrencia",
    "grafo_narrativa_cuenta.csv": "grafo_narrativa_cuenta",
    "trolls_top10.csv": "trolls_top10",
    "trolls_temporal.csv": "trolls_temporal",
    "trolls_grupos.csv": "trolls_grupos",
    "trolls_rafagas.csv": "trolls_rafagas",
    "trolls_rafagas_dia.csv": "trolls_rafagas_dia",
    "trolls_rafagas_por_autor.csv": "trolls_rafagas_por_autor",
    "trolls_rafagas_resumen.csv": "trolls_rafagas_resumen",
    "trolls_rafagas_dia_temporal.csv": "trolls_rafagas_dia_temporal",
    "grafo_nodes.csv": "grafo_nodes",
    "grafo_edges.csv": "grafo_edges",
    "entidades_tipo_cuenta.csv": "entidades_tipo",
    "entidades_confianza.csv": "entidades_confianza",
    "entidades_evaluacion.csv": "entidades_evaluacion",
    "entidades_trackeadas.csv": "entidades_trackeadas",
    "entidades_grupos.csv": "entidades_grupos",
    "entidades_vinculos.csv": "entidades_vinculos",
    "comentarios_posicion_plataforma.csv": "comentarios_posicion",
    "comentarios_clusters_texto.csv": "clusters_texto",
    "comentarios_clusters_resumen.csv": "clusters_resumen",
    "volumenes_cuenta.csv": "volumenes_cuenta",
}


def _export_df_csv(con, sql: str, path: Path) -> int:
    df = con.sql(sql).df()
    for col in df.columns:
        dtype = str(df[col].dtype).lower()
        if "datetime" in dtype or "timestamp" in dtype:
            df[col] = df[col].astype(str)
    df.to_csv(path, index=False)
    return len(df)


def _read_csv_df(path: Path):
    import pandas as pd

    return pd.read_csv(path)


def _csv_records(path: Path) -> list[dict]:
    if not path.is_file() or path.stat().st_size == 0:
        return []
    df = _read_csv_df(path)
    return json.loads(df.to_json(orient="records"))


def build_embedded_data(data_dir: Path) -> dict:
    """Load exported CSVs into the JS DATA object (self-contained HTML)."""
    embedded: dict[str, list[dict]] = {}
    for filename, key in CSV_KEY_MAP.items():
        embedded[key] = _csv_records(data_dir / filename)
    return embedded


def _top_author_ids(con, limit: int = 35) -> set[str]:
    rows = con.sql(
        f"""
        SELECT source_id
        FROM gold.grafo_edges_agg_trolls
        WHERE edge_type = 'ataca' AND source_id LIKE 'autor:%'
        GROUP BY source_id
        ORDER BY SUM(peso_total) DESC
        LIMIT {limit}
        """
    ).fetchall()
    return {r[0] for r in rows}


def _short_label(label: str, tipo: str) -> str:
    if tipo == "autor" and label and len(label) > 14:
        return label[:12] + "…"
    if tipo == "cohorte_dia":
        return label.replace(" 00:00:00", "")[:16]
    if tipo == "narrativa":
        return label.replace("_", " ")[:18]
    return label or "?"


def _node_tooltip(row) -> str:
    parts = [str(row.label), f"tipo: {row.tipo}"]
    if getattr(row, "plataforma", None):
        parts.append(f"plataforma: {row.plataforma}")
    if getattr(row, "peso_actividad", None):
        parts.append(f"actividad: {row.peso_actividad}")
    return " | ".join(parts)


def _edge_label(edge_type: str, peso: int) -> str:
    abbr = {"ataca": "→", "co_rafaga": "↔", "usa_narrativa": "nar", "en_cohorte": "coh"}
    return f"{abbr.get(edge_type, edge_type)} {peso}"


def export_grafo_csv(con, data_dir: Path) -> tuple[int, int]:
    top_authors = _top_author_ids(con)
    edges_raw = con.sql(
        """
        SELECT source_id, target_id, edge_type, peso_total, eventos, metadata_ejemplo
        FROM gold.grafo_edges_agg_trolls
        ORDER BY peso_total DESC
        """
    ).df()
    vertices = con.sql(
        "SELECT vertex_id, label, tipo, plataforma, peso_actividad FROM gold.grafo_vertices_trolls"
    ).df()

    kept_nodes: set[str] = set(top_authors)
    kept_nodes.update(v for v in vertices["vertex_id"] if str(v).startswith("cuenta:"))
    kept_nodes.update(v for v in vertices["vertex_id"] if str(v).startswith("cohorte:"))

    filtered_edges = []
    for row in edges_raw.itertuples(index=False):
        src, tgt, etype = row.source_id, row.target_id, row.edge_type
        if etype == "ataca" and src in top_authors:
            kept_nodes.add(src)
            kept_nodes.add(tgt)
            filtered_edges.append(row)
        elif etype == "co_rafaga" and src in top_authors and tgt in top_authors:
            filtered_edges.append(row)
        elif etype == "en_cohorte" and src in top_authors:
            kept_nodes.add(tgt)
            filtered_edges.append(row)
        elif etype == "usa_narrativa" and src in top_authors:
            kept_nodes.add(tgt)
            filtered_edges.append(row)

    node_rows = vertices[vertices["vertex_id"].isin(kept_nodes)]
    nodes_path = data_dir / "grafo_nodes.csv"
    edges_path = data_dir / "grafo_edges.csv"

    with nodes_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["id", "label", "tipo", "color", "shape", "size", "title", "plataforma"],
        )
        w.writeheader()
        for row in node_rows.itertuples(index=False):
            style = NODE_STYLE.get(row.tipo, NODE_STYLE["autor"])
            size = style["size"]
            if row.tipo == "autor" and row.peso_actividad:
                size = min(40, style["size"] + int(row.peso_actividad) // 2)
            w.writerow(
                {
                    "id": row.vertex_id,
                    "label": _short_label(str(row.label), row.tipo),
                    "tipo": row.tipo,
                    "color": style["color"],
                    "shape": style["shape"],
                    "size": size,
                    "title": _node_tooltip(row),
                    "plataforma": row.plataforma or "",
                }
            )

    with edges_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["id", "from", "to", "label", "color", "width", "dashes", "edge_type", "title"],
        )
        w.writeheader()
        for i, row in enumerate(filtered_edges):
            style = EDGE_STYLE.get(row.edge_type, EDGE_STYLE["ataca"])
            w_val = max(1, min(12, int(row.peso_total * style["width_factor"])))
            w.writerow(
                {
                    "id": f"e{i}",
                    "from": row.source_id,
                    "to": row.target_id,
                    "label": _edge_label(row.edge_type, int(row.peso_total)),
                    "color": style["color"],
                    "width": w_val,
                    "dashes": str(style["dashes"]).lower(),
                    "edge_type": row.edge_type,
                    "title": f"{row.edge_type} · peso {row.peso_total}"
                    + (f" · {row.metadata_ejemplo}" if row.metadata_ejemplo else ""),
                }
            )

    return len(node_rows), len(filtered_edges)


def export_kpis(con, data_dir: Path) -> None:
    generated = date.today().isoformat()
    total_clas = con.sql("SELECT COUNT(*) FROM gold.v_comentarios_clasificados").fetchone()[0]
    total_perfiles = con.sql(
        "SELECT COUNT(*) FROM gold.v_entidades_resumen"
    ).fetchone()[0]
    clusters_texto = con.sql(
        "SELECT COUNT(*) FROM gold.v_comentarios_clusters_texto"
    ).fetchone()[0]
    posible_mc = con.sql(
        "SELECT COUNT(*) FROM gold.v_entidades_resumen WHERE posible_multicuenta"
    ).fetchone()[0]
    rafaga = con.sql("SELECT * FROM gold.v_trolls_rafagas_resumen").fetchone()
    autores_rafaga = rafaga[0] if rafaga else 0

    rows = [
        ("generated", generated),
        ("comentarios_clasificados", total_clas),
        ("perfiles_entidades", total_perfiles),
        ("clusters_copy_pasta", clusters_texto),
        ("posible_multicuenta", posible_mc),
        ("autores_con_rafaga", autores_rafaga),
    ]
    for slug_row in con.sql(
        "SELECT cuenta_slug, comentarios_clasificados, pct_troll, pct_apoyo "
        "FROM gold.v_sentimiento_resumen_cuenta ORDER BY cuenta_slug"
    ).fetchall():
        slug, n, pct_t, pct_a = slug_row
        rows.append((f"cuenta_{slug}_comentarios", n))
        rows.append((f"cuenta_{slug}_pct_troll", pct_t))
        rows.append((f"cuenta_{slug}_pct_apoyo", pct_a))

    path = data_dir / "kpis.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        w.writerows(rows)


README = """# Dashboard redes — análisis unificado

Un solo reporte interactivo: sentimiento, narrativa, trolls, entidades y copy-pasta.

| Archivo | Rol |
|---------|-----|
| `report.html` | Dashboard HTML+JS autocontenido (Chart.js + vis.js) |
| `data/*.csv` | Datasets exportados (opcional, para análisis externo) |

## Abrir

Doble clic en `report.html` o:

```bash
open reports/redes/dashboard/report.html
```

Los datos van embebidos en el HTML — no requiere servidor local.

## Regenerar

```bash
uv run python scripts/python/db.py mcp-stop
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/redes/ingest_redes_gold.sql
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/redes/ingest_network_profile.sql
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/redes/ingest_gold_entidades.sql
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/redes/ingest_redes_comment_similarity.sql
uv run python scripts/python/reports/generate_redes_dashboard.py
```

Generado: {generated}
"""


def main() -> int:
    con = db.connect_for_ingest(release_mcp=True)
    out_dir = db.get_report_bundle("redes", "dashboard")
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    generated = date.today().isoformat()
    counts: dict[str, int] = {}

    for filename, sql in SQL_EXPORTS:
        path = data_dir / filename
        try:
            counts[filename] = _export_df_csv(con, sql, path)
        except Exception as exc:
            print(f"⚠️  Skip {filename}: {exc}")
            counts[filename] = 0

    try:
        n_nodes, n_edges = export_grafo_csv(con, data_dir)
        counts["grafo_nodes.csv"] = n_nodes
        counts["grafo_edges.csv"] = n_edges
    except Exception as exc:
        print(f"⚠️  Skip grafo: {exc}")

    try:
        export_kpis(con, data_dir)
        counts["kpis.csv"] = 1
    except Exception as exc:
        print(f"⚠️  Skip kpis: {exc}")

    con.close()

    embedded = build_embedded_data(data_dir)
    data_json = json.dumps(embedded, ensure_ascii=False)
    html = (
        TEMPLATE_PATH.read_text(encoding="utf-8")
        .replace("__GENERATED__", generated)
        .replace("__DATA_JSON__", data_json)
    )
    (out_dir / "report.html").write_text(html, encoding="utf-8")
    (out_dir / "README.md").write_text(README.format(generated=generated), encoding="utf-8")

    print(f"Bundle: {out_dir}/")
    print(f"  report.html")
    print(f"  data/ ({len(counts)} files)")
    for name, n in sorted(counts.items()):
        print(f"    {name}: {n} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
