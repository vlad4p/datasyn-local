#!/usr/bin/env python3
"""Generate interactive troll entity graph (vis.js) from gold grafo_*_trolls views."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402

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


def _top_author_ids(con, limit: int = 35) -> set[str]:
    rows = con.sql(
        f"""
        SELECT source_id
        FROM gold.grafo_edges_agg_trolls
        WHERE edge_type = 'ataca'
          AND source_id LIKE 'autor:%'
        GROUP BY source_id
        ORDER BY SUM(peso_total) DESC
        LIMIT {limit}
        """
    ).fetchall()
    return {r[0] for r in rows}


def build_graph(con) -> dict:
    top_authors = _top_author_ids(con)

    edges_raw = con.sql(
        """
        SELECT source_id, target_id, edge_type, peso_total, eventos, metadata_ejemplo
        FROM gold.grafo_edges_agg_trolls
        ORDER BY peso_total DESC
        """
    ).df()

    vertices = con.sql(
        """
        SELECT vertex_id, label, tipo, plataforma, peso_actividad
        FROM gold.grafo_vertices_trolls
        """
    ).df()

    # Filter edges to subgraph
    kept_nodes: set[str] = set(top_authors)
    kept_nodes.update(v for v in vertices["vertex_id"] if str(v).startswith("cuenta:"))
    kept_nodes.update(v for v in vertices["vertex_id"] if str(v).startswith("cohorte:"))

    filtered_edges = []
    for row in edges_raw.itertuples(index=False):
        src, tgt, etype, peso = row.source_id, row.target_id, row.edge_type, int(row.peso_total)
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

    # Add narrative nodes only if connected
    node_rows = vertices[vertices["vertex_id"].isin(kept_nodes)]

    nodes = []
    for row in node_rows.itertuples(index=False):
        style = NODE_STYLE.get(row.tipo, NODE_STYLE["autor"])
        size = style["size"]
        if row.tipo == "autor" and row.peso_actividad:
            size = min(40, style["size"] + int(row.peso_actividad) // 2)
        nodes.append(
            {
                "id": row.vertex_id,
                "label": _short_label(row.label, row.tipo),
                "tipo": row.tipo,
                "title": _node_tooltip(row),
                "color": style["color"],
                "shape": style["shape"],
                "size": size,
            }
        )

    edges = []
    for i, row in enumerate(filtered_edges):
        style = EDGE_STYLE.get(row.edge_type, EDGE_STYLE["ataca"])
        w = max(1, min(12, int(row.peso_total * style["width_factor"])))
        edges.append(
            {
                "id": f"e{i}",
                "from": row.source_id,
                "to": row.target_id,
                "label": _edge_label(row.edge_type, row.peso_total),
                "title": f"{row.edge_type} · peso {row.peso_total}"
                + (f" · {row.metadata_ejemplo}" if row.metadata_ejemplo else ""),
                "color": style["color"],
                "dashes": style["dashes"],
                "width": w,
                "edge_type": row.edge_type,
            }
        )

    stats = _compute_stats(con, filtered_edges, nodes)
    return {"nodes": nodes, "edges": edges, "estadisticas": stats, "insights": _insights(stats)}


def _short_label(label: str, tipo: str) -> str:
    if tipo == "autor" and label and len(label) > 14:
        return label[:12] + "…"
    if tipo == "cohorte_dia":
        return label.replace(" 00:00:00", "")[:16]
    if tipo == "narrativa":
        return label.replace("_", " ")[:18]
    return label or "?"


def _node_tooltip(row) -> str:
    parts = [row.label, f"tipo: {row.tipo}"]
    if row.plataforma:
        parts.append(f"plataforma: {row.plataforma}")
    if row.peso_actividad:
        parts.append(f"actividad: {row.peso_actividad}")
    return "\n".join(parts)


def _edge_label(edge_type: str, peso: int) -> str:
    abbr = {"ataca": "→", "co_rafaga": "↔", "usa_narrativa": "nar", "en_cohorte": "coh"}
    return f"{abbr.get(edge_type, edge_type)} {peso}"


def _compute_stats(con, edges, nodes) -> dict:
    co = con.sql(
        """
        SELECT COUNT(*) AS pares FROM gold.grafo_edges_agg_trolls WHERE edge_type = 'co_rafaga'
        """
    ).fetchone()[0]
    peak = con.sql(
        """
        SELECT cuenta_slug, CAST(dia AS DATE) AS dia, autores_con_rafaga, comentarios_en_rafagas
        FROM gold.v_trolls_rafagas_dia
        ORDER BY autores_con_rafaga DESC, comentarios_en_rafagas DESC
        LIMIT 1
        """
    ).fetchone()
    multi = con.sql(
        "SELECT COUNT(*) FROM gold.v_trolls_grupos_multobjetivo"
    ).fetchone()[0]
    by_type = {}
    for n in nodes:
        by_type[n["tipo"]] = by_type.get(n["tipo"], 0) + 1
    edge_types = {}
    for e in edges:
        et = e.edge_type if hasattr(e, "edge_type") else e["edge_type"]
        edge_types[et] = edge_types.get(et, 0) + 1
    return {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "node_types": by_type,
        "edge_types": edge_types,
        "pares_co_rafaga_total": co,
        "autores_multi_objetivo": multi,
        "pico_cohorte": {
            "cuenta": peak[0],
            "dia": str(peak[1]),
            "autores": peak[2],
            "comentarios": peak[3],
        },
    }


def _insights(stats: dict) -> list[str]:
    pico = stats["pico_cohorte"]
    return [
        f"Hub central: **{pico['cuenta']}** concentra la mayoría de aristas `ataca`.",
        f"Cohorte más densa: **{pico['dia']}** con **{pico['autores']}** autores en ráfaga simultánea "
        f"({pico['comentarios']} comentarios en bursts).",
        f"**{stats['pares_co_rafaga_total']}** pares de autores comparten día+cuenta con ráfaga "
        f"(aristas `co_rafaga` ↔) — posible sincronía, no prueba de coordinación.",
        f"**{stats['autores_multi_objetivo']}** autores atacan ≥2 cuentas trackeadas "
        f"(ej. turca1985, PelusonOfpink) — puente entre comunidades.",
        "Narrativas compartidas (`usa_narrativa`) conectan autores con temas similares "
        "(spam/enlaces, insulto, conspiranoia).",
    ]


HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Grafo trolls — entidades e interacciones</title>
  <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style>
    :root { --bg:#0f1419; --surface:#1a2332; --text:#e7ecf3; --muted:#8b9cb3; --border:#2d3a4f; }
    * { box-sizing:border-box; margin:0; padding:0; }
    body { font-family: system-ui, sans-serif; background:var(--bg); color:var(--text); height:100vh; display:flex; flex-direction:column; }
    header { padding:1rem 1.25rem; border-bottom:1px solid var(--border); background:var(--surface); }
    header h1 { font-size:1.2rem; }
    header p { color:var(--muted); font-size:0.85rem; margin-top:0.25rem; }
    .layout { display:flex; flex:1; min-height:0; }
    #network { flex:1; background:#0a0e14; }
    aside { width:380px; border-left:1px solid var(--border); background:var(--surface); overflow-y:auto; padding:1rem; font-size:0.88rem; }
    aside h2 { font-size:0.95rem; margin:1rem 0 0.5rem; }
    aside h2:first-child { margin-top:0; }
    .legend { display:flex; flex-wrap:wrap; gap:0.5rem; margin-bottom:0.75rem; }
    .legend span { display:inline-flex; align-items:center; gap:0.35rem; font-size:0.78rem; color:var(--muted); }
    .dot { width:10px; height:10px; border-radius:50%; }
    .insight { margin-bottom:0.65rem; line-height:1.45; color:var(--muted); }
    .insight strong { color:var(--text); }
    .stat-grid { display:grid; grid-template-columns:1fr 1fr; gap:0.5rem; margin-bottom:0.75rem; }
    .stat { background:var(--bg); padding:0.5rem 0.65rem; border-radius:8px; border:1px solid var(--border); }
    .stat .n { font-size:1.2rem; font-weight:700; }
    .stat .l { font-size:0.72rem; color:var(--muted); text-transform:uppercase; }
    .controls { display:flex; flex-wrap:wrap; gap:0.5rem; margin-top:0.5rem; }
    button, select { background:#243044; color:var(--text); border:1px solid var(--border); border-radius:6px; padding:0.35rem 0.6rem; font-size:0.8rem; cursor:pointer; }
    ul.edge-list { list-style:none; padding:0; }
    ul.edge-list li { padding:0.35rem 0; border-bottom:1px solid var(--border); font-size:0.8rem; color:var(--muted); }
    details.guide { margin:0.75rem 0; border:1px solid var(--border); border-radius:8px; background:var(--bg); }
    details.guide summary { cursor:pointer; padding:0.5rem 0.65rem; color:#5b8def; font-weight:600; font-size:0.82rem; }
    .guide-body { padding:0 0.65rem 0.65rem; font-size:0.78rem; color:var(--muted); line-height:1.5; }
    .guide-body p { margin-bottom:0.45rem; }
    .guide-body strong { color:var(--text); }
    .guide-body dl dt { color:var(--text); font-weight:600; margin-top:0.35rem; }
    .guide-body dl dd { margin:0 0 0.25rem 0; }
    .links a { color:#5b8def; text-decoration:none; display:block; margin:0.25rem 0; font-size:0.78rem; }
    .links a:hover { text-decoration:underline; }
  </style>
</head>
<body>
  <header>
    <h1>Grafo de trolls — entidades e interacciones</h1>
    <p>Autores identificados · cuentas objetivo · narrativas · cohortes de ráfaga · Generado: __GENERATED__</p>
    <div class="controls">
      <select id="filterEdge"><option value="">Todas las relaciones</option></select>
      <button id="btnFit">Ajustar vista</button>
      <button id="btnPhysics">Toggle física</button>
    </div>
  </header>
  <div class="layout">
    <div id="network"></div>
    <aside>
      <h2>Resumen</h2>
      <div class="stat-grid" id="stats"></div>

      <details class="guide" open>
        <summary>Metodología y procesamiento</summary>
        <div class="guide-body">
          <p><strong>Flujo:</strong> silver.tw_tweets_replies + tw_comments_classification → gold.v_trolls_actividad (solo trolls con autor identificado) → gold.v_trolls_rafagas → gold.grafo_*_trolls.</p>
          <p><strong>Subgrafo mostrado:</strong> ~35 autores con más actividad en ráfagas + cuentas objetivo + narrativas + cohortes con ≥2 autores/día.</p>
          <p><strong>Filtro aristas:</strong> use el desplegable superior para ver solo <code>co_rafaga</code>, <code>ataca</code>, etc.</p>
          <p><strong>Límite:</strong> solo Twitter con handle; no prueba identidad real ni coordinación.</p>
        </div>
      </details>

      <details class="guide" open>
        <summary>Cómo leer el grafo</summary>
        <div class="guide-body">
          <p><strong>Nodos grandes (rojos):</strong> autores con más comentarios en ráfagas. Hover = tooltip con nombre.</p>
          <p><strong>Cajas verdes:</strong> cuentas PTS objetivo (myriambregman, nicolasdelcano, ptsarg).</p>
          <p><strong>Hexágonos azules:</strong> cohorte = día+cuenta donde ≥2 autores tuvieron ráfaga simultánea.</p>
          <p><strong>Rombo violeta:</strong> narrativa temática del comentario (spam, insulto, etc.).</p>
          <p><strong>Controles:</strong> rueda = zoom · arrastrar = pan · clic nodo = resaltar vecinos · Ajustar vista = centrar · Física = estabilizar layout.</p>
        </div>
      </details>

      <h2>Leyenda de nodos</h2>
      <div class="legend">
        <span><i class="dot" style="background:#f07178"></i> Autor troll</span>
        <span><i class="dot" style="background:#3dd68c"></i> Cuenta objetivo</span>
        <span><i class="dot" style="background:#a78bfa"></i> Narrativa</span>
        <span><i class="dot" style="background:#60a5fa"></i> Cohorte (día)</span>
      </div>

      <details class="guide" open>
        <summary>Tipos de arista (relaciones)</summary>
        <div class="guide-body">
          <dl>
            <dt>→ ataca</dt>
            <dd>Autor → cuenta. Peso = comentarios troll en ráfagas hacia esa figura. Muestra quién concentra fuego contra quién.</dd>
            <dt>↔ co_rafaga</dt>
            <dd>Autor ↔ autor. Ambos tuvieron ráfaga (≥3 trolls) el <em>mismo día</em> contra la <em>misma cuenta</em>. Sincronía temporal; no implica que se conozcan ni mismo post.</dd>
            <dt>usa_narrativa (nar)</dt>
            <dd>Autor → tema. Vincula handle con categoría inferida del resumen LLM.</dd>
            <dt>en_cohorte (coh)</dt>
            <dd>Autor → nodo cohorte-día. Autor participó en un día con múltiples ráfagas contra la misma cuenta.</dd>
          </dl>
        </div>
      </details>

      <h2>Relaciones observables</h2>
      <div id="insights"></div>
      <h2>Conteo de aristas</h2>
      <ul class="edge-list" id="edgeTypes"></ul>

      <details class="guide">
        <summary>Reportes relacionados</summary>
        <div class="guide-body links">
          <a href="../gold-report/report.html">Dashboard analítico (Chart.js) — sentimiento, narrativa, KPIs</a>
          <a href="../analisis-completo/report.pdf">PDF consolidado con tablas y gráficos estáticos</a>
          <a href="grafo.json">Datos del grafo (JSON)</a>
        </div>
      </details>
    </aside>
  </div>
  <script>
    const GRAFO = __GRAFO_JSON__;
    const nodesDS = new vis.DataSet(GRAFO.nodes.map(n => ({
      id: n.id, label: n.label, title: n.title, color: n.color,
      shape: n.shape, size: n.size, font: { color: '#e7ecf3', size: 11 },
    })));
    let allEdges = GRAFO.edges.map(e => ({
      id: e.id, from: e.from, to: e.to, label: e.label, title: e.title,
      color: e.color, dashes: e.dashes, width: e.width,
      edge_type: e.edge_type, font: { size: 9, color: '#8b9cb3', strokeWidth: 0 },
    }));
    const edgesDS = new vis.DataSet(allEdges);

    const statsEl = document.getElementById('stats');
    const s = GRAFO.estadisticas;
    statsEl.innerHTML = [
      ['Nodos', s.total_nodes], ['Aristas', s.total_edges],
      ['Pares co-ráfaga', s.pares_co_rafaga_total], ['Multi-objetivo', s.autores_multi_objetivo],
    ].map(([l,n]) => `<div class="stat"><div class="n">${n}</div><div class="l">${l}</div></div>`).join('');

    document.getElementById('insights').innerHTML = GRAFO.insights.map(t =>
      `<p class="insight">${t.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')}</p>`
    ).join('');

    const et = GRAFO.estadisticas.edge_types;
    document.getElementById('edgeTypes').innerHTML = Object.entries(et).map(([k,v]) =>
      `<li><strong>${k}</strong> — ${v} aristas</li>`
    ).join('');

    const sel = document.getElementById('filterEdge');
    [...new Set(allEdges.map(e => e.edge_type))].sort().forEach(t => {
      const o = document.createElement('option'); o.value = t; o.textContent = t; sel.appendChild(o);
    });
    sel.addEventListener('change', () => {
      const v = sel.value;
      edgesDS.clear();
      edgesDS.add(v ? allEdges.filter(e => e.edge_type === v) : allEdges);
    });

    let physics = true;
    const options = {
      physics: { enabled: true, barnesHut: { gravitationalConstant: -8000, springLength: 120, avoidOverlap: 0.2 } },
      interaction: { hover: true, tooltipDelay: 100, navigationButtons: true },
      edges: { smooth: { type: 'dynamic' }, arrowStrikethrough: false },
    };
    const network = new vis.Network(document.getElementById('network'), { nodes: nodesDS, edges: edgesDS }, options);
    document.getElementById('btnFit').onclick = () => network.fit({ animation: true });
    document.getElementById('btnPhysics').onclick = () => {
      physics = !physics;
      network.setOptions({ physics: { enabled: physics } });
    };
  </script>
</body>
</html>
"""


