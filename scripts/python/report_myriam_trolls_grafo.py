#!/usr/bin/env python3
"""Generate interactive graph report: haters/trolls around @myriambregman."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402

TOP_TROLLS = 80
TOP_APOYO = 20
MIN_SHARED_TWEETS = 2
OUTPUT = db.get_reports_path() / "redes" / f"myriambregman-tw-trolls-grafo_{date.today():%Y%m%d}.html"


def fetch_metrics(con) -> dict:
    row = con.sql("""
        SELECT
          COUNT(*) AS total_clasificados,
          COUNT(*) FILTER (WHERE criteria_label = 'derecha_o_troll') AS trolls,
          COUNT(*) FILTER (WHERE criteria_label = 'apoyo_izquierda') AS apoyo,
          COUNT(*) FILTER (WHERE criteria_label = 'ambiguo') AS ambiguo,
          COUNT(DISTINCT parent_tweet_id) AS tweets_cubiertos
        FROM silver.tw_comments_classification
        WHERE parent_author_username = 'myriambregman'
    """).fetchone()
    likes = con.sql("""
        SELECT
          COALESCE(SUM(r.like_count) FILTER (WHERE c.criteria_label = 'derecha_o_troll'), 0) AS likes_trolls,
          COALESCE(SUM(r.like_count) FILTER (WHERE c.criteria_label = 'apoyo_izquierda'), 0) AS likes_apoyo
        FROM silver.tw_comments_classification c
        JOIN silver.tw_tweets_replies r ON c.reply_tweet_id = r.tweet_id
        WHERE c.parent_author_username = 'myriambregman'
    """).fetchone()
    autores = con.sql("""
        SELECT criteria_label, COUNT(DISTINCT r.author_username) AS n
        FROM silver.tw_comments_classification c
        JOIN silver.tw_tweets_replies r ON c.reply_tweet_id = r.tweet_id
        WHERE c.parent_author_username = 'myriambregman'
          AND r.author_username IS NOT NULL
        GROUP BY 1
    """).fetchall()
    return {
        "total_clasificados": row[0],
        "trolls": row[1],
        "apoyo": row[2],
        "ambiguo": row[3],
        "tweets_cubiertos": row[4],
        "likes_trolls": int(likes[0]),
        "likes_apoyo": int(likes[1]),
        "autores_unicos": {r[0]: r[1] for r in autores},
    }


def fetch_top_accounts(con, label: str, limit: int) -> list[dict]:
    rows = con.sql(f"""
        SELECT
          r.author_username,
          COUNT(*) AS comentarios,
          COALESCE(SUM(r.like_count), 0) AS likes,
          COUNT(DISTINCT c.parent_tweet_id) AS tweets
        FROM silver.tw_comments_classification c
        JOIN silver.tw_tweets_replies r ON c.reply_tweet_id = r.tweet_id
        WHERE c.parent_author_username = 'myriambregman'
          AND c.criteria_label = '{label}'
          AND r.author_username IS NOT NULL
        GROUP BY 1
        ORDER BY comentarios DESC, likes DESC
        LIMIT {limit}
    """).fetchall()
    return [
        {"username": r[0], "comentarios": r[1], "likes": int(r[2]), "tweets": r[3]}
        for r in rows
    ]


def fetch_tweets_breakdown(con) -> list[dict]:
    rows = con.sql("""
        SELECT
          c.parent_tweet_id,
          LEFT(t.text, 80) AS preview,
          COUNT(*) FILTER (WHERE c.criteria_label = 'derecha_o_troll') AS trolls,
          COUNT(*) FILTER (WHERE c.criteria_label = 'apoyo_izquierda') AS apoyo,
          COUNT(*) AS total
        FROM silver.tw_comments_classification c
        JOIN silver.tw_tweets t ON c.parent_tweet_id = t.tweet_id
        WHERE c.parent_author_username = 'myriambregman'
        GROUP BY 1, 2
        ORDER BY trolls DESC
    """).fetchall()
    return [
        {"tweet_id": r[0], "preview": r[1], "trolls": r[2], "apoyo": r[3], "total": r[4]}
        for r in rows
    ]


def fetch_cooccurrence(con, usernames: set[str]) -> list[dict]:
    if len(usernames) < 2:
        return []
    user_list = ", ".join(f"'{u}'" for u in usernames)
    rows = con.sql(f"""
        WITH troll_replies AS (
          SELECT r.author_username, c.parent_tweet_id
          FROM silver.tw_comments_classification c
          JOIN silver.tw_tweets_replies r ON c.reply_tweet_id = r.tweet_id
          WHERE c.parent_author_username = 'myriambregman'
            AND c.criteria_label = 'derecha_o_troll'
            AND r.author_username IN ({user_list})
        )
        SELECT a.author_username, b.author_username,
               COUNT(DISTINCT a.parent_tweet_id) AS shared
        FROM troll_replies a
        JOIN troll_replies b
          ON a.parent_tweet_id = b.parent_tweet_id
         AND a.author_username < b.author_username
        GROUP BY 1, 2
        HAVING COUNT(DISTINCT a.parent_tweet_id) >= {MIN_SHARED_TWEETS}
        ORDER BY shared DESC
    """).fetchall()
    return [{"from": r[0], "to": r[1], "shared": r[2]} for r in rows]


def build_graph(top_trolls: list[dict], top_apoyo: list[dict], cooc: list[dict]) -> dict:
    nodes: list[dict] = []
    edges: list[dict] = []
    id_map: dict[str, int] = {}
    nid = 1

    nodes.append({
        "id": 0,
        "label": "@myriambregman",
        "tipo": "cuenta_principal",
        "comentarios": 0,
        "likes": 0,
    })
    id_map["myriambregman"] = 0

    for acc in top_trolls:
        nodes.append({
            "id": nid,
            "label": f"@{acc['username']}",
            "tipo": "troll",
            "comentarios": acc["comentarios"],
            "likes": acc["likes"],
            "tweets": acc["tweets"],
        })
        id_map[acc["username"]] = nid
        edges.append({
            "from": nid,
            "to": 0,
            "type": "reply_to",
            "weight": acc["comentarios"],
        })
        nid += 1

    for acc in top_apoyo:
        nodes.append({
            "id": nid,
            "label": f"@{acc['username']}",
            "tipo": "apoyo",
            "comentarios": acc["comentarios"],
            "likes": acc["likes"],
            "tweets": acc["tweets"],
        })
        id_map[acc["username"]] = nid
        edges.append({
            "from": nid,
            "to": 0,
            "type": "reply_to",
            "weight": acc["comentarios"],
        })
        nid += 1

    for pair in cooc:
        fa, fb = pair["from"], pair["to"]
        if fa in id_map and fb in id_map:
            edges.append({
                "from": id_map[fa],
                "to": id_map[fb],
                "type": "co_reply",
                "weight": pair["shared"],
            })

    type_counts: dict[str, int] = {}
    for n in nodes:
        type_counts[n["tipo"]] = type_counts.get(n["tipo"], 0) + 1
    edge_types: dict[str, int] = {}
    for e in edges:
        edge_types[e["type"]] = edge_types.get(e["type"], 0) + 1

    return {
        "nodes": nodes,
        "edges": edges,
        "estadisticas": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "node_types": type_counts,
            "edge_types": edge_types,
        },
    }


def build_html(metrics: dict, graph: dict, top_trolls: list[dict], tweets: list[dict]) -> str:
    data_json = json.dumps(
        {"metrics": metrics, "graph": graph, "top_trolls": top_trolls, "tweets": tweets},
        ensure_ascii=False,
    )
    fecha = date.today().isoformat()
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Haters/Trolls — @myriambregman | datasyn</title>
  <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>
    :root {{
      --bg: #0f1419; --card: #1a2332; --text: #e7ecf3; --muted: #8b9cb3;
      --accent: #ef4444; --apoyo: #22c55e; --centro: #a855f7; --border: #2d3a4f;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--text); line-height: 1.5; }}
    header {{ padding: 2rem; border-bottom: 1px solid var(--border);
      background: linear-gradient(135deg, #3b1a1a 0%, #0f1419 55%); }}
    header h1 {{ margin: 0 0 .25rem; font-size: 1.6rem; }}
    header p {{ margin: 0; color: var(--muted); font-size: .9rem; }}
    .badge {{ display: inline-block; margin-top: .5rem; padding: .2rem .6rem; border-radius: 4px;
      font-size: .75rem; background: #2a1a1a; color: #fca5a5; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 1.5rem 2rem 3rem; }}
    section {{ margin-bottom: 2.5rem; }}
    h2 {{ font-size: 1.2rem; margin: 0 0 1rem; border-left: 4px solid var(--accent); padding-left: .75rem; }}
    h3 {{ font-size: .95rem; color: var(--muted); margin: 0 0 .75rem; }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: .75rem; margin-bottom: 1.25rem; }}
    .kpi {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: .9rem 1rem; }}
    .kpi .val {{ font-size: 1.4rem; font-weight: 700; }}
    .kpi .lbl {{ font-size: .72rem; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }}
    .grid-2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; }}
    .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 1rem 1.25rem; }}
    .card canvas {{ max-height: 280px; }}
    #network-wrap {{ position: relative; }}
    #network {{ width: 100%; height: 520px; border-radius: 8px; background: #121820; border: 1px solid var(--border); }}
    .controls {{ display: flex; flex-wrap: wrap; gap: .5rem; margin-bottom: .75rem; }}
    .controls button, .controls select {{
      padding: .45rem .85rem; border-radius: 6px; border: 1px solid var(--border);
      background: #243044; color: var(--text); cursor: pointer; font-size: .85rem;
    }}
    .controls button:hover {{ background: #2d3f58; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 1rem; font-size: .8rem; color: var(--muted); margin-top: .5rem; }}
    .legend span {{ display: flex; align-items: center; gap: .35rem; }}
    .dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
    .finding {{ background: #1e2a3a; border-left: 3px solid var(--accent); padding: .75rem 1rem; margin: .5rem 0; border-radius: 0 6px 6px 0; font-size: .9rem; }}
    table {{ width: 100%; border-collapse: collapse; font-size: .82rem; }}
    th, td {{ padding: .45rem .6rem; text-align: left; border-bottom: 1px solid var(--border); }}
    th {{ color: var(--muted); }}
    footer {{ text-align: center; padding: 1.5rem; color: var(--muted); font-size: .78rem; border-top: 1px solid var(--border); }}
    .prose {{ color: #c5d0de; font-size: .9rem; }}
    .prose ul {{ padding-left: 1.2rem; }}
  </style>
</head>
<body>
  <header>
    <h1>Red de haters/trolls — @myriambregman</h1>
    <p>Grafo de relaciones entre cuentas clasificadas como derecha/troll · Generado {fecha}</p>
    <span class="badge">Fuente: silver.tw_comments_classification (LLM) · Top {TOP_TROLLS} trolls + {TOP_APOYO} apoyo</span>
  </header>
  <main>
    <section id="resumen">
      <h2>Resumen</h2>
      <div class="kpi-grid" id="kpis"></div>
      <div id="findings"></div>
    </section>

    <section id="grafo">
      <h2>Grafo interactivo</h2>
      <p class="prose" style="margin-bottom:.75rem">
        <strong>@myriambregman</strong> en el centro (morado). Nodos rojos = trolls; verdes = apoyo.
        Aristas hacia el centro = respuestas; grises = co-respuesta en el mismo tweet (≥{MIN_SHARED_TWEETS} tweets compartidos).
        Tamaño del nodo ∝ comentarios; grosor de arista ∝ peso.
      </p>
      <div class="controls">
        <button id="btnFit">Ajustar vista</button>
        <button id="btnPhysics">Pausar física</button>
        <select id="filterTipo">
          <option value="all">Todos los nodos</option>
          <option value="troll">Solo trolls</option>
          <option value="apoyo">Solo apoyo</option>
          <option value="troll+centro">Trolls + Myriam</option>
        </select>
      </div>
      <div id="network-wrap"><div id="network"></div></div>
      <div class="legend">
        <span><i class="dot" style="background:var(--centro)"></i> Cuenta principal</span>
        <span><i class="dot" style="background:var(--accent)"></i> derecha_o_troll</span>
        <span><i class="dot" style="background:var(--apoyo)"></i> apoyo_izquierda</span>
        <span><i class="dot" style="background:#64748b;width:20px;height:2px;border-radius:0"></i> co-respuesta entre trolls</span>
      </div>
    </section>

    <section id="charts">
      <h2>Distribución y engagement</h2>
      <div class="grid-2">
        <div class="card"><h3>Clasificación de comentarios</h3><canvas id="chartClass"></canvas></div>
        <div class="card"><h3>Likes por clasificación</h3><canvas id="chartLikes"></canvas></div>
        <div class="card"><h3>Trolls vs apoyo por tweet</h3><canvas id="chartTweets"></canvas></div>
        <div class="card"><h3>Top 15 trolls (comentarios)</h3><canvas id="chartTop"></canvas></div>
      </div>
    </section>

    <section id="tabla">
      <h2>Top cuentas troll</h2>
      <div class="card">
        <table id="tblTrolls"><thead><tr>
          <th>#</th><th>Cuenta</th><th>Comentarios</th><th>Likes</th><th>Tweets distintos</th>
        </tr></thead><tbody></tbody></table>
      </div>
    </section>
  </main>
  <footer>datasyn-local · report/redes/ · Datos legacy CSV (tw_*) · No incluir en git</footer>

  <script>
  const DATA = {data_json};
  const COLORS = {{ cuenta_principal: '#a855f7', troll: '#ef4444', apoyo: '#22c55e' }};
  let network = null, physicsOn = true;

  function renderKPIs() {{
    const m = DATA.metrics;
    const pctTroll = (100 * m.trolls / m.total_clasificados).toFixed(1);
    const pctLikesTroll = (100 * m.likes_trolls / (m.likes_trolls + m.likes_apoyo)).toFixed(1);
    document.getElementById('kpis').innerHTML = [
      ['Comentarios clasificados', m.total_clasificados],
      ['Trolls (derecha_o_troll)', m.trolls + ' (' + pctTroll + '%)'],
      ['Apoyo izquierda', m.apoyo],
      ['Autores troll únicos', m.autores_unicos.derecha_o_troll || 0],
      ['Likes en trolls', m.likes_trolls.toLocaleString()],
      ['Tweets cubiertos', m.tweets_cubiertos],
    ].map(([l,v]) => `<div class="kpi"><div class="val">${{v}}</div><div class="lbl">${{l}}</div></div>`).join('');

    document.getElementById('findings').innerHTML = `
      <div class="finding">El <strong>${{pctTroll}}%</strong> de los comentarios clasificados son trolls/derecha, pero concentran el <strong>${{pctLikesTroll}}%</strong> de los likes entre trolls+apoyo — visibilidad asimétrica.</div>
      <div class="finding"><strong>${{m.autores_unicos.derecha_o_troll || 0}}</strong> cuentas distintas etiquetadas como troll; el grafo muestra las top ${{DATA.graph.nodes.filter(n=>n.tipo==='troll').length}} por volumen de respuestas.</div>
      <div class="finding">Las aristas grises conectan trolls que co-responden en los mismos hilos (≥{MIN_SHARED_TWEETS} tweets) — posibles clusters de hostilidad coordinada o recurrente.</div>`;
  }}

  function buildVisData(filter) {{
    const g = DATA.graph;
    let nodes = g.nodes.filter(n => n.tipo === 'cuenta_principal' || filter === 'all' || filter === 'troll+centro' && n.tipo !== 'apoyo' || n.tipo === filter);
    const ids = new Set(nodes.map(n => n.id));
    const maxC = Math.max(...nodes.filter(n=>n.comentarios).map(n=>n.comentarios), 1);
    const visNodes = nodes.map(n => ({{
      id: n.id,
      label: n.tipo === 'cuenta_principal' ? n.label : n.label.replace('@','').slice(0,12),
      title: `${{n.label}}\\nComentarios: ${{n.comentarios||'—'}}\\nLikes: ${{(n.likes||0).toLocaleString()}}`,
      color: {{ background: COLORS[n.tipo], border: '#fff', highlight: {{ background: '#fff', border: COLORS[n.tipo] }} }},
      size: n.tipo === 'cuenta_principal' ? 40 : 12 + 28 * (n.comentarios || 0) / maxC,
      font: {{ size: n.tipo === 'cuenta_principal' ? 14 : 9, color: '#e7ecf3' }},
      borderWidth: n.tipo === 'cuenta_principal' ? 3 : 1,
    }}));
    const visEdges = g.edges.filter(e => {{
      if (!ids.has(e.from) || !ids.has(e.to)) return false;
      if (filter === 'troll' && e.type === 'reply_to' && e.to === 0) return true;
      if (filter === 'apoyo') return e.type === 'reply_to';
      return true;
    }}).map(e => ({{
      from: e.from, to: e.to,
      width: e.type === 'co_reply' ? 1 + e.weight : 1 + Math.min(e.weight, 8),
      color: e.type === 'co_reply' ? {{ color: '#64748b', opacity: 0.45 }} : {{ color: '#475569', opacity: 0.6 }},
      dashes: e.type === 'co_reply',
      smooth: {{ type: 'continuous' }},
      title: e.type === 'co_reply' ? `Co-respuesta: ${{e.weight}} tweets` : `Respuestas: ${{e.weight}}`,
    }}));
    return {{ nodes: new vis.DataSet(visNodes), edges: new vis.DataSet(visEdges) }};
  }}

  function initNetwork(filter='all') {{
    const container = document.getElementById('network');
    const {{ nodes, edges }} = buildVisData(filter);
    const options = {{
      physics: {{
        enabled: physicsOn,
        barnesHut: {{ gravitationalConstant: -8000, centralGravity: 0.35, springLength: 120, damping: 0.85 }},
        stabilization: {{ iterations: 150 }}
      }},
      interaction: {{ hover: true, tooltipDelay: 100, zoomView: true }},
      edges: {{ smooth: {{ type: 'continuous' }} }},
    }};
    if (network) network.destroy();
    network = new vis.Network(container, {{ nodes, edges }}, options);
  }}

  function renderCharts() {{
    const m = DATA.metrics;
    Chart.defaults.color = '#8b9cb3';
    Chart.defaults.borderColor = '#2d3a4f';

    new Chart(document.getElementById('chartClass'), {{
      type: 'doughnut',
      data: {{
        labels: ['Troll/derecha', 'Apoyo izquierda', 'Ambiguo'],
        datasets: [{{ data: [m.trolls, m.apoyo, m.ambiguo], backgroundColor: ['#ef4444','#22c55e','#eab308'] }}]
      }},
      options: {{ plugins: {{ legend: {{ position: 'bottom' }} }} }}
    }});

    new Chart(document.getElementById('chartLikes'), {{
      type: 'bar',
      data: {{
        labels: ['Trolls', 'Apoyo'],
        datasets: [{{ label: 'Likes', data: [m.likes_trolls, m.likes_apoyo], backgroundColor: ['#ef4444','#22c55e'] }}]
      }},
      options: {{ scales: {{ y: {{ beginAtZero: true }} }} }}
    }});

    const tw = DATA.tweets;
    new Chart(document.getElementById('chartTweets'), {{
      type: 'bar',
      data: {{
        labels: tw.map((_,i) => 'Tweet ' + (i+1)),
        datasets: [
          {{ label: 'Trolls', data: tw.map(t=>t.trolls), backgroundColor: '#ef4444' }},
          {{ label: 'Apoyo', data: tw.map(t=>t.apoyo), backgroundColor: '#22c55e' }},
        ]
      }},
      options: {{ scales: {{ x: {{ stacked: true }}, y: {{ stacked: true, beginAtZero: true }} }} }}
    }});

    const top = DATA.top_trolls.slice(0, 15);
    new Chart(document.getElementById('chartTop'), {{
      type: 'bar',
      data: {{
        labels: top.map(t => '@' + t.username.slice(0,14)),
        datasets: [{{ label: 'Comentarios', data: top.map(t=>t.comentarios), backgroundColor: '#ef4444' }}]
      }},
      options: {{ indexAxis: 'y', scales: {{ x: {{ beginAtZero: true }} }} }}
    }});
  }}

  function renderTable() {{
    const tbody = document.querySelector('#tblTrolls tbody');
    tbody.innerHTML = DATA.top_trolls.slice(0, 25).map((t,i) =>
      `<tr><td>${{i+1}}</td><td>@${{t.username}}</td><td>${{t.comentarios}}</td><td>${{t.likes.toLocaleString()}}</td><td>${{t.tweets}}</td></tr>`
    ).join('');
  }}

  document.getElementById('btnFit').onclick = () => network?.fit();
  document.getElementById('btnPhysics').onclick = () => {{
    physicsOn = !physicsOn;
    network?.setOptions({{ physics: {{ enabled: physicsOn }} }});
    document.getElementById('btnPhysics').textContent = physicsOn ? 'Pausar física' : 'Reanudar física';
  }};
  document.getElementById('filterTipo').onchange = (e) => initNetwork(e.target.value);

  renderKPIs();
  initNetwork();
  renderCharts();
  renderTable();
  </script>
</body>
</html>"""


def main() -> None:
    con = db.connect()
    try:
        metrics = fetch_metrics(con)
        top_trolls = fetch_top_accounts(con, "derecha_o_troll", TOP_TROLLS)
        top_apoyo = fetch_top_accounts(con, "apoyo_izquierda", TOP_APOYO)
        tweets = fetch_tweets_breakdown(con)
        troll_names = {t["username"] for t in top_trolls}
        cooc = fetch_cooccurrence(con, troll_names)
        graph = build_graph(top_trolls, top_apoyo, cooc)

        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(build_html(metrics, graph, top_trolls, tweets), encoding="utf-8")
        print(f"✅ Reporte: {OUTPUT}")
        print(f"   Nodos: {graph['estadisticas']['total_nodes']}, Aristas: {graph['estadisticas']['total_edges']}")
        print(f"   Co-ocurrencias troll-troll: {len(cooc)}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
