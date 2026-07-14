<div align="center">

# 📰 datasyn-local

**Skills para analizar y procesar datos** — usando lenguaje natural.

<p>
  <span style="background:#0e2d58;color:#fffceb;padding:4px 10px;border-radius:4px;font-weight:600">🤖 Asistente IA</span>
  <span style="background:#559778;color:#fffceb;padding:4px 10px;border-radius:4px;font-weight:600">🗄️ DuckDB</span>
  <span style="background:#395a8e;color:#fffceb;padding:4px 10px;border-radius:4px;font-weight:600">🔌 MCP</span>
</p>

*Versión en [English](README.en.md)*

</div>

---

## En resumen

**datasyn-local** agrega a tu Asistente de IA instrucciones (skills + prompts) para realizar analisis de datos. Por ejemplo puedes solicitarle en lenguaje natural:

***
 *"ingesta este CSV data_example.csv", "limpia los duplicados", "crea un analisis de sentimiento", "finalmente crea un reporte interactivo en html"*
***

y tu **asistente de IA** traduce ese pedido y crea los scripts en **sql**, **python** o **sh**; que luego ejecutara para realizar el analisis

## Índice

1. [Instalar](#instalar)
2. [Dónde guardar un CSV en landing](#donde-guardar-un-csv-en-landing)
3. [Cómo ingestar un CSV en DuckDB](#como-ingestar-un-csv-en-duckdb)
4. [Importar otra base DuckDB y consultar tablas](#importar-otra-base-duckdb-y-consultar-tablas)
5. [Cómo funciona](#como-funciona)
6. [Ejemplo completo](#ejemplo-completo)
7. [Crear una nueva skill](#crear-una-nueva-skill)
8. [Gitflow](#gitflow)
9. [Guías](#guias)
10. [Herramientas](#herramientas)

---

## Instalar

Para empezar solo necesitás **(1)** un asistente de IA y **(2)** clonar este repositorio. El [prompt de arranque](#arranque) configura el resto (`uv`, skills, MCP).

### 1. Instalá un asistente de IA

Usá cualquiera de estos (los más conocidos):

- [Cursor](https://cursor.com/)
- [Claude Code](https://claude.ai/code) (Anthropic)
- [GitHub Copilot](https://github.com/features/copilot) en [VS Code](https://code.visualstudio.com/)
- [Google Antigravity](https://antigravity.google/)
- [OpenCode](https://opencode.ai/)

### 2. Cloná el repositorio

```bash
git clone <URL-del-repositorio>
cd datasyn-local
```

Abrí la carpeta en tu asistente y seguí con [Arranque](#arranque).

### Configurar herramientas

El prompt de arranque instala y configura lo necesario. Si querés saber qué usa el proyecto:

- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)** — entorno Python

Otras herramientas (por ejemplo **R**) se especifican solo si el análisis las pide.

---

## Arranque

Ya tenés el repo abierto en el asistente. Pegá el prompt de abajo: él configura `uv` (Python), enlaza los [skills](skills/) y conecta el servidor MCP de DuckDB.

1. **Pegá** el bloque en el chat del asistente.
2. **Seguí** el resumen — no deberías tener que ejecutar comandos por tu cuenta.

<details>
<summary><strong>📋 Clic para ver el prompt de arranque</strong></summary>

```text
Bootstrap datasyn-local en este workspace. El usuario es cientifico/periodista/investigador — explica los pasos en lenguaje claro.

0. Configura el entorno uv primero:
   - Si no hay uv: instálalo (curl -LsSf https://astral.sh/uv/install.sh | sh o brew install uv)
   - Desde la raíz del repo: uv sync --all-extras
   - Verifica: uv --version y uv run python -c "import duckdb; print('duckdb', duckdb.__version__)"

1. Lee AGENTS.md, CONTEXT.md y skills/README.md (usa el skill setup-uv si hace falta más detalle).

2. Enlaza skills según el IDE:
   - **Cursor:** ln -sfn "$(pwd)/skills" .cursor/skills
   - **VS Code:** no necesita enlace — lee skills/ directamente

3. Configura el servidor MCP de DuckDB (para que el asistente pueda consultar la base de datos):
   - Ejecuta: uv run python scripts/python/db.py mcp-config
     (esto genera .cursor/mcp.json con la configuración)
   - **VS Code:** copia .cursor/mcp.json a .vscode/mcp.json:
     cp .cursor/mcp.json .vscode/mcp.json
     (VS Code 1.96+ usa .vscode/mcp.json automáticamente)
   - **VS Code alternativo:** también puedes pegar el contenido de .cursor/mcp.json
     dentro de .vscode/settings.json bajo la clave "github.copilot.chat.agent.mcpServers"
   - **Cursor:** el archivo .cursor/mcp.json ya está listo

4. Ejecuta el bootstrap desde la raíz del repo:
   chmod +x scripts/sh/bootstrap.sh
   ./scripts/sh/bootstrap.sh
   (configura MCP, verifica MCP y muestra estado de la base.)

Reglas: ingest y reportes son skills (SQL), no apps Python extra. Los archivos externos siempre van primero a data/landing/. Resume cada paso de forma clara
```

</details>

### ✅ Cuando termine el asistente

| | Deberías tener |
|---|----------------|
| 🐍 | `uv` + `.venv` con dependencias |
| 🔌 | `.cursor/mcp.json` (Cursor) o `.vscode/mcp.json` (VS Code) — ambos locales, no se suben a git |
| 🛠️ | `skills/` enlazados en el IDE |
| 🗄️ | MCP conectado a `data/duckdb/datasyn.duckdb` |

---

## Donde guardar un CSV en landing

Todo archivo crudo (CSV, JSON, scrape, exportación) entra primero en **`data/landing/`**. Esa carpeta es la zona de **originales**: no se edita ahí; la limpieza y el análisis ocurren después, dentro de DuckDB.

Vocabulario compartido: [`CONTEXT.md`](CONTEXT.md). Principio: **conservar originales**.

### Ejemplo con el CSV de muestra

Hay un dataset de tweets ficticios en [`examples/data_example.csv`](examples/data_example.csv). Copialo a landing:

```bash
cp examples/data_example.csv data/landing/
```

`data/landing/` está en `.gitignore` (no se sube a git). El archivo en `examples/` sí se versiona para que cualquiera pueda repetir el tutorial.

Más detalle: [`examples/README.md`](examples/README.md).

---

## Como ingestar un CSV en DuckDB

**No tenés que escribir SQL.** Pedís en lenguaje natural; el asistente usa las **skills** ([`ingest-data`](skills/ingest/ingest-data/SKILL.md) → [`ingest-data-bronze`](skills/ingest/bronze/ingest-data-bronze/SKILL.md)), genera el SQL y carga la tabla en DuckDB automáticamente.

Flujo resumido:

1. El CSV ya está en `data/landing/` (paso anterior).
2. Pegás el prompt de abajo en el chat.
3. El asistente crea `bronze.tweets_example`, valida filas y puede hacer un mini-análisis.

<details>
<summary><strong>📋 Prompt — ingestar el CSV de ejemplo y analizarlo</strong></summary>

```text
Ingestá data/landing/data_example.csv en DuckDB como bronze.tweets_example
(skill ingest-data). Después mostrame COUNT(*), DESCRIBE y 5 filas,
y un mini-análisis: top autores por likes y tweets por día.
```

</details>

> **Nota técnica (opcional):** las consultas van por MCP; la escritura (CREATE TABLE / ingest) usa `db.py run-sql --ingest` y puede pedir parar MCP un momento. Reglas en [`AGENTS.md`](AGENTS.md).

---

## Importar otra base DuckDB y consultar tablas

Si alguien te pasa un archivo como **`warehouse-01.duckdb`** (por ejemplo con scrapes de Twitter/X ya cargados), podés usarlo como base principal.

### Pasos

```bash
# 1. Colocá el archivo en data/duckdb/
cp /ruta/a/warehouse-01.duckdb data/duckdb/

# 2. Apuntá datasyn a esa base
export DATASYN_DB_PATH=data/duckdb/warehouse-01.duckdb

# 3. Regenerá la config MCP y verificá
uv run python scripts/python/db.py mcp-config
uv run python scripts/python/db.py info
```

Reiniciá el servidor MCP en el IDE para que tome la nueva ruta. Luego pedí en el chat, por ejemplo:

```text
Listá las tablas de la base y mostrá los 10 tweets con más likes
de silver.tk_tw_tweet (o la tabla equivalente). ¿Qué muestran los datos?
```

Las tablas `silver.tk_tw_*` son el resultado típico de scrapear una cuenta con [`scrape-twikit-twitter`](skills/collect/twikit/scrape-twikit-twitter/SKILL.md).

### Otras opciones

| Objetivo | Cómo |
|----------|------|
| Combinar dos bases sin reemplazar la tuya | `ATTACH` en solo lectura — ver [`docs/guia-datos.md`](docs/guia-datos.md) §2.3 |
| Scrapear vos una cuenta de X | misma guía §1 + skill `scrape-twikit-twitter` |

---

## Como funciona

### Principios

| Principio | Qué significa para ti |
|-----------|------------------------|
| **Conservar originales** | Descargas y extracciones quedan en `data/landing/` — sin sobrescribir |
| **Usar lenguaje natural** | Pides en lenguaje claro; los **skills** convierten el pedido en SQL de DuckDB (vía MCP) |

### Las piezas

| Pieza | Rol |
|-------|-----|
| 🤖 **Asistente IA + [skills](skills/)** | Convierten tu pedido en lenguaje natural en pasos concretos de SQL |
| 📋 **[AGENTS.md](AGENTS.md)** | Define el tono, las reglas y el flujo de trabajo del asistente |
| 📖 **[CONTEXT.md](CONTEXT.md)** | Vocabulario compartido — medalla, landing, reportes, MCP vs ingest |
| 🗄️ **DuckDB** (`data/duckdb/`) | Motor analítico local donde viven las tablas |
| 🔌 **MCP** | Puente que deja al asistente ejecutar SQL sobre la base |
| 📂 **`data/landing/` → `reports/<project>/`** | Originales crudos a la entrada, salidas publicables a la salida |

### Skills por alcance

Los skills están agrupados en **buckets** bajo [`skills/`](skills/). Índice completo: [`skills/README.md`](skills/README.md). Guía de estructura: [`docs/skills-layout.md`](docs/skills-layout.md).

| Alcance | Carpeta | Skill router |
|---------|---------|--------------|
| **Recolectar** | [`skills/collect/`](skills/collect/README.md) | `scrape-sociavault`, `web-scraping` |
| **Ingestar** | [`skills/ingest/`](skills/ingest/README.md) | `ingest-data` → bronze / silver / gold |
| **Analizar** | [`skills/analyze/`](skills/analyze/README.md) | reportes, grafos |
| **Esquema** | [`skills/schema/`](skills/schema/README.md) | `create-table` |
| **Infra** | [`skills/infra/`](skills/infra/README.md) | `setup-uv`, `configure-duckdb-mcp` |
| **Ingeniería** | [`skills/engineering/`](skills/engineering/README.md) | `gitflow`, `data-privacy` |

Router de flujos (usuario): [`datasyn-router`](skills/datasyn-router/SKILL.md).

### Del dato crudo al reporte

Tus datos suben de calidad por etapas —el **patrón de medalla**— y en cada una un **skill** hace el trabajo. Tú solo describes lo que necesitas; el asistente elige la etapa y el skill correctos.

<p align="center"><img src="docs/diagrams/flow.svg" alt="De la fuente a la historia — recolectar, landing, DuckDB, reportes" width="860"/></p>

| Etapa | Qué pasa | Skill que lo hace |
|-------|----------|-------------------|
| **Landing** | Guardas descargas, scrapes y exportaciones sin tocarlas | [`web-scraping`](skills/collect/web-scraping/SKILL.md) |
| 🟤 **Bronze** | Los archivos crudos entran a DuckDB tal cual | [`ingest-data-bronze`](skills/ingest/bronze/ingest-data-bronze/SKILL.md) |
| ⚪ **Silver** | Se limpia, deduplica, normaliza y une | [`ingest-data-silver`](skills/ingest/silver/ingest-data-silver/SKILL.md) |
| 🟡 **Gold** | Se agrega y resume en datasets listos para usar | [`ingest-data-gold`](skills/ingest/gold/ingest-data-gold/SKILL.md) |
| **Reportes** | Se generan análisis y documentos finales | [`statistical-report`](skills/analyze/reports/statistical-report/SKILL.md) · [`sentiment-analysis`](skills/analyze/reports/sentiment-analysis/SKILL.md) · [`graph-analysis`](skills/analyze/graph/graph-analysis/SKILL.md) |

> El skill [`ingest-data`](skills/ingest/ingest-data/SKILL.md) es el punto de entrada: analiza tu pedido y lo enruta a la etapa (bronze, silver o gold) correcta.

Pipeline legacy FB/TW (CSV en `data/landing/redes/`):

<p align="center"><img src="docs/diagrams/medallion-redes.svg" alt="Medallón redes — landing, bronze, silver, gold, report bundles" width="900"/></p>

### Un pedido de punta a punta

Un solo mensaje ("ingesta este archivo y resúmelo") sigue siempre el mismo camino:

<p align="center"><img src="docs/diagrams/request-lifecycle.svg" alt="Un pedido — lenguaje claro a respuesta auditable vía MCP" width="560"/></p>

### Mapa del repositorio

Izquierda: configuración y comportamiento del agente. Derecha: evidencia y salidas publicables.

<p align="center"><img src="docs/diagrams/repo-layout.svg" alt="Layout del repositorio datasyn — agente y carpetas de datos" width="680"/></p>

---

## Ejemplo completo

**Extraer → ingestar → reporte de analisis de sentimiento** en un solo mensaje:

<p align="center"><img src="docs/diagrams/investigation-example.svg" alt="Investigación completa — extracción, ingesta, reporte de sentimiento" width="720"/></p>

Pégalo en el asistente:

```text
Ejecuta un pipeline completo y explica cada paso en lenguaje claro:

1. Extrae titulares recientes de noticias del New York Times
   (skill web-scraping) y guarda los resultados crudos en data/landing/
   — conserva la URL de origen y la fecha de captura para la trazabilidad.
2. Ingesta ese archivo en DuckDB como una tabla llamada nyt_news
   (skill ingest-data). Después muestra COUNT(*), DESCRIBE y 5 filas de ejemplo.
3. Realiza un análisis de sentimiento sobre el texto de titulares y resúmenes
   (skill sentiment-analysis) y escribe un reporte markdown en reports/<project>/
   con: tono general, desglose positivo/neutral/negativo, algunas citas
   representativas y los límites del método.

Recuerda: los archivos externos van primero a data/landing/, la ingesta y
los reportes son skills (SQL de DuckDB), e indica qué muestran los datos,
cómo lo sabemos y cuáles son las salvedades.
```

---

## Crear una nueva skill

En este proyecto, una **skill** es una guía de trabajo en Markdown que le enseña al asistente *cómo* hacer una tarea concreta (ingestar un CSV, limpiar duplicados, escribir un reporte). No es código que se ejecuta: es una receta en lenguaje claro con reglas, pasos y plantillas de SQL. Cuando pides algo, el asistente busca la skill adecuada y la sigue.

**Dónde se guardan:** cada skill vive en un bucket de alcance dentro de [`skills/`](skills/) — por ejemplo `skills/ingest/`, `skills/collect/`, `skills/analyze/` — con un archivo `SKILL.md` en su carpeta.

```
skills/
├── ingest/
│   └── bronze/
│       └── ingest-data-bronze/
│           └── SKILL.md
└── analyze/
    └── reports/
        └── statistical-report/
            └── SKILL.md
```

Vocabulario compartido: [`CONTEXT.md`](CONTEXT.md). Índice completo: [`skills/README.md`](skills/README.md). Guía de estructura: [`docs/skills-layout.md`](docs/skills-layout.md).

**Cómo crear una:** crea la carpeta y un `SKILL.md` que empiece con un encabezado (frontmatter) con `name` y `description`. La `description` es clave: el asistente la usa para decidir cuándo aplicar la skill.

````markdown
---
name: export-csv
description: >-
  Exporta una tabla de DuckDB a un archivo CSV en reports/<project>/.
  Úsala cuando el usuario pida descargar, exportar o guardar
  una tabla o consulta como CSV.
---

# Exportar a CSV

Pasos:

1. Confirma con el usuario qué tabla o consulta exportar.
2. Ejecuta el COPY vía MCP:

   ```sql
   COPY (SELECT * FROM gold.mi_tabla)
   TO 'reports/mi-proyecto/mi_tabla.csv' (HEADER, DELIMITER ',');
   ```

3. Valida: confirma que el archivo existe y su número de filas.
````

> 💡 Después de crearla, súmala al catálogo de [`skills/README.md`](skills/README.md) y, si tu IDE las cachea, vuelve a enlazar la carpeta (`ln -sfn "$(pwd)/skills" .cursor/skills`). Mira cualquier skill existente, como [`ingest-data`](skills/ingest/ingest-data/SKILL.md), como referencia de estilo.

---

## Gitflow

El repo usa **Gitflow**: `main` es producción; `develop` integra el trabajo terminado; las features son ramas cortas que se fusionan en `develop`.

```
main     ●─────────●─────────────────●  (tags: v1.0.0)
          \       /
develop    ●──●──●──●──●──●──●  ← integración
                \    /
feature          ●──●           ← trabajo nuevo
```

| Rama | Prefijo | Base | Merge a | Uso |
|------|---------|------|---------|-----|
| **main** | — | — | — | Código listo para release |
| **develop** | — | `main` | — | Integración diaria |
| **feature** | `feature/` | `develop` | `develop` | Skills, ingest, scripts |
| **release** | `release/` | `develop` | `main` + `develop` | Estabilizar versión |
| **hotfix** | `hotfix/` | `main` | `main` + `develop` | Fix urgente en producción |

### Flujo típico (feature)

```bash
git checkout develop && git pull origin develop
git checkout -b feature/mi-cambio
# ... commits (solo código/skills/SQL — nunca data/landing/, .env, reportes)
git push -u origin HEAD
# PR → develop (preferido) o merge local --no-ff
git checkout develop && git merge --no-ff feature/mi-cambio
git branch -d feature/mi-cambio
git push origin --delete feature/mi-cambio   # si quedó en remoto
```

### Estado actual

```bash
./scripts/sh/gitflow.sh status    # rama, tipo, divergencia vs main/develop
./scripts/sh/gitflow.sh branches  # features locales y si ya están en develop
```

Guía completa para el asistente: [`skills/engineering/gitflow/SKILL.md`](skills/engineering/gitflow/SKILL.md) · referencia: [`skills/engineering/gitflow/reference.md`](skills/engineering/gitflow/reference.md)

**Reglas de commit:** `feat(scope):`, `fix(scope):`, `docs(scope):` — sin PII ni datos crudos en mensajes. Ver skill [`data-privacy`](skills/engineering/data-privacy/SKILL.md) antes de commitear.

---

## Guias

| Guía | Contenido |
|------|-----------|
| [`docs/guia-datos.md`](docs/guia-datos.md) | Prompts listos: credenciales X/Twitter (twikit), scrape, LLM opcional + clusters, reportes; compartir o apuntar a una DuckDB externa |
| [`docs/guia-monitoreo-redes.md`](docs/guia-monitoreo-redes.md) | Monitor unificado: estudiar personas multiplataforma, reacciones, haters, grafos, comparativas |
| [`docs/monitoreo-redes-tecnico.md`](docs/monitoreo-redes-tecnico.md) | Doc técnica del sistema de monitoreo (identidad, gold, dashboard) |

Diagramas: [`docs/diagrams/README.md`](docs/diagrams/README.md) — fuentes SVG en [`docs/diagrams/`](docs/diagrams/), paleta en [`docs/colors/README.md`](docs/colors/README.md).

---

## Herramientas

| Herramienta | Para qué sirve | Documentación |
|-------------|----------------|----------------|
| 🗄️ **DuckDB** | Base de datos analítica local; ejecuta el SQL que crea y consulta tus tablas | [duckdb.org/docs](https://duckdb.org/docs/) |
| 🔌 **MCP** (Model Context Protocol) | Estándar abierto que conecta al asistente de IA con DuckDB para ejecutar SQL | [modelcontextprotocol.io](https://modelcontextprotocol.io/) · [duckdb_mcp](https://github.com/duckdb/duckdb-mcp-server) |
| 🧩 **Skills** | Guías de tarea en Markdown por alcance (ver [`skills/`](skills/) y [`docs/skills-layout.md`](docs/skills-layout.md)) | [Agent Skills (Anthropic)](https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills/overview) · [Cursor Rules & Skills](https://docs.cursor.com/) |
| 🐍 **uv** | Gestor de entornos y dependencias de Python | [docs.astral.sh/uv](https://docs.astral.sh/uv/) |

---

## ⚠️ Disclaimer

Este repositorio fue creado con ayuda de IA (modelos de **Anthropic**, **Gemini**, **DeepSeek** y algunos proveedores de **OpenRouter**). Revisa tus configuraciones de **billing**, **limita tus cuotas** y verifica los **permisos** antes de usarlo.

