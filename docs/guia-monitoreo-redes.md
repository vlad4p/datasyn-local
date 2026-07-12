# Guía — Monitor unificado de redes sociales

Cómo estudiar a una **persona** (Myriam Bregman, Nicolás del Caño, PTS…) a través de sus cuentas en Facebook y Twitter/X: reacciones, engagement, audiencia (haters / apoyo / bots), narrativas, grafos y comparativas.

**Cómo usar esta guía:** copiá cada **Prompt** y pegalo en el chat del asistente. Él sigue skills y `AGENTS.md`. Ajustá personas y filtros a tu caso.

> Privacidad: skill [`data-privacy`](../skills/engineering/data-privacy/SKILL.md). No commitees `reports/`, DuckDB ni landing.

Skill principal: [`social-monitor`](../skills/analyze/reports/social-monitor/SKILL.md).  
Doc técnica: [`monitoreo-redes-tecnico.md`](monitoreo-redes-tecnico.md).

---

## 1. Abrir el dashboard

Salida: `reports/monitor/dashboard/report.html` (autocontenido, offline).

<details>
<summary><strong>Prompt — regenerar y abrir el monitor</strong></summary>

```text
Regenerá el dashboard unificado de monitoreo de redes (skill social-monitor):
1) detené MCP si hace falta
2) corré ingest_identidades.sql e ingest_social_monitor_gold.sql
3) generá el HTML con generate_social_monitor_dashboard.py
4) abrí reports/monitor/dashboard/report.html
Contame qué personas y plataformas aparecen en el selector.
```

</details>

### Qué vas a ver

| Sección | Para qué sirve |
|---------|----------------|
| **Perfil** | Cuentas de la persona por plataforma + datos OSINT (sitio, Wikidata, rol) |
| **Reacciones** | Likes/loves/angrys… (FB) y likes/RT/quotes/views (TW) |
| **Engagement** | Evolución del engagement por post |
| **Audiencia** | Mix haters / apoyo / neutral + señal de bots (heurística) |
| **Haters / Top 10** | Autores hostiles más activos |
| **Apoyo / Top 10** | Defensores / reacciones positivas (TW) |
| **Narrativas** | Temas recurrentes — toggle Haters/Apoyo |
| **Grafos** | Toggle **Haters/Apoyo** en Relaciones TW (risk/señales, puentes, co-seguidores); comportamiento FB; clusters |
| **Comparativa** | Varias personas en la misma línea de tiempo |
| **Metodología** | Límites del dato (leelos siempre) |

Usá el selector **Persona** (arriba) y, si querés, filtrá por **Plataforma**.

---

## 2. Estudiar un perfil (ej. Myriam Bregman)

1. Elegí la persona en el selector.
2. Revisá **Perfil**: ¿qué cuentas FB/TW están vinculadas? ¿followers?
3. **Reacciones** y **Engagement**: ¿qué tipo de reacción domina? ¿hay picos?
4. **Audiencia**: proporción de haters vs apoyo; ¿cuántos actores con señal bot?
5. **Haters / Top 10**, **Apoyo / Top 10** y **Narrativas**: ¿quiénes atacan, quiénes defienden, y con qué temas?
6. **Grafos**: en **Relaciones TW** usá el toggle Haters/Apoyo; mirá risk_band/señales, puentes y co-seguidores (recordá: sincronía ≠ prueba de coordinación).

<details>
<summary><strong>Prompt — briefing de una persona</strong></summary>

```text
Usando gold.v_monitor_* (skill social-monitor), hacé un briefing periodístico
sobre la persona myriambregman: cuentas vinculadas, engagement reciente,
mix de audiencia (haters/apoyo/bots), top 5 haters, top 5 defensores y top narrativas.
Indicá límites del dato (FB legacy vs twikit, heurísticas).
No pegues textos crudos de comentarios; usá agregados.
```

</details>

---

## 3. Comparar varias cuentas / personas

En **Comparativa** elegí la métrica:

