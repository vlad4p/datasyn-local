# Architecture diagrams

SVG diagrams embedded in [`README.md`](../../README.md) and [`README.en.md`](../../README.en.md). Palette and role colors: [`docs/colors/README.md`](../colors/README.md).

## Inventory

| File | Used in | Purpose |
|------|---------|---------|
| [`flow.svg`](flow.svg) | README intro / medallion | Collect → landing → DuckDB → reports/ |
| [`repo-layout.svg`](repo-layout.svg) | README | AGENTS, skills, scripts vs landing, duckdb, reports |
| [`request-lifecycle.svg`](request-lifecycle.svg) | README | One plain-language request → MCP SQL → report |
| [`investigation-example.svg`](investigation-example.svg) | README | NYT scrape → ingest → sentiment report |
| [`medallion-redes.svg`](medallion-redes.svg) | README | Legacy FB/TW CSV → gold views → report bundles |

## FigJam source

Mermaid prototypes and editable boards live in FigJam:

- **Medallion redes pipeline:** [FigJam board](https://www.figma.com/board/bfbCJswHvDEzMVevjuq17M) (`bfbCJswHvDEzMVevjuq17M`)

To add or refresh diagrams:

1. Use Figma MCP `generate_diagram` with Mermaid (no emojis in syntax).
2. Apply datasyn palette from [`docs/colors/README.md`](../colors/README.md).
3. Export or hand-edit committed SVG under `docs/diagrams/`.
4. Validate and sync README embeds (below).

## Maintenance

```bash
# Validate SVG XML
xmllint --noout docs/diagrams/*.svg

# Re-embed <img> tags in READMEs (after inline SVG → img migration)
uv run python scripts/python/tools/embed_readme_diagrams.py README.md README.en.md
```

When adding a diagram:

1. Add `docs/diagrams/<name>.svg`.
2. Extend `META` in [`scripts/python/tools/embed_readme_diagrams.py`](../../scripts/python/tools/embed_readme_diagrams.py) if using the embed helper.
3. Reference with repo-relative path: `<img src="docs/diagrams/<name>.svg" …>`.

Related: [`docs/skills-layout.md`](../skills-layout.md) · [`skills/README.md`](../../skills/README.md)
