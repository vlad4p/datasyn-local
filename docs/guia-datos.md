# Guía de datos — X/Twitter, LLM y DuckDB

Cómo recolectar una cuenta pública de X, (opcionalmente) clasificar replies y clusters de narrativa con un LLM, generar reportes, y compartir o apuntar a otra base DuckDB.

**Cómo usar esta guía:** copiá cada **Prompt** y pegalo en el chat del asistente. Él sigue skills y `AGENTS.md` (privacidad, gitignore, plan→confirm). Ajustá handles, fechas y rutas a tu caso.

> Privacidad y qué no va a git (`.env`, cookies, DuckDB, landing, `reports/`): skill [`data-privacy`](../skills/engineering/data-privacy/SKILL.md) — no hace falta repetirlo en cada prompt.

---

## 1. Recolectar y analizar X/Twitter (twikit)

Skill: [`scrape-twikit-twitter`](../skills/collect/twikit/scrape-twikit-twitter/SKILL.md).

### 1.1 Configurar credenciales de Twitter

Variables en [`.env.example`](../.env.example) → `.env`:

| Variable | Rol |
|----------|-----|
| `TWITTER_USERNAME` | Usuario, teléfono o email |
| `TWITTER_EMAIL` | Segundo factor opcional |
| `TWITTER_PASSWORD` | Contraseña |
| `TWITTER_TOTP_SECRET` | 2FA TOTP (opcional) |
| `TWITTER_COOKIES_PATH` | Default: `.data/twikit_cookies.json` |

