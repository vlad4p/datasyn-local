---
name: datasyn-router
description: Route user requests to the right datasyn skill bucket and workflow.
disable-model-invocation: true
---

# datasyn router

Maps user intent → scope bucket → skill. Read [`CONTEXT.md`](../../CONTEXT.md) for shared vocabulary.

## Flow map

```
User request
     │
     ├─ collect / scrape / download ──→ collect/
     ├─ ingest / import / clean / join ──→ ingest/
     ├─ report / analyze / graph ──────→ analyze/
     ├─ schema / create table ─────────→ schema/
     ├─ setup / MCP / uv ──────────────→ infra/
     └─ git / commit / privacy ────────→ engineering/
```

## Collect

| User says | Skill |
|-----------|-------|
| Scrape a website, fetch URL | [`web-scraping`](../collect/web-scraping/SKILL.md) |
| Scrape redes / SociaVault / FB / IG / TikTok | [`scrape-sociavault`](../collect/sociavault/scrape-sociavault/SKILL.md) → platform skill |
| Scrape Twitter/X (canonical) | [`scrape-twikit-twitter`](../collect/twikit/scrape-twikit-twitter/SKILL.md) |

Bucket index: [`collect/README.md`](../collect/README.md)

## Ingest

| User says | Skill |
|-----------|-------|
| Ingest / import / load (unsure which zone) | [`ingest-data`](../ingest/ingest-data/SKILL.md) |
| Raw CSV/JSON/Parquet to DuckDB | [`ingest-data-bronze`](../ingest/bronze/ingest-data-bronze/SKILL.md) |
| Clean, dedupe, normalize, join | [`ingest-data-silver`](../ingest/silver/ingest-data-silver/SKILL.md) |
| Aggregate, KPIs, summaries | [`ingest-data-gold`](../ingest/gold/ingest-data-gold/SKILL.md) |
| Gold vistas redes Facebook | [`redes-gold`](../ingest/gold/redes-gold/SKILL.md) |

Bucket index: [`ingest/README.md`](../ingest/README.md)

## Analyze

| User says | Skill |
|-----------|-------|
| EDA, profile, statistical report | [`statistical-report`](../analyze/reports/statistical-report/SKILL.md) |
| Sentiment, tone, framing | [`sentiment-analysis`](../analyze/reports/sentiment-analysis/SKILL.md) |
| Redes PTS FB: trolls, ráfagas, HTML | [`redes-analysis`](../analyze/reports/redes-analysis/SKILL.md) |
| Troll blacklist / block list (twikit) | [`troll-blacklist`](../analyze/reports/troll-blacklist/SKILL.md) |
| Build graph tables | [`graph-ingest`](../analyze/graph/graph-ingest/SKILL.md) |
| Network analysis, centrality | [`graph-analysis`](../analyze/graph/graph-analysis/SKILL.md) |
| Interactive HTML graph | [`interactive-graph-reports`](../analyze/graph/interactive-graph-reports/SKILL.md) |

Bucket index: [`analyze/README.md`](../analyze/README.md)

## Schema

| User says | Skill |
|-----------|-------|
| Design table schema | [`create-table`](../schema/create-table/SKILL.md) |

## Infra

| User says | Skill |
|-----------|-------|
| Setup Python / uv | [`setup-uv`](../infra/setup-uv/SKILL.md) |
| Configure DuckDB MCP | [`configure-duckdb-mcp`](../infra/configure-duckdb-mcp/SKILL.md) |
| Add Python helper script | [`create-python-script`](../infra/create-python-script/SKILL.md) |

Bucket index: [`infra/README.md`](../infra/README.md)

## Engineering

| User says | Skill |
|-----------|-------|
| Before commit / PR / scrape with PII | [`data-privacy`](../engineering/data-privacy/SKILL.md) |
| Branch, release, PR workflow | [`gitflow`](../engineering/gitflow/SKILL.md) |

Bucket index: [`engineering/README.md`](../engineering/README.md)

## End-to-end examples

| Goal | Steps |
|------|-------|
| CSV → report | `ingest-data-bronze` → `ingest-data-silver` → `statistical-report` |
| Twitter scrape → analysis | `scrape-twikit-twitter` → classify → `troll-blacklist` / hater report |
| Entity network | `graph-ingest` → `graph-analysis` → optional `interactive-graph-reports` |
| Redes FB legacy → dashboard | `redes-gold` → `redes-analysis` (HTML + grafo) |
