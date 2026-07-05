---
name: redes-analysis
description: >-
  Analyze legacy Facebook/Twitter redes data and generate HTML/PDF reports from
  gold views — sentiment, narrative, trolls, ráfagas, interactive graphs.
  Use when the user asks for redes reports, troll analysis, PTS account dashboards,
  or interpretation of gold redes charts and tables.
---

# Redes analysis — tablas, consultas y reportes

**Project output:** `reports/redes/<report-slug>/` — one folder per report (see layout below)  
**Path helper:** `db.get_report_bundle("redes", "<slug>")`  
**Gold ingest:** skill [`redes-gold`](../../../ingest/gold/redes-gold/SKILL.md)  
**Privacy:** [`data-privacy`](../../../engineering/data-privacy/SKILL.md) — never commit `reports/**`

---

## Report layout (`reports/redes/`)

Each report lives in its **own folder** with main file + data:

```
reports/redes/
├── README.md                # índice del proyecto
├── gold-report/
│   ├── report.html
│   ├── data.json
│   └── README.md
├── trolls-grafo/
│   ├── report.html
│   ├── grafo.json
│   └── README.md
├── analisis-completo/
│   ├── report.pdf
│   └── README.md
├── myriambregman-tw/        # legacy TW @myriambregman
│   ├── report.html
│   ├── data.json
│   ├── sentiment.md
│   ├── trolls-grafo-notes.md
│   ├── assets/haters.csv
│   └── README.md
└── _exports/
    └── export_YYYYMMDD.zip
```

Cross-links between bundles use relative paths: `../trolls-grafo/report.html`, `../analisis-completo/report.pdf`.

General convention: skill [`statistical-report`](statistical-report/SKILL.md).

---

## When to use

| User asks | Action |
|-----------|--------|
| Reporte HTML redes / dashboard PTS | Run gold + `generate_redes_gold_report.py` |
| Grafo interactivo trolls | Run gold + `generate_trolls_grafo_report.py` |
| PDF consolidado | Run gold + HTML reports + `generate_redes_pdf_report.py` |
| Top trolls, ráfagas, pico de hostilidad | MCP queries on `gold.v_trolls_*` |
| Sentimiento por cuenta | MCP on `gold.v_sentimiento_*` |

---

## End-to-end pipeline

```
silver.fb_* / tw_* + classification
        ↓  ingest_redes_gold.sql
gold.v_* / gold.grafo_*
        ↓  MCP queries (exploración)
        ↓  Python report scripts (HTML/PDF)
reports/redes/<report-slug>/
```

### 1. Refresh gold (writes — stop MCP)

```bash
uv run python scripts/python/db.py mcp-stop
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_redes_gold.sql
```

### 2. Explore (reads — MCP preferred)

Use MCP `query` for ad-hoc analysis. Example patterns in [`redes-gold`](../../../ingest/gold/redes-gold/SKILL.md).

### 3. Generate reports

```bash
uv run python scripts/python/generate_redes_gold_report.py
uv run python scripts/python/generate_trolls_grafo_report.py
uv run --with matplotlib python scripts/python/generate_redes_pdf_report.py
```

| Script | Bundle folder | Files |
|--------|---------------|-------|
| `generate_redes_gold_report.py` | `gold-report/` | `report.html`, `data.json`, `README.md` |
| `generate_trolls_grafo_report.py` | `trolls-grafo/` | `report.html`, `grafo.json`, `README.md` |
| `generate_redes_pdf_report.py` | `analisis-completo/` | `report.pdf`, `README.md` |

Open HTML locally:

```bash
open reports/redes/gold-report/report.html
open reports/redes/trolls-grafo/report.html
```

### 4. Export zip (compartir offline)

```bash
uv run python scripts/python/export_redes_reports_zip.py
# → reports/redes/_exports/export_{date}.zip
```

El zip empaqueta cada carpeta bajo `reports/redes/<slug>/`. Filtrar: `--bundle gold-report --bundle trolls-grafo`

---

## Report sections — qué analiza cada gráfico

Each HTML report embeds collapsible **“Cómo interpretar · origen de datos”** blocks. Summary:

### Dashboard Chart.js (`gold-report/report.html`)

| # | Sección | Vista gold | Lectura |
|---|---------|------------|---------|
| KPI | Totales por cuenta | `v_sentimiento_resumen_cuenta` | Volumen clasificado; % apoyo vs troll |
| 1 | Sentimiento por cuenta | `v_sentimiento_por_cuenta` | Barras 100% — mix posición LLM |
| 2 | Evolución temporal | `v_sentimiento_temporal` | Picos rojos = días hostiles |
| 3 | Narrativas | `v_narrativa_distribucion`, `v_narrativa_temporal` | Mix temático + serie semanal |
| 4 | Top 10 trolls | `v_trolls_top10` | Ranking TW (FB casi anónimo) |
| 5 | Trolls en el tiempo | `v_trolls_temporal` | Volumen vs autores distintos |
| 6 | Multi-objetivo + ráfagas | `v_trolls_grupos_multobjetivo`, `v_trolls_rafagas` | Tabla: N comentarios, Min minutos |
| 6b | Autores en ráfagas/día | `v_trolls_rafagas_dia` | Cohortes sincronizadas |
| 7 | Grafo narrativas | `grafo_edges_agg_narrativa` | Co-ocurrencia temática |

**Metodología** (bloque superior): bronze → silver → LLM → gold → HTML.

### Grafo interactivo (`trolls-grafo/report.html`)

| Nodo | Color | Significado |
|------|-------|-------------|
| Autor | Rojo | Top ~35 autores por peso `ataca` |
| Cuenta | Verde | Figura PTS objetivo |
| Narrativa | Violeta | Tema LLM/heurística |
| Cohorte | Azul | Día+cuenta con ≥2 ráfagas |

| Arista | Significado |
|--------|-------------|
| `ataca` | Autor → cuenta (peso = comentarios en ráfagas) |
| `co_rafaga` | Autor ↔ autor mismo día/cuenta (sincronía, no prueba de coordinación) |
| `usa_narrativa` | Autor → tema |
| `en_cohorte` | Autor → nodo cohorte-día |

Panel lateral: metodología, leyenda, filtros por tipo de arista, enlaces al dashboard y PDF.

### PDF (`analisis-completo/report.pdf`)

Estático (~16 págs): KPIs, gráficos matplotlib, tablas top trolls/ráfagas, enlaces a HTML interactivos. Requiere `matplotlib` (`uv run --with matplotlib`).

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
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_network_profile.sql
```

```sql
SELECT platform, handle, display_name, profile_url, is_tracked
FROM silver.network_profile
WHERE is_tracked OR comments_count > 10
ORDER BY comments_count DESC LIMIT 20;
```

---

## Extending reports

To add a new chart to the dashboard:

1. Add or extend a gold view in `ingest_redes_gold.sql`
2. Export in `load_data()` inside `generate_redes_gold_report.py`
3. Add Chart.js section + `<details class="guide">` with Análisis / Procesamiento / Lectura / Límite
4. Regenerate all bundles; cross-links use relative paths between sibling folders

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
