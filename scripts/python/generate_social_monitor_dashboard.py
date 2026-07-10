#!/usr/bin/env python3
"""Generate unified social-monitor dashboard: CSV datasets + self-contained HTML."""

from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "social_monitor_dashboard.html"

NODE_STYLE = {
    "autor": {"color": "#f07178", "shape": "dot", "size": 16},
    "hater": {"color": "#f07178", "shape": "dot", "size": 20},
    "neighbor": {"color": "#60a5fa", "shape": "dot", "size": 12},
    "cuenta_objetivo": {"color": "#3dd68c", "shape": "box", "size": 26},
    "narrativa": {"color": "#a78bfa", "shape": "diamond", "size": 20},
    "cohorte_dia": {"color": "#60a5fa", "shape": "hexagon", "size": 18},
}

EDGE_STYLE = {
    "ataca": {"color": "#f0717866", "dashes": False, "width_factor": 0.15},
    "co_rafaga": {"color": "#fbbf2488", "dashes": True, "width_factor": 2},
    "usa_narrativa": {"color": "#a78bfa55", "dashes": True, "width_factor": 0.5},
    "en_cohorte": {"color": "#60a5fa66", "dashes": True, "width_factor": 0.3},
    "co_followers": {"color": "#fbbf2488", "dashes": True, "width_factor": 0.05},
    "bridge_follower": {"color": "#60a5fa66", "dashes": True, "width_factor": 0.3},
    "narrativa_coocurrencia": {"color": "#a78bfa88", "dashes": False, "width_factor": 0.2},
    "narrativa_cuenta": {"color": "#3dd68c66", "dashes": True, "width_factor": 0.3},
    "autor_narrativa": {"color": "#a78bfa55", "dashes": True, "width_factor": 0.4},
}

SQL_EXPORTS: list[tuple[str, str]] = [
    (
        "kpis.csv",
        "SELECT * FROM gold.v_monitor_kpis",
    ),
    (
        "perfiles.csv",
        """
        SELECT persona_id, nombre_canonico, tipo, rol, partido, plataforma,
               handle, url, followers_count, following_count, posts_count,
               is_verified, bio, location, account_created_at, sitio_web,
               wikidata_id, provincia, cuenta_slug
        FROM gold.v_monitor_perfil
        ORDER BY nombre_canonico, plataforma
        """,
    ),
    (
        "reacciones_resumen.csv",
        """
        SELECT persona_id, nombre_canonico, plataforma,
               COUNT(*) AS posts,
               SUM(reacciones_total) AS reacciones_total,
               SUM(likes) AS likes,
               SUM(loves) AS loves,
               SUM(wows) AS wows,
               SUM(hahas) AS hahas,
               SUM(sads) AS sads,
               SUM(angrys) AS angrys,
               SUM(cares) AS cares,
               SUM(comentarios) AS comentarios,
               SUM(compartidos) AS compartidos,
               SUM(COALESCE(retweets, 0)) AS retweets,
               SUM(COALESCE(quotes, 0)) AS quotes,
               SUM(COALESCE(views, 0)) AS views
        FROM gold.v_monitor_reacciones
        GROUP BY persona_id, nombre_canonico, plataforma
        ORDER BY nombre_canonico, plataforma
        """,
    ),
    (
        "engagement.csv",
        """
        SELECT persona_id, nombre_canonico, plataforma,
               CAST(dia AS VARCHAR) AS dia,
               posts, reacciones, comentarios, compartidos,
               retweets, quotes, views, likes, engagement_por_post
        FROM gold.v_monitor_engagement
        WHERE dia IS NOT NULL
        ORDER BY dia, persona_id, plataforma
        """,
    ),
    (
        "audiencia_resumen.csv",
        """
        SELECT persona_id, nombre_canonico, plataforma, audiencia_clase,
               eventos, actores_distintos, eventos_bot_heuristico, actores_bot_heuristico
        FROM gold.v_monitor_audiencia_resumen
        ORDER BY persona_id, plataforma, eventos DESC
        """,
    ),
    (
        "haters_top10.csv",
        """
        SELECT persona_id, nombre_canonico, plataforma, ranking,
               actor_id, actor_nombre, score_eventos, dias_activos,
               cuentas_objetivo, narrativas, tier, risk_score
        FROM gold.v_monitor_haters_top10
        ORDER BY persona_id, plataforma, ranking
        """,
    ),
    (
        "narrativa.csv",
        """
        SELECT persona_id, nombre_canonico, plataforma, narrativa, posicion,
               comentarios, pct_narrativa
        FROM gold.v_monitor_narrativa
        ORDER BY persona_id, plataforma, comentarios DESC
        """,
    ),
    (
        "temporal.csv",
        """
        SELECT persona_id, nombre_canonico, plataforma,
               CAST(dia AS VARCHAR) AS dia,
               posicion, sentimiento, comentarios, narrativa
        FROM gold.v_monitor_temporal
        WHERE dia IS NOT NULL
        ORDER BY dia, persona_id, plataforma
        """,
    ),
    (
        "temporal_engagement.csv",
        """
        SELECT persona_id, nombre_canonico, plataforma,
               CAST(dia AS VARCHAR) AS dia,
               posts, reacciones, comentarios, engagement_por_post
        FROM gold.v_monitor_temporal_engagement
        WHERE dia IS NOT NULL
        ORDER BY dia, persona_id
        """,
    ),
]

