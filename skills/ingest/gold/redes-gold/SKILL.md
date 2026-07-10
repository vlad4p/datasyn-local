---
name: redes-gold
description: >-
  Build gold analytics views for legacy Facebook redes data — sentiment,
  narrative, trolls, ráfagas, and graph tables. Runs scripts/sql/ingest_redes_gold.sql.
  Use when the user asks for gold redes views, troll KPIs, narrativa, or report-ready
  aggregates from silver.fb_* classification tables. (Twitter is twikit-only.)
---

# Redes gold — vistas analíticas (Facebook only)

**Zone:** `gold.*` views from legacy `silver.fb_*` + LLM classification.  
**Script:** [`scripts/sql/ingest_redes_gold.sql`](../../../../scripts/sql/ingest_redes_gold.sql)  
**Reference:** [`references/gold-views.md`](references/gold-views.md)  
**Twitter:** use twikit (`tk_tw_*` / `gold.tk_hater_*` / skill `troll-blacklist`) — not this pipeline.

---

## Prerequisites

1. Silver Facebook ingested — see [`references/redes-legacy-csv.md`](../../references/redes-legacy-csv.md)
2. Classification table populated: `silver.fb_comment_classification`
3. Optional: `silver.network_profile` — [`scripts/sql/ingest_network_profile.sql`](../../../../scripts/sql/ingest_network_profile.sql) (FB-only)
4. Optional: entidades gold — [`scripts/sql/ingest_gold_entidades.sql`](../../../../scripts/sql/ingest_gold_entidades.sql) (después de `network_profile`)

---

## Workflow

1. **Verify silver** (MCP `query` or `db.py info`)
   ```sql
   SELECT COUNT(*) FROM silver.fb_comment_classification;
   SELECT fanpage_descripcion, COUNT(*) AS n
   FROM silver.fb_comment_classification
   GROUP BY 1 ORDER BY 2 DESC LIMIT 5;
   ```

2. **Stop MCP** — gold script writes to DuckDB
   ```bash
   uv run python scripts/python/db.py mcp-stop
   uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_redes_gold.sql
   uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_gold_entidades.sql
   ```

3. **Validate gold**
   ```sql
   SELECT * FROM gold.v_sentimiento_resumen_cuenta ORDER BY comentarios_clasificados DESC;
   SELECT COUNT(*) FROM gold.v_trolls_actividad;
   SELECT edge_type, COUNT(*) FROM gold.grafo_edges_agg_trolls GROUP BY 1;
   ```

4. **Reports** → skill [`redes-analysis`](../../../analyze/reports/redes-analysis/SKILL.md)

---

## Cuentas trackeadas (`gold.v_cuentas_trackeadas`)

| slug | Plataforma | Handle |
|------|------------|--------|
| `myriambregman` | FB + TW | myriambregman |
| `nicolasdelcano` | FB + TW | nicolasdelcano |
| `christiancastillo` | FB | (sin clasificados actuales) |
| `ptsarg` | TW | PTSarg |

---

## View groups (18 views)

| Grupo | Vistas | Pregunta analítica |
|-------|--------|-------------------|
| **Base** | `v_cuentas_trackeadas`, `v_comentarios_clasificados`, `v_comentario_narrativa` | Unificación FB+TW, posición LLM, narrativa heurística |
| **Sentimiento** | `v_sentimiento_por_cuenta`, `v_sentimiento_resumen_cuenta`, `v_sentimiento_temporal` | Mix apoyo/troll por cuenta y día |
| **Narrativa** | `v_narrativa_distribucion`, `v_narrativa_temporal`, `v_narrativa_top_resumenes` | Temas dominantes y evolución semanal |
| **Trolls** | `v_trolls_actividad`, `v_trolls_top10`, `v_trolls_temporal`, `v_trolls_grupos_multobjetivo` | Ranking, serie temporal, multi-objetivo |
| **Ráfagas** | `v_trolls_rafagas`, `v_trolls_rafagas_dia`, `v_trolls_rafagas_resumen`, `v_trolls_rafagas_por_autor`, `v_trolls_cohortes_dia` | Burst ≥3 trolls/autor/día/cuenta; cohortes |
| **Grafo** | `grafo_vertices/edges/edges_agg_trolls`, `grafo_vertices/edges/edges_agg_narrativa` | Red trolls + co-ocurrencia narrativa |

Full column definitions: [`references/gold-views.md`](references/gold-views.md).

---

## Key definitions

### Posición LLM (`posicion`)

| Valor | Origen |
|-------|--------|
| `apoyo_izquierda` | Código `1` |
| `derecha_o_troll` | Código `2` |
| `neutral` | Código `3` |
| `ambiguo` | Códigos `1,2` |
| `inclasificable` | `INCLASIFICABLE` |

### Narrativa (`narrativa`)

Heurística SQL sobre `resumen` (texto LLM) + fallback a `posicion`. No es topic modeling.

### Ráfaga

≥ **3** comentarios `derecha_o_troll` del **mismo autor** el **mismo día** contra la **misma cuenta**.  
`co_rafaga` (grafo): dos autores con ráfaga el mismo día contra la misma cuenta — **sincronía temporal**, no coordinación probada.

### Trolls con autor identificado

`gold.v_trolls_actividad` exige handle TW (`reply_author_username`) o FB (`user_name` / `user_id`). FB identifica ~0,04% de autores troll.

---

## Example queries (MCP after ingest)

```sql
-- Top 10 trolls TW hacia Myriam
SELECT * FROM gold.v_trolls_top10
WHERE cuenta_slug = 'myriambregman' AND plataforma = 'twitter'
ORDER BY comentarios_troll DESC LIMIT 10;

-- Día con más autores en ráfaga
SELECT * FROM gold.v_trolls_rafagas_dia
ORDER BY autores_distintos DESC, comentarios_en_rafagas DESC LIMIT 10;

-- Multi-objetivo
SELECT * FROM gold.v_trolls_grupos_multobjetivo ORDER BY cuentas_atacadas DESC LIMIT 10;
```

---

## Caveats

- TW classification = muestra (top-10 tweets por volumen de replies por cuenta).
- FB masivo pero casi anónimo en autores.
- Christian Castillo puede tener 0 clasificados.
- No mezclar con pipeline SociaVault (`sv_*`) sin join explícito.

---

## Related

| Skill | When |
|-------|------|
| [`ingest-data-gold`](../ingest-data-gold/SKILL.md) | Patrón gold genérico |
| [`redes-analysis`](../../../analyze/reports/redes-analysis/SKILL.md) | HTML/PDF + interpretación |
| [`sentiment-analysis`](../../../analyze/reports/sentiment-analysis/SKILL.md) | Marco posición/narrativa |
| [`graph-ingest`](../../../analyze/graph/graph-ingest/SKILL.md) | Grafos genéricos + redes trolls |
