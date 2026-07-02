# Report outputs

Agent-generated analysis files live here, grouped by project:

```
report/<project>/<report-name>
```

| Segment | Example | Notes |
|---------|---------|--------|
| `<project>` | `redes`, `grafo`, `nyt` | Kebab-case domain or dataset slug |
| `<report-name>` | `fb-silver-report_20260629.html` | Descriptive filename; optional `_YYYYMMDD` suffix |

## Skills that write here

| Output type | Skill |
|-------------|-------|
| EDA, profiling, multi-format | [`statistical-report`](../skills/analyze/reports/statistical-report/SKILL.md) |
| Text tone / framing | [`sentiment-analysis`](../skills/analyze/reports/sentiment-analysis/SKILL.md) |
| Network analysis (markdown) | [`graph-analysis`](../skills/analyze/graph/graph-analysis/SKILL.md) |
| Interactive HTML graphs | [`interactive-graph-reports`](../skills/analyze/graph/interactive-graph-reports/SKILL.md) |

This directory is **gitignored** (outputs may contain PII or scraped text). Commit skills and SQL only — see [`data-privacy`](../skills/engineering/data-privacy/SKILL.md).

Path helper: `db.get_report_path(project, name)` in `scripts/python/db.py`.

Vocabulary: [`CONTEXT.md`](../CONTEXT.md).