CSV_KEY_MAP: dict[str, str] = {
    "kpis.csv": "kpis",
    "perfiles.csv": "perfiles",
    "reacciones_resumen.csv": "reacciones",
    "engagement.csv": "engagement",
    "audiencia_resumen.csv": "audiencia",
    "haters_top10.csv": "haters",
    "narrativa.csv": "narrativa",
    "temporal.csv": "temporal",
    "temporal_engagement.csv": "temporal_engagement",
    "grafo_comportamiento_nodes.csv": "grafo_comportamiento_nodes",
    "grafo_comportamiento_edges.csv": "grafo_comportamiento_edges",
    "grafo_narrativa_nodes.csv": "grafo_narrativa_nodes",
    "grafo_narrativa_edges.csv": "grafo_narrativa_edges",
    "grafo_coordinacion_nodes.csv": "grafo_coordinacion_nodes",
    "grafo_coordinacion_edges.csv": "grafo_coordinacion_edges",
}


def _export_df_csv(con, sql: str, path: Path) -> int:
    df = con.sql(sql).df()
    for col in df.columns:
        dtype = str(df[col].dtype).lower()
        if "datetime" in dtype or "timestamp" in dtype:
            df[col] = df[col].astype(str)
        elif dtype == "object":
            # arrays / lists → string
            sample = df[col].dropna()
            if len(sample) and hasattr(sample.iloc[0], "__iter__") and not isinstance(
                sample.iloc[0], (str, bytes)
            ):
                df[col] = df[col].apply(
                    lambda x: ",".join(map(str, x)) if x is not None and not isinstance(x, str) else x
                )
    df.to_csv(path, index=False)
    return len(df)


def _csv_records(path: Path) -> list[dict]:
    if not path.is_file() or path.stat().st_size == 0:
        return []
    import pandas as pd

    df = pd.read_csv(path)
    return json.loads(df.to_json(orient="records"))


def build_embedded_data(data_dir: Path) -> dict:
    embedded: dict[str, list[dict]] = {}
    for filename, key in CSV_KEY_MAP.items():
        embedded[key] = _csv_records(data_dir / filename)
    return embedded


def _write_graph_csv(
    nodes_path: Path,
    edges_path: Path,
    node_rows: list[dict],
    edge_rows: list[dict],
) -> tuple[int, int]:
    with nodes_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["id", "label", "tipo", "color", "shape", "size", "title", "plataforma"],
        )
        w.writeheader()
        w.writerows(node_rows)
    with edges_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["id", "from", "to", "label", "color", "width", "dashes", "edge_type", "title"],
        )
        w.writeheader()
        w.writerows(edge_rows)
    return len(node_rows), len(edge_rows)


