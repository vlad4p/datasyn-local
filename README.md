<div align="center">

# 📰 datasyn-local

**Investigate with data on your own machine** — no data-science background required.

<p>
  <span style="background:#0e2d58;color:#fffceb;padding:4px 10px;border-radius:4px;font-weight:600">🤖 AI assistant</span>
  <span style="background:#559778;color:#fffceb;padding:4px 10px;border-radius:4px;font-weight:600">🗄️ DuckDB</span>
  <span style="background:#395a8e;color:#fffceb;padding:4px 10px;border-radius:4px;font-weight:600">🔌 MCP</span>
</p>

*Also available in [Español neutro](README.es.md)*

</div>

---

## At a glance

You collect sources → the assistant stores originals → DuckDB holds structured tables → reports hold your findings. **You never need to write SQL or Python.**

![From source to story — collect, landing, DuckDB, reports](docs/diagrams/flow.svg)

| | |
|---|---|
| **You** | Journalist, researcher, investigator |
| **Assistant** | Cursor, Claude Code, etc. + [skills](skills/) |
| **Rules** | [AGENTS.md](AGENTS.md) — provenance, method, evidence, limits |

---

## ✨ Who is this for?

**Journalists, researchers, and curious investigators** who work with sources, documents, and public records — not necessarily with SQL or Python.

You bring the questions and the story. **Your AI assistant** handles setup with the **startup prompt** below. Day-to-day work uses **[skills](skills/)**; tone and rules live in **[AGENTS.md](AGENTS.md)**.

> **You do not need to be a data analyst.** Keep raw files, ask in plain language, and let the assistant ingest, query, and draft reports.

---

## 🧭 How it works

### Principles

| Principle | What it means for you |
|-----------|------------------------|
| **Preserve originals** | Downloads and scrapes stay in `data/landing/` — never overwritten |
| **Speak, don’t code** | You ask in plain language; **skills** turn requests into DuckDB SQL (via MCP) |
| **Stay auditable** | Every answer states *what the data shows*, *how we know*, and *the limits* |

### Figure 1 — Data pipeline

The assistant picks the right **skill** at each stage (orange = raw files, green = database, navy = reports).

![Data pipeline: web-scraping → landing → ingest-data → DuckDB → reports](docs/diagrams/flow.svg)

| Step | You | Skill | Output |
|:----:|-----|-------|--------|
| 1 | Save downloads, scrapes, exports | `web-scraping` | `data/landing/` |
| 2 | Ask to “ingest” a file | `ingest-data` | DuckDB table |
| 3 | Ask questions in plain language | SQL + MCP | answers in chat |
| 4 | Request analysis or a report | `statistical-report` / `sentiment-analysis` | `reports/` |

### Figure 2 — One request, end to end

One message (“ingest this file and summarize it”) follows the same path every time:

![Request lifecycle: ask → AGENTS.md → SQL via MCP → report → auditable answer](docs/diagrams/request-lifecycle.svg)

### Figure 3 — Repository map

Left: configuration and agent behavior. Right: your evidence and published output.

![Repository map: AGENTS.md, skills, db.py vs landing, duckdb, reports](docs/diagrams/repo-layout.svg)

---

## 📌 Requirements

- **Python 3.11+** (installed by the assistant if needed)
- **[uv](https://docs.astral.sh/uv/)** — Python environment (configured by the startup prompt)
- **An AI assistant with skills** (e.g. Cursor)

---

## 🚀 Startup — copy this prompt

### Figure 4 — First-time setup

Clone the repo, paste the prompt below, follow the assistant’s summary.

![Startup flow: clone → paste prompt → assistant runs bootstrap → ready](docs/diagrams/startup.svg)

1. **Clone** this repo and open it in your IDE.
2. **Paste** the block below into the assistant chat.
3. **Follow** the summary — you should not need to run commands yourself.

<details>
<summary><strong>📋 Click to expand the startup prompt</strong></summary>

```text
Bootstrap datasyn-local in this workspace. The user is a journalist/researcher, not a data engineer — explain steps in plain language.

0. Configure the uv environment first:
   - If uv is missing: install it (curl -LsSf https://astral.sh/uv/install.sh | sh or brew install uv)
   - From the repo root: uv sync --all-extras
   - Verify: uv --version and uv run python -c "import duckdb; print('duckdb', duckdb.__version__)"

1. Read AGENTS.md and skills/README.md (use setup-uv skill if more detail is needed).

2. If using Cursor: link skills with ln -sfn "$(pwd)/skills" .cursor/skills

3. Run infrastructure bootstrap from repo root:
   chmod +x scripts/sh/bootstrap.sh
   ./scripts/sh/bootstrap.sh
   (MCP config, MCP check, and database status.)

Rules: ingest and reports are skills (SQL), not extra Python apps. External files always go to data/landing/ first. Summarize each step for a non-technical reader.
```

</details>

### ✅ After the assistant finishes

| | You should have |
|---|-----------------|
| 🐍 | `uv` + `.venv` with dependencies |
| 🔌 | `.cursor/mcp.json` (local, gitignored) |
| 🛠️ | `skills/` linked for your IDE |
| 🗄️ | MCP connected to `data/duckdb/datasyn.duckdb` |

---

## 🗞️ Full example — headlines to sentiment

### Figure 5 — One prompt, full investigation

**Scrape → ingest → sentiment report** in a single chat message:

![Investigation example: NYT scrape → nyt_news table → sentiment report](docs/diagrams/investigation-example.svg)

Paste into the assistant:

```text
Run a full pipeline for me, explaining each step in plain language:

1. Scrape recent New York Times news headlines (web-scraping skill) and
   save the raw results to data/landing/ — keep the source URL and the
   capture date for provenance.
2. Ingest that file into DuckDB as a table called nyt_news
   (ingest-data skill). Then show COUNT(*), DESCRIBE, and 5 sample rows.
3. Run a sentiment analysis on the headline/summary text
   (sentiment-analysis skill) and write a markdown report to reports/
   with: overall tone, a positive/neutral/negative breakdown, a few
   representative quotes, and the limits of the method.

Remember: external files go to data/landing/ first, ingest and reports
are skills (DuckDB SQL), and tell me what the data shows, how we know,
and what the caveats are.
```

> ⚖️ **Sources:** respect each site's terms and `robots.txt`; prefer official feeds or APIs when available. The assistant records source URL and capture date so findings stay auditable.

---

## 📊 All diagrams

| Diagram | File |
|---------|------|
| Data pipeline | [docs/diagrams/flow.svg](docs/diagrams/flow.svg) |
| Request lifecycle | [docs/diagrams/request-lifecycle.svg](docs/diagrams/request-lifecycle.svg) |
| Repository map | [docs/diagrams/repo-layout.svg](docs/diagrams/repo-layout.svg) |
| Startup | [docs/diagrams/startup.svg](docs/diagrams/startup.svg) |
| Full investigation example | [docs/diagrams/investigation-example.svg](docs/diagrams/investigation-example.svg) |
