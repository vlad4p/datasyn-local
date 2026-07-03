# DuckDB storage

Default database: `data/duckdb/datasyn.duckdb` (gitignored).

Connect from Python: `scripts/python/db.py` → `db.connect()` or `db.connect_for_ingest()` for writes.

## Schemas (medallion)

| Schema | Zone | Populated by |
|--------|------|--------------|
| `bronze.*` | Raw ingest | [`ingest-data-bronze`](../../skills/ingest/bronze/ingest-data-bronze/SKILL.md) |
| `silver.*` | Clean, joined | [`ingest-data-silver`](../../skills/ingest/silver/ingest-data-silver/SKILL.md) |
| `gold.*` | Aggregates, KPIs | [`ingest-data-gold`](../../skills/ingest/gold/ingest-data-gold/SKILL.md) |

Sources land in `data/landing/` first. Router skill: [`ingest-data`](../../skills/ingest/ingest-data/SKILL.md).

## Query vs write

| Task | Tool |
|------|------|
| Reports, EDA, chat | MCP `query` (see [`configure-duckdb-mcp`](../../skills/infra/configure-duckdb-mcp/SKILL.md)) |
| DDL, MERGE, scrape ingest | `db.py run-sql --ingest` or `connect_for_ingest()` — stop MCP first (`db.py mcp-stop`) |

Vocabulary: [`CONTEXT.md`](../../CONTEXT.md).
