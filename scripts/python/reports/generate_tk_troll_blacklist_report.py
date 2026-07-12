#!/usr/bin/env python3
"""Generate twikit troll blacklist report (CSV + markdown + HTML).

Output: reports/twikit-myriam/troll-blacklist/
  blacklist.csv, blacklist_block.csv, report.md, report.html, data.json

IMPORTANT: This does NOT block anyone on X. It exports an auditable list
for manual review/blocking.

Usage:
  uv run python scripts/python/db.py mcp-stop
  uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/twikit/ingest_tk_troll_blacklist.sql
  uv run python scripts/python/reports/generate_tk_troll_blacklist_report.py
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import db  # noqa: E402

PROJECT = "twikit-myriam"
BUNDLE = "troll-blacklist"

FULL_COLS = [
    "tier",
    "username",
    "user_id",
    "score",
    "reasons",
    "hater_replies",
    "replies_total",
    "hater_ratio",
    "target_accounts",
    "parent_tweets",
    "narrativas",
    "in_co_burst",
    "risk_band",
    "risk_score",
    "is_bridge",
    "display_name",
]

BLOCK_COLS = ["username", "user_id"]


def _json_default(o: Any) -> Any:
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    return str(o)


def _rows(con, sql: str) -> tuple[list[str], list[dict[str, Any]]]:
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return cols, [dict(zip(cols, r)) for r in cur.fetchall()]


def _write_csv(path: Path, cols: list[str], data: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for row in data:
            w.writerow({k: ("" if v is None else v) for k, v in row.items()})


def export_payload(con) -> dict[str, Any]:
    _, by_tier = _rows(
        con,
        """
        SELECT tier, COUNT(*) AS n, ROUND(AVG(score), 2) AS avg_score,
               MAX(score) AS max_score
        FROM gold.tk_troll_blacklist
        GROUP BY tier
        ORDER BY CASE WHEN tier = 'block' THEN 0 ELSE 1 END
        """,
    )
    _, top_block = _rows(
        con,
        f"""
        SELECT {", ".join(FULL_COLS)}
        FROM gold.tk_troll_blacklist
        WHERE tier = 'block'
        ORDER BY score DESC, hater_replies DESC
        LIMIT 50
        """,
    )
    _, top_watch = _rows(
        con,
        f"""
        SELECT {", ".join(FULL_COLS)}
        FROM gold.tk_troll_blacklist
        WHERE tier = 'watch'
        ORDER BY score DESC, hater_replies DESC
        LIMIT 30
        """,
    )
    _, reason_freq = _rows(
        con,
        """
        WITH exploded AS (
          SELECT tier, TRIM(UNNEST(STRING_SPLIT(reasons, '|'))) AS reason
          FROM gold.tk_troll_blacklist
          WHERE reasons IS NOT NULL
        )
        SELECT reason, COUNT(*) AS n,
               COUNT(*) FILTER (WHERE tier = 'block') AS n_block
        FROM exploded
        WHERE reason <> ''
        GROUP BY reason
        ORDER BY n DESC
        """,
    )
    _, all_rows = _rows(
        con,
        f"""
        SELECT {", ".join(FULL_COLS)}
        FROM gold.tk_troll_blacklist
        ORDER BY CASE WHEN tier = 'block' THEN 0 ELSE 1 END,
                 score DESC, hater_replies DESC
        """,
    )
    block_rows = [r for r in all_rows if r.get("tier") == "block"]
    watch_rows = [r for r in all_rows if r.get("tier") == "watch"]

    kpis = {
        "total_listed": len(all_rows),
        "n_block": len(block_rows),
        "n_watch": len(watch_rows),
        "authors_twikit": con.execute(
            "SELECT COUNT(DISTINCT author_id) FROM silver.tk_tw_reply"
        ).fetchone()[0],
        "enriched_profiles": con.execute(
            "SELECT COUNT(*) FROM silver.tk_tw_profile_enriched"
        ).fetchone()[0],
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "source": "twikit",
        "auto_block": False,
        "note": (
            "Lista auditable para bloqueo MANUAL en X. "
            "No se ejecuta ningún bloqueo automático."
        ),
    }
    return {
        "kpis": kpis,
        "by_tier": by_tier,
        "top_block": top_block,
        "top_watch": top_watch,
        "reason_freq": reason_freq,
        "all_rows": all_rows,
        "block_rows": block_rows,
        "watch_rows": watch_rows,
    }


def _md_table(rows: list[dict[str, Any]], cols: list[str], limit: int = 25) -> str:
    if not rows:
        return "_Sin filas._\n"
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    lines = [header, sep]
    for r in rows[:limit]:
        cells = []
        for c in cols:
            v = r.get(c)
            if v is None:
                cells.append("")
            elif isinstance(v, float):
                cells.append(f"{v:.3f}")
            else:
                cells.append(str(v).replace("|", "/"))
        lines.append("| " + " | ".join(cells) + " |")
    if len(rows) > limit:
        lines.append(f"\n_… {len(rows) - limit} filas más en CSV._\n")
    return "\n".join(lines) + "\n"


def write_markdown(out: Path, payload: dict[str, Any]) -> None:
    k = payload["kpis"]
    md = f"""# Troll blacklist (twikit) — {k['generated_at']}

