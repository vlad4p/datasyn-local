# Diagrams

SVG diagrams for the README (datasyn palette: ivory `#fffceb`, ink `#49443b`).

| File | Used in README as |
|------|-------------------|
| `flow.svg` | Data pipeline — collect → landing → DuckDB → reports |
| `request-lifecycle.svg` | One plain-language request → auditable answer |
| `repo-layout.svg` | Agent/skills vs your data folders |
| `startup.svg` | First-time setup flow |
| `investigation-example.svg` | NYT scrape → ingest → sentiment example |

Embed in Markdown:

```markdown
![Description](docs/diagrams/flow.svg)
```

Validate after edits:

```bash
xmllint --noout docs/diagrams/*.svg
```
