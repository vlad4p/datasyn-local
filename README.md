# datasyn-local

Plantilla **local-first** para análisis de datos con [DuckDB](https://duckdb.org/), Python ([uv](https://docs.astral.sh/uv/)) y agentes IA vía [duckdb_mcp](https://duckdb.org/community_extensions/extensions/duckdb_mcp).

Pensada para trabajo periodístico o de investigación: datos crudos con procedencia, SQL reproducible, reportes en markdown y trazas auditables.

## Requisitos

| Herramienta | Versión |
|-------------|---------|
| Python | 3.11+ |
| [uv](https://docs.astral.sh/uv/) | reciente |
| [Cursor](https://cursor.com/) u otro cliente MCP | opcional |

## Inicio rápido (5 minutos)

```bash
git clone https://github.com/TU_ORG/datasyn-local.git
cd datasyn-local

# Instalar uv (si no lo tenés)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Dependencias + comprobar MCP
make setup

# Demo con datos de ejemplo
cp samples/example.csv data/landing/demo.csv
make ingest FILE=data/landing/demo.csv TABLE=demo
make info
make report TABLE=demo
```

Salida esperada:

- Tabla `demo` en `data/duckdb/datasyn.duckdb` (no se sube a git)
- Reporte en `reports/demo_report_*.md`
- Trazas en `.logs/traces_*.jsonl` (gitignored)

## Estructura del proyecto

```
datasyn-local/
├── data/
│   ├── landing/          # Datos crudos ANTES de DuckDB (scrapes, CSV, JSON…)
│   └── duckdb/           # Archivo .duckdb persistente
├── src/                  # Librería Python (conexión DB, trazas)
├── scripts/              # CLIs (ingest, reportes, MCP)
├── reports/              # Reportes markdown generados
├── .logs/                # Trazas JSONL de acciones
├── samples/              # CSV de ejemplo (seguro para clonar)
├── config/settings.yaml  # Rutas por defecto
├── .cursor/
│   ├── skills/           # Flujos para el agente de Cursor
│   ├── agents/           # Persona del analista
│   ├── rules/            # Reglas del proyecto
│   └── mcp.json.example  # Plantilla MCP (sin rutas personales)
├── AGENTS.md             # Instrucciones para agentes IA
└── SECURITY.md           # Privacidad y checklist antes de publicar
```

## Flujo de trabajo

```text
1. Descargar / scrapear  →  data/landing/
2. Ingestar              →  DuckDB (tabla)
3. Consultar / analizar  →  SQL o Python (src/)
4. Documentar            →  reports/
5. Auditar (opcional)    →  .logs/
```

### 1. Poner datos en landing

Todo archivo externo va primero a `data/landing/` sin modificar:

```bash
cp mi_export.csv data/landing/
# o: scraper que guarda en data/landing/
```

### 2. Ingestar a DuckDB

```bash
make ingest FILE=data/landing/mi_export.csv TABLE=mi_export
```

Formatos: `.csv`, `.json`, `.xlsx`. El nombre de tabla solo admite letras, números y `_` (protección contra inyección SQL).

### 3. Consultar

```bash
make info
make sql QUERY="SELECT * FROM mi_export LIMIT 10"
uv run python -m src.cli sql "SHOW TABLES"
```

### 4. Reporte estadístico

```bash
make report TABLE=mi_export
```

Genera `reports/mi_export_report_YYYYMMDD_HHMMSS.md` con `DESCRIBE` y `SUMMARIZE`.

### 5. Trazas (auditoría local)

```python
from src.trace import log_event

log_event("analysis.done", actor="agent", data={"table": "mi_export"})
```

Archivos: `.logs/traces_YYYYMMDD.jsonl` — **no subir a git**.

## Configuración opcional

```bash
cp .env.example .env
```

| Variable | Default |
|----------|---------|
| `DATASYN_DB_PATH` | `data/duckdb/datasyn.duckdb` |
| `DATASYN_LANDING_PATH` | `data/landing` |
| `DATASYN_REPORTS_PATH` | `reports` |
| `DATASYN_LOGS_PATH` | `.logs` |

## Cursor: agente y skills

1. Abrí el repo en Cursor.
2. El agente del proyecto está en `.cursor/agents/datasyn-analyst.md`.
3. Los **skills** en `.cursor/skills/` se activan solos (ingest, scraping, reportes, MCP…).
4. Leé `AGENTS.md` para convenciones completas.

## MCP (DuckDB en Cursor)

El servidor MCP expone las tablas de tu DuckDB al IDE. **No commitees** rutas de tu máquina.

```bash
# Genera .cursor/mcp.json local (gitignored)
make mcp-config

# Verificar extensión
make mcp-check
```

Reiniciá Cursor o recargá MCP. La plantilla pública está en `.cursor/mcp.json.example`.

> **Seguridad:** MCP lee todas las tablas de tu base local. Usalo solo en proyectos de confianza. Ver [SECURITY.md](SECURITY.md).

## Comandos Make

| Comando | Descripción |
|---------|-------------|
| `make install` | Instalar dependencias (`uv sync`) |
| `make setup` | install + MCP check + debug |
| `make info` | Rutas y listado de tablas |
| `make ingest FILE=… TABLE=…` | landing → DuckDB |
| `make report TABLE=…` | Perfil estadístico → `reports/` |
| `make sql QUERY='…'` | SQL ad hoc |
| `make mcp-config` | Crear `.cursor/mcp.json` local |
| `make mcp-check` | Probar extensión `duckdb_mcp` |
| `make debug` | Comprobar entorno |
| `make shell` | IPython |

## Desarrollo

```bash
uv add nombre-paquete
uv run ruff check src/ scripts/
```

Código reutilizable → `src/`. Entradas CLI → `scripts/`. Siempre ejecutar con `uv run python …`.

## Qué no va en git

Definido en `.gitignore`:

- Bases `.duckdb`, landing, reportes, `.logs`, `.env`
- `.cursor/mcp.json`, `kilo.json` (config local con rutas absolutas)

Antes de hacer el repo público: [SECURITY.md](SECURITY.md).

## Licencia

MIT — ver [LICENSE](LICENSE).
