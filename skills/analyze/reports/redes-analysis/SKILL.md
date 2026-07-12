---
name: redes-analysis
description: >-
  Analyze legacy Facebook redes data and generate HTML reports from
  gold views — sentiment, narrative, trolls, ráfagas, interactive graphs,
  entidades, copy-pasta. Use when the user asks for redes reports, troll analysis,
  PTS account dashboards, or interpretation of gold redes charts and tables.
  (Twitter/X → twikit skills: scrape-twikit-twitter, troll-blacklist.)
---

# Redes analysis — tablas, consultas y reportes

**Project output:** `reports/redes/dashboard/` — unified HTML dashboard with external CSV datasets  
**Path helper:** `db.get_report_bundle("redes", "dashboard")`  
**Gold ingest:** skill [`redes-gold`](../../../ingest/gold/redes-gold/SKILL.md) (Facebook only)  
**Twitter trolls:** skill [`troll-blacklist`](../troll-blacklist/SKILL.md)  
**Privacy:** [`data-privacy`](../../../engineering/data-privacy/SKILL.md) — never commit `reports/**`

---

## Report layout (`reports/redes/`)

Single unified dashboard:

```
reports/redes/
├── README.md                # índice del proyecto
├── dashboard/
│   ├── report.html          # Chart.js + vis.js shell
│   ├── data/*.csv           # datasets exportados desde DuckDB
│   └── README.md
└── _exports/
    └── export_YYYYMMDD.zip
```

General convention: skill [`statistical-report`](statistical-report/SKILL.md).

---

## When to use

| User asks | Action |
|-----------|--------|
| Reporte HTML redes / dashboard PTS | Run gold + entidades + similarity SQL + `generate_redes_dashboard.py` |
| Grafo interactivo trolls | Same dashboard — sección **Grafo** (vis.js) |
| Top trolls, ráfagas, pico de hostilidad | MCP queries on `gold.v_trolls_*` |
| Sentimiento por cuenta | MCP on `gold.v_sentimiento_*` |
| Entidades / multicuenta | MCP on `gold.v_entidades_*` |

---

## End-to-end pipeline

```
silver.fb_* + classification
        ↓  ingest_redes_gold.sql
gold.v_* / gold.grafo_*
        ↓  ingest_network_profile.sql, ingest_gold_entidades.sql, ingest_redes_comment_similarity.sql
        ↓  MCP queries (exploración)
        ↓  generate_redes_dashboard.py
reports/redes/dashboard/
```

### 1. Refresh gold (writes — stop MCP)

```bash
uv run python scripts/python/db.py mcp-stop
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/redes/ingest_redes_gold.sql
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/redes/ingest_network_profile.sql
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/redes/ingest_gold_entidades.sql
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/redes/ingest_redes_comment_similarity.sql
```

### 2. Explore (reads — MCP preferred)

Use MCP `query` for ad-hoc analysis. Example patterns in [`redes-gold`](../../../ingest/gold/redes-gold/SKILL.md).

### 3. Generate dashboard

```bash
uv run python scripts/python/reports/generate_redes_dashboard.py
```

| Script | Bundle folder | Files |
|--------|---------------|-------|
| `generate_redes_dashboard.py` | `dashboard/` | `report.html` (datos embebidos), `data/*.csv`, `README.md` |

Open locally (self-contained — double-click or `open`):

```bash
open reports/redes/dashboard/report.html
```

### 4. Export zip (compartir offline)

```bash
uv run python scripts/python/reports/export_redes_reports_zip.py
# → reports/redes/_exports/export_{date}.zip
```

---

## Dashboard sections — qué analiza cada gráfico

