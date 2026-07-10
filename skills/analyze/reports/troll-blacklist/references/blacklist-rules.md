# Reglas de troll bloqueable (twikit-only)

**Fuente de verdad:** `scripts/sql/ingest_tk_troll_blacklist.sql`  
**Tabla:** `gold.tk_troll_blacklist`  
**Alcance:** solo datos descargados con twikit (`silver.tk_tw_*`, `gold.tk_hater_*`).  
**Uso:** lista auditable para bloqueo **manual** en X. **No** se bloquea automáticamente.

---

## Universo

Todos los autores con al menos 1 reply en `silver.tk_tw_reply` (por `author_id` / `username`).

---

## Señales de comportamiento (todos)

Derivadas de `silver.tk_tw_reply` + `silver.tk_tw_reply_classification`
(`criterio_label = 'derecha_o_troll'`):

| Señal | Definición |
|-------|------------|
| `replies_total` | Nº de replies del autor en el scrape |
| `hater_replies` | Nº de replies clasificados `derecha_o_troll` |
| `hater_ratio` | `hater_replies / replies_total` |
| `parent_tweets` | Nº de `parent_tweet_id` distintos |
| `target_accounts` | Nº de cuentas trackeadas distintas atacadas (`silver.tk_tw_tweet.username`) |
| `narrativas` | Nº de clusters distintos en `gold.tk_hater_narrativa_assignment` |
| `in_co_burst` | Participó en co-ráfaga: ≥2 autores con reply hater al mismo `parent_tweet_id` en ventana de 30 minutos |

---

## Señales de perfil enriquecido (subset)

Solo si el autor está en `gold.tk_hater_profile_risk` / grafo:

| Señal | Fuente |
|-------|--------|
| `risk_band` / `risk_score` | `gold.tk_hater_profile_risk` |
| flags de perfil | `flag_empty_bio`, `flag_new_account`, `flag_high_output_low_audience`, etc. |
| `is_bridge` | `gold.tk_hater_grafo_bridge_followers` con `haters_followed >= 2` (el autor es follower puente **o** es un hater enriquecido con audiencia compartida) |

---

## Score compuesto (defaults)

| Regla | Puntos | Condición |
|-------|--------|-----------|
| `hater_replies_ge5` | +2 | `hater_replies >= 5` |
| `hater_replies_ge3` | +1 | `hater_replies >= 3` (si no aplica ge5) |
| `hater_ratio_high` | +1 | `hater_ratio >= 0.6` AND `replies_total >= 3` |
| `multi_target` | +1 | `target_accounts >= 3` |
| `co_burst` | +1 | `in_co_burst` |
| `risk_high` | +3 | `risk_band = 'high'` |
| `risk_medium` | +1 | `risk_band = 'medium'` |
| `bridge` | +1 | puente multi-hater / `flag_shared_audience` |

`score` = suma de puntos. `reasons` = lista de reglas disparadas separadas por ` | ` (auditable).

---

## Tiers

| Tier | Criterio |
|------|----------|
| **`block`** | `score >= 4` **OR** `risk_band = 'high'` **OR** (`hater_replies >= 5` AND `hater_ratio >= 0.6`) |
| **`watch`** | no es `block` **AND** (`score >= 2` **OR** `hater_replies >= 3`) |
| *(fuera de lista)* | resto — no se exporta a CSV de bloqueo |

---

## Export

| Archivo | Contenido |
|---------|-----------|
| `blacklist.csv` | Todas las filas `block` + `watch` con score, reasons, métricas |
| `blacklist_block.csv` | Solo `tier = 'block'`: `username`, `user_id` |

---

## Límites

- Solo replies capturados en el scrape twikit (no el 100% de la UI de X).
- Clasificación LLM puede errar; revisar `reasons` antes de bloquear.
- Co-ráfaga ≠ prueba de coordinación organizada.
- Perfil enriquecido solo cubre un subset (p.ej. top haters scrapeados).
