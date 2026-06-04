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

## ✨ Who is this for?

**Journalists, researchers, and curious investigators** who work with sources, documents, and public records — not necessarily with SQL or Python.

You bring the questions and the story. **Your AI assistant** (Cursor, Claude Code, etc.) handles setup using a **startup prompt** below. Day-to-day workflows live in **[skills](skills/)**; tone and rules in **[AGENTS.md](AGENTS.md)**.

> **You do not need to be a data analyst.** Keep raw files, ask plain-language questions, and let the assistant ingest, query, and draft reports.

---

## 🧭 How it works (simple)

<p align="center">
  <img src="docs/diagrams/flow.svg" alt="From source to story: collect → landing → DuckDB → reports" width="780" />
</p>

| Step | What you do | What the machine does |
|------|-------------|------------------------|
| 1 | Save downloads, scrapes, exports | Stores originals in `data/landing/` |
| 2 | Ask the assistant to “ingest” a file | Loads a table in DuckDB (via **ingest-data** skill) |
| 3 | Ask questions in plain language | SQL + MCP behind the scenes |
| 4 | Request a report | Writes markdown/JSON/HTML under `reports/` (**statistical-report** skill) |

### 🔄 What happens behind one request

<p align="center">
  <img src="docs/diagrams/request-lifecycle.svg" alt="How one request becomes an auditable answer" width="520" />
</p>

---

## 🗂️ What goes where

<p align="center">
  <img src="docs/diagrams/repo-layout.svg" alt="Repository layout: the brain vs your data" width="700" />
</p>

| | Piece | Location |
|---|--------|----------|
| ✨ | **Startup prompt** | This README ↓ |
| 📋 | **Agent behavior** | [`AGENTS.md`](AGENTS.md) |
| 🛠️ | **Task guides** | [`skills/`](skills/) — configure in your IDE |
| 🗄️ | **Database + MCP** | [`scripts/python/db.py`](scripts/python/db.py) |
| 📁 | **Raw evidence** | `data/landing/` |
| 💾 | **Structured data** | `data/duckdb/datasyn.duckdb` |
| 📊 | **Published output** | `reports/` |

---

## 📌 Requirements

- **Python 3.11+** (installed by the assistant if needed)
- **[uv](https://docs.astral.sh/uv/)** — fast Python environment tool (the prompt configures it)
- **An AI assistant with skills** (e.g. Cursor)

---

## 🚀 Startup — copy this prompt

1. **Clone** this repo and open it in your IDE.  
2. **Paste** the block below into the assistant chat.  
3. **Follow** the assistant’s summary — you should not need to run commands yourself.

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

If there are no tables, propose a demo:
- cp samples/example.csv data/landing/demo.csv
- ingest with ingest-data skill (DuckDB SQL only)
- markdown EDA report with statistical-report skill

Rules: ingest and reports are skills (SQL), not extra Python apps. External files always go to data/landing/ first. Summarize each step for a non-technical reader.
```

</details>

### ✅ After the assistant finishes

| | You should have |
|---|-----------------|
| 🐍 | `uv` + `.venv` with dependencies |
| 🔌 | `.cursor/mcp.json` (local, gitignored) |
| 🛠️ | `skills/` linked for your IDE |
| 📊 | Optional demo table `demo` + a sample report |

---

## 💬 After startup — example requests

Say things like:

| 💬 You say | 🛠️ Skill used |
|-----------|--------------|
| *“Ingest `data/landing/interviews.csv` as interviews”* | `ingest-data` |
| *“Profile the interviews table — markdown summary”* | `statistical-report` |
| *“Check if MCP is connected”* | `configure-duckdb-mcp` |

The assistant reads **AGENTS.md** each session and picks the right skill.

---

## 📂 Project layout

```text
datasyn-local/
├── 📋 AGENTS.md              ← agent rules (sessions)
├── 📖 README.md / README.es.md
├── 🛠️ skills/
├── scripts/
│   ├── python/db.py          ← database + MCP
│   └── sh/bootstrap.sh       ← one-shot setup script
├── 📁 data/landing/          ← raw files (your sources)
├── 💾 data/duckdb/           ← local database
├── 📊 reports/               ← your written output
└── 📄 samples/example.csv    ← safe demo file
```

---

## 🎨 Brand palette (datasyn)

Light, editorial look from [`docs/colors/`](docs/colors/):

| Role | Color | Hex | Use in this repo |
|------|-------|-----|------------------|
| Background | Ivory | `#fffceb` | Calm canvas |
| Ink | Ink | `#49443b` | Headings, borders |
| Muted | Grey | `#7e7f7e` | Secondary text |
| **AI / agent** | Navy | `#0e2d58` | Assistant, prompts |
| **SQL / DuckDB** | Green | `#559778` | Database, success |
| **UI / tools** | Blue | `#395a8e` | IDE, brain |
| **Storage / landing** | Orange | `#de6433` | Raw files |
| Warning | Yellow | `#f4bd48` | Caution notes |
| Error | Red | `#a33a29` | Failures |

<p align="center">
  <img src="docs/colors/core-palette.svg" alt="datasyn core palette" width="720" />
</p>
