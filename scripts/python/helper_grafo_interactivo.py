"""
helper_grafo_interactivo.py - Utility functions for generating interactive graph reports

Usage:
    from helper_grafo_interactivo import export_graph_data, generate_html_report
    
    export_graph_data(
        nodes=organismos,
        edges=relationships,
        output_dir='reports/',
        filename='grafo.json'
    )
    
    generate_html_report(
        grafo_json='grafo.json',
        title='Mi Grafo',
        output_dir='reports/'
    )
"""

import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple


def export_graph_data(
    nodes: List[Dict],
    edges: List[Dict],
    output_dir: str = 'reports/',
    filename: str = 'grafo.json'
) -> Path:
    """
    Export nodes and edges to a single JSON file with statistics.
    
    Args:
        nodes: List of node dicts with keys: id, label, tipo (required)
        edges: List of edge dicts with keys: from, to, type (required)
        output_dir: Directory to save output
        filename: Output filename
    
    Returns:
        Path to generated JSON file
    """
    output_path = Path(output_dir) / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Calculate statistics
    stats = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "node_types": {},
        "edge_types": {},
        "avg_degree": len(edges) * 2 / max(len(nodes), 1)
    }
    
    for node in nodes:
        tipo = node.get('tipo', 'unknown')
        stats['node_types'][tipo] = stats['node_types'].get(tipo, 0) + 1
    
    for edge in edges:
        edge_type = edge.get('type', 'unknown')
        stats['edge_types'][edge_type] = stats['edge_types'].get(edge_type, 0) + 1
    
    data = {
        "nodes": nodes,
        "edges": edges,
        "estadisticas": stats
    }
    
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"✅ Exported {len(nodes)} nodes, {len(edges)} edges to {output_path}")
    
    return output_path


