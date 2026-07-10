"""Genera visualización interactiva del grafo (vis.js + controles)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import db

reports = db.get_reports_path()
landing = db.get_landing_path()
fecha = date.today().strftime("%Y%m%d")


def load_graph() -> dict:
    path = landing / f"grafo_data_{fecha}.json"
    if not path.exists():
        # fallback: rebuild from DB
        import subprocess
        subprocess.run(
            ["uv", "run", "python", "scripts/python/analisis_entidades_grafo.py"],
            cwd=db.get_db_path().parent.parent, capture_output=True,
        )
    return json.loads(path.read_text(encoding="utf-8"))


def build_html(data: dict) -> str:
    nodes = data["nodes"]
    edges = data["edges"]

    # compute degree for sizing
    degree_map: dict[int, int] = {}
    for e in edges:
        degree_map[e["from"]] = degree_map.get(e["from"], 0) + 1
        degree_map[e["to"]] = degree_map.get(e["to"], 0) + 1
    max_deg = max(degree_map.values()) if degree_map else 1

    # colors by type
    colors = {
        "empresa_sa": "#4CAF50",
        "persona": "#2196F3",
        "profesional": "#FF9800",
        "organismo": "#f44336",
        "lugar": "#9C27B0",
        "oficina": "#607D8B",
    }
    shapes = {
        "empresa_sa": "box",
        "organismo": "box",
        "lugar": "diamond",
        "oficina": "square",
        "persona": "dot",
        "profesional": "dot",
    }

    nodes_json = json.dumps([
        {
            "id": n["id"],
            "label": n["label"],
            "title": f"{n['label']}<br/>Tipo: {n['tipo']}<br/>Conexiones: {degree_map.get(n['id'], 0)}",
            "color": {"background": colors.get(n["tipo"], "#999"), "border": "#333"},
            "shape": shapes.get(n["tipo"], "dot"),
            "size": 15 + 20 * (degree_map.get(n["id"], 0) / max_deg),
            "font": {"size": 10, "face": "monospace"},
            "group": n["tipo"],
            "tipo": n["tipo"],
        }
        for n in nodes
    ], ensure_ascii=False)

    edges_json = json.dumps([
        {
            "from": e["from"],
            "to": e["to"],
            "width": 1 + min(e.get("weight", 1), 5),
            "title": f"Co-ocurrencias: {e.get('weight', 1)}<br/>Tipo: {e.get('type', '')}",
            "color": {"color": "#999", "opacity": 0.5},
            "smooth": {"type": "continuous"},
        }
        for e in edges
    ], ensure_ascii=False)

    type_counts = {}
    for n in nodes:
        t = n["tipo"]
        type_counts[t] = type_counts.get(t, 0) + 1
    stats_json = json.dumps({
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "type_counts": type_counts,
    }, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Grafo — Boletín Oficial</title>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:system-ui,sans-serif; background:#1a1a2e; color:#eee; }}
#header {{ background:#16213e; padding:12px 20px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px; border-bottom:2px solid #0f3460; }}
#header h1 {{ font-size:16px; color:#e94560; }}
#controls {{ display:flex; gap:8px; flex-wrap:wrap; align-items:center; }}
#controls label {{ font-size:12px; color:#aaa; }}
#controls select, #controls input, #controls button {{ padding:4px 10px; border-radius:4px; border:1px solid #0f3460; background:#1a1a2e; color:#eee; font-size:12px; }}
#controls button {{ background:#e94560; color:#fff; cursor:pointer; border:none; }}
#controls button:hover {{ background:#c73650; }}
#stats {{ font-size:11px; color:#888; }}
#network {{ width:100%; height:calc(100vh - 100px); background:#16213e; }}
#legend {{ position:fixed; bottom:20px; right:20px; background:#16213e; padding:10px 14px; border-radius:8px; border:1px solid #0f3460; font-size:11px; z-index:10; }}
#legend div {{ display:flex; align-items:center; gap:6px; margin:3px 0; }}
.dot {{ width:10px; height:10px; border-radius:50%; display:inline-block; }}
.box {{ width:10px; height:10px; display:inline-block; }}
.diamond {{ width:10px; height:10px; display:inline-block; transform:rotate(45deg); }}
.square {{ width:10px; height:10px; display:inline-block; }}
</style>
</head>
<body>
<div id="header">
  <div><h1>🕸️ Grafo Boletín Oficial</h1><div id="stats"></div></div>
  <div id="controls">
    <label>Filtrar:</label>
    <select id="filterType"><option value="">Todos</option></select>
    <input type="text" id="searchInput" placeholder="Buscar entidad…" style="width:160px">
    <label><input type="checkbox" id="physicsToggle" checked> Física</label>
    <button onclick="resetView()">Reset</button>
  </div>
</div>
<div id="network"></div>
<div id="legend"></div>

<script>
const NODES = {nodes_json};
const EDGES = {edges_json};
const STATS = {stats_json};

// Populate legend
const COLORS = {{"empresa_sa":"#4CAF50","persona":"#2196F3","profesional":"#FF9800","organismo":"#f44336","lugar":"#9C27B0","oficina":"#607D8B"}};
const SHAPES = {{"empresa_sa":"box","organismo":"box","lugar":"diamond","oficina":"square","persona":"dot","profesional":"dot"}};
const LABELS = {{"empresa_sa":"Empresa SA","persona":"Persona","profesional":"Profesional","organismo":"Organismo","lugar":"Lugar","oficina":"Oficina"}};
const legend = document.getElementById('legend');
legend.innerHTML = '<b>Tipos</b><br>' + Object.entries(LABELS).map(([k,v]) =>
  '<div><span class="'+SHAPES[k]+'" style="background:'+COLORS[k]+'"></span> '+v+' ('+STATS.type_counts[k]+')</div>'
).join('') + '<br><span style="color:#888">Co-ocurrencia en aviso</span>';

document.getElementById('stats').textContent = STATS.total_nodes + ' nodos · ' + STATS.total_edges + ' aristas';

// vis.js
const container = document.getElementById('network');
const items = new vis.DataSet(NODES);
const conns = new vis.DataSet(EDGES);

const allTypes = [...new Set(NODES.map(n => n.tipo))];
const sel = document.getElementById('filterType');
allTypes.forEach(t => {{ const o = document.createElement('option'); o.value = t; o.textContent = LABELS[t] || t; sel.appendChild(o); }});

let network = null;

function initNetwork(nodes, edges) {{
  const options = {{
    nodes: {{ borderWidth: 1, font: {{ size: 10, face: 'monospace', color: '#eee' }} }},
    edges: {{ arrows: {{ to: {{ enabled: false }} }}, smooth: {{ type: 'continuous' }} }},
    physics: {{
      enabled: true,
      barnesHut: {{ gravitationalConstant: -30000, centralGravity: 0.3, springLength: 180, springConstant: 0.04, damping: 0.9 }},
    }},
    groups: Object.fromEntries(Object.entries(COLORS).map(([k,v]) => [k, {{ color: {{ background: v, border: '#333' }} }}])),
    interaction: {{ hover: true, tooltipDelay: 200, navigationButtons: true, keyboard: true }},
  }};
  network = new vis.Network(container, {{ nodes, edges }}, options);
}}

initNetwork(items, conns);

// Filter
document.getElementById('filterType').addEventListener('change', function() {{
  const t = this.value;
  if (!t) {{ items.forEach(n => items.update({{ id: n.id, hidden: false }})); return; }}
  items.forEach(n => items.update({{ id: n.id, hidden: n.tipo !== t }}));
  network.fit();
}});

// Search
document.getElementById('searchInput').addEventListener('input', function() {{
  const q = this.value.toLowerCase();
  items.forEach(n => {{
    const match = n.label.toLowerCase().includes(q);
    items.update({{ id: n.id, hidden: !match }});
  }});
  if (q) network.fit();
}});

// Physics toggle
document.getElementById('physicsToggle').addEventListener('change', function() {{
  network.setOptions({{ physics: {{ enabled: this.checked }} }});
}});

function resetView() {{
  items.forEach(n => items.update({{ id: n.id, hidden: false }}));
  document.getElementById('filterType').value = '';
  document.getElementById('searchInput').value = '';
  network.fit();
}}

window.addEventListener('resize', () => network && network.fit());
</script>
</body>
</html>"""


def main():
    print("📦 Cargando datos del grafo...")
    data = load_graph()
    print(f"  → {len(data['nodes'])} nodos, {len(data['edges'])} aristas")

    html = build_html(data)
    out = reports / f"grafo_interactivo_{fecha}.html"
    out.write_text(html, encoding="utf-8")
    print(f"  → {out} ({len(html)} bytes)")
    print("\nAbrí el archivo en tu navegador para explorar el grafo.")


if __name__ == "__main__":
    main()
