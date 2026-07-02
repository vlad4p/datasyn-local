# Skills layout

Task workflows live under [`skills/`](../skills/). Each skill is a folder with a `SKILL.md` file. Skills are grouped by **scope** (bucket), with optional **sub-scopes** for format or platform detail in `references/`.

## Agent docs

| File | Role |
|------|------|
| [`AGENTS.md`](../AGENTS.md) | Identity, plan-before-execute, MCP vs Python write split |
| [`CONTEXT.md`](../CONTEXT.md) | Shared vocabulary — medallion zones, report paths, tool split |
| [`skills/README.md`](../skills/README.md) | Full catalog and IDE setup |
| [`skills/datasyn-router/SKILL.md`](../skills/datasyn-router/SKILL.md) | User-invoked flow router (type `/datasyn-router` in supported IDEs) |

## Scope buckets

```
skills/
├── datasyn-router/          # user router
├── collect/                 # fetch → data/landing/
│   ├── web-scraping/
│   └── sociavault/          # sub-scope: FB, TW, IG, TT
├── ingest/                  # medallion: bronze → silver → gold
│   ├── ingest-data/         # router
│   ├── bronze/
│   ├── silver/
│   └── gold/
├── analyze/                 # reports and graphs
│   ├── reports/
│   └── graph/
├── schema/
│   └── create-table/
├── infra/                   # uv, MCP, optional Python helpers
└── engineering/             # gitflow, data-privacy
```

| Scope | Index | Router skill |
|-------|-------|--------------|
| Collect | [`collect/README.md`](../skills/collect/README.md) | `scrape-sociavault` |
| Ingest | [`ingest/README.md`](../skills/ingest/README.md) | `ingest-data` |
| Analyze | [`analyze/README.md`](../skills/analyze/README.md) | — |
| Schema | [`schema/README.md`](../skills/schema/README.md) | `create-table` |
| Infra | [`infra/README.md`](../skills/infra/README.md) | — |
| Engineering | [`engineering/README.md`](../skills/engineering/README.md) | — |

## Sub-scopes (`references/`)

Detail that does not need its own skill lives in `references/`:

| Path | Contents |
|------|----------|
| [`ingest/bronze/references/formats.md`](../skills/ingest/bronze/references/formats.md) | CSV, JSON, Parquet, XLSX load templates |
| [`collect/sociavault/references/`](../skills/collect/sociavault/references/count-limits.md) | `--last N`, shared scripts |
| [`collect/references/landing-paths.md`](../skills/collect/references/landing-paths.md) | Landing folder conventions |

Add a new leaf skill only when a workflow is end-to-end distinct (e.g. a new scrape source with its own script pipeline).

## Invocation

| Type | Frontmatter | Examples |
|------|-------------|----------|
| **User-invoked** | `disable-model-invocation: true` | `datasyn-router`, `gitflow`, `setup-uv`, `configure-duckdb-mcp` |
| **Model-invoked** | (default) | `ingest-data`, `scrape-sociavault`, `statistical-report`, `data-privacy` |

## IDE setup

```bash
ln -sfn "$(pwd)/skills" .cursor/skills   # Cursor
```

VS Code reads `skills/` directly. After adding or moving skills, re-run the symlink if your IDE caches paths.

## Adding a skill

1. Pick the scope bucket (e.g. `skills/analyze/reports/my-report/`).
2. Create `SKILL.md` with `name` and `description` in frontmatter.
3. Add the skill to the bucket `README.md` and [`skills/README.md`](../skills/README.md).
4. If user-facing flows change, update [`datasyn-router`](../skills/datasyn-router/SKILL.md).
