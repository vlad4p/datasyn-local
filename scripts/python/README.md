# Python scripts

Optional helpers under `scripts/python/`. **Ingest and reports are skills (SQL)** — these scripts support MCP, scraping, classification, and report export.

## Core

| Script | Usage |
|--------|--------|
| `db.py` | DuckDB paths, connection, MCP (`mcp-config`, `mcp-serve`, `run-sql`) |
| `classify_sv_comments.py` | LLM classification for SociaVault comments (`LLM_API_KEY` in `.env`) |
| `classify_tk_tw_replies.py` | Batch LLM classify twikit replies + hater narrative clusters (`CHAT_MODEL`/`LLM_MODEL`) |
| `embed_readme_diagrams.py` | Sync diagram `<img>` tags in README files from `docs/diagrams/*.svg` |

```bash
uv run python scripts/python/db.py info
uv run python scripts/python/db.py mcp-check
uv run python scripts/python/db.py mcp-config
uv run python scripts/python/db.py mcp-serve   # Cursor MCP (stdio)
```

## SociaVault scrape

| Script | Usage |
|--------|--------|
| `sociavault_client.py` | SociaVault REST API client (`SOCIAVAULT_API_KEY`) |
| `sociavault_scrape_common.py` | Shared landing paths, manifest, ingest helpers |
| `scrape_sociavault_facebook.py` | Facebook → `data/landing/redes/sociavault/facebook/` |
| `scrape_sociavault_twitter.py` | X/Twitter via SociaVault (**deprecated** — prefer twikit) |
| `scrape_sociavault_instagram.py` | Instagram → `data/landing/redes/sociavault/instagram/` |
| `scrape_sociavault_tiktok.py` | TikTok → `data/landing/redes/sociavault/tiktok/` |

```bash
uv run python scripts/python/scrape_sociavault_twitter.py \
  --handle myriambregman --last 10 --fetch-replies --ingest-full

./scripts/sh/scrape_sociavault.sh twitter myriambregman --last 10 --fetch-replies
```

Skill: [`scrape-sociavault`](../../skills/collect/sociavault/scrape-sociavault/SKILL.md)

## Twikit scrape (X session)

| Script | Usage |
|--------|--------|
| `scrape_twikit_twitter.py` | X/Twitter via twikit → `data/landing/redes/twikit/twitter/` |

```bash
# Auth: TWITTER_USERNAME / TWITTER_PASSWORD in .env (cookies saved to .data/)
uv run python scripts/python/scrape_twikit_twitter.py \
  --handle myriambregman --last 10 --fetch-replies
```

Skill: [`scrape-twikit-twitter`](../../skills/collect/twikit/scrape-twikit-twitter/SKILL.md)

```bash
# Classify replies + cluster hater narratives (batch LLM)
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_tk_tw_classification.sql
uv run python scripts/python/classify_tk_tw_replies.py --batch-size 50 --cluster-haters
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_tk_hater_narrativa.sql
# Refresh Twitter account catalog (is_hater + profile fields)
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_twikit_twitter_silver.sql
uv run python scripts/python/generate_tk_hater_clusters_report.py
# Auditable troll blacklist (no auto-block on X)
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_tk_troll_blacklist.sql
uv run python scripts/python/generate_tk_troll_blacklist_report.py
```

## Redes reports (legacy Facebook CSV)

Skill: [`redes-analysis`](../../skills/analyze/reports/redes-analysis/SKILL.md). Gold SQL: `scripts/sql/ingest_redes_gold.sql` (FB-only).  
Unified monitor: [`social-monitor`](../../skills/analyze/reports/social-monitor/SKILL.md) — `ingest_identidades.sql` + `ingest_social_monitor_gold.sql`.

| Script | Output bundle under `reports/` |
|--------|--------------------------------|
| `generate_social_monitor_dashboard.py` | `monitor/dashboard/` — unified persona monitor (Chart.js + vis.js) |
| `generate_redes_dashboard.py` | `redes/dashboard/` — Chart.js + vis.js dashboard |
| `export_redes_reports_zip.py` | `redes/_exports/export_{date}.zip` |
| `generate_tk_hater_clusters_report.py` | `twikit-myriam/hater-clusters/` |
| `generate_tk_troll_blacklist_report.py` | `twikit-myriam/troll-blacklist/` |

## Graph helpers

| Script | Usage |
|--------|--------|
| `helper_grafo_interactivo.py` | Export graph JSON + HTML (vis.js / Chart.js) |
| `grafo_interactivo.py` | Build interactive graph from landing JSON or DB |
| `extraer_entidades.py` | Extract entities for graph ingest |
| `analisis_entidades_grafo.py` | Entity graph analysis pipeline |

Skill: [`interactive-graph-reports`](../../skills/analyze/graph/interactive-graph-reports/SKILL.md)

## Boletín / contrataciones

| Script | Usage |
|--------|--------|
| `boletin_scraper.py` | Scrape Boletín Oficial avisos |
| `scrape_boletin.py` | Landing + ingest wrapper |
| `boletin_contrataciones_scraper.py` | Contrataciones scrape |
| `scrape_contrataciones.py` | Landing + ingest wrapper |
| `analizar_contrataciones.py` | Parse contrataciones PDFs |
| `analizar_pdfs_contrataciones.py` | PDF text extraction |

Shell wrappers: `scripts/sh/scrape_boletin_diario.sh`, `scripts/sh/scrape_contrataciones_diario.sh`

## Import from repo root

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path("scripts/python").resolve()))
import db

con = db.connect()
```

Skills: [`ingest-data`](../../skills/ingest/ingest-data/SKILL.md) · layout: [`docs/skills-layout.md`](../../docs/skills-layout.md)