def generate_html_interactive(
    grafo_json: str,
    output_path: str = 'reports/grafo_interactivo.html',
    title: str = 'Grafo Interactivo',
    physics_enabled: bool = True,
    node_colors: Optional[Dict[str, str]] = None
) -> Path:
    """
    Generate interactive HTML report with vis.js + React.
    
    Args:
        grafo_json: Path to grafo.json file
        output_path: Output HTML file path
        title: Report title
        physics_enabled: Enable physics simulation
        node_colors: Dict mapping node tipo to color hex codes
    
    Returns:
        Path to generated HTML file
    """
    
    colors = node_colors or {
        'organismo': '#667eea',
        'adjudicatario': '#764ba2',
        'default': '#999999'
    }
    
    html_template = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <script src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        #app {{ display: flex; height: 100vh; }}
        #network {{ flex: 1; }}
        .sidebar {{ width: 350px; background: #f8f9fa; padding: 1.5rem; overflow-y: auto; border-right: 1px solid #ddd; }}
        .stat {{ margin-bottom: 1.5rem; padding: 1rem; background: white; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .stat-title {{ font-weight: 600; color: #667eea; margin-bottom: 0.5rem; }}
        .stat-value {{ font-size: 1.8rem; font-weight: bold; }}
        input {{ width: 100%; padding: 0.6rem; margin-bottom: 1rem; border: 1px solid #ddd; border-radius: 4px; }}
        button {{ width: 100%; padding: 0.6rem; background: #667eea; color: white; border: none; border-radius: 4px; cursor: pointer; margin-bottom: 0.5rem; }}
        button:hover {{ background: #5568d3; }}
        .detail {{ margin-top: 1.5rem; padding: 1rem; background: white; border-radius: 4px; }}
        .detail-field {{ margin-bottom: 0.8rem; }}
        .detail-label {{ font-size: 0.8rem; color: #999; text-transform: uppercase; }}
        .detail-value {{ font-weight: 500; }}
    </style>
</head>
<body>
    <div id="app"></div>
    
    <script type="text/babel">
        const {{ useState, useEffect, useRef }} = React;
        
        function App() {{
            const [data, setData] = useState(null);
            const [selectedNode, setSelectedNode] = useState(null);
            const [search, setSearch] = useState('');
            const networkRef = useRef(null);
            const containerRef = useRef(null);
            
            useEffect(() => {{
                fetch('{grafo_json}')
                    .then(r => r.json())
                    .then(setData)
                    .catch(err => console.error('Error:', err));
            }}, []);
            
            useEffect(() => {{
                if (!data || !containerRef.current) return;
                
                const colorMap = {json.dumps(colors)};
                
                const nodes = new vis.DataSet(
                    data.nodes.map(n => ({{
                        id: n.id,
                        label: n.label,
                        title: n.label,
                        color: colorMap[n.tipo] || colorMap.default,
                        shape: n.tipo === 'organismo' ? 'box' : 'dot',
                        size: 20,
                        font: {{ size: 12 }}
                    }}))
                );
                
                const edges = new vis.DataSet(
                    data.edges.map(e => ({{
                        from: e.from,
                        to: e.to,
                        label: e.type,
                        arrows: 'to',
                        smooth: {{ type: 'continuous' }}
                    }}))
                );
                
                const options = {{
                    physics: {{
                        enabled: {str(physics_enabled).lower()},
                        barnesHut: {{
                            gravitationalConstant: -26000,
                            centralGravity: 0.3,
                            springLength: 200
                        }}
                    }}
                }};
                
                networkRef.current = new vis.Network(
                    containerRef.current,
                    {{ nodes, edges }},
                    options
                );
                
                networkRef.current.on('click', (params) => {{
                    if (params.nodes.length > 0) {{
                        const nodeId = params.nodes[0];
                        const node = nodes.get(nodeId);
                        setSelectedNode(node);
                    }}
                }});
            }}, [data]);
            
            if (!data) return <div style={{{{ padding: '2rem' }}}}>Cargando...</div>;
            
            return (
                <div style={{{{ display: 'flex', height: '100vh' }}}}>
                    <div className="sidebar">
                        <h2 style={{{{ marginBottom: '1.5rem' }}}}>📊 {{title}}</h2>
                        
                        <div className="stat">
                            <div className="stat-title">Nodos</div>
                            <div className="stat-value">{{data.estadisticas.total_nodes}}</div>
                        </div>
                        
                        <div className="stat">
                            <div className="stat-title">Relaciones</div>
                            <div className="stat-value">{{data.estadisticas.total_edges}}</div>
                        </div>
                        
                        <input 
                            type="text" 
                            placeholder="Buscar nodo..."
                            value={{search}}
                            onChange={{(e) => setSearch(e.target.value)}}
                        />
                        
                        <button onClick={{() => networkRef.current?.fit()}}>
                            Ajustar vista
                        </button>
                        
                        <button onClick={{() => setSelectedNode(null)}}>
                            Limpiar
                        </button>
                        
                        {{selectedNode && (
                            <div className="detail">
                                <div className="detail-field">
                                    <div className="detail-label">Nombre</div>
                                    <div className="detail-value">{{selectedNode.label}}</div>
                                </div>
                                <div className="detail-field">
                                    <div className="detail-label">ID</div>
                                    <div className="detail-value">{{selectedNode.id}}</div>
                                </div>
                            </div>
                        )}}
                    </div>
                    
                    <div ref={{containerRef}} style={{{{ flex: 1 }}}}></div>
                </div>
            );
        }}
        
        ReactDOM.render(<App />, document.getElementById('app'));
    </script>
</body>
</html>
"""
    
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html_template, encoding='utf-8')
    print(f"✅ Generated interactive report: {output_file}")
    
    return output_file


def generate_analytics_html(
    grafo_json: str,
    output_path: str = 'reports/analisis_grafo.html',
    title: str = 'Análisis del Grafo'
) -> Path:
    """
    Generate analytics HTML report with Chart.js.
    
    Args:
        grafo_json: Path to grafo.json file
        output_path: Output HTML file path
        title: Report title
    
    Returns:
        Path to generated HTML file
    """
    
    html_template = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 2rem;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: white; margin-bottom: 2rem; text-align: center; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 2rem; }}
        .card {{ background: white; border-radius: 8px; padding: 2rem; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }}
        .card h2 {{ color: #667eea; margin-bottom: 1.5rem; border-bottom: 2px solid #f0f0f0; padding-bottom: 1rem; }}
        .chart-container {{ position: relative; height: 400px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
        th, td {{ padding: 0.8rem; text-align: left; border-bottom: 1px solid #f0f0f0; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 {title}</h1>
        
        <div class="grid">
            <div class="card">
                <h2>Distribución de Nodos</h2>
                <div class="chart-container">
                    <canvas id="nodeChart"></canvas>
                </div>
            </div>
            
            <div class="card">
                <h2>Distribución de Relaciones</h2>
                <div class="chart-container">
                    <canvas id="edgeChart"></canvas>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        fetch('{grafo_json}')
            .then(r => r.json())
            .then(data => {{
                const stats = data.estadisticas;
                
                // Node types chart
                new Chart(document.getElementById('nodeChart'), {{
                    type: 'doughnut',
                    data: {{
                        labels: Object.keys(stats.node_types),
                        datasets: [{{
                            data: Object.values(stats.node_types),
                            backgroundColor: ['#667eea', '#764ba2', '#f093fb', '#74b9ff']
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{ legend: {{ position: 'bottom' }} }}
                    }}
                }});
                
                // Edge types chart
                new Chart(document.getElementById('edgeChart'), {{
                    type: 'bar',
                    data: {{
                        labels: Object.keys(stats.edge_types),
                        datasets: [{{
                            label: 'Cantidad',
                            data: Object.values(stats.edge_types),
                            backgroundColor: '#667eea'
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {{ y: {{ beginAtZero: true }} }}
                    }}
                }});
            }});
    </script>
</body>
</html>
"""
    
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html_template, encoding='utf-8')
    print(f"✅ Generated analytics report: {output_file}")
    
    return output_file


def calculate_degree_centrality(edges: List[Dict]) -> Dict[int, int]:
    """Calculate degree centrality for each node."""
    degrees = {}
    for edge in edges:
        from_id = edge.get('from')
        to_id = edge.get('to')
        
        degrees[from_id] = degrees.get(from_id, 0) + 1
        degrees[to_id] = degrees.get(to_id, 0) + 1
    
    return degrees


def get_top_nodes(
    nodes: List[Dict],
    edges: List[Dict],
    metric: str = 'degree',
    top_n: int = 10
) -> List[Tuple[int, str, int]]:
    """
    Get top nodes by centrality metric.
    
    Args:
        nodes: List of nodes
        edges: List of edges
        metric: 'degree' (default)
        top_n: Number of top nodes to return
    
    Returns:
        List of (node_id, label, value) tuples
    """
    
    if metric == 'degree':
        centrality = calculate_degree_centrality(edges)
    else:
        raise ValueError(f"Unsupported metric: {metric}")
    
    node_map = {n['id']: n['label'] for n in nodes}
    ranked = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:top_n]
    
    return [(node_id, node_map[node_id], value) for node_id, value in ranked]


# Example usage
if __name__ == '__main__':
    # Sample data
    nodes = [
        {'id': 1, 'label': 'Organismo A', 'tipo': 'organismo'},
        {'id': 2, 'label': 'Organismo B', 'tipo': 'organismo'},
        {'id': 101, 'label': 'Contractor X', 'tipo': 'adjudicatario'},
        {'id': 102, 'label': 'Contractor Y', 'tipo': 'adjudicatario'},
    ]
    
    edges = [
        {'from': 1, 'to': 101, 'type': 'ADJUDICA_A'},
        {'from': 1, 'to': 102, 'type': 'ADJUDICA_A'},
        {'from': 2, 'to': 101, 'type': 'ADJUDICA_A'},
    ]
    
    # Export graph
    export_graph_data(nodes, edges, output_dir='reports/', filename='test_grafo.json')
    
    # Generate reports
    generate_html_interactive('reports/test_grafo.json', 'reports/test_interactivo.html')
    generate_analytics_html('reports/test_grafo.json', 'reports/test_analytics.html')
    
    # Calculate centrality
    top = get_top_nodes(nodes, edges, top_n=3)
    print(f"\nTop nodes by degree:")
    for node_id, label, degree in top:
        print(f"  {label}: {degree}")
