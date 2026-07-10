# Social media monitoring system — technical guide

Maintainer documentation for the unified social monitoring stack: curated identity dimension, cross-platform gold views, HTML dashboard generator, and skills.

Journalist-facing guide (Spanish): [`guia-monitoreo-redes.md`](guia-monitoreo-redes.md).  
Skill: [`skills/analyze/reports/social-monitor/SKILL.md`](../skills/analyze/reports/social-monitor/SKILL.md).

---

## Architecture

```
config/identidades.seed.csv
config/identidad_cuentas.seed.csv
        │
        ▼  scripts/sql/ingest_identidades.sql
silver.identidad
silver.identidad_cuenta
silver.v_identidad_cuentas
        │
        ├─ silver.fb_* + gold.v_* / grafo_*_trolls (legacy FB)
        └─ silver.tk_tw_* + gold.tk_hater_* / tk_troll_blacklist (twikit)
        │
        ▼  scripts/sql/ingest_social_monitor_gold.sql
gold.v_monitor_*
        │
        ▼  scripts/python/generate_social_monitor_dashboard.py
           + templates/social_monitor_dashboard.html
reports/monitor/dashboard/   (gitignored)
```

**Design choice:** do not replace existing FB (`redes-analysis`) or twikit (`troll-blacklist`) pipelines. The monitor layer **joins** them via a curated persona key (`persona_id`).

---

## Identity model

| Object | Role |
|--------|------|
| `silver.identidad` | Canonical person / org / media row + OSINT fields |
| `silver.identidad_cuenta` | Bridge: `persona_id` → `plataforma` + `platform_user_id` / `handle` |
| `silver.v_identidad_cuentas` | Convenience join view |

### Seed files (versioned, public figures only)

| File | Columns (key) |
|------|----------------|
| `config/identidades.seed.csv` | `persona_id`, `nombre_canonico`, `alias` (`\|`-separated), `tipo`, `rol`, `partido`, `es_objetivo`, `sitio_web`, `wikidata_id`, `genero`, `provincia`, `fuentes_osint`, `notas` |
| `config/identidad_cuentas.seed.csv` | `persona_id`, `plataforma`, `platform_user_id`, `handle`, `url`, `es_oficial`, `fuente` |

Ingest resolves empty Twitter/Facebook IDs against `silver.tk_tw_profile` and `silver.fb_fanpage` when handles match.

### OSINT checklist (fields to keep updating)

| Field | Source ideas |
|-------|----------------|
| Cross-platform handles | Official bios, link-in-bio, Wikipedia |
| Stable `platform_user_id` | FB page id, Twitter snowflake id, IG id from fanpage CSV |
| Verification / created_at | `tk_tw_profile_enriched`, platform APIs |
| Bio / location | Enriched profile scrapes |
| `sitio_web`, `wikidata_id` | Manual seed |
| `partido`, `rol`, `provincia` | Manual seed / public records |

`silver.network_profile` remains the FB-first auto graph; the curated identity layer is the **source of truth** for monitoring targets.

---

## Gold views (`gold.v_monitor_*`)

| View | Purpose |
|------|---------|
| `v_monitor_cuenta_map` | Map persona ↔ `cuenta_slug` / handle / fanpage |
| `v_monitor_perfil` | Per-account stats + OSINT |
| `v_monitor_reacciones` | Post-level reactions (FB breakdown + TW engagement) |
| `v_monitor_engagement` | Daily engagement KPIs |
| `v_monitor_audiencia` | Classified commenters/repliers + bot heuristic flags |
| `v_monitor_audiencia_resumen` | Aggregates by class |
| `v_monitor_haters_top10` | Union of FB `v_trolls_top10` + TW `tk_troll_blacklist` |
| `v_monitor_narrativa` | FB narrativa + TW hater clusters |
| `v_monitor_temporal` | Comparable hostility / position time series |
| `v_monitor_temporal_engagement` | Comparable engagement series |
| `v_monitor_grafo_comportamiento_*` | FB troll attack / burst graph |
| `v_monitor_grafo_narrativa_*` | Narrative co-occurrence graph |
| `v_monitor_grafo_coordinacion_*` | TW co-followers / bridges + FB `co_rafaga` (legacy views) |
| `v_monitor_kpis` | Global KPI row |

