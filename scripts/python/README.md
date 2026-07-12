# Python scripts

Organized by function under `scripts/python/`. Ingest/report **pipelines** live in skills; these modules are the runnable entrypoints.

```text
scripts/python/
  db.py                 # DuckDB paths, MCP, Quack, run-sql (+ resolve_sql)
  scrape/
    twikit/             # X/Twitter via twikit
    sociavault/         # SociaVault FB/IG/TT (+ deprecated TW)
    boletin/            # Boletín / contrataciones scrapers
  classify/             # LLM classify (twikit, SV, La Nación)
  reports/              # HTML/CSV report generators + templates/
  analyze/              # Graph helpers, entity extract
  tools/                # Misc (embed README diagrams)
```

`db.resolve_sql("ingest_….sql")` finds files under `scripts/sql/**` by basename.

## db

```bash
uv run python scripts/python/db.py info
uv run python scripts/python/db.py mcp-check
uv run python scripts/python/db.py mcp-config
uv run python scripts/python/db.py mcp-serve
uv run python scripts/python/db.py mcp-stop
```

## scrape

| Path | Usage |
|------|--------|
| `scrape/twikit/scrape_twikit_twitter.py` | X via twikit → landing |
| `scrape/twikit/enrich_twikit_profiles.py` | Enrich haters/apoyo profiles + follows |
| `scrape/sociavault/scrape_sociavault_*.py` | SociaVault platforms |
| `scrape/boletin/scrape_boletin.py` | Boletín Oficial |
| `scrape/boletin/scrape_contrataciones.py` | Contrataciones |

```bash
uv run python scripts/python/scrape/twikit/scrape_twikit_twitter.py \
  --handle myriambregman --since 2026-07-01 --until 2026-08-01 \
  --fetch-replies --max-replies 100 --ingest
```

## classify

| Path | Usage |
|------|--------|
| `classify/classify_tk_tw_replies.py` | Twikit replies + narrative clusters |
| `classify/classify_lanacion_to_hater_clusters.py` | LN → hater cluster affinity |
| `classify/classify_sv_comments.py` | SociaVault comment LLM labels |

## reports

| Path | Bundle |
|------|--------|
| `reports/generate_social_monitor_dashboard.py` | `reports/monitor/dashboard/` |
| `reports/generate_redes_dashboard.py` | `reports/redes/dashboard/` |
| `reports/generate_tk_hater_clusters_report.py` | twikit hater clusters |
| `reports/generate_tk_troll_blacklist_report.py` | troll blacklist |
| `reports/export_redes_reports_zip.py` | zip of redes bundles |

Templates: `reports/templates/`.

## analyze / tools

| Path | Usage |
|------|--------|
| `analyze/helper_grafo_interactivo.py` | vis.js graph HTML helpers |
| `analyze/extraer_entidades.py` | Entity extract for graph ingest |
| `tools/embed_readme_diagrams.py` | Sync diagram `<img>` in READMEs |

## Import pattern

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path("scripts/python").resolve()))
import db

con = db.connect()
sql_path = db.resolve_sql("ingest_identidades.sql")
```

Skills: [`ingest-data`](../../skills/ingest/ingest-data/SKILL.md) · SQL index: [`../sql/README.md`](../sql/README.md)
