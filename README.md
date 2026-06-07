<div align="center">

# 📰 datasyn-local

**Analiza tus datos en tu propia computadora** — usando lenguaje natural.

<p>
  <span style="background:#0e2d58;color:#fffceb;padding:4px 10px;border-radius:4px;font-weight:600">🤖 Asistente IA</span>
  <span style="background:#559778;color:#fffceb;padding:4px 10px;border-radius:4px;font-weight:600">🗄️ DuckDB</span>
  <span style="background:#395a8e;color:#fffceb;padding:4px 10px;border-radius:4px;font-weight:600">🔌 MCP</span>
</p>

*Versión en [English](README.en.md)*

</div>

---

## En resumen

**datasyn-local** convierte tu computadora en un espacio de análisis de datos que se maneja **conversando**. Le pides en lenguaje natural —"ingesta este CSV", "limpia los duplicados", "crea un reporte de sentimiento"— y un asistente de IA traduce ese pedido en **SQL de DuckDB**, construye los datasets y entrega resultados auditables. Todo corre **local**: tus fuentes nunca salen de tu máquina.


## 📌 Requisitos
A continuacion se listan los requisitos, que de ser necesario instalará tu asistente.
- **Python 3.11+** 
- **[uv](https://docs.astral.sh/uv/)** — entorno Python (lo configura el prompt de arranque)
- **Un asistente de IA** (Cursor, VS Code + GitHub Copilot, o similar)

---

## 🚀 Arranque — copia este prompt

No instalas nada a mano: clonas el repositorio, pegas el prompt de abajo en tu asistente y él configura `uv` (Python), enlaza los [skills](skills/) y conecta el servidor MCP de DuckDB.

1. **Clona** este repositorio y ábrelo en el IDE.
2. **Pega** el bloque en el chat del asistente.
3. **Sigue** el resumen — no deberías tener que ejecutar comandos por tu cuenta.

<details>
<summary><strong>📋 Clic para ver el prompt de arranque</strong></summary>

```text
Bootstrap datasyn-local en este workspace. El usuario es periodista/investigador — explica los pasos en lenguaje claro.

0. Configura el entorno uv primero:
   - Si no hay uv: instálalo (curl -LsSf https://astral.sh/uv/install.sh | sh o brew install uv)
   - Desde la raíz del repo: uv sync --all-extras
   - Verifica: uv --version y uv run python -c "import duckdb; print('duckdb', duckdb.__version__)"

1. Lee AGENTS.md y skills/README.md (usa el skill setup-uv si hace falta más detalle).

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

Reglas: ingest y reportes son skills (SQL), no apps Python extra. Los archivos externos siempre van primero a data/landing/. Resume cada paso para alguien no técnico.
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

## 🧭 Cómo funciona

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
| 🗄️ **DuckDB** (`data/duckdb/`) | Motor analítico local donde viven las tablas |
| 🔌 **MCP** | Puente que deja al asistente ejecutar SQL sobre la base |
| 📂 **`data/landing/` → `reports/`** | Originales crudos a la entrada, salidas publicables a la salida |

### Del dato crudo al reporte

Tus datos suben de calidad por etapas —el **patrón de medalla**— y en cada una un **skill** hace el trabajo. Tú solo describes lo que necesitas; el asistente elige la etapa y el skill correctos.

<p align="center"><img src="docs/diagrams/flow.svg" alt="De la fuente a la historia — recolectar, landing, DuckDB, reportes" width="860"/></p>

| Etapa | Qué pasa | Skill que lo hace |
|-------|----------|-------------------|
| **Landing** | Guardas descargas, scrapes y exportaciones sin tocarlas | [`web-scraping`](skills/web-scraping/SKILL.md) |
| 🟤 **Bronze** | Los archivos crudos entran a DuckDB tal cual | [`ingest-data-bronze`](skills/ingest-data-bronze/SKILL.md) |
| ⚪ **Silver** | Se limpia, deduplica, normaliza y une | [`ingest-data-silver`](skills/ingest-data-silver/SKILL.md) |
| 🟡 **Gold** | Se agrega y resume en datasets listos para usar | [`ingest-data-gold`](skills/ingest-data-gold/SKILL.md) |
| **Reportes** | Se generan análisis y documentos finales | [`statistical-report`](skills/statistical-report/SKILL.md) · [`sentiment-analysis`](skills/sentiment-analysis/SKILL.md) · [`graph-analysis`](skills/graph-analysis/SKILL.md) |

> El skill [`ingest-data`](skills/ingest-data/SKILL.md) es el punto de entrada: analiza tu pedido y lo enruta a la etapa (bronze, silver o gold) correcta.

---

## 🗞️ Ejemplo completo — de titulares a *emociones...*

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
   (skill sentiment-analysis) y escribe un reporte markdown en reports/
   con: tono general, desglose positivo/neutral/negativo, algunas citas
   representativas y los límites del método.

Recuerda: los archivos externos van primero a data/landing/, la ingesta y
los reportes son skills (SQL de DuckDB), e indica qué muestran los datos,
cómo lo sabemos y cuáles son las salvedades.
```

---

## 🧩 Crear una nueva skill

En este proyecto, una **skill** es una guía de trabajo en Markdown que le enseña al asistente *cómo* hacer una tarea concreta (ingestar un CSV, limpiar duplicados, escribir un reporte). No es código que se ejecuta: es una receta en lenguaje claro con reglas, pasos y plantillas de SQL. Cuando pides algo, el asistente busca la skill adecuada y la sigue.

**Dónde se guardan:** cada skill vive en su propia carpeta dentro de [`skills/`](skills/), con un archivo `SKILL.md` adentro.

```
skills/
└── mi-skill/
    └── SKILL.md
```

**Cómo crear una:** crea la carpeta y un `SKILL.md` que empiece con un encabezado (frontmatter) con `name` y `description`. La `description` es clave: el asistente la usa para decidir cuándo aplicar la skill.

````markdown
---
name: export-csv
description: >-
  Exporta una tabla de DuckDB a un archivo CSV en reports/.
  Úsala cuando el usuario pida descargar, exportar o guardar
  una tabla o consulta como CSV.
---

# Exportar a CSV

Pasos:

1. Confirma con el usuario qué tabla o consulta exportar.
2. Ejecuta el COPY vía MCP:

   ```sql
   COPY (SELECT * FROM gold.mi_tabla)
   TO 'reports/mi_tabla.csv' (HEADER, DELIMITER ',');
   ```

3. Valida: confirma que el archivo existe y su número de filas.
````

> 💡 Después de crearla, súmala al catálogo de [`skills/README.md`](skills/README.md) y, si tu IDE las cachea, vuelve a enlazar la carpeta (`ln -sfn "$(pwd)/skills" .cursor/skills`). Mira cualquier skill existente, como [`ingest-data`](skills/ingest-data/SKILL.md), como referencia de estilo.

---

## 🛠️ Herramientas que usa

| Herramienta | Para qué sirve | Documentación |
|-------------|----------------|----------------|
| 🗄️ **DuckDB** | Base de datos analítica local; ejecuta el SQL que crea y consulta tus tablas | [duckdb.org/docs](https://duckdb.org/docs/) |
| 🔌 **MCP** (Model Context Protocol) | Estándar abierto que conecta al asistente de IA con DuckDB para ejecutar SQL | [modelcontextprotocol.io](https://modelcontextprotocol.io/) · [duckdb_mcp](https://github.com/duckdb/duckdb-mcp-server) |
| 🧩 **Skills** | Guías de tarea en Markdown que el asistente sigue (ver [`skills/`](skills/)) | [Agent Skills (Anthropic)](https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills/overview) · [Cursor Rules & Skills](https://docs.cursor.com/) |
| 🐍 **uv** | Gestor de entornos y dependencias de Python | [docs.astral.sh/uv](https://docs.astral.sh/uv/) |

---

## ⚠️ Disclaimer

Este repositorio fue creado con ayuda de IA (modelos de **Anthropic**, **Gemini**, **DeepSeek** y algunos proveedores de **OpenRouter**). Revisa tus configuraciones de **billing**, **limita tus cuotas** y verifica los **permisos** antes de usarlo.