Dashboard **Relaciones TW** mode exports directly from `gold.tk_hater_profile_risk`, `tk_hater_grafo_co_*`, `tk_hater_grafo_bridge_followers`, and a filtered viz (haters + bridges ≥3) — same analysis as `reports/twikit-myriam/hater-profiles-graph`.

SQL: [`scripts/sql/ingest_social_monitor_gold.sql`](../scripts/sql/ingest_social_monitor_gold.sql)

### Bot heuristic (Twitter)

From `gold.tk_hater_profile_risk` flags:

- `flag_new_account`
- `flag_follow_ratio_high`
- `flag_high_output_low_audience`
- `flag_empty_bio`

These are **signals**, not labels of automation.

---

## Dashboard generator

| Piece | Path |
|-------|------|
| Generator | `scripts/python/generate_social_monitor_dashboard.py` |
| Template | `scripts/python/templates/social_monitor_dashboard.html` |
| Output | `reports/monitor/dashboard/` via `db.get_report_bundle("monitor", "dashboard")` |

Stack: **Chart.js 4.4.1** + **vis-network** (same as `redes_dashboard`). Data is embedded as `const DATA = …` so the HTML opens offline.

### Regenerate

```bash
uv run python scripts/python/db.py mcp-stop
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_identidades.sql
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_social_monitor_gold.sql
uv run python scripts/python/generate_social_monitor_dashboard.py
```

Writes require MCP stopped (single DuckDB writer). Analysis reads should use MCP `query` when available.

---

## How to extend

### Add a persona

1. Append rows to both seed CSVs.
2. Re-run `ingest_identidades.sql` + `ingest_social_monitor_gold.sql`.
3. Regenerate the dashboard.

### Add a platform (Instagram / TikTok)

1. Add `identidad_cuenta` rows (`plataforma=instagram|tiktok`).
2. When `silver.sv_ig_*` / `sv_tt_*` have data, extend `v_monitor_reacciones`, `v_monitor_engagement`, and `v_monitor_audiencia` with `UNION ALL` branches (mirror FB/TW patterns).
3. Add platform filter option in the HTML template if needed.

### Add a chart

1. Prefer a new/extended `gold.v_monitor_*` view.
2. Add `(filename, sql)` to `SQL_EXPORTS` in the generator.
3. Map it in `CSV_KEY_MAP` and wire Chart.js / table in the template.

---

## Skills & routing

| File | Update when changing this system |
|------|----------------------------------|
| `skills/analyze/reports/social-monitor/SKILL.md` | Workflow source of truth |
| `skills/analyze/README.md` | Analyze catalog |
| `skills/README.md` | Root catalog |
| `skills/datasyn-router/SKILL.md` | Intent routing |
| `docs/skills-layout.md` | Tree / examples |

Upstream: `redes-gold`, twikit hater/blacklist SQL, `scrape-twikit-twitter`, legacy FB ingest.

---

## Privacy & git

Never commit:

- `reports/**` (including `monitor/dashboard/`)
- `data/landing/**`, `data/duckdb/*.duckdb`
- `.env`, cookies, MCP local config

Seeds under `config/identidades*.csv` contain **public figure** metadata only — review before commit if you add non-public actors.

---

## Limitations

- v1 populated from Facebook legacy + Twitter twikit only.
- SociaVault IG/TikTok/FB modern: schema exists, no live rows in typical local DB.
- Graph sparsity depends on upstream gold (e.g. FB troll graph may be thin if ráfagas are rare).
- Classification and bot/coordination signals are probabilistic.

---

## Related

| Doc / skill | Role |
|-------------|------|
| [`guia-monitoreo-redes.md`](guia-monitoreo-redes.md) | Journalist usage |
| [`skills-layout.md`](skills-layout.md) | Skills conventions |
| [`CONTEXT.md`](../CONTEXT.md) | Shared vocabulary |
| [`redes-analysis`](../skills/analyze/reports/redes-analysis/SKILL.md) | FB-only dashboard |
| [`troll-blacklist`](../skills/analyze/reports/troll-blacklist/SKILL.md) | Twikit block list |
