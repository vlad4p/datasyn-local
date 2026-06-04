# Scripts

CLI utilities run with **uv** from the repository root:

```bash
uv run python scripts/ingest.py data/landing/foo.csv my_table
uv run python scripts/stat_report.py my_table
uv run python scripts/mcp_server.py --check
```

Or via Makefile: `make ingest`, `make report`, `make mcp-check`.

| Script | Purpose |
|--------|---------|
| `ingest.py` | CSV / JSON / XLSX → DuckDB |
| `stat_report.py` | DESCRIBE + SUMMARIZE → `reports/` |
| `mcp_server.py` | DuckDB MCP stdio server |
| `configure_mcp.py` | Write local `.cursor/mcp.json` (`make mcp-config`) |
| `run_mcp.sh` | MCP launcher for Cursor |

Shared logic belongs in `src/`; scripts stay thin entry points.
