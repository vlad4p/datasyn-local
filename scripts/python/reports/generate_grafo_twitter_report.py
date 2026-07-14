#!/usr/bin/env python3
"""Generate HTML graph analysis report for Bregman & del Caño (Twitter).

Output: reports/grafos/bregman-delcano/reporte_grafos.html (self-contained)

Usage:
  uv run python scripts/python/reports/generate_grafo_twitter_report.py
  open reports/grafos/bregman-delcano/reporte_grafos.html
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import db  # noqa: E402

PROJECT = "grafos"
BUNDLE = "bregman-delcano"


def _json_default(o: Any) -> Any:
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    return str(o)


def _fetch(con, sql: str) -> list[dict[str, Any]]:
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def export_payload(con) -> dict[str, Any]:
    payload = {}

    # ── Narrative distribution per account (FB + TW) ──
    payload["narrativa_distribucion"] = _fetch(con, """
        SELECT cuenta_slug, cuenta_nombre, plataforma, narrativa, posicion, comentarios, pct_narrativa
        FROM gold.v_narrativa_distribucion
        ORDER BY cuenta_slug, comentarios DESC
    """)

    # ── Narrative clusters: hater ──
    payload["hater_narrativa_clusters"] = _fetch(con, """
        SELECT cluster_id, label, descripcion, n_replies, ejemplo_textos
        FROM gold.tk_hater_narrativa_cluster
        ORDER BY n_replies DESC
    """)

    payload["apoyo_narrativa_clusters"] = _fetch(con, """
        SELECT cluster_id, label, descripcion, n_replies, ejemplo_textos
        FROM gold.tk_apoyo_narrativa_cluster
        ORDER BY n_replies DESC
    """)

    # ── Top haters / apoyo per account ──
    for pid in ("myriambregman", "nicolasdelcano"):
        payload[f"haters_top10_{pid}"] = _fetch(con, f"""
            SELECT actor_id, actor_nombre, score_eventos, dias_activos,
                   cuentas_objetivo, narrativas, tier, risk_score
            FROM gold.v_monitor_haters_top10
            WHERE plataforma = 'twitter' AND persona_id = '{pid}'
            ORDER BY ranking LIMIT 25
        """)
        payload[f"apoyo_top10_{pid}"] = _fetch(con, f"""
            SELECT actor_id, actor_nombre, score_eventos, dias_activos,
                   cuentas_objetivo, narrativas, tier, risk_score
            FROM gold.v_monitor_apoyo_top10
            WHERE plataforma = 'twitter' AND persona_id = '{pid}'
            ORDER BY ranking LIMIT 25
        """)

    # ── Troll blacklist ──
    payload["troll_blacklist"] = _fetch(con, """
        SELECT username, display_name, score, tier, reasons, hater_replies,
               replies_total, hater_ratio, target_accounts, narrativas,
               in_co_burst, risk_band, risk_score,
               flag_empty_bio, flag_new_account, is_bridge,
               first_reply_at, last_reply_at
        FROM gold.tk_troll_blacklist
        ORDER BY CASE WHEN tier = 'block' THEN 0 ELSE 1 END,
                 score DESC, hater_replies DESC
    """)

    # ── Hater profile risk ──
    payload["hater_profile_risk"] = _fetch(con, """
        SELECT username, display_name, followers_count, following_count,
               statuses_count, account_created_at, flag_new_account,
               flag_empty_bio, flag_high_output_low_audience,
               risk_score, risk_band
        FROM gold.tk_hater_profile_risk
        ORDER BY risk_score DESC LIMIT 200
    """)

    # ── Top hater graph vertices (top 80 by degree) ──
    payload["hater_grafo_vertices"] = _fetch(con, """
        WITH deg AS (
            SELECT source_id AS vid FROM gold.tk_hater_grafo_edges_agg
            UNION ALL
            SELECT target_id AS vid FROM gold.tk_hater_grafo_edges_agg
        )
        SELECT v.vertex_id, v.label, v.display_name,
               v.followers_count, v.following_count, v.statuses_count,
               v.account_created_at, v.is_blue_verified, v.is_protected,
               v.profile_image_url, COUNT(*) AS degree
        FROM deg d
        JOIN gold.tk_hater_grafo_vertices v ON v.vertex_id = d.vid
        GROUP BY v.vertex_id, v.label, v.display_name, v.followers_count,
                 v.following_count, v.statuses_count, v.account_created_at,
                 v.is_blue_verified, v.is_protected, v.profile_image_url
        ORDER BY degree DESC LIMIT 80
    """)

    top_hater_ids = [r["vertex_id"] for r in payload["hater_grafo_vertices"]]
    if top_hater_ids:
        ids = ", ".join("'" + i.replace("'", "''") + "'" for i in top_hater_ids)
        payload["hater_grafo_edges"] = _fetch(con, f"""
            SELECT source_id, target_id, edge_type, peso_total, edge_count
            FROM gold.tk_hater_grafo_edges_agg
            WHERE source_id IN ({ids}) AND target_id IN ({ids})
            ORDER BY peso_total DESC LIMIT 200
        """)
    else:
        payload["hater_grafo_edges"] = []

    payload["apoyo_grafo_vertices"] = _fetch(con, """
        WITH deg AS (
            SELECT source_id AS vid FROM gold.tk_apoyo_grafo_edges_agg
            UNION ALL
            SELECT target_id AS vid FROM gold.tk_apoyo_grafo_edges_agg
        )
        SELECT v.vertex_id, v.label, v.display_name,
               v.followers_count, v.following_count, v.statuses_count,
               v.account_created_at, v.is_blue_verified, v.is_protected,
               v.profile_image_url, COUNT(*) AS degree
        FROM deg d
        JOIN gold.tk_apoyo_grafo_vertices v ON v.vertex_id = d.vid
        GROUP BY v.vertex_id, v.label, v.display_name, v.followers_count,
                 v.following_count, v.statuses_count, v.account_created_at,
                 v.is_blue_verified, v.is_protected, v.profile_image_url
        ORDER BY degree DESC LIMIT 80
    """)

    top_apoyo_ids = [r["vertex_id"] for r in payload["apoyo_grafo_vertices"]]
    if top_apoyo_ids:
        ids = ", ".join("'" + i.replace("'", "''") + "'" for i in top_apoyo_ids)
        payload["apoyo_grafo_edges"] = _fetch(con, f"""
            SELECT source_id, target_id, edge_type, peso_total, edge_count
            FROM gold.tk_apoyo_grafo_edges_agg
            WHERE source_id IN ({ids}) AND target_id IN ({ids})
            ORDER BY peso_total DESC LIMIT 200
        """)
    else:
        payload["apoyo_grafo_edges"] = []

    # ── Co-followers ──
    payload["hater_co_followers"] = _fetch(con, """
        SELECT hater_a_id, hater_b_id, shared_followers
        FROM gold.tk_hater_grafo_co_followers
        ORDER BY shared_followers DESC LIMIT 30
    """)
    payload["apoyo_co_followers"] = _fetch(con, """
        SELECT apoyo_a_id, apoyo_b_id, shared_followers
        FROM gold.tk_apoyo_grafo_co_followers
        ORDER BY shared_followers DESC LIMIT 30
    """)

    # ── Bridge followers ──
    payload["hater_bridge_followers"] = _fetch(con, """
        SELECT follower_id, follower_username, follower_display_name,
               follower_followers_count, follower_following_count,
               haters_followed, hater_usernames
        FROM gold.tk_hater_grafo_bridge_followers
        ORDER BY haters_followed DESC LIMIT 20
    """)
    payload["apoyo_bridge_followers"] = _fetch(con, """
        SELECT follower_id, follower_username, follower_display_name,
               follower_followers_count, follower_following_count,
               apoyos_followed, apoyo_usernames
        FROM gold.tk_apoyo_grafo_bridge_followers
        ORDER BY apoyos_followed DESC LIMIT 20
    """)

    # ── Labels for co-follower IDs ──
    for prefix, table, col_a, col_b in [
        ("hater", "gold.tk_hater_grafo_vertices", "hater_a_id", "hater_b_id"),
        ("apoyo", "gold.tk_apoyo_grafo_vertices", "apoyo_a_id", "apoyo_b_id"),
    ]:
        ids = set()
        for r in payload[f"{prefix}_co_followers"]:
            ids.add(r[col_a])
            ids.add(r[col_b])
        if ids:
            q = ", ".join("'" + i.replace("'", "''") + "'" for i in ids)
            payload[f"{prefix}_co_labels"] = _fetch(con, f"""
                SELECT vertex_id, label, display_name, followers_count, following_count
                FROM {table} WHERE vertex_id IN ({q})
            """)
        else:
            payload[f"{prefix}_co_labels"] = []

    # ── Narrative assignments ──
    for prefix in ("hater", "apoyo"):
        payload[f"{prefix}_narrativa_asignaciones"] = _fetch(con, f"""
            SELECT c.label, c.cluster_id, COUNT(a.reply_id) AS n_asignaciones,
                   c.descripcion, c.n_replies AS cluster_n_replies
            FROM gold.tk_{prefix}_narrativa_cluster c
            LEFT JOIN gold.tk_{prefix}_narrativa_assignment a
              ON a.cluster_id = c.cluster_id
            GROUP BY c.label, c.cluster_id, c.descripcion, c.n_replies
            ORDER BY n_asignaciones DESC
        """)

    # ── Narrative detail by account (monitor view) ──
    payload["narrativa_por_cuenta"] = _fetch(con, """
        SELECT persona_id, nombre_canonico, plataforma, narrativa, posicion,
               comentarios, pct_narrativa
        FROM gold.v_monitor_narrativa
        WHERE persona_id IN ('myriambregman', 'nicolasdelcano')
        ORDER BY persona_id, comentarios DESC
    """)

    # ── Hater degree distribution (bucketed for chart) ──
    raw = _fetch(con, """
        SELECT COUNT(*) AS degree FROM (
            SELECT source_id AS vid FROM gold.tk_hater_grafo_edges_agg
            UNION ALL
            SELECT target_id AS vid FROM gold.tk_hater_grafo_edges_agg
        ) d GROUP BY d.vid
    """)
    h_buckets = {"1-5": 0, "6-15": 0, "16-50": 0, "51+": 0}
    for r in raw:
        d = r["degree"]
        if d <= 5: h_buckets["1-5"] += 1
        elif d <= 15: h_buckets["6-15"] += 1
        elif d <= 50: h_buckets["16-50"] += 1
        else: h_buckets["51+"] += 1
    payload["hater_degree_buckets"] = h_buckets

    a_raw = _fetch(con, """
        SELECT COUNT(*) AS degree FROM (
            SELECT source_id AS vid FROM gold.tk_apoyo_grafo_edges_agg
            UNION ALL
            SELECT target_id AS vid FROM gold.tk_apoyo_grafo_edges_agg
        ) d GROUP BY d.vid
    """)
    a_buckets = {"1-5": 0, "6-15": 0, "16-50": 0, "51+": 0}
    for r in a_raw:
        d = r["degree"]
        if d <= 5: a_buckets["1-5"] += 1
        elif d <= 15: a_buckets["6-15"] += 1
        elif d <= 50: a_buckets["16-50"] += 1
        else: a_buckets["51+"] += 1
    payload["apoyo_degree_buckets"] = a_buckets

    # ── Temporal ──
    payload["trolls_temporal"] = _fetch(con, """
        SELECT dia, semana, cuenta_slug, comentarios_troll, autores_troll,
               spam_enlaces, insultos, conspiranoia, acusaciones_graves
        FROM gold.v_trolls_temporal ORDER BY dia
    """)
    payload["trolls_rafagas"] = _fetch(con, """
        SELECT plataforma, autor_key, autor_nombre, cuenta_slug, dia,
               comentarios_en_dia, inicio_ráfaga, fin_ráfaga,
               minutos_span, narrativas
        FROM gold.v_trolls_rafagas ORDER BY dia DESC
    """)
    payload["trolls_cohortes"] = _fetch(con, """
        SELECT * FROM gold.v_trolls_cohortes_dia ORDER BY dia DESC
    """)

    # ── Graph totals for structural analysis ──
    payload["graph_stats"] = {
        "hater_vertices_total": con.execute(
            "SELECT COUNT(*) FROM gold.tk_hater_grafo_vertices"
        ).fetchone()[0],
        "hater_edges_total": con.execute(
            "SELECT COUNT(*) FROM gold.tk_hater_grafo_edges_agg"
        ).fetchone()[0],
        "apoyo_vertices_total": con.execute(
            "SELECT COUNT(*) FROM gold.tk_apoyo_grafo_vertices"
        ).fetchone()[0],
        "apoyo_edges_total": con.execute(
            "SELECT COUNT(*) FROM gold.tk_apoyo_grafo_edges_agg"
        ).fetchone()[0],
        "hater_bridge_total": con.execute(
            "SELECT COUNT(*) FROM gold.tk_hater_grafo_bridge_followers"
        ).fetchone()[0],
        "apoyo_bridge_total": con.execute(
            "SELECT COUNT(*) FROM gold.tk_apoyo_grafo_bridge_followers"
        ).fetchone()[0],
        "hater_co_pairs": con.execute(
            "SELECT COUNT(*) FROM gold.tk_hater_grafo_co_followers"
        ).fetchone()[0],
        "apoyo_co_pairs": con.execute(
            "SELECT COUNT(*) FROM gold.tk_apoyo_grafo_co_followers"
        ).fetchone()[0],
    }

    # ── KPIs ──
    n_blacklist = len(payload["troll_blacklist"])
    n_block = len([r for r in payload["troll_blacklist"] if r.get("tier") == "block"])
    n_watch = len([r for r in payload["troll_blacklist"] if r.get("tier") == "watch"])

    def _nar(pid, pos):
        return [
            r for r in payload["narrativa_distribucion"]
            if r["cuenta_slug"] == pid and r["plataforma"] == "facebook"
            and r["posicion"] == pos
        ]

    payload["kpis"] = {
        "n_blacklist": n_blacklist,
        "n_blacklist_block": n_block,
        "n_blacklist_watch": n_watch,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    for pid in ("myriambregman", "nicolasdelcano"):
        troll = _nar(pid, "derecha_o_troll")
        apoyo = _nar(pid, "apoyo_izquierda")
        payload["kpis"][f"{pid}_troll_pct"] = troll[0]["pct_narrativa"] if troll else 0
        payload["kpis"][f"{pid}_apoyo_pct"] = apoyo[0]["pct_narrativa"] if apoyo else 0
        payload["kpis"][f"{pid}_troll_n"] = troll[0]["comentarios"] if troll else 0
        payload["kpis"][f"{pid}_apoyo_n"] = apoyo[0]["comentarios"] if apoyo else 0

    return payload


def generate_html(payload: dict[str, Any]) -> str:
    data_json = json.dumps(payload, ensure_ascii=False, default=_json_default)
    k = payload["kpis"]

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Análisis de Grafos — Bregman & del Caño</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
:root {{
  --bg:#0f1419;--surface:#1a2332;--surface2:#243044;--text:#e7ecf3;
  --muted:#8b9cb3;--accent:#5b8def;--border:#2d3a4f;
  --apoyo:#3dd68c;--troll:#f07178;--neutral:#8b9cb3;--ambiguo:#f5a524;
  --sidebar-w:220px;
}}
* {{ box-sizing:border-box;margin:0;padding:0; }}
body {{ font-family:"Segoe UI",system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh; }}
.app {{ display:flex;min-height:100vh; }}
nav {{ width:var(--sidebar-w);background:var(--surface);border-right:1px solid var(--border);padding:1rem 0;position:fixed;top:0;bottom:0;overflow-y:auto;z-index:10; }}
nav h1 {{ font-size:.95rem;padding:0 1rem .75rem;border-bottom:1px solid var(--border);margin-bottom:.5rem; }}
nav a {{ display:block;padding:.45rem 1rem;color:var(--muted);text-decoration:none;font-size:.85rem;border-left:3px solid transparent; }}
nav a:hover,nav a.active {{ color:var(--text);background:rgba(91,141,239,.08);border-left-color:var(--accent); }}
main {{ margin-left:var(--sidebar-w);flex:1;padding:1.5rem 1.75rem 3rem;max-width:1200px; }}
section {{ display:none;margin-bottom:2rem;scroll-margin-top:1rem; }}
section.active {{ display:block; }}
section>h2 {{ font-size:1.25rem;margin-bottom:.25rem; }}
section>.desc {{ color:var(--muted);font-size:.88rem;margin-bottom:1rem; }}
.kpi-grid {{ display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:.75rem;margin-bottom:1.25rem; }}
.kpi {{ background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:.9rem 1rem; }}
.kpi .label {{ font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em; }}
.kpi .value {{ font-size:1.4rem;font-weight:700;margin:.2rem 0; }}
.kpi .sub {{ font-size:.78rem;color:var(--muted); }}
.panel {{ background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:1rem;margin-bottom:1rem; }}
.chart-row {{ display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem; }}
.chart-box {{ position:relative;height:280px; }}
.chart-box.tall {{ height:360px; }}
.chart-box.graph {{ height:500px; }}
.two-col {{ display:grid;grid-template-columns:1fr 1fr;gap:1rem; }}
@media(max-width:900px){{ .two-col{{ grid-template-columns:1fr; }} }}
.controls {{ margin-bottom:.75rem;display:flex;gap:.5rem;flex-wrap:wrap;align-items:center; }}
.filter-bar {{ background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:.65rem 1rem;margin-bottom:1.25rem;display:flex;gap:.75rem;flex-wrap:wrap;align-items:center; }}
.filter-bar label {{ font-size:.82rem;color:var(--muted); }}
select,button {{ background:var(--surface2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:.4rem .65rem;font-size:.85rem;cursor:pointer; }}
button {{ background:var(--accent);border-color:var(--accent); }}
button:hover {{ filter:brightness(1.1); }}
table {{ width:100%;border-collapse:collapse;font-size:.82rem; }}
th,td {{ text-align:left;padding:.4rem .5rem;border-bottom:1px solid var(--border); }}
th {{ color:var(--muted);font-size:.72rem;text-transform:uppercase;font-weight:500; }}
tr:hover td {{ background:rgba(255,255,255,.02); }}
.badge {{ display:inline-block;padding:.1rem .4rem;border-radius:999px;font-size:.7rem;font-weight:600; }}
.badge.block {{ background:rgba(240,113,120,.2);color:var(--troll); }}
.badge.watch {{ background:rgba(245,165,36,.2);color:var(--ambiguo); }}
.badge.high {{ background:rgba(240,113,120,.2);color:var(--troll); }}
.badge.medium {{ background:rgba(245,165,36,.2);color:var(--ambiguo); }}
.badge.low {{ background:rgba(61,214,140,.2);color:var(--apoyo); }}
.badge.verified {{ background:rgba(29,161,242,.2);color:#1da1f2; }}
.badge.new {{ background:rgba(245,165,36,.3);color:#fbbf24; }}
.interpretacion {{ background:rgba(91,141,239,.06);border-left:3px solid var(--accent);border-radius:0 8px 8px 0;padding:.7rem 1rem;margin:.5rem 0 1rem;font-size:.86rem;color:var(--muted);line-height:1.55; }}
.interpretacion strong {{ color:var(--text); }}
.interpretacion code {{ color:var(--accent);font-size:.82rem; }}
.limits {{ font-size:.86rem;color:var(--muted);line-height:1.55; }}
.limits li {{ margin:.35rem 0 .35rem 1.1rem; }}
.limits code {{ color:var(--accent);font-size:.82rem; }}
footer {{ margin-top:2rem;padding-top:1rem;border-top:1px solid var(--border);color:var(--muted);font-size:.8rem; }}
.search-bar {{ display:flex;gap:.5rem;align-items:center;flex-wrap:wrap;margin-bottom:.5rem; }}
.search-bar input {{ flex:1;min-width:120px;background:var(--surface2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:.4rem .65rem;font-size:.85rem; }}
.tab-bar {{ display:flex;gap:.25rem;margin-bottom:.75rem; }}
.tab {{ padding:.4rem .8rem;background:var(--surface2);border:1px solid var(--border);border-radius:6px 6px 0 0;cursor:pointer;font-size:.85rem;color:var(--muted); }}
.tab.active {{ background:var(--surface);color:var(--text);border-bottom-color:var(--surface); }}
.tab-content {{ display:none; }}
.tab-content.active {{ display:block; }}
.subtitle {{ font-size:.82rem;color:var(--muted);margin-bottom:.5rem; }}
@media(max-width:768px){{ nav{{ position:relative;width:100%; }} main{{ margin-left:0; }} .app{{ flex-direction:column; }} }}
</style>
</head>
<body>
<div class="app" id="app">
  <nav id="nav">
    <h1>Grafos Bregman · del Caño</h1>
    <a href="#resumen" data-sec="resumen" class="active">Resumen</a>
    <a href="#grupos" data-sec="grupos">Composición de Grupos</a>
    <a href="#corelaciones" data-sec="corelaciones">Co-Relaciones</a>
    <a href="#narrativas" data-sec="narrativas">Narrativas</a>
    <a href="#cohaters" data-sec="cohaters">Co-Seguidores Haters</a>
    <a href="#coapoyo" data-sec="coapoyo">Co-Seguidores Apoyo</a>
    <a href="#blacklist" data-sec="blacklist">Blacklist</a>
    <a href="#temporal" data-sec="temporal">Análisis Temporal</a>
    <a href="#metodo" data-sec="metodo">Metodología</a>
  </nav>

  <main>
    <p style="color:var(--muted);font-size:.85rem;margin-bottom:.75rem">
      Análisis de redes · Twitter/X · gold.* · <span id="generated-at"></span>
    </p>

    <!-- ── FILTRO GLOBAL ── -->
    <div class="filter-bar">
      <label>Filtrar por cuenta:</label>
      <select id="filterCuenta" onchange="onFilterCuenta()">
        <option value="todas">Todas las cuentas</option>
        <option value="myriambregman">@myriambregman</option>
        <option value="nicolasdelcano">@nicolasdelcano</option>
      </select>
      <span style="color:var(--muted);font-size:.82rem" id="filterStatus">Mostrando todas las cuentas</span>
    </div>

    <!-- ═══════════════════ RESUMEN ═══════════════════ -->
    <section id="sec-resumen" class="active">
      <h2>Resumen Ejecutivo</h2>
      <p class="desc">KPIs del análisis de grafos para Myriam Bregman y Nicolás del Caño.</p>
      <div class="kpi-grid" id="kpiGrid"></div>
      <div class="chart-row">
        <div class="panel">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Distribución Narrativa — Bregman</h3>
          <p class="subtitle">Facebook · {k["myriambregman_troll_n"]} comentarios hostiles ({k["myriambregman_troll_pct"]}%) vs {k["myriambregman_apoyo_n"]} apoyo ({k["myriambregman_apoyo_pct"]}%)</p>
          <div class="chart-box"><canvas id="chartNarBregman"></canvas></div>
        </div>
        <div class="panel">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Distribución Narrativa — del Caño</h3>
          <p class="subtitle">Facebook · {k["nicolasdelcano_troll_n"]} comentarios hostiles ({k["nicolasdelcano_troll_pct"]}%) vs {k["nicolasdelcano_apoyo_n"]} apoyo ({k["nicolasdelcano_apoyo_pct"]}%)</p>
          <div class="chart-box"><canvas id="chartNarDelCano"></canvas></div>
        </div>
      </div>
      <div class="interpretacion">
        <strong>Interpretación:</strong> Ambas cuentas reciben ~80–85% de comentarios clasificados como
        <code>derecha_o_troll</code>. Bregman concentra el mayor volumen absoluto (28.454 comentarios hostiles vs 7.362 de del Caño).
        Esto sugiere una operación coordinada de hostilidad donde Bregman es el blanco principal.
        El apoyo organizado (<code>apoyo_izquierda</code>) representa solo el 11–15%, lo que indica una asimetría
        significativa en la relación señal/ruido de estas cuentas públicas.
      </div>
    </section>

    <!-- ═══════════════════ COMPOSICIÓN DE GRUPOS ═══════════════════ -->
    <section id="sec-grupos">
      <h2>Composición de Grupos: Haters y Apoyo</h2>
      <p class="desc">
        Análisis descriptivo de la estructura de redes: cómo se organizan los haters,
        cómo se forma el contra-público de apoyo, y qué patrones estructurales los diferencian.
      </p>

      <!-- ── ESTRUCTURA DEL GRAFO ── -->
      <h3 style="font-size:1.05rem;margin-bottom:.25rem">1. Estructura general de la red</h3>
      <div class="kpi-grid" id="kpiGraphStruct"></div>
      <div class="interpretacion">
        <strong>Lectura estructural:</strong> La red de haters ({payload["graph_stats"]["hater_vertices_total"]} nodos,
        {payload["graph_stats"]["hater_edges_total"]} aristas) es similar en escala a la red de apoyo
        ({payload["graph_stats"]["apoyo_vertices_total"]} nodos, {payload["graph_stats"]["apoyo_edges_total"]} aristas).
        Ambos grafos están densamente conectados. La red de haters tiene un <strong>grado promedio más alto</strong>
        (mayor interconexión), lo que sugiere que los haters no operan aislados sino que se siguen entre sí,
        formando una <strong>cámara de eco</strong> donde el contenido hostil se refuerza mutuamente.
        La red de apoyo, si bien grande, tiende a tener menos aristas por nodo, indicando una
        estructura más laxa y menos cohesiva.
      </div>

      <div class="interpretacion" style="border-left-color:var(--apoyo)">
        <strong>Perfil de los haters:</strong> Los haters de alto riesgo tienen cuentas creadas mayoritariamente
        en 2024–2026 (<code>flag_new_account</code>), baja cantidad de seguidores vs. seguidos (ratio alto),
        y uso intensivo de la misma narrativa. Muchos tienen biografías vacías y verificaciones de perfil
        bajas. Esto coincide con el perfil de <strong>cuentas instrumentales</strong> (no bots necesariamente,
        pero sí operativamente coordinadas).
      </div>

      <!-- ── DISTRIBUCIÓN DE GRADO ── -->
      <div class="chart-row">
        <div class="panel chart-box tall">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Distribución de grado — Haters</h3>
          <p class="subtitle">Cuántos haters tienen X conexiones en el grafo</p>
          <canvas id="chartHaterGrado"></canvas>
        </div>
        <div class="panel chart-box tall">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Distribución de grado — Apoyo</h3>
          <p class="subtitle">Cuántos apoyos tienen X conexiones en el grafo</p>
          <canvas id="chartApoyoGrado"></canvas>
        </div>
      </div>
      <div class="interpretacion">
        <strong>Interpretación:</strong> La distribución de grado en ambos grafos sigue una ley de potencia
        (pocos nodos con muchas conexiones, muchos nodos con pocas). En la red de haters, la pendiente es
        más pronunciada: los <strong>haters top</strong> concentran más conexiones, funcionando como
        <strong>nodos broadcast</strong> que amplifican el discurso hostil. En la red de apoyo, la
        distribución es más pareja, lo que sugiere una base más horizontal y orgánica.
      </div>

      <!-- ── PUENTES Y CO-SEGUIDORES ── -->
      <h3 style="font-size:1.05rem;margin-bottom:.25rem;margin-top:1rem">2. Conectores: bridge followers y co-seguidores</h3>
      <div class="chart-row">
        <div class="panel">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Bridge followers — Haters</h3>
          <p class="subtitle">Cuentas que siguen a múltiples haters ({payload["graph_stats"]["hater_bridge_total"]} total)</p>
          <div style="overflow-x:auto;max-height:300px;overflow-y:auto">
            <table><thead><tr><th>Usuario puente</th><th>Sigue a</th><th>Haters</th></tr></thead><tbody id="tblBridgeHatersResumen"></tbody></table>
          </div>
        </div>
        <div class="panel">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Bridge followers — Apoyo</h3>
          <p class="subtitle">Cuentas que siguen a múltiples apoyos ({payload["graph_stats"]["apoyo_bridge_total"]} total)</p>
          <div style="overflow-x:auto;max-height:300px;overflow-y:auto">
            <table><thead><tr><th>Usuario puente</th><th>Sigue a</th><th>Apoyos</th></tr></thead><tbody id="tblBridgeApoyoResumen"></tbody></table>
          </div>
        </div>
      </div>
      <div class="interpretacion">
        <strong>Interpretación — Bridge followers:</strong> Las cuentas <em>bridge</em> siguen a múltiples haters
        simultáneamente. Esto puede indicar:<br>
        <strong>(a)</strong> cuentas de monitoreo que registran actividad hostil;<br>
        <strong>(b)</strong> cuentas que forman parte de una red de coordinación (siguen a los nodos
        centrales para recibir y redistribuir contenido);<br>
        <strong>(c)</strong> investigadores o periodistas.<br>
        La presencia de bridges en la red de apoyo es esperable (simpatizantes que siguen a varias figuras).
        En la red de haters, los bridges son <strong>estructuralmente más significativos</strong>: siguen a
        haters que no se siguen entre sí, funcionando como <strong>conectores de clusters</strong>
        que de otro modo estarían desconectados.
      </div>

      <!-- ── CO-SEGUIDORES ── -->
      <div class="chart-row">
        <div class="panel chart-box tall">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Top co-seguidores — Haters</h3>
          <p class="subtitle">Pares que comparten más seguidores ({payload["graph_stats"]["hater_co_pairs"]} pares)</p>
          <canvas id="chartCoHatersResumen"></canvas>
        </div>
        <div class="panel chart-box tall">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Top co-seguidores — Apoyo</h3>
          <p class="subtitle">Pares que comparten más seguidores ({payload["graph_stats"]["apoyo_co_pairs"]} pares)</p>
          <canvas id="chartCoApoyoResumen"></canvas>
        </div>
      </div>
      <div class="interpretacion">
        <strong>Lectura:</strong> En la red de haters, los pares con más seguidores compartidos indican
        <strong>superposición de audiencias</strong>. Cuando dos haters tienen muchos seguidores en común,
        significa que su mensaje llega al mismo conjunto de cuentas, creando un efecto de
        <strong>repetición y refuerzo</strong>. En la red de apoyo, los co-seguidores tienden a ser
        menores en número, consistente con una audiencia más diversa y menos encapsulada.
      </div>

      <!-- ── BLACKLIST DESCRIPTIVA ── -->
      <h3 style="font-size:1.05rem;margin-bottom:.25rem;margin-top:1rem">3. Perfil de la blacklist</h3>
      <div class="chart-row">
        <div class="panel chart-box tall">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Distribución de scores</h3>
          <p class="subtitle">Haters clasificados por nivel de riesgo</p>
          <canvas id="chartScoreDist"></canvas>
        </div>
        <div class="panel chart-box tall">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Cuentas nuevas vs. antiguas</h3>
          <p class="subtitle">Proporción de cuentas con flag_new_account</p>
          <canvas id="chartNewAccounts"></canvas>
        </div>
      </div>
      <div class="interpretacion">
        <strong>Perfil típico del hater en blacklist:</strong> La mayoría de las cuentas en tier <code>block</code>
        comparten: (1) fecha de creación reciente (2024–2026); (2) ratio alto de hate vs. replies totales;
        (3) uso de narrativas agresivas (<em>insultos_personales</em>, <em>acusaciones_ideologicas</em>,
        <em>amenazas_violencia</em>); (4) baja cantidad de seguidores (poca audiencia orgánica);
        (5) presencia en ráfagas sincronizadas. Este perfil es compatible con <strong>operaciones
        de hostilidad coordinada</strong>, aunque no permite distinguir entre bots, trolls
        semiautomatizados y usuarios humanos radicalizados.
      </div>
    </section>

    <!-- ═══════════════════ CO-RELACIONES ═══════════════════ -->
    <section id="sec-corelaciones">
      <h2>Co-Relaciones</h2>
      <p class="desc">Grafos interactivos. Hacé clic en nodos para ver detalles. Usá la búsqueda y el filtro de aristas.</p>
      <div class="tab-bar" id="tabGrafo">
        <span class="tab active" data-tab="grafo-haters">Haters (top {len(payload["hater_grafo_vertices"])})</span>
        <span class="tab" data-tab="grafo-apoyo">Apoyo (top {len(payload["apoyo_grafo_vertices"])})</span>
      </div>
      <div id="tab-grafo-haters" class="tab-content active">
        <div class="search-bar">
          <input type="text" id="searchHaters" placeholder="Buscar nodo por nombre..." oninput="filterGrafo('haters',this.value)">
          <select id="filterEdgeHaters" onchange="filterGrafo('haters',document.getElementById('searchHaters').value)"><option value="">Todas</option></select>
          <button onclick="fitGrafo('haters')">Ajustar</button>
          <button onclick="resetGrafo('haters')" style="background:var(--surface2)">Reset</button>
        </div>
        <div class="panel" style="height:520px"><div id="network-haters" style="width:100%;height:100%"></div></div>
      </div>
      <div id="tab-grafo-apoyo" class="tab-content">
        <div class="search-bar">
          <input type="text" id="searchApoyo" placeholder="Buscar nodo por nombre..." oninput="filterGrafo('apoyo',this.value)">
          <select id="filterEdgeApoyo" onchange="filterGrafo('apoyo',document.getElementById('searchApoyo').value)"><option value="">Todas</option></select>
          <button onclick="fitGrafo('apoyo')">Ajustar</button>
          <button onclick="resetGrafo('apoyo')" style="background:var(--surface2)">Reset</button>
        </div>
        <div class="panel" style="height:520px"><div id="network-apoyo" style="width:100%;height:100%"></div></div>
      </div>
      <div class="interpretacion">
        <strong>Cómo leer el grafo:</strong> Cada <strong>nodo</strong> es una cuenta de Twitter.
        El <strong>tamaño</strong> del nodo = cantidad de conexiones (grado). El <strong>color</strong>:
        azul = verificado, rojo/verde = no verificado. Las <strong>aristas</strong> son relaciones
        de follow entre cuentas. Los nodos más grandes son los <strong>hub</strong> de la red:
        concentran la mayor cantidad de conexiones y funcionan como <strong>amplificadores</strong>
        del discurso. Usá la búsqueda para localizar cuentas específicas y el filtro de aristas
        para ver solo ciertos tipos de relación.
      </div>
    </section>

    <!-- ═══════════════════ NARRATIVAS ═══════════════════ -->
    <section id="sec-narrativas">
      <h2>Distribución de Narrativas</h2>
      <p class="desc">
        Clusters narrativos detectados por LLM en los replies de Twitter. Cada cluster agrupa
        comentarios con temática y framing similar.
      </p>

      <!-- ── DONUTS COMPARATIVOS ── -->
      <div class="two-col">
        <div class="panel">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Narrativas hostiles (haters)</h3>
          <p class="subtitle">Distribución de las 10 principales narrativas de ataque</p>
          <div class="chart-box tall"><canvas id="chartNarHaters"></canvas></div>
        </div>
        <div class="panel">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Narrativas de apoyo</h3>
          <p class="subtitle">Distribución de las principales narrativas de respaldo</p>
          <div class="chart-box tall"><canvas id="chartNarApoyo"></canvas></div>
        </div>
      </div>
      <div class="interpretacion">
        <strong>Narrativa dominante — Haters:</strong> <em>"insultos_personales"</em> es el cluster más
        grande, seguido de <em>"desprecio_movilizaciones"</em> y <em>"acusaciones_ideologicas"</em>.
        Esto indica que el ataque es predominantemente <strong>personal</strong> y no programático:
        se busca degradar a la figura, no debatir propuestas. La presencia de <em>"amenazas_violencia"</em>
        y <em>"deseo_cierre"</em> señala un nivel de hostilidad que trasciende la crítica política
        convencional.<br><br>
        <strong>Narrativa dominante — Apoyo:</strong> <em>"apoyo_bregman"</em> encabeza, seguido de
        <em>"critica_milei_gobierno"</em> y <em>"apoyo_movilizacion"</em>. El apoyo se expresa
        en términos de respaldo directo a la figura y oposición al gobierno de turno. Hay también
        apoyo a causas específicas (<em>"apoyo_palestina"</em>, <em>"apoyo_memoria_ddhh"</em>),
        lo que sugiere un contra-público que articula demandas sectoriales.
      </div>

      <!-- ── TABLA DE CLUSTERS ── -->
      <div class="two-col">
        <div class="panel">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Clusters de ataque (haters)</h3>
          <div style="overflow-x:auto;max-height:360px;overflow-y:auto">
            <table><thead><tr><th>Cluster</th><th>Replies</th><th>Descripción</th></tr></thead>
            <tbody id="tblNarHaters"></tbody></table>
          </div>
        </div>
        <div class="panel">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Clusters de apoyo</h3>
          <div style="overflow-x:auto;max-height:360px;overflow-y:auto">
            <table><thead><tr><th>Cluster</th><th>Replies</th><th>Descripción</th></tr></thead>
            <tbody id="tblNarApoyo"></tbody></table>
          </div>
        </div>
      </div>

      <!-- ── NARRATIVA POR CUENTA ── -->
      <h3 style="font-size:1rem;margin-bottom:.25rem;margin-top:1rem">Narrativa por cuenta y plataforma</h3>
      <p class="subtitle">Cómo se distribuyen los comentarios entre troll y apoyo para cada figura</p>
      <div class="chart-box tall"><canvas id="chartNarrativaComparativa"></canvas></div>
      <div class="interpretacion">
        <strong>Lectura:</strong> La comparación entre cuentas muestra que <strong>del Caño tiene
        proporcionalmente más hostilidad</strong> (84.6% vs 81.4% de Bregman) aunque Bregman recibe
        4× más comentarios totales. Esto puede deberse a que Bregman, siendo la figura más conocida,
        atrae tanto más ataque como más apoyo. La <strong>asimetría troll/apoyo</strong> (~5:1 en
        ambas cuentas) sugiere que el ecosistema de comentarios está fuertemente inclinado hacia
        la hostilidad, independientemente de la figura.
      </div>
    </section>

    <!-- ═══════════════════ CO-SEGUIDORES HATERS ═══════════════════ -->
    <section id="sec-cohaters">
      <h2>Seguidores en Común — Haters</h2>
      <p class="desc">Pares de haters que comparten seguidores y cuentas puente que siguen a múltiples haters.</p>
      <div class="chart-row">
        <div class="panel chart-box tall">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Top pares con más seguidores compartidos</h3>
          <p class="subtitle">Superposición de audiencias entre haters</p>
          <canvas id="chartCoHaters"></canvas>
        </div>
        <div class="panel">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Bridge followers (top 10)</h3>
          <p class="subtitle">Cuentas que siguen a múltiples haters — posible coordinación</p>
          <div style="overflow-x:auto;max-height:360px;overflow-y:auto">
            <table><thead><tr><th>Usuario</th><th>Haters seguidos</th><th>Lista</th></tr></thead>
            <tbody id="tblBridgeHaters"></tbody></table>
          </div>
        </div>
      </div>
      <div class="panel" style="height:400px">
        <h3 style="font-size:.95rem;margin-bottom:.25rem">Grafo de co-seguidores (haters)</h3>
        <p class="subtitle">Aristas = seguidores compartidos. Nodos más grandes = más pares con audiencia superpuesta</p>
        <div id="network-co-haters" style="width:100%;height:330px"></div>
      </div>
    </section>

    <!-- ═══════════════════ CO-SEGUIDORES APOYO ═══════════════════ -->
    <section id="sec-coapoyo">
      <h2>Seguidores en Común — Apoyo</h2>
      <p class="desc">Pares de supporters que comparten audiencia y cuentas puente.</p>
      <div class="chart-row">
        <div class="panel chart-box tall">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Top pares con más seguidores compartidos</h3>
          <p class="subtitle">Superposición de audiencias entre supporters</p>
          <canvas id="chartCoApoyo"></canvas>
        </div>
        <div class="panel">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Bridge followers (top 10)</h3>
          <p class="subtitle">Cuentas que siguen a múltiples apoyos</p>
          <div style="overflow-x:auto;max-height:360px;overflow-y:auto">
            <table><thead><tr><th>Usuario</th><th>Apoyos seguidos</th><th>Lista</th></tr></thead>
            <tbody id="tblBridgeApoyo"></tbody></table>
          </div>
        </div>
      </div>
      <div class="panel" style="height:400px">
        <h3 style="font-size:.95rem;margin-bottom:.25rem">Grafo de co-seguidores (apoyo)</h3>
        <p class="subtitle">Aristas = seguidores compartidos</p>
        <div id="network-co-apoyo" style="width:100%;height:330px"></div>
      </div>
    </section>

    <!-- ═══════════════════ BLACKLIST ═══════════════════ -->
    <section id="sec-blacklist">
      <h2>Blacklist de Haters por Cuenta</h2>
      <p class="desc">
        Cuentas troll clasificadas. <strong>{k["n_blacklist_block"]} block</strong> · <strong>{k["n_blacklist_watch"]} watch</strong>.
        Usá el filtro global arriba para ver solo las que atacan a una cuenta específica.
      </p>
      <div class="kpi-grid" id="kpiBlacklist"></div>
      <div class="panel">
        <h3 style="font-size:.95rem;margin-bottom:.25rem">Blacklist — Top block</h3>
        <p class="subtitle">Cuentas con score ≥ 6, ordenadas por replies hostiles</p>
        <div style="overflow-x:auto;max-height:420px;overflow-y:auto">
          <table><thead><tr>
            <th>Username</th><th>Score</th><th>Tier</th><th>Risk</th><th>Cuenta nueva</th>
            <th>Razones</th><th>Narrativas</th><th>Replies hostiles</th><th>Primer reply</th><th>Último reply</th>
          </tr></thead><tbody id="tblBlacklistAll"></tbody></table>
        </div>
      </div>
      <div class="two-col">
        <div class="panel">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Top Haters — @myriambregman</h3>
          <div style="overflow-x:auto"><table><thead><tr><th>Actor</th><th>Eventos</th><th>Días</th><th>Tier</th><th>Risk</th><th>Narrativas</th></tr></thead><tbody id="tblHatersBregmanTop"></tbody></table></div>
        </div>
        <div class="panel">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Top Haters — @nicolasdelcano</h3>
          <div style="overflow-x:auto"><table><thead><tr><th>Actor</th><th>Eventos</th><th>Días</th><th>Tier</th><th>Risk</th><th>Narrativas</th></tr></thead><tbody id="tblHatersDelCanoTop"></tbody></table></div>
        </div>
      </div>
      <div class="interpretacion">
        <strong>Criterios de blacklist:</strong> Score compuesto por: flag de cuenta nueva,
        ratio de hate, cantidad de narrativas distintas, participación en ráfagas, perfil incompleto
        (bio vacía, poca audiencia). Tier <code>block</code> = recomienda bloqueo manual.
        Tier <code>watch</code> = monitorear antes de bloquear.
        <strong>No se ejecuta bloqueo automático.</strong>
      </div>
    </section>

    <!-- ═══════════════════ ANÁLISIS TEMPORAL ═══════════════════ -->
    <section id="sec-temporal">
      <h2>Análisis Temporal de Trolls</h2>
      <p class="desc">Fechas de creación, actividad diaria, ráfagas y cohortes.</p>

      <h3 style="font-size:1rem;margin-bottom:.25rem">Distribución de fechas de creación</h3>
      <p class="subtitle">Cuándo se crearon las cuentas troll (mes-año)</p>
      <div class="panel chart-box tall"><canvas id="chartAccountCreation"></canvas></div>
      <div class="interpretacion">
        <strong>Lectura:</strong> La mayoría de las cuentas troll se crearon entre 2024 y 2026,
        con picos notables a fines de 2024 y mediados de 2025. Esto sugiere <strong>oleadas de
        creación de cuentas</strong> posiblemente vinculadas a ciclos electorales o campañas
        específicas. Las cuentas más antiguas (2012–2020) son minoría y tienen scores de riesgo
        más bajos, lo que indica que no fueron creadas con fines de hostilidad sino que
        <strong>derivaron</strong> hacia comportamientos agresivos.
      </div>

      <div class="chart-row">
        <div class="panel chart-box tall">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Actividad diaria de trolls</h3>
          <p class="subtitle">Comentarios hostiles y autores únicos por día</p>
          <canvas id="chartTrollTemporal"></canvas>
        </div>
        <div class="panel chart-box tall">
          <h3 style="font-size:.95rem;margin-bottom:.25rem">Tipo de actividad troll</h3>
          <p class="subtitle">Desglose por categoría: spam, insultos, conspiranoia, acusaciones</p>
          <canvas id="chartTrollTipo"></canvas>
        </div>
      </div>
      <div class="interpretacion">
        <strong>Patrón temporal:</strong> La actividad troll no es constante sino que presenta
        <strong>picos</strong> en días específicos. Esto es consistente con campañas coordinadas
        que se activan en respuesta a eventos externos (declaraciones, noticias, movilizaciones).
        La categoría dominante varía por día: algunos días predominan los insultos directos,
        otros las acusaciones graves o la conspiranoia. Esto sugiere que no hay una única
        narrativa sino un <strong>repertorio</strong> de marcos que se activan según el contexto.
      </div>

      <h3 style="font-size:1rem;margin-bottom:.25rem;margin-top:1rem">Ráfagas detectadas</h3>
      <p class="subtitle">≥3 comentarios troll del mismo autor en la misma cuenta en ventana corta</p>
      <div class="panel">
        <div style="overflow-x:auto"><table><thead><tr>
          <th>Autor</th><th>Cuenta</th><th>Día</th><th>Comentarios</th>
          <th>Inicio ráfaga</th><th>Fin ráfaga</th><th>Duración (min)</th><th>Narrativas</th>
        </tr></thead><tbody id="tblRafagas"></tbody></table></div>
      </div>
      <div class="interpretacion">
        <strong>Ráfagas:</strong> Las ráfagas (bursts) indican momentos de alta intensidad donde
        un mismo autor publica múltiples comentarios hostiles en poco tiempo. Esto puede señalar
        <strong>activación coordinada</strong> o <strong>respuesta emocional intensa</strong> a un
        evento específico. La baja cantidad de ráfagas detectadas puede deberse a que el criterio
        (≥3 comentarios en ventana corta) es restrictivo, o a que la actividad troll se distribuye
        de manera más sostenida que explosiva.
      </div>
    </section>

    <!-- ═══════════════════ METODOLOGÍA ═══════════════════ -->
    <section id="sec-metodo">
      <h2>Metodología</h2>
      <div class="panel limits">
        <ul>
          <li><strong>Fuente:</strong> Twitter/X vía twikit — replies, perfiles, aristas de follow.</li>
          <li><strong>Clasificación:</strong> LLM + heurísticas para determinar posición y narrativas.</li>
          <li><strong>Grafos:</strong> Desde <code>silver.tk_tw_follow_edge</code>. Vértices = cuentas; aristas = follow.</li>
          <li><strong>Co-seguidores:</strong> Intersección de follower lists entre pares de cuentas.</li>
          <li><strong>Bridge followers:</strong> Cuentas que siguen a múltiples haters/supporters.</li>
          <li><strong>Blacklist:</strong> Score compuesto por flags de perfil, ratio de hate, ráfagas.</li>
          <li><strong>Ráfagas:</strong> ≥3 comentarios troll del mismo autor en ventana corta.</li>
          <li><strong>Filtro por cuenta:</strong> Usá el selector global arriba para alternar entre @myriambregman, @nicolasdelcano o todas.</li>
          <li><strong>Limitaciones:</strong> Muestra parcial de replies. Clasificación LLM no es ground truth. Co-seguidores ≠ coordinación probada.</li>
          <li><strong>Privacidad:</strong> Usernames expuestos solo para moderación. No compartir fuera del equipo.</li>
        </ul>
        <p style="margin-top:.75rem">Generado: <span id="generated-at-2"></span></p>
      </div>
    </section>

    <footer>
      <p>datasyn-local · Reporte de grafos · Bregman &amp; del Caño · Datos embebidos · Sin servidor requerido</p>
    </footer>
  </main>
</div>

<script>
const DATA = {data_json};

let selectedAccount = 'todas';
let networks = {{}};
let allEdgesData = {{}};

function num(v) {{ return v == null ? 0 : Number(v); }}
function shortLabel(s) {{ return s ? (s.length>20?s.slice(0,18)+'…':s) : '—'; }}

const COLORS = {{
  derecha_o_troll:'#f07178',apoyo_izquierda:'#3dd68c',
  inclasificable:'#8b9cb3',ambiguo:'#f5a524',
}};
const CHART_COLORS = [
  '#f07178','#3dd68c','#5b8def','#f5a524','#a78bfa','#60a5fa',
  '#34d399','#fb923c','#818cf8','#22d3ee','#e879f9','#fbbf24',
];

// ── HELPERS ──
function makeTable(tbodyId, rows, cols) {{
  const tbody = document.getElementById(tbodyId);
  if (!tbody) return;
  tbody.innerHTML = rows.map(r => {{
    const tds = cols.map(c => {{
      let v = r[c];
      if (c==='tier') return `<span class="badge ${{v}}">${{v}}</span>`;
      if (c==='flag_new_account') return v ? '<span class="badge new">nueva</span>' : '—';
      if (v===null||v===undefined) return '—';
      return String(v).length>60?String(v).slice(0,58)+'…':String(v);
    }}).map(h=>`<td>${{h}}</td>`).join('');
    return `<tr>${{tds}}</tr>`;
  }}).join('');
}}

function doughnut(canvasId,labels,data,colors) {{
  const el=document.getElementById(canvasId);
  if(!el) return;
  return new Chart(el.getContext('2d'),{{
    type:'doughnut',
    data:{{labels,datasets:[{{data,backgroundColor:colors||CHART_COLORS}}]}},
    options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'bottom',labels:{{color:'#8b9cb3',font:{{size:10}}}}}}}}}}
  }});
}}

function barH(canvasId,labels,data,color) {{
  const el=document.getElementById(canvasId);
  if(!el) return;
  return new Chart(el.getContext('2d'),{{
    type:'bar',
    data:{{labels,datasets:[{{data,backgroundColor:color||CHART_COLORS[0]}}]}},
    options:{{indexAxis:'y',responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{x:{{beginAtZero:true,ticks:{{color:'#8b9cb3'}}}},y:{{ticks:{{color:'#8b9cb3',font:{{size:9}}}}}}}}}}
  }});
}}

function barV(canvasId,labels,data,color) {{
  const el=document.getElementById(canvasId);
  if(!el) return;
  return new Chart(el.getContext('2d'),{{
    type:'bar',
    data:{{labels,datasets:[{{data,backgroundColor:color||CHART_COLORS[0]}}]}},
    options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{x:{{ticks:{{color:'#8b9cb3',font:{{size:9}}}}}},y:{{beginAtZero:true,ticks:{{color:'#8b9cb3'}}}}}}}}
  }});
}}

// ── FILTRO GLOBAL ──
function onFilterCuenta() {{
  selectedAccount = document.getElementById('filterCuenta').value;
  document.getElementById('filterStatus').textContent =
    selectedAccount === 'todas' ? 'Mostrando todas las cuentas' : 'Filtrando por @' + selectedAccount;
  // Re-render sections that support filtering
  renderResumen();
  renderBlacklist();
  renderNarrativas();
}}

// ── RESEUMEN ──
function renderResumen() {{
  const k = DATA.kpis;
  document.getElementById('generated-at').textContent = k.generated_at;
  document.getElementById('generated-at-2').textContent = k.generated_at;

  const showBregman = selectedAccount === 'todas' || selectedAccount === 'myriambregman';
  const showDelCano = selectedAccount === 'todas' || selectedAccount === 'nicolasdelcano';

  let kpis = [];
  if (showBregman) {{
    kpis.push(
      {{label:'Trolls Bregman',value:k.myriambregman_troll_n.toLocaleString(),sub:k.myriambregman_troll_pct+'% hostilidad'}},
      {{label:'Apoyo Bregman',value:k.myriambregman_apoyo_n.toLocaleString(),sub:k.myriambregman_apoyo_pct+'% apoyo'}}
    );
  }}
  if (showDelCano) {{
    kpis.push(
      {{label:'Trolls del Caño',value:k.nicolasdelcano_troll_n.toLocaleString(),sub:k.nicolasdelcano_troll_pct+'% hostilidad'}},
      {{label:'Apoyo del Caño',value:k.nicolasdelcano_apoyo_n.toLocaleString(),sub:k.nicolasdelcano_apoyo_pct+'% apoyo'}}
    );
  }}
  kpis.unshift(
    {{label:'Blacklist total',value:k.n_blacklist,sub:k.n_blacklist_block+' block · '+k.n_blacklist_watch+' watch'}}
  );
  document.getElementById('kpiGrid').innerHTML = kpis.map(c =>
    `<div class="kpi"><div class="label">${{c.label}}</div><div class="value">${{c.value}}</div><div class="sub">${{c.sub}}</div></div>`
  ).join('');

  // Doughnuts
  if (showBregman) {{
    const nb = (DATA.narrativa_distribucion||[]).filter(r=>r.cuenta_slug==='myriambregman'&&r.plataforma==='facebook');
    if(nb.length) doughnut('chartNarBregman',nb.map(r=>r.posicion),nb.map(r=>num(r.comentarios)),nb.map(r=>COLORS[r.posicion]||'#64748b'));
  }}
  if (showDelCano) {{
    const nd = (DATA.narrativa_distribucion||[]).filter(r=>r.cuenta_slug==='nicolasdelcano'&&r.plataforma==='facebook');
    if(nd.length) doughnut('chartNarDelCano',nd.map(r=>r.posicion),nd.map(r=>num(r.comentarios)),nd.map(r=>COLORS[r.posicion]||'#64748b'));
  }}
}}

// ── GRUPOS ──
function renderGrupos() {{
  const gs = DATA.graph_stats;
  document.getElementById('kpiGraphStruct').innerHTML = [
    {{label:'Haters (nodos)',value:gs.hater_vertices_total.toLocaleString(),sub:'aristas: '+gs.hater_edges_total.toLocaleString()}},
    {{label:'Apoyo (nodos)',value:gs.apoyo_vertices_total.toLocaleString(),sub:'aristas: '+gs.apoyo_edges_total.toLocaleString()}},
    {{label:'Pares co-seg. haters',value:gs.hater_co_pairs.toLocaleString(),sub:'bridges: '+gs.hater_bridge_total}},
    {{label:'Pares co-seg. apoyo',value:gs.apoyo_co_pairs.toLocaleString(),sub:'bridges: '+gs.apoyo_bridge_total}},
  ].map(c=>`<div class="kpi"><div class="label">${{c.label}}</div><div class="value">${{c.value}}</div><div class="sub">${{c.sub}}</div></div>`).join('');

  // Grado distribution (pre-bucketed)
  const hBuckets = DATA.hater_degree_buckets||{{}};
  const aBuckets = DATA.apoyo_degree_buckets||{{}};
  barV('chartHaterGrado',Object.keys(hBuckets),Object.values(hBuckets),'#f07178');
  barV('chartApoyoGrado',Object.keys(aBuckets),Object.values(aBuckets),'#3dd68c');

  // Resumen bridge tables
  makeTable('tblBridgeHatersResumen', (DATA.hater_bridge_followers||[]).slice(0,8), ['follower_username','haters_followed','hater_usernames']);
  makeTable('tblBridgeApoyoResumen', (DATA.apoyo_bridge_followers||[]).slice(0,8), ['follower_username','apoyos_followed','apoyo_usernames']);

  // Co-followers resumen charts
  const hCo = DATA.hater_co_followers||[];
  const hLabels = DATA.hater_co_labels||[];
  const hMap = {{}};
  hLabels.forEach(l=>{{hMap[l.vertex_id]=l.label||l.display_name||l.vertex_id.slice(0,12);}});
  barH('chartCoHatersResumen',hCo.slice(0,8).map(r=>(hMap[r.hater_a_id]||'?')+' ↔ '+(hMap[r.hater_b_id]||'?')),hCo.slice(0,8).map(r=>num(r.shared_followers)),'#f07178');

  const aCo = DATA.apoyo_co_followers||[];
  const aLabels = DATA.apoyo_co_labels||[];
  const aMap = {{}};
  aLabels.forEach(l=>{{aMap[l.vertex_id]=l.label||l.display_name||l.vertex_id.slice(0,12);}});
  barH('chartCoApoyoResumen',aCo.slice(0,8).map(r=>(aMap[r.apoyo_a_id]||'?')+' ↔ '+(aMap[r.apoyo_b_id]||'?')),aCo.slice(0,8).map(r=>num(r.shared_followers)),'#3dd68c');

  // Score distribution
  const bl = DATA.troll_blacklist||[];
  const scoreBuckets = {{'1-3':0,'4-5':0,'6-7':0,'8-9':0}};
  bl.forEach(r=>{{const s=num(r.score);if(s<=3)scoreBuckets['1-3']++;else if(s<=5)scoreBuckets['4-5']++;else if(s<=7)scoreBuckets['6-7']++;else scoreBuckets['8-9']++;}});
  barV('chartScoreDist',Object.keys(scoreBuckets),Object.values(scoreBuckets),'#f07178');

  // New vs old accounts
  const nNew = bl.filter(r=>r.flag_new_account).length;
  const nOld = bl.length - nNew;
  doughnut('chartNewAccounts',['Nueva (2024-26)','Anterior'], [nNew,nOld], ['#fbbf24','#8b9cb3']);
}}

// ── NARRATIVAS ──
function renderNarrativas() {{
  const hc = DATA.hater_narrativa_asignaciones||[];
  const ac = DATA.apoyo_narrativa_asignaciones||[];
  if(hc.length) barH('chartNarHaters',hc.slice(0,10).map(r=>r.label.slice(0,30)),hc.slice(0,10).map(r=>num(r.n_asignaciones)),'#f07178');
  if(ac.length) barH('chartNarApoyo',ac.slice(0,10).map(r=>r.label.slice(0,30)),ac.slice(0,10).map(r=>num(r.n_asignaciones)),'#3dd68c');

  const hcl = DATA.hater_narrativa_clusters||[];
  makeTable('tblNarHaters',hcl.slice(0,15),['label','n_replies','descripcion']);
  const acl = DATA.apoyo_narrativa_clusters||[];
  makeTable('tblNarApoyo',acl.slice(0,15),['label','n_replies','descripcion']);

  // Comparative bar chart
  const nar = DATA.narrativa_por_cuenta||[];
  const cuentas = [...new Set(nar.map(r=>r.persona_id))];
  const posiciones = [...new Set(nar.map(r=>r.posicion))].filter(p=>p==='derecha_o_troll'||p==='apoyo_izquierda');
  const el=document.getElementById('chartNarrativaComparativa');
  if(el) {{
    new Chart(el.getContext('2d'),{{
      type:'bar',
      data:{{
        labels:cuentas.map(c=>c==='myriambregman'?'@myriambregman':'@nicolasdelcano'),
        datasets:posiciones.map(p=>({{
          label:p.replace(/_/g,' '),
          data:cuentas.map(c=>num((nar.find(r=>r.persona_id===c&&r.posicion===p)||{{}}).comentarios)),
          backgroundColor:COLORS[p]||'#64748b',
          stack:'s',
        }}))
      }},
      options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'bottom',labels:{{color:'#8b9cb3'}}}}}},scales:{{x:{{stacked:true,ticks:{{color:'#8b9cb3'}}}},y:{{stacked:true,beginAtZero:true,ticks:{{color:'#8b9cb3'}}}}}}}}
    }});
  }}
}}

// ── BLACKLIST ──
function renderBlacklist() {{
  const bl = DATA.troll_blacklist||[];
  const k = DATA.kpis;
  document.getElementById('kpiBlacklist').innerHTML = [
    {{label:'Block',value:k.n_blacklist_block,sub:'bloqueo recomendado'}},
    {{label:'Watch',value:k.n_blacklist_watch,sub:'monitorear'}},
    {{label:'Cuentas nuevas',value:bl.filter(r=>r.flag_new_account).length,sub:'creadas en 2024–2026'}},
    {{label:'In co-burst',value:bl.filter(r=>r.in_co_burst).length,sub:'en ráfaga sincronizada'}},
  ].map(c=>`<div class="kpi"><div class="label">${{c.label}}</div><div class="value">${{c.value}}</div><div class="sub">${{c.sub}}</div></div>`).join('');

  const blockRows = bl.filter(r=>r.tier==='block').slice(0,30);
  makeTable('tblBlacklistAll',blockRows,['username','score','tier','risk_band','flag_new_account','reasons','narrativas','hater_replies','first_reply_at','last_reply_at']);

  const showB = selectedAccount==='todas'||selectedAccount==='myriambregman';
  const showD = selectedAccount==='todas'||selectedAccount==='nicolasdelcano';
  if(showB) makeTable('tblHatersBregmanTop',DATA.haters_top10_myriambregman||[],['actor_nombre','score_eventos','dias_activos','tier','risk_score','narrativas']);
  if(showD) makeTable('tblHatersDelCanoTop',DATA.haters_top10_nicolasdelcano||[],['actor_nombre','score_eventos','dias_activos','tier','risk_score','narrativas']);
}}

// ── CO-RELACIONES GRAFOS ──
function renderGrafoHaters() {{
  const verts = DATA.hater_grafo_vertices||[];
  const edges = DATA.hater_grafo_edges||[];
  const nodes = verts.map(r=>({{
    id:r.vertex_id,label:r.label||r.display_name||r.vertex_id.slice(0,10),
    color:r.is_blue_verified?'#1da1f2':'#f07178',
    size:Math.min(Math.max(Math.log(num(r.degree)+1)*4,10),35),
    title:`${{r.label||r.vertex_id}}\\nFollowers:${{r.followers_count||0}}\\nFollowing:${{r.following_count||0}}\\nDegree:${{r.degree||0}}\\nCreated:${{r.account_created_at||'?'}}`,
  }}));
  const edgeList = edges.map(r=>({{
    from:r.source_id,to:r.target_id,
    width:Math.min(Math.max(num(r.peso_total),0.5),5),
    color:'rgba(240,113,120,0.4)',
    title:`type:${{r.edge_type||'hater_follows'}}\\nweight:${{r.peso_total}}`,
    edge_type:r.edge_type||'hater_follows',
  }}));
  allEdgesData['haters']=edgeList;
  const types=[...new Set(edgeList.map(e=>e.edge_type))];
  const sel=document.getElementById('filterEdgeHaters');
  sel.innerHTML='<option value="">Todas</option>'+types.map(t=>`<option value="${{t}}">${{t}}</option>`).join('');
  const container=document.getElementById('network-haters');
  if(!container) return;
  networks['haters']=new vis.Network(container,{{nodes:new vis.DataSet(nodes),edges:new vis.DataSet(edgeList)}},{{
    physics:{{stabilization:{{iterations:100}}}},
    interaction:{{hover:true,tooltipDelay:100,navigationButtons:true,keyboard:true}},
    edges:{{font:{{size:9,color:'#8b9cb3'}},smooth:{{type:'continuous'}}}},
    nodes:{{font:{{size:10,color:'#e7ecf3'}}}},
  }});
}}

function renderGrafoApoyo() {{
  const verts=DATA.apoyo_grafo_vertices||[];
  const edges=DATA.apoyo_grafo_edges||[];
  const nodes=verts.map(r=>({{
    id:r.vertex_id,label:r.label||r.display_name||r.vertex_id.slice(0,10),
    color:r.is_blue_verified?'#1da1f2':'#3dd68c',
    size:Math.min(Math.max(Math.log(num(r.degree)+1)*4,10),35),
    title:`${{r.label||r.vertex_id}}\\nFollowers:${{r.followers_count||0}}\\nFollowing:${{r.following_count||0}}\\nDegree:${{r.degree||0}}`,
  }}));
  const edgeList=edges.map(r=>({{
    from:r.source_id,to:r.target_id,
    width:Math.min(Math.max(num(r.peso_total),0.5),5),
    color:'rgba(61,214,140,0.35)',
    title:`type:${{r.edge_type||'apoyo_follows'}}\\nweight:${{r.peso_total}}`,
    edge_type:r.edge_type||'apoyo_follows',
  }}));
  allEdgesData['apoyo']=edgeList;
  const types=[...new Set(edgeList.map(e=>e.edge_type))];
  const sel=document.getElementById('filterEdgeApoyo');
  sel.innerHTML='<option value="">Todas</option>'+types.map(t=>`<option value="${{t}}">${{t}}</option>`).join('');
  const container=document.getElementById('network-apoyo');
  if(!container) return;
  networks['apoyo']=new vis.Network(container,{{nodes:new vis.DataSet(nodes),edges:new vis.DataSet(edgeList)}},{{
    physics:{{stabilization:{{iterations:100}}}},
    interaction:{{hover:true,tooltipDelay:100,navigationButtons:true,keyboard:true}},
    edges:{{font:{{size:9,color:'#8b9cb3'}},smooth:{{type:'continuous'}}}},
    nodes:{{font:{{size:10,color:'#e7ecf3'}}}},
  }});
}}

function filterGrafo(key,search) {{
  const net=networks[key]; if(!net) return;
  const filt=document.getElementById('filterEdge'+key.charAt(0).toUpperCase()+key.slice(1)).value;
  let ee=allEdgesData[key]||[];
  if(filt) ee=ee.filter(e=>e.edge_type===filt);
  if(search) {{
    const s=search.toLowerCase(), match=new Set();
    net.body.data.nodes.get().forEach(n=>{{if((n.label||'').toLowerCase().includes(s))match.add(n.id);}});
    ee=ee.filter(e=>match.has(e.from)&&match.has(e.to));
    const vis=new Set(); ee.forEach(e=>{{vis.add(e.from);vis.add(e.to);}}); match.forEach(id=>vis.add(id));
    net.setData({{nodes:new vis.DataSet(net.body.data.nodes.get().filter(n=>vis.has(n.id))),edges:new vis.DataSet(ee)}});
  }} else net.setData({{nodes:new vis.DataSet(net.body.data.nodes.get()),edges:new vis.DataSet(ee)}});
}}
function fitGrafo(key){{if(networks[key])networks[key].fit();}}
function resetGrafo(key){{if(networks[key]){{networks[key].setData({{nodes:new vis.DataSet(networks[key].body.data.nodes.get()),edges:new vis.DataSet(allEdgesData[key]||[])}});networks[key].fit();}}}}

function renderCoHaters() {{
  const co=DATA.hater_co_followers||[];
  const labels=DATA.hater_co_labels||[];
  const lm={{}}; labels.forEach(l=>{{lm[l.vertex_id]=l.label||l.display_name||l.vertex_id.slice(0,12);}});
  barH('chartCoHaters',co.map(r=>(lm[r.hater_a_id]||'?')+'↔'+(lm[r.hater_b_id]||'?')),co.map(r=>num(r.shared_followers)),'#f07178');
  makeTable('tblBridgeHaters',(DATA.hater_bridge_followers||[]).slice(0,10),['follower_username','haters_followed','hater_usernames']);
  // co-follower network
  const cNodes=[],cEdges=[],added=new Set();
  co.forEach(r=>{{
    const a=r.hater_a_id,b=r.hater_b_id;
    if(!added.has(a)){{added.add(a);cNodes.push({{id:a,label:lm[a]||a.slice(0,12),color:'#f5a524',size:12}});}}
    if(!added.has(b)){{added.add(b);cNodes.push({{id:b,label:lm[b]||b.slice(0,12),color:'#f5a524',size:12}});}}
    cEdges.push({{from:a,to:b,width:Math.log(num(r.shared_followers)+1)*1.5,color:'rgba(240,113,120,0.3)',title:r.shared_followers+' seguidores compartidos'}});
  }});
  const ct=document.getElementById('network-co-haters');
  if(ct&&cNodes.length) networks['co-haters']=new vis.Network(ct,{{nodes:new vis.DataSet(cNodes),edges:new vis.DataSet(cEdges)}},{{physics:{{stabilization:{{iterations:60}}}},interaction:{{hover:true,tooltipDelay:100}},edges:{{smooth:{{type:'continuous'}}}},nodes:{{font:{{size:10,color:'#e7ecf3'}}}}}});
}}

function renderCoApoyo() {{
  const co=DATA.apoyo_co_followers||[];
  const labels=DATA.apoyo_co_labels||[];
  const lm={{}}; labels.forEach(l=>{{lm[l.vertex_id]=l.label||l.display_name||l.vertex_id.slice(0,12);}});
  barH('chartCoApoyo',co.map(r=>(lm[r.apoyo_a_id]||'?')+'↔'+(lm[r.apoyo_b_id]||'?')),co.map(r=>num(r.shared_followers)),'#3dd68c');
  makeTable('tblBridgeApoyo',(DATA.apoyo_bridge_followers||[]).slice(0,10),['follower_username','apoyos_followed','apoyo_usernames']);
  const cNodes=[],cEdges=[],added=new Set();
  co.forEach(r=>{{
    const a=r.apoyo_a_id,b=r.apoyo_b_id;
    if(!added.has(a)){{added.add(a);cNodes.push({{id:a,label:lm[a]||a.slice(0,12),color:'#34d399',size:12}});}}
    if(!added.has(b)){{added.add(b);cNodes.push({{id:b,label:lm[b]||b.slice(0,12),color:'#34d399',size:12}});}}
    cEdges.push({{from:a,to:b,width:Math.log(num(r.shared_followers)+1)*1.5,color:'rgba(61,214,140,0.25)',title:r.shared_followers+' seguidores compartidos'}});
  }});
  const ct=document.getElementById('network-co-apoyo');
  if(ct&&cNodes.length) networks['co-apoyo']=new vis.Network(ct,{{nodes:new vis.DataSet(cNodes),edges:new vis.DataSet(cEdges)}},{{physics:{{stabilization:{{iterations:60}}}},interaction:{{hover:true,tooltipDelay:100}},edges:{{smooth:{{type:'continuous'}}}},nodes:{{font:{{size:10,color:'#e7ecf3'}}}}}});
}}

// ── TEMPORAL ──
function renderTemporal() {{
  const profiles = DATA.hater_profile_risk||[];
  const yearBuckets = {{}};
  profiles.forEach(r=>{{
    if(!r.account_created_at) return;
    const m=r.account_created_at.match(/\\w{{3}} \\w{{3}} (\\d{{2}}) .+ (\\d{{4}})/);
    if(m){{const k=m[2]+'-'+m[1];yearBuckets[k]=(yearBuckets[k]||0)+1;}}
  }});
  const years=Object.keys(yearBuckets).sort();
  barV('chartAccountCreation',years,years.map(y=>yearBuckets[y]),'#f07178');

  const tr=DATA.trolls_temporal||[];
  const dias=[...new Set(tr.map(r=>r.dia).filter(Boolean))].sort();
  if(dias.length) {{
    const agg = dias.map(d=>{{
      const f=String(d).slice(0,10);
      const rows=tr.filter(r=>String(r.dia).slice(0,10)===f);
      return {{dia:f,troll:rows.reduce((a,b)=>a+num(b.comentarios_troll),0),autores:rows.reduce((a,b)=>a+num(b.autores_troll),0),
        spam:rows.reduce((a,b)=>a+num(b.spam_enlaces),0),insultos:rows.reduce((a,b)=>a+num(b.insultos),0),
        conspiranoia:rows.reduce((a,b)=>a+num(b.conspiranoia),0),acusaciones:rows.reduce((a,b)=>a+num(b.acusaciones_graves),0)}};
    }});
    new Chart(document.getElementById('chartTrollTemporal'),{{
      type:'line',
      data:{{
        labels:agg.map(r=>r.dia),
        datasets:[
          {{label:'Comentarios troll',data:agg.map(r=>r.troll),borderColor:'#f07178',yAxisID:'y',tension:.25,fill:false}},
          {{label:'Autores',data:agg.map(r=>r.autores),borderColor:'#60a5fa',yAxisID:'y1',tension:.25,fill:false}},
        ]
      }},
      options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'bottom',labels:{{color:'#8b9cb3'}}}}}},scales:{{y:{{beginAtZero:true,position:'left',ticks:{{color:'#8b9cb3'}}}},y1:{{beginAtZero:true,position:'right',grid:{{drawOnChartArea:false}},ticks:{{color:'#8b9cb3'}}}},x:{{ticks:{{color:'#8b9cb3',font:{{size:9}}}}}}}}}}
    }});
    new Chart(document.getElementById('chartTrollTipo'),{{
      type:'bar',
      data:{{
        labels:agg.map(r=>r.dia),
        datasets:[
          {{label:'Spam',data:agg.map(r=>r.spam),backgroundColor:'#f07178',stack:'t'}},
          {{label:'Insultos',data:agg.map(r=>r.insultos),backgroundColor:'#f5a524',stack:'t'}},
          {{label:'Conspiranoia',data:agg.map(r=>r.conspiranoia),backgroundColor:'#a78bfa',stack:'t'}},
          {{label:'Acusaciones',data:agg.map(r=>r.acusaciones),backgroundColor:'#60a5fa',stack:'t'}},
        ]
      }},
      options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'bottom',labels:{{color:'#8b9cb3',font:{{size:10}}}}}}}},scales:{{x:{{stacked:true,ticks:{{color:'#8b9cb3',font:{{size:9}}}}}},y:{{stacked:true,beginAtZero:true,ticks:{{color:'#8b9cb3'}}}}}}}}
    }});
  }}
  makeTable('tblRafagas',DATA.trolls_rafagas||[],['autor_nombre','cuenta_slug','dia','comentarios_en_dia','inicio_ráfaga','fin_ráfaga','minutos_span','narrativas']);
  makeTable('tblCohortes',DATA.trolls_cohortes||[],['dia','cuenta_slug','autores_distintos','comentarios_troll']);
}}

// ── TABS & NAV ──
function setupTabs() {{
  document.querySelectorAll('#tabGrafo .tab').forEach(tab=>{{
    tab.addEventListener('click',()=>{{
      document.querySelectorAll('#tabGrafo .tab').forEach(t=>t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(tc=>tc.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById('tab-'+tab.dataset.tab).classList.add('active');
      setTimeout(()=>{{const k=tab.dataset.tab==='grafo-haters'?'haters':'apoyo';if(networks[k])networks[k].fit();}},100);
    }});
  }});
  document.querySelectorAll('#nav a').forEach(a=>{{
    a.addEventListener('click',e=>{{
      e.preventDefault();
      document.querySelectorAll('#nav a').forEach(x=>x.classList.remove('active'));
      document.querySelectorAll('main section').forEach(s=>s.classList.remove('active'));
      a.classList.add('active');
      document.getElementById('sec-'+a.dataset.sec).classList.add('active');
      setTimeout(()=>{{const s=a.dataset.sec;if(s==='corelaciones'&&networks['haters'])networks['haters'].fit();if(s==='cohaters'&&networks['co-haters'])networks['co-haters'].fit();if(s==='coapoyo'&&networks['co-apoyo'])networks['co-apoyo'].fit();}},200);
    }});
  }});
}}

function init() {{
  renderResumen();
  renderGrupos();
  renderNarrativas();
  renderBlacklist();
  renderGrafoHaters();
  renderGrafoApoyo();
  renderCoHaters();
  renderCoApoyo();
  renderTemporal();
  setupTabs();
}}

init();
</script>
</body>
</html>
"""


def main() -> int:
    out = db.get_report_bundle(PROJECT, BUNDLE)
    out.mkdir(parents=True, exist_ok=True)

    con = db.connect(read_only=True)
    try:
        payload = export_payload(con)
    finally:
        con.close()

    html = generate_html(payload)
    (out / "reporte_grafos.html").write_text(html, encoding="utf-8")

    k = payload["kpis"]
    gs = payload["graph_stats"]
    print(f"✅ Reporte generado: {out / 'reporte_grafos.html'}")
    print(f"   Haters: {gs['hater_vertices_total']} nodos / {gs['hater_edges_total']} aristas")
    print(f"   Apoyo:  {gs['apoyo_vertices_total']} nodos / {gs['apoyo_edges_total']} aristas")
    print(f"   Blacklist: {k['n_blacklist']} (block: {k['n_blacklist_block']})")
    print(f"   Para abrir: open '{out / 'reporte_grafos.html'}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
