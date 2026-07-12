---
name: social-monitor
description: >-
  Unified social media monitoring report: curated persona identity across
  platforms (FB + Twitter/X, extensible to IG/TikTok), reactions, engagement,
  audience (haters/supporters/bots), top-10 haters and apoyo/defensores,
  narratives (hostile + support clusters), comparative timelines, and graphs
  (behavior, coordination, narrative clusters) with Haters/Apoyo toggle.
  Use when the user asks for monitoreo de redes, dashboard unificado,
  comparar cuentas/personas, o estudiar un perfil multiplataforma.
---

# Social monitor — reporte unificado de redes

**Project output:** `reports/monitor/dashboard/`  
**Path helper:** `db.get_report_bundle("monitor", "dashboard")`  
**Privacy:** [`data-privacy`](../../../engineering/data-privacy/SKILL.md) — never commit `reports/**`

Cross-platform monitoring keyed by **persona** (not by isolated account).

---

## When to use

| User asks | Action |
|-----------|--------|
| Monitor / dashboard unificado de redes | Refresh identity + gold + generate dashboard |
| Estudiar a Myriam / Nicolás / PTS en FB+TW | Same — use persona selector in HTML |
| Comparar cuentas en el tiempo | Sección **Comparativa** del dashboard |
| Haters top 10 / apoyo / narrativas / grafos | Secciones Haters, Apoyo, Narrativas, Grafos (toggle polaridad) |
| Actualizar identidades / OSINT | Edit `config/identidades*.csv` → re-ingest |
| Hechos × Redes / La Nación vs TW | Stage LN from Quack + contexto gold (below) |

**Related (platform-specific):**
- Legacy FB only → [`redes-analysis`](redes-analysis/SKILL.md)
- Twikit blacklist → [`troll-blacklist`](troll-blacklist/SKILL.md)

---

## End-to-end pipeline

```
config/identidades.seed.csv + identidad_cuentas.seed.csv
        ↓  ingest_identidades.sql
silver.identidad + silver.identidad_cuenta
        ↓  (+ existing FB gold + twikit gold + apoyo graph/narrativa)
        ↓  ingest_social_monitor_gold.sql
gold.v_monitor_*
        ↓  generate_social_monitor_dashboard.py
reports/monitor/dashboard/report.html
```

### 1. Refresh identity + gold (writes — stop MCP)

```bash
uv run python scripts/python/db.py mcp-stop
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/monitor/ingest_identidades.sql
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/monitor/ingest_social_monitor_gold.sql
```

Prereqs (if stale):
- FB gold: `ingest_redes_gold.sql` (skill [`redes-gold`](../../../ingest/gold/redes-gold/SKILL.md))
- Twikit gold: hater narrativa / profile graph / troll blacklist SQL
- **Apoyo (supporters):** enrich + graph + narrativa (see below)

### Apoyo / defensores pipeline (mirror of haters)

```bash
# After classify_tk_tw_replies.py has labeled apoyo_izquierda replies:
uv run python scripts/python/db.py mcp-stop
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/twikit/ingest_twikit_twitter_silver.sql  # is_supporter
uv run python scripts/python/scrape/twikit/enrich_twikit_profiles.py --role apoyo --top-supporters 30 \
  --max-follows 2000 --ingest
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/twikit/ingest_tk_apoyo_profile_graph.sql
uv run python scripts/python/classify/classify_tk_tw_replies.py --cluster-only --cluster-apoyo
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/monitor/ingest_social_monitor_gold.sql
uv run python scripts/python/reports/generate_social_monitor_dashboard.py
```

Landing: `data/landing/redes/twikit/profiles/apoyo/{slug}_{date}/` (separate from hater profiles).
Gold: `gold.tk_apoyo_grafo_*`, `gold.tk_apoyo_profile_risk`, `gold.tk_apoyo_narrativa_*`, `gold.v_monitor_apoyo_top10`.

### Hechos × Redes (La Nación × Twitter)

Persona scope: `myriambregman`. Docs: [`docs/monitoreo-redes-tecnico.md`](../../../../docs/monitoreo-redes-tecnico.md).

```bash
uv run python scripts/python/db.py mcp-stop
uv run python scripts/python/db.py run-sql --ingest --attach-quack \
  --file scripts/sql/news/ingest_lanacion_silver.sql
uv run python scripts/python/db.py run-sql --ingest \
  --file scripts/sql/news/ingest_contexto_ln_tw.sql
uv run python scripts/python/classify/classify_lanacion_to_hater_clusters.py
uv run python scripts/python/db.py run-sql --ingest \
  --file scripts/sql/news/ingest_contexto_ln_hater_afinidade.sql
```

### 2. Generate dashboard

```bash
uv run python scripts/python/reports/generate_social_monitor_dashboard.py
open reports/monitor/dashboard/report.html
```

| Script | Bundle | Files |
|--------|--------|-------|
| `generate_social_monitor_dashboard.py` | `monitor/dashboard/` | `report.html`, `data/*.csv`, `data.json`, `README.md` |
| Template | `scripts/python/reports/templates/social_monitor_dashboard.html` | Chart.js 4.4.1 + vis-network |

