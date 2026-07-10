# Shell scripts

| Script | Purpose |
|--------|---------|
| `bootstrap.sh` | MCP config, MCP check, and `db.py info` |
| `run_mcp.sh` | **MCP entrypoint** for Cursor/VS Code (→ `sh/mcp-serve.sh`) |
| `mcp-serve.sh` | DuckDB MCP stdio server (`uv run` → `db.py mcp-serve`) |
| `gitflow.sh` | Gitflow branch status, naming validation, merged-feature cleanup |
| `scrape_sociavault.sh` | SociaVault scrape + ingest + entities + classify (`--last N`) |

Run from repository root:

```bash
chmod +x scripts/sh/bootstrap.sh scripts/run_mcp.sh
./scripts/sh/bootstrap.sh
```

## DuckDB MCP

**Setup:** `./scripts/sh/bootstrap.sh` or `uv run python scripts/python/db.py mcp-config`

**Cursor:** Settings → MCP → enable `datasyn-duckdb` → Restart

**Query in chat** (MCP tools): *"List silver tables"*, *"Describe sv_tw_tweet"*, *"How many rows in silver.sv_tw_tweet?"*

**Before ingest** (Python writes): `uv run python scripts/python/db.py mcp-stop`

Full guide: [`skills/infra/configure-duckdb-mcp/SKILL.md`](../../skills/infra/configure-duckdb-mcp/SKILL.md)

Skills layout: [`docs/skills-layout.md`](../../docs/skills-layout.md)

### Troubleshooting `run_mcp.sh ENOENT`

If Cursor logs `spawn .../scripts/run_mcp.sh ENOENT`:

```bash
chmod +x scripts/run_mcp.sh scripts/sh/mcp-serve.sh
uv run python scripts/python/db.py mcp-config
```

Point Cursor MCP command to: `<repo>/scripts/run_mcp.sh`

## Gitflow helper

Branch model: `main` (production) · `develop` (integration) · `feature/*` · `release/*` · `hotfix/*`.

See [`skills/engineering/gitflow/SKILL.md`](../../skills/engineering/gitflow/SKILL.md) for the full workflow.

```bash
./scripts/sh/gitflow.sh status     # current branch, type, vs main/develop
./scripts/sh/gitflow.sh check      # validate branch name (exit 1 if invalid)
./scripts/sh/gitflow.sh branches   # list feature/* and merge status into develop
./scripts/sh/gitflow.sh cleanup    # delete local feature branches already merged into develop
```

**Start a feature:**

```bash
git checkout develop && git pull origin develop
git checkout -b feature/short-kebab-name
```

**Finish a feature** (after merge to `develop`):

```bash
git branch -d feature/short-kebab-name
git push origin --delete feature/short-kebab-name   # optional
```

## SociaVault scrape

```bash
./scripts/sh/scrape_sociavault.sh twitter myriambregman --last 10 --fetch-replies
```
