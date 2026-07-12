# Skills

Task workflows for AI assistants. **No Python scripts** — the agent runs DuckDB SQL and writes outputs following these guides.

Shared vocabulary: [`CONTEXT.md`](../CONTEXT.md). Agent behavior: [`AGENTS.md`](../AGENTS.md). Layout guide: [`docs/skills-layout.md`](../docs/skills-layout.md).

## Configure in your AI assistant

Copy or link this folder into your tool's skills directory:

| Tool | Typical path |
|------|----------------|
| **Cursor** | `.cursor/skills/` → symlink: `ln -sfn "$(pwd)/skills" .cursor/skills` |
| **Claude Code** | `.claude/skills/` or project skills setting |
| **Other** | Follow your client's docs for project-level `SKILL.md` folders |

**First-time setup:** copy the bootstrap prompt from [`README.md`](../README.md).

## User-invoked

| Skill | Purpose |
|-------|---------|
| [`datasyn-router`](datasyn-router/SKILL.md) | Map user intent → bucket → skill |
| [`setup-uv`](infra/setup-uv/SKILL.md) | Python environment with uv |
| [`configure-duckdb-mcp`](infra/configure-duckdb-mcp/SKILL.md) | MCP server setup; Quack client |
| [`host-quack`](infra/host-quack/SKILL.md) | Host local datasyn.duckdb as Quack warehouse |
| [`gitflow`](engineering/gitflow/SKILL.md) | Branching, releases, PRs |

## Scope buckets

| Scope | Index | Router skill |
|-------|-------|--------------|
| **Collect** | [`collect/README.md`](collect/README.md) | [`scrape-sociavault`](collect/sociavault/scrape-sociavault/SKILL.md) |
| **Ingest** | [`ingest/README.md`](ingest/README.md) | [`ingest-data`](ingest/ingest-data/SKILL.md) |
| **Analyze** | [`analyze/README.md`](analyze/README.md) | — |
| **Schema** | [`schema/README.md`](schema/README.md) | — |
| **Infra** | [`infra/README.md`](infra/README.md) | — |
| **Engineering** | [`engineering/README.md`](engineering/README.md) | — |

## Full catalog (model-invoked)

### Collect

| Skill | When to use |
|-------|-------------|
| [`web-scraping`](collect/web-scraping/SKILL.md) | Fetch data to `data/landing/` |
| [`scrape-sociavault`](collect/sociavault/scrape-sociavault/SKILL.md) | SociaVault pipeline entry |
| [`scrape-sociavault-facebook`](collect/sociavault/scrape-sociavault-facebook/SKILL.md) | Facebook via SociaVault |
| [`scrape-sociavault-twitter`](collect/sociavault/scrape-sociavault-twitter/SKILL.md) | X/Twitter via SociaVault (**deprecated** — use twikit) |
| [`scrape-twikit-twitter`](collect/twikit/scrape-twikit-twitter/SKILL.md) | X/Twitter via twikit (canonical) |
| [`scrape-sociavault-instagram`](collect/sociavault/scrape-sociavault-instagram/SKILL.md) | Instagram via SociaVault |
| [`scrape-sociavault-tiktok`](collect/sociavault/scrape-sociavault-tiktok/SKILL.md) | TikTok via SociaVault |

### Ingest

| Skill | Zone | When to use |
|-------|------|-------------|
| [`ingest-data`](ingest/ingest-data/SKILL.md) | Entry | Route to bronze/silver/gold |
| [`ingest-data-bronze`](ingest/bronze/ingest-data-bronze/SKILL.md) | `bronze.*` | Raw files → DuckDB |
| [`ingest-data-silver`](ingest/silver/ingest-data-silver/SKILL.md) | `silver.*` | Clean, dedupe, join |
| [`ingest-data-gold`](ingest/gold/ingest-data-gold/SKILL.md) | `gold.*` | Aggregate, KPIs |
| [`redes-gold`](ingest/gold/redes-gold/SKILL.md) | `gold.*` | FB legacy: sentimiento, trolls, grafos |

Sub-scope: [`ingest/bronze/references/formats.md`](ingest/bronze/references/formats.md)

### Analyze

| Skill | When to use |
|-------|-------------|
| [`statistical-report`](analyze/reports/statistical-report/SKILL.md) | EDA and multi-format reports |
| [`sentiment-analysis`](analyze/reports/sentiment-analysis/SKILL.md) | Text tone / framing |
| [`social-monitor`](analyze/reports/social-monitor/SKILL.md) | Unified multi-platform monitoring (persona → accounts) |
| [`redes-analysis`](analyze/reports/redes-analysis/SKILL.md) | FB legacy dashboards, trolls, HTML |
| [`troll-blacklist`](analyze/reports/troll-blacklist/SKILL.md) | Twikit block/watch list (manual) |
| [`graph-ingest`](analyze/graph/graph-ingest/SKILL.md) | Build graph tables |
| [`graph-analysis`](analyze/graph/graph-analysis/SKILL.md) | Network metrics and reports |
| [`interactive-graph-reports`](analyze/graph/interactive-graph-reports/SKILL.md) | HTML graph visualizations |

### Schema

| Skill | When to use |
|-------|-------------|
| [`create-table`](schema/create-table/SKILL.md) | Schema design |

### Infra

| Skill | When to use |
|-------|-------------|
| [`create-python-script`](infra/create-python-script/SKILL.md) | Optional code in `scripts/python/` |

### Engineering

| Skill | When to use |
|-------|-------------|
| [`data-privacy`](engineering/data-privacy/SKILL.md) | Prevent data leaks before commits/PRs |