### 3. Explore (reads — MCP preferred)

```sql
SELECT * FROM gold.v_monitor_perfil WHERE persona_id = 'myriambregman';
SELECT * FROM gold.v_monitor_haters_top10 WHERE persona_id = 'myriambregman';
SELECT * FROM gold.v_monitor_apoyo_top10 WHERE persona_id = 'myriambregman';
SELECT * FROM gold.v_monitor_audiencia_resumen WHERE persona_id = 'myriambregman';
SELECT * FROM gold.v_monitor_temporal ORDER BY dia DESC LIMIT 20;
```

---

## Dashboard sections

| Sección | Fuente principal | Lectura |
|---------|------------------|---------|
| **Perfil** | `gold.v_monitor_perfil` | Cuentas por plataforma + OSINT |
| **Reacciones** | `gold.v_monitor_reacciones` | Likes/loves/… (FB); likes/RT/quotes (TW) |
| **Engagement** | `gold.v_monitor_engagement` | Serie temporal eng/post |
| **Audiencia** | `gold.v_monitor_audiencia*` | hater / apoyo / neutral / bot heurístico |
| **Haters** | `gold.v_monitor_haters_top10` | Top 75 TW (+ top 10 FB) |
| **Apoyo** | `gold.v_monitor_apoyo_top10` | Top 50 defensores TW |
| **Narrativas** | `gold.v_monitor_narrativa` | Clusters hostiles + apoyo (toggle polaridad) |
| **Grafos** | `gold.tk_hater_*` + `gold.tk_apoyo_*` | Toggle **Haters/Apoyo** en Relaciones TW |
| **Comparativa** | `gold.v_monitor_temporal*` | Multi-persona en el tiempo |
| **Hechos × Redes** | `gold.v_contexto_ln_*` | LN pol/soc vs TW (picos, titulares, afinidad cluster) |

---

## Identity / OSINT seed

| File | Role |
|------|------|
| [`config/identidades.seed.csv`](../../../../config/identidades.seed.csv) | Personas (nombre, rol, partido, Wikidata, sitio…) |
| [`config/identidad_cuentas.seed.csv`](../../../../config/identidad_cuentas.seed.csv) | Bridge persona → plataforma / handle / user_id |

**OSINT checklist** (fill in seed as available): handles cruzados, `platform_user_id` estable, verificación, fecha de creación, bio/ubicación, sitio oficial, Wikidata, partido/rol.

**Promover defensores recurrentes:** cuentas de `v_monitor_apoyo_top10` que merezcan identidad propia se agregan **manualmente** a los seed CSVs (no auto-link). Re-correr `ingest_identidades.sql`.

---

## Gold views (`gold.v_monitor_*`)

| View | Purpose |
|------|---------|
| `v_monitor_cuenta_map` | persona ↔ cuenta_slug / handle |
| `v_monitor_perfil` | stats + OSINT por cuenta |
| `v_monitor_reacciones` | post-level reactions |
| `v_monitor_engagement` | daily engagement |
| `v_monitor_audiencia` | classified commenters/repliers |
| `v_monitor_audiencia_resumen` | aggregates |
| `v_monitor_haters_top10` | top haters per persona |
| `v_monitor_apoyo_top10` | top supporters / defensores per persona |
| `v_monitor_narrativa` | narrative mix (hater + apoyo TW clusters) |
| `v_monitor_temporal` | comparable time series |
| `v_monitor_temporal_engagement` | engagement time series |
| `v_monitor_grafo_*` | behavior / narrative / coordination graphs |
| `v_monitor_kpis` | global KPIs |

SQL: [`scripts/sql/monitor/ingest_social_monitor_gold.sql`](../../../../scripts/sql/monitor/ingest_social_monitor_gold.sql)

---

## Extending

1. **Nueva persona:** add rows to both seed CSVs → re-run `ingest_identidades.sql` + gold + generator.
2. **Nueva plataforma (IG/TikTok):** add `identidad_cuenta` rows; extend gold views to `silver.sv_ig_*` / `sv_tt_*` when data exists.
3. **Nuevo gráfico:** add export in `generate_social_monitor_dashboard.py` + section in the HTML template.

---

## Limitations (always state)

- v1 data: Facebook legacy + Twitter twikit only (IG/TikTok schema-ready, empty).
- Bot detection is heuristic — not ground truth.
- `co_rafaga` / `co_followers` = sync / shared audience, not proof of coordination.
- LLM + keyword classification; TW sample is partial.

---

## Related skills

| Skill | Role |
|-------|------|
| [`redes-analysis`](redes-analysis/SKILL.md) | FB-only PTS dashboard |
| [`troll-blacklist`](troll-blacklist/SKILL.md) | Twikit block/watch export |
| [`redes-gold`](../../../ingest/gold/redes-gold/SKILL.md) | FB gold views |
| [`interactive-graph-reports`](../graph/interactive-graph-reports/SKILL.md) | vis.js patterns |
| [`data-privacy`](../../../engineering/data-privacy/SKILL.md) | Never commit reports/data |
