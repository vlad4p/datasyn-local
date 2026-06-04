<div align="center">

# 📰 datasyn-local

**Investiga con datos en tu propia computadora** — sin ser experto en análisis de datos.

<p>
  <span style="background:#0e2d58;color:#fffceb;padding:4px 10px;border-radius:4px;font-weight:600">🤖 Asistente IA</span>
  <span style="background:#559778;color:#fffceb;padding:4px 10px;border-radius:4px;font-weight:600">🗄️ DuckDB</span>
  <span style="background:#395a8e;color:#fffceb;padding:4px 10px;border-radius:4px;font-weight:600">🔌 MCP</span>
</p>

*Versión en [English](README.md)*

</div>

---

## ✨ ¿Para quién es?

**Periodistas, investigadores y equipos que trabajan con fuentes, documentos y datos públicos** — no hace falta saber SQL ni Python.

Vos traés las preguntas y la hipótesis. **El asistente de IA** (Cursor, Claude Code, etc.) configura el entorno con el **prompt de arranque** de abajo. El trabajo diario está en **[skills](skills/)**; el tono y las reglas en **[AGENTS.md](AGENTS.md)**.

> **No necesitás ser analista de datos.** Guardá los archivos originales, pedí en lenguaje claro y dejá que el asistente ingiera, consulte y arme reportes.

---

## 🧭 Cómo funciona (en simple)

<p align="center">
  <img src="docs/diagrams/flow.svg" alt="De la fuente a la historia: recolectar → landing → DuckDB → reports" width="780" />
</p>

| Paso | Qué hacés vos | Qué hace la máquina |
|------|----------------|---------------------|
| 1 | Guardás descargas, scrapes, exportaciones | Conserva originales en `data/landing/` |
| 2 | Pedís “ingestar” un archivo | Carga una tabla en DuckDB (skill **ingest-data**) |
| 3 | Hacés preguntas en castellano claro | SQL y MCP por detrás |
| 4 | Pedís un reporte | Escribe markdown/JSON/HTML en `reports/` (skill **statistical-report**) |

### 🔄 Qué pasa detrás de un pedido

<p align="center">
  <img src="docs/diagrams/request-lifecycle.svg" alt="Cómo un pedido se vuelve una respuesta auditable" width="520" />
</p>

---

## 🗂️ Qué va en cada lugar

<p align="center">
  <img src="docs/diagrams/repo-layout.svg" alt="Estructura del repositorio: el cerebro y tus datos" width="700" />
</p>

| | Pieza | Ubicación |
|---|--------|-----------|
| ✨ | **Prompt de arranque** | Este archivo ↓ |
| 📋 | **Comportamiento del agente** | [`AGENTS.md`](AGENTS.md) |
| 🛠️ | **Guías de tareas** | [`skills/`](skills/) — configurar en el IDE |
| 🗄️ | **Base de datos + MCP** | [`scripts/python/db.py`](scripts/python/db.py) |
| 📁 | **Evidencia en bruto** | `data/landing/` |
| 💾 | **Datos estructurados** | `data/duckdb/datasyn.duckdb` |
| 📊 | **Salida publicable** | `reports/` |

---

## 📌 Requisitos

- **Python 3.11+** (lo instala el asistente si falta)
- **[uv](https://docs.astral.sh/uv/)** — herramienta de entorno Python (el prompt la configura)
- **Un asistente de IA con skills** (por ejemplo Cursor)

---

## 🚀 Arranque — copiá este prompt

1. **Cloná** este repositorio y abrilo en el IDE.  
2. **Pegá** el bloque en el chat del asistente.  
3. **Seguí** el resumen del asistente — no deberías tener que ejecutar comandos vos mismo.

<details>
<summary><strong>📋 Clic para ver el prompt de arranque</strong></summary>

```text
Bootstrap datasyn-local en este workspace. El usuario es periodista/investigador, no ingeniero de datos — explicá los pasos en lenguaje claro.

0. Configurá el entorno uv primero:
   - Si no hay uv: instalalo (curl -LsSf https://astral.sh/uv/install.sh | sh o brew install uv)
   - Desde la raíz del repo: uv sync --all-extras
   - Verificá: uv --version y uv run python -c "import duckdb; print('duckdb', duckdb.__version__)"

1. Leé AGENTS.md y skills/README.md (usá el skill setup-uv si hace falta más detalle).

2. Si uso Cursor: enlazá skills con ln -sfn "$(pwd)/skills" .cursor/skills

3. Ejecutá el bootstrap desde la raíz del repo:
   chmod +x scripts/sh/bootstrap.sh
   ./scripts/sh/bootstrap.sh
   (configura MCP, verifica MCP y muestra estado de la base.)

Si no hay tablas, proponé un demo:
- cp samples/example.csv data/landing/demo.csv
- ingestar con el skill ingest-data (solo SQL DuckDB)
- reporte markdown EDA con el skill statistical-report

Reglas: ingest y reportes son skills (SQL), no apps Python extra. Los archivos externos siempre van primero a data/landing/. Resumí cada paso para alguien no técnico.
```

</details>


## 💬 Después del arranque — ejemplos

Podés pedir, por ejemplo:

| 💬 Pedís | 🛠️ Skill |
|---------|---------|
| *“Ingesta `data/landing/entrevistas.csv` como entrevistas”* | `ingest-data` |
| *“Perfil de la tabla entrevistas — resumen en markdown”* | `statistical-report` |
| *“Revisa si MCP está conectado”* | `configure-duckdb-mcp` |

En cada sesión el asistente lee **AGENTS.md** y elige el skill correcto.

---

## 📂 Estructura del proyecto

```text
datasyn-local/
├── 📋 AGENTS.md
├── 📖 README.md / README.es.md
├── 🛠️ skills/
├── scripts/
│   ├── python/db.py
│   └── sh/bootstrap.sh
├── 📁 data/landing/
├── 💾 data/duckdb/
├── 📊 reports/
└── 📄 samples/example.csv
```

---