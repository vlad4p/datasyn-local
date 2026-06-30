# Shell scripts

| Script | Purpose |
|--------|---------|
| `bootstrap.sh` | MCP config, MCP check, and `db.py info` |
| `gitflow.sh` | Gitflow branch status, naming validation, merged-feature cleanup |

Run from repository root:

```bash
chmod +x scripts/sh/bootstrap.sh
./scripts/sh/bootstrap.sh
```

## Gitflow helper

Branch model: `main` (production) · `develop` (integration) · `feature/*` · `release/*` · `hotfix/*`.

See [`skills/gitflow/SKILL.md`](../../skills/gitflow/SKILL.md) for the full workflow.

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
