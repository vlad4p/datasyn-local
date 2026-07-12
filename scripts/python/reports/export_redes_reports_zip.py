#!/usr/bin/env python3
"""Export redes report bundles into a zip — one folder per report under reports/redes/."""

from __future__ import annotations

import argparse
import zipfile
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import db

# Bundles under reports/redes/<slug>/ (stable folder names)
REDES_BUNDLES: list[tuple[str, str]] = [
    ("dashboard", "Dashboard unificado — Chart.js + vis.js, CSV externos"),
]


def _bundle_dir(bundle: str) -> Path:
    return db.get_report_bundle("redes", bundle)


def collect_bundles(include: list[str] | None = None) -> list[tuple[str, list[Path], str]]:
    """Return (folder_name, paths, description) for each non-empty bundle."""
    bundles: list[tuple[str, list[Path], str]] = []
    for slug, desc in REDES_BUNDLES:
        if include and slug not in include:
            continue
        bdir = _bundle_dir(slug)
        if not bdir.is_dir():
            continue
        paths = sorted(p for p in bdir.rglob("*") if p.is_file() and p.name != ".DS_Store")
        if paths:
            bundles.append((slug, paths, desc))
    return bundles


def export_zip(
    out_path: Path | None = None,
    include: list[str] | None = None,
) -> Path:
    bundles = collect_bundles(include)
    if not bundles:
        raise SystemExit(
            "No report bundles found. Expected folders under reports/redes/: "
            + ", ".join(s for s, _ in REDES_BUNDLES)
        )

    generated = date.today().isoformat()
    redes_root = db.get_reports_path() / "redes"
    exports_dir = redes_root / "_exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    if out_path is None:
        out_path = exports_dir / f"export_{date.today().strftime('%Y%m%d')}.zip"

    root_readme = [
        "# Exportación reportes redes — datasyn-local",
        "",
        f"Generado: {generated}",
        "",
        "Cada carpeta es un reporte autocontenido bajo `reports/redes/<slug>/`.",
        "",
        "## Carpetas",
        "",
    ]
    for folder, paths, desc in bundles:
        root_readme.append(f"- **{folder}/** — {desc}")
        root_readme.append(f"  Archivos: {', '.join(p.name for p in paths)}")
        root_readme.append("")

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", "\n".join(root_readme))
        for folder, paths, _desc in bundles:
            bdir = _bundle_dir(folder)
            for path in paths:
                rel = path.relative_to(bdir)
                arcname = f"{folder}/{rel.as_posix()}"
                zf.write(path, arcname)
                print(f"  + {arcname}")

    print(f"\nZIP: {out_path} ({len(bundles)} bundles)")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export reports/redes/* bundles to zip")
    parser.add_argument(
        "--bundle",
        action="append",
        dest="include",
        help="Include only this bundle slug (repeatable). Default: all found.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output zip path (default: reports/redes/_exports/export_{date}.zip)",
    )
    args = parser.parse_args()
    export_zip(out_path=args.output, include=args.include)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