**Cuentas solo-Google / Cloudflare 403:** exportá cookies del navegador (`auth_token` + `ct0`) a `.data/twikit_cookies.json`.  
**Dependencia:** fork [`rlyehlab/twikit-`](https://github.com/rlyehlab/twikit-) `2.3.4`.

<details>
<summary><strong>Prompt — preparar credenciales twikit</strong></summary>

```text
Configurá credenciales de X/Twitter para twikit (skill scrape-twikit-twitter):
copiá .env.example → .env si falta, listá las variables TWITTER_* a completar,
y si el login falla (Google/Cloudflare) explicá cómo poner cookies en
.data/twikit_cookies.json (auth_token + ct0). No muestres secretos.
```

</details>

### 1.2 Scrapear una cuenta

**Salida:** `data/landing/redes/twikit/twitter/{slug}_{YYYYMMDD}/` → `bronze.tk_tw_*` / `silver.tk_tw_profile|tweet|reply`.

<details>
<summary><strong>Prompt — scrape + ingest (rango de fechas)</strong></summary>

```text
Con scrape-twikit-twitter, scrapea @myriambregman:
desde 2026-07-01 hasta 2026-08-01 (until exclusivo), con replies
(máx 100 por tweet, concurrency 3) e ingest a bronze/silver.
Al final mostrá COUNT de silver.tk_tw_tweet y silver.tk_tw_reply
y la ruta de landing.
```

</details>

<details>
<summary><strong>Prompt — scrape + ingest (últimos N)</strong></summary>

```text
Con scrape-twikit-twitter, scrapea @HANDLE los últimos 10 tweets
con replies (máx 100) e ingest. Mostrá conteos en
silver.tk_tw_tweet y silver.tk_tw_reply.
```

</details>

### 1.3 LLM opcional — clusters de narrativa

El scrape **no requiere** LLM. Con modelo configurado:

1. **Clasificar** replies (posición + resumen + `narrativa_raw`).
2. **Clusterizar** haters (`derecha_o_troll`) en narrativas canónicas (gold).

Variables: `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, alias `CHAT_MODEL` (preferido por el clasificador), `LLM_BASE_URL`. Extra: `uv sync --extra llm`.

| Tabla / vista | Rol |
|---------------|-----|
| `silver.tk_tw_reply_classification` | Posición + resumen + `narrativa_raw` |
| `gold.tk_hater_narrativa_cluster` | Catálogo de narrativas |
| `gold.tk_hater_narrativa_assignment` | reply → cluster |
| `gold.v_tk_hater_narrativa_*` | Resumen / por tweet / temporal / detalle |
| `silver.tk_tw_user` | Catálogo twikit-only (`is_hater`) |
| `gold.tk_troll_blacklist` | Lista block/watch auditable |

**Límites del método** (para reportes): cobertura clasificación; cluster canónico > `narrativa_raw`; no es ground truth.

<details>
<summary><strong>Prompt — configurar LLM (opcional)</strong></summary>

```text
Explicame cómo configurar el LLM opcional para clasificar replies twikit
y clusters de narrativa: variables LLM_* / CHAT_MODEL en .env
(DeepSeek por defecto; OpenAI como alternativa), qué análisis habilita,
y que el scrape funciona sin LLM.
```

</details>

<details>
<summary><strong>Prompt — clasificar + clusterizar haters</strong></summary>

```text
Con silver.tk_tw_reply ya cargado y LLM listo (CHAT_MODEL o LLM_MODEL):
aplicá DDL de clasificación, corré classify_tk_tw_replies.py
(--batch-size 50 --cluster-haters), refrescá views gold de narrativa,
y reportá cobertura, conteo por criterio_label y top clusters
(gold.v_tk_hater_narrativa_resumen). Incluí límites del método LLM.
```

</details>

### 1.4 Crear reportes

Salidas en `reports/<project>/<slug>/` (gitignored).

<details>
<summary><strong>Prompt — reporte markdown</strong></summary>

```text
Con statistical-report, generá un markdown de narrativas haters twikit
(gold.v_tk_hater_narrativa_resumen y v_tk_hater_narrativa_temporal)
en reports/twikit-myriam/narrativa-brief/: top clusters, serie diaria
y límites del método. Qué muestran los datos y cómo lo sabemos.
```

</details>

<details>
<summary><strong>Prompt — reporte HTML de clusters</strong></summary>

```text
Generá el HTML de clusters haters twikit con
generate_tk_hater_clusters_report.py y confirmá la salida en
reports/twikit-myriam/hater-clusters/.
```

</details>

<details>
<summary><strong>Prompt — troll blacklist (bloqueo manual)</strong></summary>

```text
Con skill troll-blacklist, construí gold.tk_troll_blacklist
(solo datos twikit) y exportá CSV + reporte en
reports/twikit-myriam/troll-blacklist/. Mostrá counts por tier
block/watch. No bloquees automáticamente en X.
```

</details>

---

## 2. Compartir o usar una base DuckDB externa

Archivo default: [`data/duckdb/datasyn.duckdb`](../data/duckdb/) (gitignored). Schemas: [`data/duckdb/README.md`](../data/duckdb/README.md). Override: `DATASYN_DB_PATH` → [`db.py`](../scripts/python/db.py) `get_db_path()`.

### 2.1 Compartir la base

<details>
<summary><strong>Prompt — compartir datasyn.duckdb</strong></summary>

```text
Cómo compartir mi datasyn.duckdb: parar MCP, qué archivos copiar
(.duckdb y .wal si hay), y cómo la otra persona la monta y regenera MCP
(mcp-config + info).
```

</details>

### 2.2 Usar una base externa

Colocá el `.duckdb` en `data/duckdb/` (o path absoluto) y seteá `DATASYN_DB_PATH`.

<details>
<summary><strong>Prompt — apuntar a una DuckDB externa</strong></summary>

```text
Quiero usar otra DuckDB: guiame a colocarla (data/duckdb/ o path absoluto),
setear DATASYN_DB_PATH, regenerar MCP (mcp-config) y verificar (db.py info).
Reiniciar MCP en el IDE.
```

</details>

### 2.3 Combinar dos bases (`ATTACH`)

<details>
<summary><strong>Prompt — ATTACH en solo lectura</strong></summary>

```text
Sin reemplazar mi base, ATTACH READ_ONLY 'ruta/a/otra.duckdb' AS externa
y mostrá COUNT de externa.silver.tk_tw_reply (o listá tablas si no existe).
```

</details>

### 2.4 Portar como carpeta (`EXPORT` / `IMPORT`)

<details>
<summary><strong>Prompt — export / import snapshot</strong></summary>

```text
Exportá la base actual con EXPORT DATABASE a
data/duckdb/export_YYYYMMDD (FORMAT PARQUET) y explicá cómo
IMPORT DATABASE en otro entorno.
```

</details>

### 2.5 Privacidad al compartir

Antes de pasar un `.duckdb` o un export: revisá handles, textos y perfiles. Skill [`data-privacy`](../skills/engineering/data-privacy/SKILL.md).

### 2.6 Warehouse remoto (Quack) — cliente

Attach alias: `"datasyn-rlab"`. Env: `QUACK_HOST`, `QUACK_PORT`, `QUACK_TOKEN`, `QUACK_DISABLE_SSL` (ver [`.env.example`](../.env.example)).

| Comando | Uso |
|---------|-----|
| `db.py quack-info` / `quack-check` | Settings + listar tablas remotas |
| `db.py quack-sql "SELECT …"` | SQL remoto (requerido para schemas ≠ `main`) |
| `db.py run-sql --ingest --attach-quack -f …` | Escribir local + leer remoto vía `.query()` |
| `db.py quack-serve` | MCP `datasyn-quack` (cliente) sobre el warehouse |

Detalle: skill [`configure-duckdb-mcp`](../skills/infra/configure-duckdb-mcp/SKILL.md) § Remote warehouse.

<details>
<summary><strong>Prompt — conectar Quack y stagedear La Nación</strong></summary>

```text
Con Quack (datasyn-rlab): verificá quack-check, stagedeá bronze.lanacion_*
al local con ingest_lanacion_silver.sql (--attach-quack), construí
contexto LN×TW (ingest_contexto_ln_tw.sql) y regenerá el dashboard
social-monitor (sección Hechos × Redes). No subas .env ni .duckdb.
```

</details>

### 2.7 Hostear datasyn.duckdb (Quack server)

Exponer **esta** base local por HTTP Quack (default `quack:127.0.0.1:9495`).

| Comando | Uso |
|---------|-----|
| `db.py quack-host` | Arrancar warehouse (bloquea; corta MCP) |
| `db.py quack-host-status` / `quack-host-stop` | Estado / liberar lock antes de ingest |

Skill: [`host-quack`](../skills/infra/host-quack/SKILL.md). Env: `QUACK_BIND_URI`, `QUACK_ALLOW_OTHER_HOSTNAME`, `QUACK_TOKEN`.

<details>
<summary><strong>Prompt — hostear DuckDB local con Quack</strong></summary>

```text
Con skill host-quack, levantá quack-host sobre datasyn.duckdb,
mostrá bind URI y status (sin pegar el token), y explicá cómo
consultar con quack-sql apuntando QUACK_HOST/PORT al bind.
Antes de ingest: quack-host-stop.
```

</details>

---

## Referencias rápidas

| Tema | Dónde |
|------|--------|
| Skill twikit | [`skills/collect/twikit/scrape-twikit-twitter/SKILL.md`](../skills/collect/twikit/scrape-twikit-twitter/SKILL.md) |
| Variables de entorno | [`.env.example`](../.env.example) |
| Storage DuckDB | [`data/duckdb/README.md`](../data/duckdb/README.md) |
| Reportes (skill) | [`skills/analyze/reports/statistical-report/SKILL.md`](../skills/analyze/reports/statistical-report/SKILL.md) |
| Privacidad / git | [`skills/engineering/data-privacy/SKILL.md`](../skills/engineering/data-privacy/SKILL.md) |
| MCP / Quack client | [`skills/infra/configure-duckdb-mcp/SKILL.md`](../skills/infra/configure-duckdb-mcp/SKILL.md) |
| Quack host | [`skills/infra/host-quack/SKILL.md`](../skills/infra/host-quack/SKILL.md) |
| Monitor técnico | [`docs/monitoreo-redes-tecnico.md`](monitoreo-redes-tecnico.md) |
