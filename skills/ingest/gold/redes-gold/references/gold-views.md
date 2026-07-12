# Gold views — redes PTS (catalog)

Source: `scripts/sql/redes/ingest_redes_gold.sql`

## Base

### `gold.v_cuentas_trackeadas`
Cuentas objetivo PTS con slug, nombre, plataforma, handles FB/TW.

### `gold.v_comentarios_clasificados`
Comentarios FB clasificados (`fb_comment` + classification). **Facebook only** — Twitter vive en twikit (`tk_tw_*`).  
Columnas clave: `plataforma`, `cuenta_slug`, `posicion`, `resumen`, `fecha`, `autor_key`, `contenido_padre_id`.

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

## Entidades (persona detrás de la cuenta)

Source: `scripts/sql/redes/ingest_gold_entidades.sql` (prereq: `silver.network_profile`).

### `gold.v_entidades`
Una fila por `canonical_key` de `silver.network_profile`.  
Infiere `nombre_inferido` (prioridad: cuenta trackeada → TW display name → fanpage `.PTS` → page name → handle).  
Columnas clave: `nombre_normalizado`, `es_organizacion`, `tipo_cuenta`, `confianza_nombre`, `multicuenta_mismo_perfil`.

### `gold.v_entidades_vinculos`
Pares de perfiles con evidencia de misma persona u organización.  
Tipos: `multired_en_perfil`, `fanpage_pts_username`, `handle_alphanum`, `mismo_instagram_id`, `cuenta_trackeada_slug`, `nombre_normalizado_igual` (baja confianza).

### `gold.v_entidades_grupos`
Componentes conectados por vínculos alta/media.  
`persona_grupo_id`, `canonical_keys[]`, `n_perfiles`, `confianza_grupo`, `tipo_grupo`.

### `gold.v_entidades_resumen`
`v_entidades` + grupo + evaluación multicuenta (`evaluacion_multicuenta`, `posible_multicuenta`).

## Edge types (trolls)

| Tipo | Dirección | Significado |
|------|-----------|-------------|
| `ataca` | autor → cuenta | Comentarios troll en ráfagas hacia la figura |
| `co_rafaga` | autor ↔ autor | Misma cuenta, mismo día, ambos en ráfaga |
| `usa_narrativa` | autor → narrativa | Tema inferido del resumen LLM |
| `en_cohorte` | autor → cohorte_dia | Día con ≥2 autores en ráfaga |
