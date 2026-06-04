# Security and privacy

## Intended use

**datasyn-local** is a **single-user, local-first** toolkit. DuckDB, landing files, reports, and `.logs/` stay on your machine unless you copy them elsewhere.

Do **not** expose the MCP server or DuckDB file to untrusted networks without additional hardening.

## Before making the repository public

### 1. Local files (never commit)

| Path | Risk |
|------|------|
| `.env` | Secrets and path overrides |
| `data/duckdb/*.duckdb` | Your actual data |
| `data/landing/*` | Raw scrapes and exports |
| `reports/*` | Analysis output |
| `.logs/*.jsonl` | Action traces (paths, queries) |
| `.cursor/mcp.json` | **Absolute paths** to your home directory |
| `kilo.json` | IDE config with machine-specific paths |

Generate MCP config locally only:

```bash
make mcp-config
```

### 2. Git history

If you ever committed `.cursor/mcp.json` with your home path or used a personal email as author, **scrub history before the first public push**:

```bash
# Example: remove mcp.json from all history
pip install git-filter-repo
git filter-repo --path .cursor/mcp.json --invert-paths

# Or start a fresh orphan branch with a clean tree
```

Review history before publishing:

```bash
git log -p -S '/Users/'
git log --format='%ae' | sort -u   # author emails in commits
```

If anything sensitive was committed, rewrite history (`git filter-repo`) or squash into a clean initial commit **before** the first public push.

### 3. MCP exposure

`scripts/mcp_server.py` publishes **all tables** in your DuckDB database to any MCP client that can launch the server (e.g. Cursor). Only enable MCP for projects you trust.

## Fixed risks in this codebase

| Issue | Mitigation |
|-------|------------|
| SQL injection via table name in `ingest` / `report` | `validate_table_name()` + quoted identifiers; file paths via bound parameters |
| Ingest from arbitrary paths | `resolve_landing_file()` requires files under `data/landing/` |
| Absolute paths in reports | Reports reference DB filename only, not full home path |
| Personal MCP paths in repo | `.cursor/mcp.json` gitignored; use `mcp.json.example` + `make mcp-config` |

## Residual risks (by design)

| Area | Note |
|------|------|
| `make sql QUERY='...'` | Runs arbitrary SQL on your local DB — expected for power users |
| Web scraping skills | Respect target sites' terms; no built-in rate limiting |
| Trace logs | May contain table names and relative paths; keep `.logs/` private |
| Third-party extensions | `duckdb_mcp` and `excel` load from DuckDB community — pin versions in production |

## Reporting

Open a GitHub security advisory or issue if you find a vulnerability in this template (not in your private data).
