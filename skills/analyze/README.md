# Analyze

Reports and network analysis from DuckDB tables. Outputs go to `reports/<project>/<report-slug>/` (one folder per report).

## Sub-scope: Reports

| Skill | When to use |
|-------|-------------|
| [`statistical-report`](reports/statistical-report/SKILL.md) | EDA, profiling, multi-format reports |
| [`sentiment-analysis`](reports/sentiment-analysis/SKILL.md) | Text tone and framing |
| [`social-monitor`](reports/social-monitor/SKILL.md) | Unified multi-platform monitoring dashboard (persona → accounts) |
| [`redes-analysis`](reports/redes-analysis/SKILL.md) | Legacy FB: gold reports, trolls, ráfagas, HTML |
| [`troll-blacklist`](reports/troll-blacklist/SKILL.md) | Twikit block/watch list (manual, auditable) |

## Sub-scope: Graph

| Skill | When to use |
|-------|-------------|
| [`graph-ingest`](graph/graph-ingest/SKILL.md) | Build `grafo_vertices` / `grafo_edges` from entity data |
| [`graph-analysis`](graph/graph-analysis/SKILL.md) | Centrality, communities, density — markdown reports |
| [`interactive-graph-reports`](graph/interactive-graph-reports/SKILL.md) | HTML graph viz (vis.js + React) |

Flow: `graph-ingest` → `graph-analysis` → optional `interactive-graph-reports`.

**Unified monitor (FB + TW):** identity seed → `gold.v_monitor_*` → `social-monitor` (HTML).  
**Redes PTS (Facebook only):** `redes-gold` (SQL views) → `redes-analysis` (HTML). Trolls graph uses `gold.grafo_*_trolls`.  
**Twitter/X:** twikit → `troll-blacklist` / hater reports.
