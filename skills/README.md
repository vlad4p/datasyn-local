# Skills

Task workflows for AI assistants. **No Python scripts** — the agent runs DuckDB SQL and writes outputs following these guides.

## Configure in your AI assistant

Copy or link this folder into your tool’s skills directory:

| Tool | Typical path |
|------|----------------|
| **Cursor** | `.cursor/skills/` → symlink: `ln -sfn "$(pwd)/skills" .cursor/skills` |
| **Claude Code** | `.claude/skills/` or project skills setting |
| **Other** | Follow your client’s docs for project-level `SKILL.md` folders |

**First-time setup:** copy the bootstrap prompt from [`README.md`](../README.md) or [`README.es.md`](../README.es.md).

**Ongoing behavior:** [`AGENTS.md`](../AGENTS.md), not here.

## Catalog

| Skill | When to use |
|-------|-------------|
| [`ingest-data`](ingest-data/SKILL.md) | Load landing files into DuckDB (many formats) |
| [`statistical-report`](statistical-report/SKILL.md) | EDA and reports (many output formats) |
| [`sentiment-analysis`](sentiment-analysis/SKILL.md) | Text tone / framing reports |
| [`web-scraping`](web-scraping/SKILL.md) | Fetch data to `data/landing/` |
| [`create-table`](create-table/SKILL.md) | Schema design |
| [`configure-duckdb-mcp`](configure-duckdb-mcp/SKILL.md) | MCP server setup |
| [`setup-uv`](setup-uv/SKILL.md) | Python environment |
| [`create-python-script`](create-python-script/SKILL.md) | Optional code in `scripts/python/` |
