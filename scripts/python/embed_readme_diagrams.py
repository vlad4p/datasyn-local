#!/usr/bin/env python3
"""Insert diagram <img> tags into README files from docs/diagrams/*.svg.

Replaces inline <svg> blocks or markdown image lines with centered HTML, e.g.:

  <p align="center"><img src="docs/diagrams/flow.svg" alt="..." width="860"/></p>

Usage (repo root):
  uv run python scripts/python/embed_readme_diagrams.py README.md README.es.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIAGRAMS = ROOT / "docs" / "diagrams"

SVG_BLOCK = re.compile(
    r'<p align="center">\s*<svg[\s\S]*?</svg>\s*</p>\s*',
    re.MULTILINE,
)
MD_IMAGE = re.compile(
    r'!\[(?P<alt>[^\]]*)\]\(docs/diagrams/(?P<name>[a-z0-9-]+)\.svg\)\s*',
)

META: dict[str, tuple[int, str, str]] = {
    "flow": (
        860,
        "From source to story — collect, landing, DuckDB, reports",
        "De la fuente a la historia — recolectar, landing, DuckDB, reportes",
    ),
    "repo-layout": (
        680,
        "datasyn repository layout — agent config and your data folders",
        "Layout del repositorio datasyn — configuración del agente y carpetas de datos",
    ),
    "request-lifecycle": (
        560,
        "One request — plain language to auditable answer via MCP",
        "Un pedido — lenguaje claro a respuesta auditable vía MCP",
    ),
    "investigation-example": (
        720,
        "Full investigation — scrape, ingest, sentiment report",
        "Investigación completa — extracción, ingesta, reporte de sentimiento",
    ),
}

DETECT = [
    (("FROM SOURCE TO STORY", "data flow"), "flow"),
    (("WHAT GOES WHERE", "repository layout"), "repo-layout"),
    (("HOW ONE REQUEST", "plain-language request"), "request-lifecycle"),
    (("FULL INVESTIGATION", "investigation example"), "investigation-example"),
]


def detect_name(block: str) -> str:
    for needles, name in DETECT:
        if any(n in block for n in needles):
            return name
    raise ValueError(f"Could not detect diagram in block: {block[:120]}...")


def img_html(name: str, lang: str) -> str:
    width, alt_en, alt_es = META[name]
    alt = alt_es if lang == "es" else alt_en
    return (
        f'<p align="center"><img src="docs/diagrams/{name}.svg" '
        f'alt="{alt}" width="{width}"/></p>\n\n'
    )


def replace_svg_blocks(content: str, lang: str) -> tuple[str, int]:
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        name = detect_name(match.group(0))
        count += 1
        return img_html(name, lang)

    return SVG_BLOCK.sub(repl, content), count


def replace_md_images(content: str, lang: str) -> tuple[str, int]:
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        name = match.group("name")
        count += 1
        return img_html(name, lang)

    return MD_IMAGE.sub(repl, content), count


def patch_diagram_footer(content: str) -> str:
    old = """Source SVGs live in [`docs/diagrams/`](docs/diagrams/). After editing them, re-embed into this README:

```bash
uv run python scripts/python/embed_readme_diagrams.py README.md
```"""
    new = (
        "Diagram sources: [`docs/diagrams/`](docs/diagrams/) — "
        "`flow.svg`, `repo-layout.svg`, "
        "`request-lifecycle.svg`, `investigation-example.svg`."
    )
    return content.replace(old, new)


def process(path: Path, lang: str) -> None:
    text = path.read_text(encoding="utf-8")
    text, n_svg = replace_svg_blocks(text, lang)
    text, n_md = replace_md_images(text, lang)
    if path.name == "README.md":
        text = patch_diagram_footer(text)
    n = n_svg + n_md
    if n == 0:
        print(f"{path.name}: nothing to update")
        return
    path.write_text(text, encoding="utf-8")
    print(f"{path.name}: updated {n} diagram(s)")


def main(argv: list[str]) -> int:
    targets = argv[1:] or ["README.md"]
    for rel in targets:
        path = ROOT / rel
        if not path.is_file():
            print(f"skip (missing): {rel}", file=sys.stderr)
            continue
        lang = "es" if rel.endswith(".es.md") else "en"
        process(path, lang)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