- **Comentarios hostiles** — volumen de posición `derecha_o_troll` / sentimiento negativo
- **Engagement por post** — intensidad de interacción
- **Reacciones** — volumen bruto

Ejemplo: Myriam vs Nicolás vs PTS en la misma serie temporal.

<details>
<summary><strong>Prompt — comparativa temporal</strong></summary>

```text
Compará myriambregman, nicolasdelcano y ptsarg en gold.v_monitor_temporal
y v_monitor_temporal_engagement: serie diaria de hostilidad y engagement.
Resumí picos y diferencias entre plataformas. Sin PII de comentaristas.
```

</details>

---

## 4. Interpretar haters, bots y grafos

| Señal | Qué significa | Qué **no** significa |
|-------|---------------|----------------------|
| **Hater** | Clasificación LLM `derecha_o_troll` (u hostil) | Que la persona sea un “troll profesional” |
| **Apoyo / defensor** | Clasificación LLM `apoyo_izquierda` | Militante orgánico confirmado |
| **Bot (heurística)** | Cuenta nueva, ratio follow alto, bio vacía, alto output / baja audiencia | Automatización confirmada |
| **co_rafaga** | Varios autores hostiles el mismo día/cuenta | Coordinación organizada |
| **co_followers / bridge** | Audiencia compartida entre haters **o** entre apoyos | Red de bots / coordinación probada |

Siempre contrastá con el volumen y el contexto político del período.

---

## 5. Actualizar identidades (OSINT)

Las personas y cuentas viven en seeds curados (solo figuras públicas de monitoreo):

| Archivo | Contenido |
|---------|-----------|
| `config/identidades.seed.csv` | Persona: nombre, rol, partido, sitio, Wikidata, provincia… |
| `config/identidad_cuentas.seed.csv` | Puente: persona → facebook/twitter/instagram + handle / user_id |

**Checklist OSINT útil para completar:**

- Handles oficiales por plataforma
- `platform_user_id` estable (FB page id, Twitter user id)
- Verificación / fecha de creación de cuenta
- Bio y ubicación públicas
- Sitio web y Wikidata/Wikipedia
- Partido / rol / provincia

**Defensores recurrentes:** las cuentas de `gold.v_monitor_apoyo_top10` que merezcan identidad propia se agregan **manualmente** a los seeds (no hay auto-link). Re-correr `ingest_identidades.sql`.

<details>
<summary><strong>Prompt — agregar o enriquecer una identidad</strong></summary>

```text
Agregá / actualizá la identidad de [NOMBRE] en config/identidades.seed.csv
y sus cuentas en config/identidad_cuentas.seed.csv (FB/TW/IG si hay IDs).
Después re-ingerí identidades + gold de social monitor y regenerá el dashboard.
Listá qué campos OSINT quedaron vacíos para completar después.
```

</details>

---

## 6. Límites (siempre declararlos)

- Hoy hay datos vivos de **Facebook legacy** y **Twitter/X (twikit)**. Instagram/TikTok están previstos en el modelo pero sin filas.
- Clasificación LLM + heurísticas — no es verdad absoluta.
- Muestra de tweets parcial (no todo el timeline histórico).
- Los reportes son locales y **gitignored**.

---

## Referencias rápidas

| Recurso | Ruta |
|---------|------|
| Skill | [`skills/analyze/reports/social-monitor/SKILL.md`](../skills/analyze/reports/social-monitor/SKILL.md) |
| Doc técnica | [`docs/monitoreo-redes-tecnico.md`](monitoreo-redes-tecnico.md) |
| Dashboard | `reports/monitor/dashboard/report.html` |
| Seeds | `config/identidades.seed.csv`, `config/identidad_cuentas.seed.csv` |
| Guía scrape X | [`docs/guia-datos.md`](guia-datos.md) |
| FB-only dashboard | skill [`redes-analysis`](../skills/analyze/reports/redes-analysis/SKILL.md) |
