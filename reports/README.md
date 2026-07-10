# Report outputs

Agent-generated analysis files live here, grouped by **project** and **report bundle**:

```
reports/<project>/<report-slug>/
  report.html | report.md | report.pdf   # main deliverable
  data.json | grafo.json | …             # companion data (optional)
  README.md                              # methodology / interpretation (optional)
  assets/                                # CSV extracts, images (optional)
```

| Segment | Example | Rule |
|---------|---------|------|
| `<project>` | `redes`, `grafo`, `nyt` | Kebab-case domain or dataset slug |
| `<report-slug>` | `dashboard`, `sentiment-brief` | Kebab-case; one folder per report |

**Examples:**

```
reports/redes/dashboard/report.html
reports/redes/dashboard/data/*.csv
reports/grafo/co-ocurrencia/report.md
reports/nyt/sentiment-brief/report.md
```

Cross-links between bundles in the same project use relative paths when multiple bundles exist.

## Path helpers (`scripts/python/db.py`)

| Function | Returns |
|----------|---------|
| `get_report_bundle(project, slug)` | `reports/<project>/<slug>/` — **preferred** for multi-file reports |
| `get_report_path(project, name)` | `reports/<project>/<name>` — single loose file (legacy/simple) |

## Skills that write here

| Output type | Skill |
|-------------|-------|
| EDA, profiling, multi-format | [`statistical-report`](../skills/analyze/reports/statistical-report/SKILL.md) |
| Redes PTS dashboards | [`redes-analysis`](../skills/analyze/reports/redes-analysis/SKILL.md) |
| Text tone / framing | [`sentiment-analysis`](../skills/analyze/reports/sentiment-analysis/SKILL.md) |
| Network analysis (markdown) | [`graph-analysis`](../skills/analyze/graph/graph-analysis/SKILL.md) |
| Interactive HTML graphs | [`interactive-graph-reports`](../skills/analyze/graph/interactive-graph-reports/SKILL.md) |

This directory is **gitignored** (outputs may contain PII or scraped text). Commit skills and SQL only — see [`data-privacy`](../skills/engineering/data-privacy/SKILL.md).

Vocabulary: [`CONTEXT.md`](../CONTEXT.md).
