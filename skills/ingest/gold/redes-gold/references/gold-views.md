# Gold views — redes PTS (catalog)

Source: `scripts/sql/ingest_redes_gold.sql`

## Base

### `gold.v_cuentas_trackeadas`
Cuentas objetivo PTS con slug, nombre, plataforma, handles FB/TW.

### `gold.v_comentarios_clasificados`
Unión FB (`fb_comment` + classification) y TW (`tw_comments_classification` + replies).  
Columnas clave: `plataforma`, `cuenta_slug`, `posicion`, `resumen`, `fecha`, `autor_handle`, `contenido_padre_id`.

### `gold.v_comentario_narrativa`
Añade `narrativa`, `sentimiento`, `es_troll` (heurística sobre `resumen`).

## Sentimiento

| View | Grain | Métricas |
|------|-------|----------|
| `v_sentimiento_por_cuenta` | cuenta × plataforma × posicion | `comentarios`, `pct_dentro_cuenta` |
| `v_sentimiento_resumen_cuenta` | cuenta | totales apoyo/troll/neutral, pct_apoyo, pct_troll |
| `v_sentimiento_temporal` | cuenta × día × posicion | serie diaria |

## Narrativa

| View | Grain | Métricas |
|------|-------|----------|
| `v_narrativa_distribucion` | cuenta × narrativa | conteos y % |
| `v_narrativa_temporal` | cuenta × semana × narrativa | serie semanal |
| `v_narrativa_top_resumenes` | cuenta × resumen | top textos LLM |

## Trolls

| View | Grain | Filtro / notas |
|------|-------|----------------|
| `v_trolls_actividad` | comentario | `es_troll` + autor identificado |
| `v_trolls_top10` | autor × cuenta × plataforma | top 10 por volumen |
| `v_trolls_temporal` | día × cuenta | comentarios + autores distintos |
| `v_trolls_grupos_multobjetivo` | autor | ≥2 cuentas atacadas |

## Ráfagas

| View | Grain | Definición |
|------|-------|------------|
| `v_trolls_rafagas` | autor × día × cuenta | ≥3 trolls; `inicio_ráfaga`, `fin_ráfaga`, `minutos_span` |
| `v_trolls_rafagas_dia` | día × cuenta | autores distintos en ráfaga, eventos, máx por autor |
| `v_trolls_rafagas_resumen` | global | KPIs agregados |
| `v_trolls_rafagas_por_autor` | autor | totales de ráfagas |
| `v_trolls_cohortes_dia` | día × cuenta | ≥2 autores con ráfaga |

## Grafo trolls

| View | Contenido |
|------|-----------|
| `grafo_vertices_trolls` | nodos: `autor`, `cuenta_objetivo`, `narrativa`, `cohorte_dia` |
| `grafo_edges_trolls` | aristas: `ataca`, `co_rafaga`, `usa_narrativa`, `en_cohorte` |
| `grafo_edges_agg_trolls` | aristas agregadas con `peso_total`, `eventos` |

## Grafo narrativa

| View | Contenido |
|------|-----------|
| `grafo_vertices_narrativa` | nodos narrativa + cuenta |
| `grafo_edges_narrativa` | `narrativa_coocurrencia`, `narrativa_cuenta` |
| `grafo_edges_agg_narrativa` | pesos agregados |

## Edge types (trolls)

| Tipo | Dirección | Significado |
|------|-----------|-------------|
| `ataca` | autor → cuenta | Comentarios troll en ráfagas hacia la figura |
| `co_rafaga` | autor ↔ autor | Misma cuenta, mismo día, ambos en ráfaga |
| `usa_narrativa` | autor → narrativa | Tema inferido del resumen LLM |
| `en_cohorte` | autor → cohorte_dia | Día con ≥2 autores en ráfaga |
