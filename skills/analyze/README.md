# Analyze

Reports and network analysis from DuckDB tables. Outputs go to `report/<project>/<report-name>`.

## Sub-scope: Reports

| Skill | When to use |
|-------|-------------|
| [`statistical-report`](reports/statistical-report/SKILL.md) | EDA, profiling, multi-format reports |
| [`sentiment-analysis`](reports/sentiment-analysis/SKILL.md) | Text tone and framing |

## Sub-scope: Graph

| Skill | When to use |
|-------|-------------|
| [`graph-ingest`](graph/graph-ingest/SKILL.md) | Build `grafo_vertices` / `grafo_edges` from entity data |
| [`graph-analysis`](graph/graph-analysis/SKILL.md) | Centrality, communities, density — markdown reports |
| [`interactive-graph-reports`](graph/interactive-graph-reports/SKILL.md) | HTML graph viz (vis.js + React) |

Flow: `graph-ingest` → `graph-analysis` → optional `interactive-graph-reports`.