| Sección | CSV principales | Lectura |
|---------|-----------------|---------|
| **Resumen** | `kpis.csv`, `sentimiento_resumen.csv` | KPIs globales y mix por cuenta |
| **Volúmenes** | `volumenes_cuenta.csv`, `comentarios_posicion_plataforma.csv` | Comentarios por plataforma/cuenta |
| **Sentimiento** | `sentimiento_por_cuenta.csv` | Barras 100% — mix posición LLM |
| **Temporal** | `sentimiento_temporal.csv`, `trolls_temporal.csv`, `trolls_rafagas_dia_temporal.csv` | Picos rojos = días hostiles; selector de cuenta |
| **Narrativa** | `narrativa_distribucion.csv`, `narrativa_temporal.csv`, `grafo_coocurrencia.csv` | Mix temático + serie semanal + co-ocurrencia |
| **Trolls** | `trolls_top10.csv`, `trolls_grupos.csv`, `trolls_rafagas*.csv` | Ranking, multi-objetivo, ráfagas |
| **Grafo** | `grafo_nodes.csv`, `grafo_edges.csv` | Red vis.js — autores, cuentas, narrativas, cohortes |
| **Entidades** | `entidades_*.csv` | Tipo de cuenta, confianza de nombre, multicuenta |
| **Comentarios similares** | `comentarios_clusters_*.csv` | Copy-pasta / clusters de texto |
| **Metodología** | — | Bronze → silver → LLM → gold → CSV → HTML |

### Grafo interactivo (sección Grafo)

| Nodo | Color | Significado |
|------|-------|-------------|
| Autor | Rojo | Top autores por peso `ataca` |
| Cuenta | Verde | Figura PTS objetivo |
| Narrativa | Violeta | Tema LLM/heurística |
| Cohorte | Azul | Día+cuenta con ≥2 ráfagas |

| Arista | Significado |
|--------|-------------|
| `ataca` | Autor → cuenta (peso = comentarios en ráfagas) |
| `co_rafaga` | Autor ↔ autor mismo día/cuenta (sincronía, no prueba de coordinación) |
| `usa_narrativa` | Autor → tema |
| `en_cohorte` | Autor → nodo cohorte-día |

---

## Ad-hoc analysis recipes

### Día con más trolls

```sql
SELECT dia, cuenta_slug, comentarios_troll, autores_distintos
FROM gold.v_trolls_temporal
ORDER BY comentarios_troll DESC LIMIT 10;
```

### Trolls recurrentes por red

```sql
SELECT plataforma, autor_handle, cuenta_slug, comentarios_troll
FROM gold.v_trolls_top10
ORDER BY plataforma, comentarios_troll DESC;
```

### Detalle temporal de un autor

```sql
SELECT dia, cuenta_slug, comentarios_en_rafaga, inicio_ráfaga, fin_ráfaga, minutos_span
FROM gold.v_trolls_rafagas
WHERE autor_handle = 'del_mendez77364'
ORDER BY dia;
```

### Perfiles unificados (opcional)

```bash
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/redes/ingest_network_profile.sql
```

```sql
SELECT platform, handle, display_name, profile_url, is_tracked
FROM silver.network_profile
WHERE is_tracked OR comments_count > 10
ORDER BY comments_count DESC LIMIT 20;
```

---

## Extending the dashboard

To add a new chart:

1. Add or extend a gold view in `ingest_redes_gold.sql` (or related SQL)
2. Add export entry in `SQL_EXPORTS` inside `generate_redes_dashboard.py`
3. Add Chart.js / vis.js section in `scripts/python/reports/templates/redes_dashboard.html`
4. Regenerate: `uv run python scripts/python/reports/generate_redes_dashboard.py`

Follow [`create-python-script`](../../../infra/create-python-script/SKILL.md) for script conventions.

---

## Limitations (always state in reports)

- Partial TW sample (top tweets by reply volume).
- FB volume high, author identification near zero.
- LLM + keyword heuristics — not ground truth.
- `co_rafaga` = temporal sync only.
- Outputs gitignored; redact handles in chat unless user needs them.

---

## Related skills

| Skill | Role |
|-------|------|
| [`redes-gold`](../../../ingest/gold/redes-gold/SKILL.md) | Build gold views |
| [`redes-legacy-csv`](../../../ingest/references/redes-legacy-csv.md) | Silver source schema |
| [`sentiment-analysis`](sentiment-analysis/SKILL.md) | Posición LLM framing |
| [`interactive-graph-reports`](../graph/interactive-graph-reports/SKILL.md) | vis.js patterns |
| [`statistical-report`](statistical-report/SKILL.md) | Generic EDA markdown |
