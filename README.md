# datasyn-local

**Investigate with data on your own machine.** You ask questions in plain language. Your AI assistant does the technical work — you do not write SQL or Python.

*Also available in [Español neutro](README.es.md)*

---

## Who is this for?

Journalists, researchers, and investigators who work with documents, downloads, and public records. You bring the story and the questions. The assistant handles setup, queries, and reports.

---

## How this repo works (step by step)

This project is a **workspace on your computer**. Data moves in one direction: **collect → store originals → load into a database → analyze → write reports**. You never edit the database by hand — you talk to the assistant.

### The full path (overview)

Every investigation follows the same route:

<p align="center"><img src="docs/diagrams/flow.svg" alt="From source to story — collect, landing, DuckDB, reports" width="860"/></p>

| Stage | What happens | Where it lives |
|-------|----------------|----------------|
| **Collect** | You download, export, or ask the assistant to scrape a site | Assistant uses the `web-scraping` skill |
| **Landing** | Raw files are saved **unchanged** (your evidence) | `data/landing/` |
| **Database** | The assistant loads files into queryable tables | `data/duckdb/datasyn.duckdb` |
| **Reports** | Analysis and write-ups you can cite | `reports/` |

The assistant chooses the right **skill** for each step (see [Step 6](#step-6--ask-for-a-report)). Rules and tone are in [AGENTS.md](AGENTS.md).

---

### Step 1 — Set up the workspace (one time)

You only do this once per machine.

1. **Clone** this repository and open the folder in your IDE (Cursor, Claude Code, or similar).
2. **Open a chat** with your AI assistant in that folder.
3. **Paste** the startup prompt below and send it. The assistant installs tools, links skills, and connects the database — you follow its summary in plain language.

<p align="center"><img src="docs/diagrams/startup.svg" alt="First-time setup — clone, paste prompt, bootstrap, ready" width="520"/></p>

<details>
<summary><strong>Startup prompt — click to copy</strong></summary>

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

**When setup is done, you should have:**

- A Python environment (`uv` + `.venv`)
- Skills linked so the assistant knows how to ingest and report
- A connection from the IDE to your local DuckDB file (via MCP)
- An empty or ready database at `data/duckdb/datasyn.duckdb`

You do not need to run terminal commands yourself if the assistant completed the prompt.

---

### Step 2 — Know where things go

The repo has two sides: **how the assistant thinks** (left) and **your data** (right).

<p align="center"><img src="docs/diagrams/repo-layout.svg" alt="datasyn repository layout — agent config and your data folders" width="680"/></p>

| Folder / file | Your role |
|---------------|-----------|
| `data/landing/` | Put every new file here first — CSV, JSON, HTML exports, scrapes. Originals stay here. |
| `data/duckdb/datasyn.duckdb` | The assistant loads tables here. You query through chat, not by opening the file. |
| `reports/` | Finished write-ups (markdown, HTML, etc.) the assistant saves for you. |
| `skills/` | Instructions for the assistant (ingest, scrape, reports). You configure once; you do not edit these for normal work. |
| `AGENTS.md` | How the assistant should answer: evidence, method, limits. |

**Important:** Anything from outside the repo (download, scrape, export) goes to **`data/landing/` first**, then you ask to ingest.

---

### Step 3 — Collect your sources

**What you do:** Save files, or ask the assistant to fetch data from the web.

**Examples of what to say:**

- “Download this CSV to landing and note the source URL.”
- “Scrape headlines from [site] and save the raw result to `data/landing/` with the capture date.”

**What the assistant does:** Uses the `web-scraping` skill (or saves your upload) and keeps **provenance** — source URL, date, original format.

**Result:** New files in `data/landing/` only. Nothing is overwritten.

---

### Step 4 — Ingest into the database

**What you do:** Ask to load a landing file into DuckDB.

**Example:**

> “Ingest `data/landing/my_export.csv` as a table called `contracts_2024`. Show row count, schema, and five sample rows.”

**What the assistant does:** Uses the `ingest-data` skill (SQL via MCP). Validates with `COUNT(*)`, `DESCRIBE`, and samples.

**Result:** A table inside `data/duckdb/datasyn.duckdb` you can question in the next steps.

---

### Step 5 — Explore and ask questions

**What you do:** Ask in plain language — counts, filters, comparisons, duplicates, trends.

**Examples:**

- “How many rows per year?”
- “List the ten largest amounts and which source file they came from.”
- “Are there missing values in the `date` column?”

**What the assistant does:** Runs SQL on DuckDB through MCP and answers in chat. Good answers include **what the data shows**, **how we know** (query or table), and **limits** (sample size, missing fields, bias).

You still do not write SQL yourself.

---

### Step 6 — Ask for a report

**What you do:** Request a structured output when you need something to share or archive.

**Examples:**

- “Write a statistical summary of `contracts_2024` to `reports/`.”
- “Run sentiment on the `headline` column and save a markdown report with quotes and caveats.”

**What the assistant does:** Uses `statistical-report` or `sentiment-analysis` (and related skills). Saves the file under `reports/`.

**Result:** A document you can open, link, or cite — with method and limitations spelled out.

---

### Step 7 — What happens when you send one message

Whether you ingest one file or run a full investigation, **each request** follows the same path inside the assistant:

<p align="center"><img src="docs/diagrams/request-lifecycle.svg" alt="One request — plain language to auditable answer via MCP" width="560"/></p>

1. **You** type a normal-language request.  
2. **Assistant** reads [AGENTS.md](AGENTS.md) and picks a skill (`ingest-data`, `web-scraping`, `sentiment-analysis`, …).  
3. **Assistant** runs SQL on your local DuckDB (MCP).  
4. **Assistant** writes to `reports/` when you asked for a report.  
5. **You** get an answer you can audit: findings, how they were derived, and what not to overclaim.

---

### Step 8 — Run a full example (scrape → ingest → report)

Once setup is done, you can do the whole pipeline in **one chat message**. The diagram below is the NYT headline example; you can swap the source for your own story.

<p align="center"><img src="docs/diagrams/investigation-example.svg" alt="Full investigation — scrape, ingest, sentiment report" width="720"/></p>

Paste this into the assistant:

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

Respect each website’s terms and `robots.txt`; prefer official APIs or feeds when they exist.

---

## Quick reference

### What you need before starting

- An AI assistant that supports **project skills** (e.g. Cursor)
- **Python 3.11+** and **[uv](https://docs.astral.sh/uv/)** — the assistant installs these during Step 1 if missing

### Skills the assistant uses (you only ask; it reads the guides)

| Ask for… | Skill |
|----------|--------|
| Fetch or save web data | `web-scraping` |
| Load a landing file into DuckDB | `ingest-data` |
| Tables, charts, numeric summaries | `statistical-report` |
| Tone and framing of text | `sentiment-analysis` |
| Design a new table layout | `create-table` |

Full list: [skills/README.md](skills/README.md).

### Three rules to remember

1. **Originals first** — `data/landing/` before ingest.  
2. **Plain language** — you ask; the assistant runs SQL.  
3. **Auditable answers** — what the data shows, how we know, what the limits are ([AGENTS.md](AGENTS.md)).

### Diagram files

Diagram sources: [`docs/diagrams/`](docs/diagrams/) — `flow.svg`, `startup.svg`, `repo-layout.svg`, `request-lifecycle.svg`, `investigation-example.svg`.