def _style_node(tipo: str, peso: float | int | None = None) -> dict:
    style = NODE_STYLE.get(tipo, NODE_STYLE["autor"])
    size = style["size"]
    try:
        if peso is not None and peso == peso:  # not NaN
            size = min(42, style["size"] + int(peso) // 5)
    except (TypeError, ValueError):
        pass
    return {**style, "size": size}


def export_grafo_comportamiento(con, data_dir: Path) -> tuple[int, int]:
    top = con.sql(
        """
        SELECT source_id
        FROM gold.v_monitor_grafo_comportamiento_edges
        WHERE edge_type = 'ataca' AND source_id LIKE 'autor:%'
        GROUP BY source_id
        ORDER BY SUM(peso_total) DESC
        LIMIT 30
        """
    ).fetchall()
    top_authors = {r[0] for r in top}
    vertices = con.sql(
        """
        SELECT vertex_id, label, tipo, plataforma, peso_actividad
        FROM gold.grafo_vertices_trolls
        """
    ).df()
    edges = con.sql(
        """
        SELECT source_id, target_id, edge_type, peso_total
        FROM gold.v_monitor_grafo_comportamiento_edges
        ORDER BY peso_total DESC
        """
    ).df()

    kept = set(top_authors)
    kept.update(v for v in vertices["vertex_id"] if str(v).startswith("cuenta:"))
    filtered = []
    for row in edges.itertuples(index=False):
        if row.edge_type == "ataca" and row.source_id in top_authors:
            kept.add(row.source_id)
            kept.add(row.target_id)
            filtered.append(row)
        elif row.edge_type == "co_rafaga" and row.source_id in top_authors and row.target_id in top_authors:
            filtered.append(row)
        elif row.edge_type in ("usa_narrativa", "en_cohorte") and row.source_id in top_authors:
            kept.add(row.target_id)
            filtered.append(row)

    node_rows = []
    for row in vertices[vertices["vertex_id"].isin(kept)].itertuples(index=False):
        st = _style_node(row.tipo, row.peso_actividad)
        label = str(row.label or "?")
        if row.tipo == "autor" and len(label) > 14:
            label = label[:12] + "…"
        node_rows.append(
            {
                "id": row.vertex_id,
                "label": label,
                "tipo": row.tipo,
                "color": st["color"],
                "shape": st["shape"],
                "size": st["size"],
                "title": f"{row.label} | {row.tipo}",
                "plataforma": row.plataforma or "",
            }
        )
    edge_rows = []
    for i, row in enumerate(filtered):
        st = EDGE_STYLE.get(row.edge_type, EDGE_STYLE["ataca"])
        edge_rows.append(
            {
                "id": f"cb{i}",
                "from": row.source_id,
                "to": row.target_id,
                "label": f"{row.edge_type[:4]} {int(row.peso_total)}",
                "color": st["color"],
                "width": max(1, min(10, int(row.peso_total * st["width_factor"]))),
                "dashes": str(st["dashes"]).lower(),
                "edge_type": row.edge_type,
                "title": f"{row.edge_type} · peso {row.peso_total}",
            }
        )
    return _write_graph_csv(
        data_dir / "grafo_comportamiento_nodes.csv",
        data_dir / "grafo_comportamiento_edges.csv",
        node_rows,
        edge_rows,
    )


def export_grafo_narrativa(con, data_dir: Path) -> tuple[int, int]:
    edges = con.sql(
        """
        SELECT source_id, target_id, edge_type, peso_total, cuenta_slug
        FROM gold.v_monitor_grafo_narrativa_edges
        WHERE edge_type IN ('narrativa_coocurrencia', 'narrativa_cuenta', 'autor_narrativa')
        ORDER BY peso_total DESC
        LIMIT 80
        """
    ).df()
    kept = set(edges["source_id"]).union(set(edges["target_id"]))
    vertices = con.sql(
        "SELECT vertex_id, label, tipo, plataforma FROM gold.v_monitor_grafo_narrativa_vertices"
    ).df()
    node_rows = []
    for row in vertices[vertices["vertex_id"].isin(kept)].itertuples(index=False):
        st = _style_node(row.tipo)
        node_rows.append(
            {
                "id": row.vertex_id,
                "label": str(row.label or "?")[:18],
                "tipo": row.tipo,
                "color": st["color"],
                "shape": st["shape"],
                "size": st["size"],
                "title": f"{row.label} | {row.tipo}",
                "plataforma": row.plataforma or "",
            }
        )
    edge_rows = []
    for i, row in enumerate(edges.itertuples(index=False)):
        st = EDGE_STYLE.get(row.edge_type, EDGE_STYLE["narrativa_coocurrencia"])
        edge_rows.append(
            {
                "id": f"nr{i}",
                "from": row.source_id,
                "to": row.target_id,
                "label": str(int(row.peso_total)),
                "color": st["color"],
                "width": max(1, min(10, int(row.peso_total * st["width_factor"]))),
                "dashes": str(st["dashes"]).lower(),
                "edge_type": row.edge_type,
                "title": f"{row.edge_type} · {row.peso_total}",
            }
        )
    return _write_graph_csv(
        data_dir / "grafo_narrativa_nodes.csv",
        data_dir / "grafo_narrativa_edges.csv",
        node_rows,
        edge_rows,
    )


def export_grafo_coordinacion(con, data_dir: Path) -> tuple[int, int]:
    # Top co-follower pairs + sample bridge edges + co_rafaga among top authors
    co = con.sql(
        """
        SELECT source_id, target_id, edge_type, peso_total
        FROM gold.v_monitor_grafo_coordinacion_edges
        WHERE edge_type = 'co_followers'
        ORDER BY peso_total DESC
        LIMIT 40
        """
    ).df()
    bridges = con.sql(
        """
        SELECT source_id, target_id, edge_type, peso_total
        FROM gold.v_monitor_grafo_coordinacion_edges
        WHERE edge_type = 'bridge_follower'
        ORDER BY peso_total DESC
        LIMIT 60
        """
    ).df()
    rafagas = con.sql(
        """
        SELECT source_id, target_id, edge_type, peso_total
        FROM gold.v_monitor_grafo_coordinacion_edges
        WHERE edge_type = 'co_rafaga'
        ORDER BY peso_total DESC
        LIMIT 40
        """
    ).df()
    import pandas as pd

    edges = pd.concat([co, bridges, rafagas], ignore_index=True)
    kept = set(edges["source_id"]).union(set(edges["target_id"]))
    vertices = con.sql(
        """
        SELECT vertex_id, label, tipo, plataforma, peso_actividad
        FROM gold.v_monitor_grafo_coordinacion_vertices
        """
    ).df()
    # Also invent nodes for bridge targets that are usernames only
    present = set(vertices["vertex_id"])
    node_rows = []
    for row in vertices[vertices["vertex_id"].isin(kept)].itertuples(index=False):
        st = _style_node(row.tipo, row.peso_actividad)
        node_rows.append(
            {
                "id": row.vertex_id,
                "label": str(row.label or "?")[:16],
                "tipo": row.tipo,
                "color": st["color"],
                "shape": st["shape"],
                "size": st["size"],
                "title": f"{row.label} | {row.tipo}",
                "plataforma": row.plataforma or "",
            }
        )
    for vid in kept - present:
        st = _style_node("neighbor")
        node_rows.append(
            {
                "id": vid,
                "label": str(vid)[:16],
                "tipo": "neighbor",
                "color": st["color"],
                "shape": st["shape"],
                "size": st["size"],
                "title": str(vid),
                "plataforma": "twitter",
            }
        )
    edge_rows = []
    for i, row in enumerate(edges.itertuples(index=False)):
        st = EDGE_STYLE.get(row.edge_type, EDGE_STYLE["co_followers"])
        edge_rows.append(
            {
                "id": f"co{i}",
                "from": row.source_id,
                "to": row.target_id,
                "label": f"{row.edge_type[:6]} {int(row.peso_total)}",
                "color": st["color"],
                "width": max(1, min(10, int(max(row.peso_total, 1) * st["width_factor"]))),
                "dashes": str(st["dashes"]).lower(),
                "edge_type": row.edge_type,
                "title": f"{row.edge_type} · peso {row.peso_total}",
            }
        )
    return _write_graph_csv(
        data_dir / "grafo_coordinacion_nodes.csv",
        data_dir / "grafo_coordinacion_edges.csv",
        node_rows,
        edge_rows,
    )


README = """# Monitor de redes — dashboard unificado

Reporte autocontenido para estudiar **personas** (identidad curada) a través de
sus cuentas en Facebook y Twitter/X.

## Abrir

```bash
open report.html
```

## Secciones

| Sección | Qué muestra |
|---------|-------------|
| Perfil | Selector de persona, cuentas por plataforma, OSINT |
| Reacciones | Desglose likes/loves/… (FB) y likes/RT/quotes (TW) |
| Engagement | Serie temporal de engagement por post |
| Audiencia | Haters / apoyo / neutral / bots (heurística) |
| Haters | Top 10 por persona + narrativas |
| Grafos | Comportamiento, coordinación, clusters de narrativa |
| Comparativa | Varias personas en la misma vista temporal |
| Metodología | Límites y pipeline |

## Regenerar

```bash
uv run python scripts/python/db.py mcp-stop
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_identidades.sql
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_social_monitor_gold.sql
uv run python scripts/python/generate_social_monitor_dashboard.py
```

**Privacidad:** no commitear este directorio (`reports/**` está gitignored).
"""


def main() -> int:
    out = db.get_report_bundle("monitor", "dashboard")
    data_dir = out / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    con = db.connect()
    print(f"→ Exporting CSVs to {data_dir}")
    for filename, sql in SQL_EXPORTS:
        n = _export_df_csv(con, sql, data_dir / filename)
        print(f"  {filename}: {n} rows")

    n1, e1 = export_grafo_comportamiento(con, data_dir)
    print(f"  grafo_comportamiento: {n1} nodes / {e1} edges")
    n2, e2 = export_grafo_narrativa(con, data_dir)
    print(f"  grafo_narrativa: {n2} nodes / {e2} edges")
    n3, e3 = export_grafo_coordinacion(con, data_dir)
    print(f"  grafo_coordinacion: {n3} nodes / {e3} edges")

    embedded = build_embedded_data(data_dir)
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = template.replace("__GENERATED__", date.today().isoformat())
    html = html.replace(
        "__DATA_JSON__",
        json.dumps(embedded, ensure_ascii=False, default=str),
    )
    (out / "report.html").write_text(html, encoding="utf-8")
    (out / "README.md").write_text(README, encoding="utf-8")
    (out / "data.json").write_text(
        json.dumps({"generated": date.today().isoformat(), "keys": list(embedded)}, indent=2),
        encoding="utf-8",
    )
    print(f"✅ Dashboard → {out / 'report.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
