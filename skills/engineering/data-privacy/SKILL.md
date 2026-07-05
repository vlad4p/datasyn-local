---
name: data-privacy
description: >-
  Prevent data leaks in git and agent outputs. Use before commits, PRs,
  scrapes, ingest, or reports when handling PII, social exports, scraped
  content, DuckDB databases, or local datasets.
---

# Data privacy & git safety

**Goal:** keep sensitive data on the local machine only. Agents must never
commit, push, or paste raw datasets into git history, PRs, or commit messages.

## Never commit

| Category | Paths / patterns |
|----------|------------------|
| Raw data | `data/landing/**`, `.data/**`, `exports/`, `downloads/`, `tmp/` |
| Database | `data/duckdb/*.duckdb`, `*.duckdb`, `*.db`, `*.sqlite` |
| Reports | `reports/**` (outputs may contain PII or scraped text) |
| Secrets | `.env`, `*.pem`, `*.key`, `credentials.json`, `secrets.*`, `cookies.txt` |
| IDE local | `.cursor/mcp.json`, `.vscode/mcp.json`, `kilo.json` |

## Safe to commit

- Skills, SQL scripts, Python helpers (`scripts/python/`, `scripts/sql/`)
- Schema design and ingest **logic** (not the data files)
- `AGENTS.md`, `README.md`, docs
- `.gitkeep` and README files under `data/` and `reports/`

## What counts as sensitive in this project

- Social media exports (Facebook, Twitter/X): usernames, comments, posts
- Scraped news, boletines, contrataciones: full article text, emails, phones
- DuckDB tables derived from the above
- Reports and HTML graphs built from that data
- API keys, tokens, session cookies from scrapers

## Agent behavior

### Before any commit (user must ask first)

1. Run `git status` and `git diff` — inspect every staged file.
2. **Reject** commits that include paths from the "Never commit" table.
3. Warn the user if untracked data files exist beside the commit (they stay local).
4. Commit messages: describe the **change** (skill, SQL, script), not sample row content.

### During analysis

- Prefer aggregates and counts over dumping full rows in chat.
- When showing samples, use `LIMIT 3` and redact obvious PII (emails, phones, handles).
- Do not copy landing file contents into markdown reports in the repo root — write to `reports/<project>/` only.

### On scrape / ingest / report

- Save raw files to `data/landing/` (gitignored).
- Load into DuckDB locally; bronze/silver/gold tables live in the `.duckdb` file (gitignored).
- Write reports to `reports/<project>/` (gitignored).

## Pre-commit checklist

- [ ] `git diff --cached` shows no files under `data/landing/`, `data/duckdb/`, `reports/`, `.data/`
- [ ] No `.env`, credentials, or MCP config files
- [ ] No `*.csv`, `*.json`, `*.xlsx`, `*.parquet` data files (unless explicitly approved fixtures in `skills/` or `docs/`)
- [ ] Commit message contains no PII or raw data excerpts

## If data was committed by mistake

1. **Stop** — do not push.
2. Tell the user; they may need `git rm --cached <file>` or history rewrite.
3. Do not run `git push --force` to `main` unless the user explicitly requests it.

## Related

- `.gitignore` at repo root
- [`gitflow`](../gitflow/SKILL.md) — PR safety checklist
- [`AGENTS.md`](../../../AGENTS.md) — standards section
