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
        "apoyo_top10.csv",
        """
        SELECT persona_id, nombre_canonico, plataforma, ranking,
               actor_id, actor_nombre, score_eventos, dias_activos,
               cuentas_objetivo, narrativas, tier, risk_score
        FROM gold.v_monitor_apoyo_top10
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
    "apoyo_top10.csv": "apoyo_top10",
    "narrativa.csv": "narrativa",
    "temporal.csv": "temporal",
    "temporal_engagement.csv": "temporal_engagement",
    "grafo_comportamiento_nodes.csv": "grafo_comportamiento_nodes",
    "grafo_comportamiento_edges.csv": "grafo_comportamiento_edges",
    "grafo_narrativa_nodes.csv": "grafo_narrativa_nodes",
    "grafo_narrativa_edges.csv": "grafo_narrativa_edges",
    "grafo_narrativa_hater_nodes.csv": "grafo_narrativa_hater_nodes",
    "grafo_narrativa_hater_edges.csv": "grafo_narrativa_hater_edges",
    "grafo_narrativa_apoyo_nodes.csv": "grafo_narrativa_apoyo_nodes",
    "grafo_narrativa_apoyo_edges.csv": "grafo_narrativa_apoyo_edges",
    "grafo_relaciones_nodes.csv": "grafo_relaciones_nodes",
    "grafo_relaciones_edges.csv": "grafo_relaciones_edges",
    "grafo_risk.csv": "grafo_risk",
    "grafo_co_followers.csv": "grafo_co_followers",
    "grafo_co_following.csv": "grafo_co_following",
    "grafo_bridges.csv": "grafo_bridges",
    "grafo_stats.csv": "grafo_stats",
    "grafo_apoyo_relaciones_nodes.csv": "grafo_apoyo_relaciones_nodes",
    "grafo_apoyo_relaciones_edges.csv": "grafo_apoyo_relaciones_edges",
    "grafo_apoyo_risk.csv": "grafo_apoyo_risk",
    "grafo_apoyo_co_followers.csv": "grafo_apoyo_co_followers",
    "grafo_apoyo_co_following.csv": "grafo_apoyo_co_following",
    "grafo_apoyo_bridges.csv": "grafo_apoyo_bridges",
    "grafo_apoyo_stats.csv": "grafo_apoyo_stats",
}

RISK_COLORS = {
    "high": "#e85d5d",
    "medium": "#e6a23c",
    "low": "#3ecf8e",
    "neighbor": "#3d8bfd",
}

SUPPORT_COLORS = {
    "high": "#1a9f6a",
    "medium": "#3dd68c",
    "low": "#8ee4b8",
    "neighbor": "#5b9fd4",
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


def export_grafo_narrativa_polaridad(
    con,
    data_dir: Path,
    *,
    polaridad: str,
) -> tuple[int, int]:
    """TW narrative cluster graph for hater or apoyo polarity.

    Nodes: narrative clusters + top authors per cluster.
    Edges: autor_narrativa + narrativa_coocurrencia (shared authors).
    """
    if polaridad == "apoyo":
        assignment = "gold.tk_apoyo_narrativa_assignment"
        cluster = "gold.tk_apoyo_narrativa_cluster"
        autor_tipo = "supporter"
        autor_color = SUPPORT_COLORS["medium"]
        cluster_color = "#3dd68c"
        out_prefix = "grafo_narrativa_apoyo"
        edge_prefix = "nap"
    else:
        assignment = "gold.tk_hater_narrativa_assignment"
        cluster = "gold.tk_hater_narrativa_cluster"
        autor_tipo = "hater"
        autor_color = RISK_COLORS["high"]
        cluster_color = "#a78bfa"
        out_prefix = "grafo_narrativa_hater"
        edge_prefix = "nh"

    try:
        clusters = con.execute(
            f"""
            SELECT cluster_id, label, n_replies, descripcion
            FROM {cluster}
            ORDER BY n_replies DESC NULLS LAST
            LIMIT 20
            """
        ).df()
    except Exception:
        clusters = __import__("pandas").DataFrame()

    if len(clusters) == 0:
        return _write_graph_csv(
            data_dir / f"{out_prefix}_nodes.csv",
            data_dir / f"{out_prefix}_edges.csv",
            [],
            [],
        )

    cluster_ids = [str(x) for x in clusters["cluster_id"].tolist()]
    placeholders = ",".join(["?"] * len(cluster_ids))

    authors = con.execute(
        f"""
        WITH counts AS (
          SELECT
            COALESCE(NULLIF(TRIM(username), ''), 'anon') AS username,
            cluster_id,
            COUNT(*) AS n
          FROM {assignment}
          WHERE cluster_id IN ({placeholders})
            AND username IS NOT NULL
            AND LENGTH(TRIM(username)) > 0
          GROUP BY 1, 2
        ),
        ranked AS (
          SELECT *,
            ROW_NUMBER() OVER (PARTITION BY cluster_id ORDER BY n DESC) AS rn
          FROM counts
        )
        SELECT username, cluster_id, n
        FROM ranked
        WHERE rn <= 5
        ORDER BY n DESC
        LIMIT 80
        """,
        cluster_ids,
    ).df()

    cooc = con.execute(
        f"""
        WITH pairs AS (
          SELECT
            a.cluster_id AS source_id,
            b.cluster_id AS target_id,
            COUNT(DISTINCT a.username) AS peso_total
          FROM {assignment} AS a
          JOIN {assignment} AS b
            ON a.username = b.username
           AND a.cluster_id < b.cluster_id
          WHERE a.cluster_id IN ({placeholders})
            AND b.cluster_id IN ({placeholders})
            AND a.username IS NOT NULL
            AND LENGTH(TRIM(a.username)) > 0
          GROUP BY 1, 2
          HAVING COUNT(DISTINCT a.username) >= 2
        )
        SELECT source_id, target_id, peso_total
        FROM pairs
        ORDER BY peso_total DESC
        LIMIT 40
        """,
        cluster_ids + cluster_ids,
    ).df()

    node_rows: list[dict] = []
    seen_authors: set[str] = set()
    for row in clusters.itertuples(index=False):
        cid = str(row.cluster_id)
        n_rep = int(row.n_replies or 0)
        node_rows.append(
            {
                "id": f"narr:{cid}",
                "label": str(row.label or "?")[:18],
                "tipo": "narrativa",
                "color": cluster_color,
                "shape": "diamond",
                "size": min(36, 16 + n_rep // 5),
                "title": f"{row.label} · {n_rep} replies · {polaridad}",
                "plataforma": "twitter",
            }
        )

    for row in authors.itertuples(index=False):
        uname = str(row.username)
        aid = f"autor:{uname.lower()}"
        if aid not in seen_authors:
            seen_authors.add(aid)
            node_rows.append(
                {
                    "id": aid,
                    "label": f"@{uname}"[:18],
                    "tipo": autor_tipo,
                    "color": autor_color,
                    "shape": "dot",
                    "size": min(28, 10 + int(row.n or 0)),
                    "title": f"@{uname} · {polaridad}",
                    "plataforma": "twitter",
                }
            )

    edge_rows: list[dict] = []
    for i, row in enumerate(authors.itertuples(index=False)):
        peso = int(row.n or 1)
        edge_rows.append(
            {
                "id": f"{edge_prefix}_an{i}",
                "from": f"autor:{str(row.username).lower()}",
                "to": f"narr:{row.cluster_id}",
                "label": str(peso),
                "color": "#a78bfa55" if polaridad != "apoyo" else "#3dd68c55",
                "width": max(1, min(8, peso)),
                "dashes": "true",
                "edge_type": "autor_narrativa",
                "title": f"autor_narrativa · {peso}",
            }
        )

    for i, row in enumerate(cooc.itertuples(index=False)):
        peso = int(row.peso_total or 1)
        edge_rows.append(
            {
                "id": f"{edge_prefix}_co{i}",
                "from": f"narr:{row.source_id}",
                "to": f"narr:{row.target_id}",
                "label": str(peso),
                "color": "#fbbf2488",
                "width": max(1, min(10, peso)),
                "dashes": "false",
                "edge_type": "narrativa_coocurrencia",
                "title": f"coocurrencia · {peso} autores",
            }
        )

    return _write_graph_csv(
        data_dir / f"{out_prefix}_nodes.csv",
        data_dir / f"{out_prefix}_edges.csv",
        node_rows,
        edge_rows,
    )


def _risk_signals(row) -> str:
    parts = []
    if getattr(row, "flag_empty_bio", False):
        parts.append("bio vacía")
    if getattr(row, "flag_new_account", False):
        parts.append("cuenta ≥2024")
    if getattr(row, "flag_follow_ratio_high", False):
        parts.append("following/followers≥5")
    if getattr(row, "flag_high_output_low_audience", False):
        parts.append("statuses/follower≥100")
    if getattr(row, "flag_low_followers_high_status", False):
        parts.append("<50 fo + ≥1k statuses")
    if getattr(row, "flag_low_likes_high_status", False):
        parts.append("pocos likes + alto output")
    if getattr(row, "flag_shared_audience", False):
        parts.append("≥3 bridge followers")
    return "; ".join(parts)


def export_grafo_relaciones_tables(con, data_dir: Path) -> None:
    """Sidecar tables from hater-profiles-graph gold (risk, co-*, bridges, stats)."""
    risk_df = con.sql(
        """
        SELECT *
        FROM gold.tk_hater_profile_risk
        ORDER BY risk_score DESC, username
        """
    ).df()
    n_risk = 0
    if len(risk_df):
        risk_df["senales"] = [_risk_signals(r) for r in risk_df.itertuples(index=False)]
        risk_df["following_followers_ratio"] = risk_df["following_followers_ratio"].round(2)
        risk_df["statuses_per_follower"] = risk_df["statuses_per_follower"].round(2)
        keep = [
            "username",
            "risk_band",
            "risk_score",
            "followers_count",
            "following_count",
            "statuses_count",
            "following_followers_ratio",
            "statuses_per_follower",
            "bridge_followers_on_me",
            "senales",
        ]
        risk_df[keep].to_csv(data_dir / "grafo_risk.csv", index=False)
        n_risk = len(risk_df)
    else:
        (data_dir / "grafo_risk.csv").write_text(
            "username,risk_band,risk_score,followers_count,following_count,"
            "statuses_count,following_followers_ratio,statuses_per_follower,"
            "bridge_followers_on_me,senales\n",
            encoding="utf-8",
        )

    n_co_fo = _export_df_csv(
        con,
        """
        SELECT
            COALESCE(va.label, c.hater_a_id) AS hater_a,
            COALESCE(vb.label, c.hater_b_id) AS hater_b,
            c.shared_followers
        FROM gold.tk_hater_grafo_co_followers AS c
        LEFT JOIN gold.tk_hater_grafo_vertices AS va ON va.vertex_id = c.hater_a_id
        LEFT JOIN gold.tk_hater_grafo_vertices AS vb ON vb.vertex_id = c.hater_b_id
        ORDER BY c.shared_followers DESC
        LIMIT 25
        """,
        data_dir / "grafo_co_followers.csv",
    )
    n_co_fl = _export_df_csv(
        con,
        """
        SELECT
            COALESCE(va.label, c.hater_a_id) AS hater_a,
            COALESCE(vb.label, c.hater_b_id) AS hater_b,
            c.shared_following
        FROM gold.tk_hater_grafo_co_following AS c
        LEFT JOIN gold.tk_hater_grafo_vertices AS va ON va.vertex_id = c.hater_a_id
        LEFT JOIN gold.tk_hater_grafo_vertices AS vb ON vb.vertex_id = c.hater_b_id
        ORDER BY c.shared_following DESC
        LIMIT 25
        """,
        data_dir / "grafo_co_following.csv",
    )
    n_br = _export_df_csv(
        con,
        """
        SELECT
            follower_username,
            follower_display_name,
            haters_followed,
            follower_followers_count,
            follower_following_count,
            array_to_string(hater_usernames, ', ') AS hater_usernames
        FROM gold.tk_hater_grafo_bridge_followers
        ORDER BY haters_followed DESC, follower_followers_count DESC
        LIMIT 40
        """,
        data_dir / "grafo_bridges.csv",
    )
    _export_df_csv(
        con,
        """
        SELECT
            (SELECT COUNT(*) FROM gold.tk_hater_grafo_vertices) AS vertices,
            (SELECT COUNT(*) FROM gold.tk_hater_grafo_vertices WHERE entity_type = 'hater') AS haters,
            (SELECT COUNT(*) FROM gold.tk_hater_grafo_vertices WHERE entity_type = 'neighbor') AS neighbors,
            (SELECT COUNT(*) FROM gold.tk_hater_grafo_edges) AS edges,
            (SELECT COUNT(*) FROM gold.tk_hater_grafo_bridge_followers) AS bridge_followers,
            (SELECT COUNT(*) FROM gold.tk_hater_grafo_co_followers) AS pares_co_seguidores,
            (SELECT COUNT(*) FROM gold.tk_hater_grafo_co_following) AS pares_co_following,
            (SELECT COUNT(*) FROM gold.tk_hater_profile_risk WHERE risk_band = 'high') AS risk_high,
            (SELECT COUNT(*) FROM gold.tk_hater_profile_risk WHERE risk_band = 'medium') AS risk_medium,
            (SELECT COUNT(*) FROM gold.tk_hater_profile_risk WHERE risk_band = 'low') AS risk_low
        """,
        data_dir / "grafo_stats.csv",
    )
    print(f"  grafo_risk: {n_risk} · co_followers: {n_co_fo} · co_following: {n_co_fl} · bridges: {n_br}")


def export_grafo_relaciones(con, data_dir: Path) -> tuple[int, int]:
    """TW follow graph viz: haters + bridge followers (≥3), colored by risk_band."""
    haters = con.sql(
        """
        SELECT
            v.vertex_id,
            v.label,
            v.entity_type AS tipo,
            v.followers_count,
            v.following_count,
            v.statuses_count,
            r.risk_band,
            r.risk_score
        FROM gold.tk_hater_grafo_vertices AS v
        LEFT JOIN gold.tk_hater_profile_risk AS r
            ON r.user_id = v.vertex_id OR LOWER(r.username) = LOWER(v.label)
        WHERE v.entity_type = 'hater'
        """
    ).df()
    bridges = con.sql(
        """
        SELECT
            follower_id AS vertex_id,
            follower_username AS label,
            'neighbor' AS tipo,
            follower_followers_count AS followers_count,
            follower_following_count AS following_count,
            CAST(NULL AS BIGINT) AS statuses_count,
            CAST(NULL AS VARCHAR) AS risk_band,
            CAST(0 AS INTEGER) AS risk_score,
            haters_followed
        FROM gold.tk_hater_grafo_bridge_followers
        WHERE haters_followed >= 3
        ORDER BY haters_followed DESC, follower_followers_count DESC
        """
    ).df()

    hater_ids = set(haters["vertex_id"].astype(str))
    bridge_ids = set(bridges["vertex_id"].astype(str))
    kept = hater_ids | bridge_ids

    edges = con.sql(
        """
        SELECT source_id, target_id, edge_type, weight
        FROM gold.tk_hater_grafo_edges
        WHERE edge_type = 'follows_hater'
        """
    ).df()
    edges = edges[
        edges["source_id"].astype(str).isin(kept) & edges["target_id"].astype(str).isin(kept)
    ]

    # Only keep bridges that appear in at least one edge (legibility)
    connected = set(edges["source_id"].astype(str)) | set(edges["target_id"].astype(str))
    bridges = bridges[bridges["vertex_id"].astype(str).isin(connected | hater_ids)]

    node_rows: list[dict] = []
    for row in haters.itertuples(index=False):
        band = (row.risk_band or "low").lower()
        color = RISK_COLORS.get(band, RISK_COLORS["low"])
        node_rows.append(
            {
                "id": str(row.vertex_id),
                "label": str(row.label or "?")[:18],
                "tipo": "hater",
                "color": color,
                "shape": "box",
                "size": 26,
                "title": f"@{row.label} [{band}] score={row.risk_score or 0}",
                "plataforma": "twitter",
                "risk_band": band,
                "risk_score": int(row.risk_score or 0),
                "followers_count": int(row.followers_count or 0),
                "haters_followed": 0,
            }
        )
    for row in bridges.itertuples(index=False):
        if str(row.vertex_id) in hater_ids:
            continue
        hf = int(row.haters_followed or 0)
        node_rows.append(
            {
                "id": str(row.vertex_id),
                "label": str(row.label or "?")[:18],
                "tipo": "neighbor",
                "color": RISK_COLORS["neighbor"],
                "shape": "dot",
                "size": min(28, 10 + hf * 2),
                "title": f"@{row.label} · puente ({hf} haters)",
                "plataforma": "twitter",
                "risk_band": "",
                "risk_score": 0,
                "followers_count": int(row.followers_count or 0),
                "haters_followed": hf,
            }
        )

    edge_rows: list[dict] = []
    for i, row in enumerate(edges.itertuples(index=False)):
        edge_rows.append(
            {
                "id": f"rel{i}",
                "from": str(row.source_id),
                "to": str(row.target_id),
                "label": "",
                "color": "#5b8def55",
                "width": 1,
                "dashes": "false",
                "edge_type": row.edge_type,
                "title": f"{row.edge_type}",
            }
        )

    nodes_path = data_dir / "grafo_relaciones_nodes.csv"
    edges_path = data_dir / "grafo_relaciones_edges.csv"
    with nodes_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "label",
                "tipo",
                "color",
                "shape",
                "size",
                "title",
                "plataforma",
                "risk_band",
                "risk_score",
                "followers_count",
                "haters_followed",
            ],
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


def export_grafo_apoyo_relaciones_tables(con, data_dir: Path) -> None:
    """Sidecar tables from apoyo profile graph gold (signals, co-*, bridges, stats)."""
    risk_df = con.sql(
        """
        SELECT *
        FROM gold.tk_apoyo_profile_risk
        ORDER BY risk_score DESC, username
        """
    ).df()
    n_risk = 0
    if len(risk_df):
        risk_df["senales"] = [_risk_signals(r) for r in risk_df.itertuples(index=False)]
        risk_df["following_followers_ratio"] = risk_df["following_followers_ratio"].round(2)
        risk_df["statuses_per_follower"] = risk_df["statuses_per_follower"].round(2)
        keep = [
            "username",
            "risk_band",
            "risk_score",
            "followers_count",
            "following_count",
            "statuses_count",
            "following_followers_ratio",
            "statuses_per_follower",
            "bridge_followers_on_me",
            "senales",
        ]
        risk_df[keep].to_csv(data_dir / "grafo_apoyo_risk.csv", index=False)
        n_risk = len(risk_df)
    else:
        (data_dir / "grafo_apoyo_risk.csv").write_text(
            "username,risk_band,risk_score,followers_count,following_count,"
            "statuses_count,following_followers_ratio,statuses_per_follower,"
            "bridge_followers_on_me,senales\n",
            encoding="utf-8",
        )

    n_co_fo = _export_df_csv(
        con,
        """
        SELECT
            COALESCE(va.label, c.apoyo_a_id) AS apoyo_a,
            COALESCE(vb.label, c.apoyo_b_id) AS apoyo_b,
            c.shared_followers
        FROM gold.tk_apoyo_grafo_co_followers AS c
        LEFT JOIN gold.tk_apoyo_grafo_vertices AS va ON va.vertex_id = c.apoyo_a_id
        LEFT JOIN gold.tk_apoyo_grafo_vertices AS vb ON vb.vertex_id = c.apoyo_b_id
        ORDER BY c.shared_followers DESC
        LIMIT 25
        """,
        data_dir / "grafo_apoyo_co_followers.csv",
    )
    n_co_fl = _export_df_csv(
        con,
        """
        SELECT
            COALESCE(va.label, c.apoyo_a_id) AS apoyo_a,
            COALESCE(vb.label, c.apoyo_b_id) AS apoyo_b,
            c.shared_following
        FROM gold.tk_apoyo_grafo_co_following AS c
        LEFT JOIN gold.tk_apoyo_grafo_vertices AS va ON va.vertex_id = c.apoyo_a_id
        LEFT JOIN gold.tk_apoyo_grafo_vertices AS vb ON vb.vertex_id = c.apoyo_b_id
        ORDER BY c.shared_following DESC
        LIMIT 25
        """,
        data_dir / "grafo_apoyo_co_following.csv",
    )
    n_br = _export_df_csv(
        con,
        """
        SELECT
            follower_username,
            follower_display_name,
            apoyos_followed,
            follower_followers_count,
            follower_following_count,
            array_to_string(apoyo_usernames, ', ') AS apoyo_usernames
        FROM gold.tk_apoyo_grafo_bridge_followers
        ORDER BY apoyos_followed DESC, follower_followers_count DESC
        LIMIT 40
        """,
        data_dir / "grafo_apoyo_bridges.csv",
    )
    _export_df_csv(
        con,
        """
        SELECT
            (SELECT COUNT(*) FROM gold.tk_apoyo_grafo_vertices) AS vertices,
            (SELECT COUNT(*) FROM gold.tk_apoyo_grafo_vertices WHERE entity_type = 'supporter') AS supporters,
            (SELECT COUNT(*) FROM gold.tk_apoyo_grafo_vertices WHERE entity_type = 'neighbor') AS neighbors,
            (SELECT COUNT(*) FROM gold.tk_apoyo_grafo_edges) AS edges,
            (SELECT COUNT(*) FROM gold.tk_apoyo_grafo_bridge_followers) AS bridge_followers,
            (SELECT COUNT(*) FROM gold.tk_apoyo_grafo_co_followers) AS pares_co_seguidores,
            (SELECT COUNT(*) FROM gold.tk_apoyo_grafo_co_following) AS pares_co_following,
            (SELECT COUNT(*) FROM gold.tk_apoyo_profile_risk WHERE risk_band = 'high') AS risk_high,
            (SELECT COUNT(*) FROM gold.tk_apoyo_profile_risk WHERE risk_band = 'medium') AS risk_medium,
            (SELECT COUNT(*) FROM gold.tk_apoyo_profile_risk WHERE risk_band = 'low') AS risk_low
        """,
        data_dir / "grafo_apoyo_stats.csv",
    )
    print(
        f"  grafo_apoyo_risk: {n_risk} · co_followers: {n_co_fo} · "
        f"co_following: {n_co_fl} · bridges: {n_br}"
    )


def export_grafo_apoyo_relaciones(con, data_dir: Path) -> tuple[int, int]:
    """TW follow graph viz: supporters + bridge followers (≥3), colored by signal band."""
    supporters = con.sql(
        """
        SELECT
            v.vertex_id,
            v.label,
            v.entity_type AS tipo,
            v.followers_count,
            v.following_count,
            v.statuses_count,
            r.risk_band,
            r.risk_score
        FROM gold.tk_apoyo_grafo_vertices AS v
        LEFT JOIN gold.tk_apoyo_profile_risk AS r
            ON r.user_id = v.vertex_id OR LOWER(r.username) = LOWER(v.label)
        WHERE v.entity_type = 'supporter'
        """
    ).df()
    bridges = con.sql(
        """
        SELECT
            follower_id AS vertex_id,
            follower_username AS label,
            'neighbor' AS tipo,
            follower_followers_count AS followers_count,
            follower_following_count AS following_count,
            CAST(NULL AS BIGINT) AS statuses_count,
            CAST(NULL AS VARCHAR) AS risk_band,
            CAST(0 AS INTEGER) AS risk_score,
            apoyos_followed
        FROM gold.tk_apoyo_grafo_bridge_followers
        WHERE apoyos_followed >= 3
        ORDER BY apoyos_followed DESC, follower_followers_count DESC
        """
    ).df()

    supporter_ids = set(supporters["vertex_id"].astype(str)) if len(supporters) else set()
    bridge_ids = set(bridges["vertex_id"].astype(str)) if len(bridges) else set()
    kept = supporter_ids | bridge_ids

    edges = con.sql(
        """
        SELECT source_id, target_id, edge_type, weight
        FROM gold.tk_apoyo_grafo_edges
        WHERE edge_type = 'follows_apoyo'
        """
    ).df()
    if len(edges) and kept:
        edges = edges[
            edges["source_id"].astype(str).isin(kept)
            & edges["target_id"].astype(str).isin(kept)
        ]
    elif not kept:
        edges = edges.iloc[0:0]

    connected = (
        set(edges["source_id"].astype(str)) | set(edges["target_id"].astype(str))
        if len(edges)
        else set()
    )
    if len(bridges):
        bridges = bridges[bridges["vertex_id"].astype(str).isin(connected | supporter_ids)]

    node_rows: list[dict] = []
    for row in supporters.itertuples(index=False):
        band = (row.risk_band or "low").lower()
        color = SUPPORT_COLORS.get(band, SUPPORT_COLORS["low"])
        node_rows.append(
            {
                "id": str(row.vertex_id),
                "label": str(row.label or "?")[:18],
                "tipo": "supporter",
                "color": color,
                "shape": "box",
                "size": 26,
                "title": f"@{row.label} [{band}] score={row.risk_score or 0}",
                "plataforma": "twitter",
                "risk_band": band,
                "risk_score": int(row.risk_score or 0),
                "followers_count": int(row.followers_count or 0),
                "apoyos_followed": 0,
            }
        )
    for row in bridges.itertuples(index=False):
        if str(row.vertex_id) in supporter_ids:
            continue
        af = int(row.apoyos_followed or 0)
        node_rows.append(
            {
                "id": str(row.vertex_id),
                "label": str(row.label or "?")[:18],
                "tipo": "neighbor",
                "color": SUPPORT_COLORS["neighbor"],
                "shape": "dot",
                "size": min(28, 10 + af * 2),
                "title": f"@{row.label} · puente ({af} apoyos)",
                "plataforma": "twitter",
                "risk_band": "",
                "risk_score": 0,
                "followers_count": int(row.followers_count or 0),
                "apoyos_followed": af,
            }
        )

    edge_rows: list[dict] = []
    for i, row in enumerate(edges.itertuples(index=False)):
        edge_rows.append(
            {
                "id": f"apoyo_rel{i}",
                "from": str(row.source_id),
                "to": str(row.target_id),
                "label": "",
                "color": "#3dd68c55",
                "width": 1,
                "dashes": "false",
                "edge_type": row.edge_type,
                "title": f"{row.edge_type}",
            }
        )

    nodes_path = data_dir / "grafo_apoyo_relaciones_nodes.csv"
    edges_path = data_dir / "grafo_apoyo_relaciones_edges.csv"
    with nodes_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "label",
                "tipo",
                "color",
                "shape",
                "size",
                "title",
                "plataforma",
                "risk_band",
                "risk_score",
                "followers_count",
                "apoyos_followed",
            ],
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
| Apoyo | Top 10 defensores + narrativas de apoyo |
| Grafos | Toggle Haters/Apoyo: Relaciones TW, comportamiento, narrativa |
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
    try:
        nh, eh = export_grafo_narrativa_polaridad(con, data_dir, polaridad="hater")
        print(f"  grafo_narrativa_hater: {nh} nodes / {eh} edges")
    except Exception as exc:
        print(f"  (narrativa hater skipped: {exc})")
        for name in ("grafo_narrativa_hater_nodes.csv", "grafo_narrativa_hater_edges.csv"):
            p = data_dir / name
            if not p.exists():
                p.write_text("", encoding="utf-8")
    try:
        na, ea = export_grafo_narrativa_polaridad(con, data_dir, polaridad="apoyo")
        print(f"  grafo_narrativa_apoyo: {na} nodes / {ea} edges")
    except Exception as exc:
        print(f"  (narrativa apoyo skipped: {exc})")
        for name in ("grafo_narrativa_apoyo_nodes.csv", "grafo_narrativa_apoyo_edges.csv"):
            p = data_dir / name
            if not p.exists():
                p.write_text("", encoding="utf-8")
    export_grafo_relaciones_tables(con, data_dir)
    n3, e3 = export_grafo_relaciones(con, data_dir)
    print(f"  grafo_relaciones: {n3} nodes / {e3} edges")
    try:
        export_grafo_apoyo_relaciones_tables(con, data_dir)
        n4, e4 = export_grafo_apoyo_relaciones(con, data_dir)
        print(f"  grafo_apoyo_relaciones: {n4} nodes / {e4} edges")
    except Exception as exc:
        print(f"  (apoyo graph skipped — run ingest_tk_apoyo_profile_graph.sql first: {exc})")
        for name in (
            "grafo_apoyo_relaciones_nodes.csv",
            "grafo_apoyo_relaciones_edges.csv",
            "grafo_apoyo_risk.csv",
            "grafo_apoyo_co_followers.csv",
            "grafo_apoyo_co_following.csv",
            "grafo_apoyo_bridges.csv",
            "grafo_apoyo_stats.csv",
        ):
            path = data_dir / name
            if not path.exists():
                path.write_text("", encoding="utf-8")

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