> **No bloqueo automático en X.** Esta es una lista + criterios auditables
> para revisión humana. Ver `blacklist-rules.md` en el skill `troll-blacklist`.

## KPIs

| Métrica | Valor |
|---------|-------|
| Autores twikit (universo) | {k['authors_twikit']} |
| En lista (block+watch) | {k['total_listed']} |
| Tier **block** | {k['n_block']} |
| Tier **watch** | {k['n_watch']} |
| Perfiles enriquecidos | {k['enriched_profiles']} |
| Fuente | {k['source']} |

## Por tier

{_md_table(payload['by_tier'], ['tier', 'n', 'avg_score', 'max_score'])}

## Frecuencia de reglas (`reasons`)

{_md_table(payload['reason_freq'], ['reason', 'n', 'n_block'])}

## Top block (muestra)

{_md_table(payload['top_block'], ['username', 'score', 'reasons', 'hater_replies', 'hater_ratio', 'risk_band'], 30)}

## Top watch (muestra)

{_md_table(payload['top_watch'], ['username', 'score', 'reasons', 'hater_replies', 'hater_ratio'], 20)}

## Archivos

- `blacklist.csv` — block + watch con métricas
- `blacklist_block.csv` — solo `username,user_id` (tier block)
- `data.json` — payload completo
- `report.html` — vista rápida

## Límites

- Solo replies capturados con twikit.
- Clasificación LLM puede errar; revisar `reasons` antes de bloquear.
- Co-ráfaga ≠ prueba de coordinación.
"""
    (out / "report.md").write_text(md, encoding="utf-8")


def write_html(out: Path, payload: dict[str, Any]) -> None:
    k = payload["kpis"]

    def rows_html(rows: list[dict[str, Any]], cols: list[str], limit: int = 40) -> str:
        th = "".join(f"<th>{c}</th>" for c in cols)
        body = []
        for r in rows[:limit]:
            tds = "".join(
                f"<td>{'' if r.get(c) is None else r.get(c)}</td>" for c in cols
            )
            body.append(f"<tr>{tds}</tr>")
        return f"<table><thead><tr>{th}</tr></thead><tbody>{''.join(body)}</tbody></table>"

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<title>Troll blacklist (twikit)</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 1.5rem; max-width: 1100px; }}
.banner {{ background: #fff3cd; border: 1px solid #ffc107; padding: 0.75rem 1rem; border-radius: 6px; }}
.kpis {{ display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0; }}
.kpi {{ background: #f4f4f5; padding: 0.75rem 1rem; border-radius: 6px; min-width: 120px; }}
.kpi b {{ display: block; font-size: 1.4rem; }}
table {{ border-collapse: collapse; width: 100%; font-size: 0.85rem; margin: 0.5rem 0 1.5rem; }}
th, td {{ border: 1px solid #ddd; padding: 0.35rem 0.5rem; text-align: left; }}
th {{ background: #f0f0f0; }}
code {{ background: #eee; padding: 0.1rem 0.3rem; border-radius: 3px; }}
</style>
</head>
<body>
<h1>Troll blacklist (twikit)</h1>
<div class="banner">
  <strong>No bloqueo automático en X.</strong> Lista auditable para revisión
  humana. Criterios en skill <code>troll-blacklist</code> /
  <code>blacklist-rules.md</code>. Generado: {k['generated_at']}
</div>
<div class="kpis">
  <div class="kpi"><span>Universo</span><b>{k['authors_twikit']}</b></div>
  <div class="kpi"><span>Listados</span><b>{k['total_listed']}</b></div>
  <div class="kpi"><span>Block</span><b>{k['n_block']}</b></div>
  <div class="kpi"><span>Watch</span><b>{k['n_watch']}</b></div>
</div>
<h2>Top block</h2>
{rows_html(payload['top_block'], ['username','score','reasons','hater_replies','hater_ratio','risk_band'])}
<h2>Top watch</h2>
{rows_html(payload['top_watch'], ['username','score','reasons','hater_replies','hater_ratio'])}
<p class="muted">CSV: <code>blacklist.csv</code>, <code>blacklist_block.csv</code></p>
</body>
</html>
"""
    (out / "report.html").write_text(html, encoding="utf-8")


def main() -> int:
    out = db.get_report_bundle(PROJECT, BUNDLE)
    out.mkdir(parents=True, exist_ok=True)

    con = db.connect(read_only=True)
    try:
        payload = export_payload(con)
    finally:
        con.close()

    _write_csv(out / "blacklist.csv", FULL_COLS, payload["all_rows"])
    _write_csv(out / "blacklist_block.csv", BLOCK_COLS, payload["block_rows"])
    (out / "data.json").write_text(
        json.dumps(
            {
                "kpis": payload["kpis"],
                "by_tier": payload["by_tier"],
                "reason_freq": payload["reason_freq"],
                "top_block": payload["top_block"],
                "top_watch": payload["top_watch"],
            },
            ensure_ascii=False,
            indent=2,
            default=_json_default,
        ),
        encoding="utf-8",
    )
    write_markdown(out, payload)
    write_html(out, payload)

    k = payload["kpis"]
    print(
        f"Wrote {out}: block={k['n_block']} watch={k['n_watch']} "
        f"(auto_block={k['auto_block']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
