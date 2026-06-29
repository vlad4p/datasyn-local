# Report outputs

Agent-generated analysis files live here, grouped by project:

```
report/<project>/<report-name>
```

| Segment | Example | Notes |
|---------|---------|--------|
| `<project>` | `redes`, `grafo`, `nyt` | Kebab-case domain or dataset slug |
| `<report-name>` | `fb-silver-report_20260629.html` | Descriptive filename; optional `_YYYYMMDD` suffix |

This directory is **gitignored** (outputs may contain PII or scraped text). Commit skills and SQL only — see **`data-privacy`**.

Path helper: `db.get_report_path(project, name)` in `scripts/python/db.py`.