BUNDLE_README = """\
# Trolls grafo — red interactiva

Grafo vis.js: autores troll, cuentas objetivo, narrativas, cohortes.

| Archivo | Rol |
|---------|-----|
| `report.html` | Vista interactiva (grafo embebido) |
| `grafo.json` | Nodos, aristas, estadísticas |

Generado: {generated}
Regenerar: `uv run python scripts/python/generate_trolls_grafo_report.py`
"""


def main() -> int:
    con = db.connect_for_ingest(release_mcp=True)
    grafo = build_graph(con)
    con.close()

    generated = date.today().isoformat()
    out_dir = db.get_report_bundle("redes", "trolls-grafo")

    json_path = out_dir / "grafo.json"
    html_path = out_dir / "report.html"
    readme_path = out_dir / "README.md"

    payload = {"generated": generated, **grafo}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    html = (
        HTML.replace("__GENERATED__", generated)
        .replace("__GRAFO_JSON__", json.dumps(grafo, ensure_ascii=False))
    )
    html_path.write_text(html, encoding="utf-8")
    readme_path.write_text(BUNDLE_README.format(generated=generated), encoding="utf-8")

    print(f"Bundle: {out_dir}/")
    print(f"  report.html")
    print(f"  grafo.json")
    print(f"Nodes: {grafo['estadisticas']['total_nodes']} · Edges: {grafo['estadisticas']['total_edges']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
