#!/usr/bin/env python3
"""Generate PDF report for redes sociales / trolls analysis (charts + tables)."""

from __future__ import annotations

import json
import sys
import textwrap
from datetime import date
from io import BytesIO
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402

REPORT_PROJECT = "redes"
STAMP = date.today().strftime("%Y%m%d")

HTML_REPORTS = [
    ("Dashboard analítico (Chart.js)", "gold-report/report.html"),
    ("Grafo interactivo de trolls (vis.js)", "trolls-grafo/report.html"),
    ("Grafo Myriam TW (legacy)", "myriambregman-tw/report.html"),
]

COLORS = {
    "apoyo_izquierda": "#3dd68c",
    "derecha_o_troll": "#f07178",
    "inclasificable": "#c084fc",
    "ambiguo": "#f5a524",
    "neutral": "#8b9cb3",
}


def _query_records(con, sql: str) -> list[dict]:
    df = con.sql(sql).df()
    for col in df.columns:
        dtype = str(df[col].dtype).lower()
        if "datetime" in dtype or "timestamp" in dtype:
            df[col] = df[col].astype(str)
    return df.to_dict(orient="records")


def load_data(con) -> dict:
    json_path = db.get_report_bundle(REPORT_PROJECT, "gold-report") / "data.json"
    if json_path.exists():
        return json.loads(json_path.read_text(encoding="utf-8"))

    from generate_redes_gold_report import load_data as load_html_data

    return load_html_data(con)


def _redes_dir() -> Path:
    return db.get_reports_path() / REPORT_PROJECT


def _footer(fig, page_num: int, total_hint: str = "") -> None:
    fig.text(
        0.5,
        0.02,
        f"datasyn-local · reports/redes/analisis-completo/report.pdf · pág. {page_num}{total_hint}",
        ha="center",
        fontsize=8,
        color="#666",
    )


def page_cover(pdf: PdfPages, generated: str) -> None:
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor("#0f1419")
    fig.text(0.5, 0.72, "Análisis de redes sociales", ha="center", fontsize=22, color="white", weight="bold")
    fig.text(0.5, 0.66, "Sentimiento · Narrativa · Trolls · Grafos", ha="center", fontsize=14, color="#8b9cb3")
    fig.text(0.5, 0.58, f"Generado: {generated}", ha="center", fontsize=11, color="#8b9cb3")
    fig.text(
        0.5,
        0.48,
        "Cuentas: Myriam Bregman · Nicolas del Caño · Christian Castillo · PTSarg",
        ha="center",
        fontsize=10,
        color="#a0aec0",
    )
    fig.text(0.5, 0.42, "Fuentes: silver.fb_* · silver.tw_* · gold.*", ha="center", fontsize=9, color="#718096")
    _footer(fig, 1)
    pdf.savefig(fig, facecolor=fig.get_facecolor())
    plt.close(fig)


def page_text(pdf: PdfPages, title: str, body: str, page_num: int) -> None:
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.subplots_adjust(top=0.92, bottom=0.08, left=0.1, right=0.9)
    fig.text(0.1, 0.94, title, fontsize=16, weight="bold", color="#1a202c")
    y = 0.88
    for para in body.strip().split("\n\n"):
        for line in textwrap.wrap(para, width=95):
            fig.text(0.1, y, line, fontsize=10, color="#2d3748", va="top")
            y -= 0.035
        y -= 0.02
    _footer(fig, page_num)
    pdf.savefig(fig)
    plt.close(fig)


def page_table(pdf: PdfPages, title: str, headers: list[str], rows: list[list], page_num: int) -> None:
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    ax.axis("off")
    ax.set_title(title, loc="left", fontsize=14, weight="bold", pad=20)
    if not rows:
        ax.text(0.5, 0.5, "Sin datos", ha="center")
    else:
        table = ax.table(
            cellText=rows,
            colLabels=headers,
            loc="upper center",
            cellLoc="left",
            colLoc="left",
            bbox=[0, 0.15, 1, 0.75],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.4)
        for (r, c), cell in table.get_celld().items():
            if r == 0:
                cell.set_facecolor("#2d3748")
                cell.set_text_props(color="white", weight="bold")
            elif r % 2 == 0:
                cell.set_facecolor("#f7fafc")
    _footer(fig, page_num)
    pdf.savefig(fig)
    plt.close(fig)


def chart_sentimiento_cuentas(pdf: PdfPages, data: dict, page_num: int) -> None:
    rows = data.get("sentimiento_resumen", [])
    if not rows:
        return
    labels = [r["cuenta_nombre"] for r in rows]
    apoyo = [r.get("apoyo_izquierda", 0) for r in rows]
    troll = [r.get("derecha_o_troll", 0) for r in rows]
    otros = [
        r.get("ambiguo_inclasificable", 0) + r.get("neutral", 0) for r in rows
    ]

    fig, ax = plt.subplots(figsize=(8.27, 6))
    x = np.arange(len(labels))
    w = 0.5
    ax.bar(x, apoyo, w, label="Apoyo izquierda", color=COLORS["apoyo_izquierda"])
    ax.bar(x, troll, w, bottom=apoyo, label="Derecha / troll", color=COLORS["derecha_o_troll"])
    ax.bar(x, otros, w, bottom=np.array(apoyo) + np.array(troll), label="Ambiguo / otro", color="#94a3b8")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("Comentarios clasificados")
    ax.set_title("Posición por cuenta trackeada (FB + TW clasificados)")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    _footer(fig, page_num)
    pdf.savefig(fig)
    plt.close(fig)


def chart_sentimiento_temporal(pdf: PdfPages, data: dict, page_num: int) -> None:
    rows = [r for r in data.get("sentimiento_temporal", []) if r.get("cuenta_slug") == "myriambregman"]
    if not rows:
        return
    dias = sorted({r["dia"][:10] for r in rows})
    apoyo = []
    troll = []
    for d in dias:
        apoyo.append(sum(r["comentarios"] for r in rows if r["dia"][:10] == d and r["posicion"] == "apoyo_izquierda"))
        troll.append(sum(r["comentarios"] for r in rows if r["dia"][:10] == d and r["posicion"] == "derecha_o_troll"))

    fig, ax = plt.subplots(figsize=(8.27, 5))
    ax.plot(dias, troll, color=COLORS["derecha_o_troll"], marker="o", label="Troll", linewidth=2)
    ax.plot(dias, apoyo, color=COLORS["apoyo_izquierda"], marker="s", label="Apoyo", linewidth=2)
    ax.set_title("Evolución diaria — Myriam Bregman")
    ax.set_ylabel("Comentarios")
    plt.xticks(rotation=45, ha="right", fontsize=8)
    ax.legend()
    fig.tight_layout()
    _footer(fig, page_num)
    pdf.savefig(fig)
    plt.close(fig)


def chart_narrativa(pdf: PdfPages, data: dict, page_num: int) -> None:
    rows = [r for r in data.get("narrativa_distribucion", []) if r.get("cuenta_slug") == "myriambregman"][:8]
    if not rows:
        return
    labels = [r["narrativa"].replace("_", "\n") for r in rows]
    vals = [r["comentarios"] for r in rows]
    fig, ax = plt.subplots(figsize=(8.27, 5))
    colors = plt.cm.Set3(np.linspace(0, 1, len(vals)))
    ax.barh(labels, vals, color=colors)
    ax.set_xlabel("Comentarios")
    ax.set_title("Narrativas dominantes — Myriam Bregman")
    ax.invert_yaxis()
    fig.tight_layout()
    _footer(fig, page_num)
    pdf.savefig(fig)
    plt.close(fig)


def chart_trolls_top(pdf: PdfPages, data: dict, page_num: int) -> None:
    rows = [r for r in data.get("trolls_top10", []) if r.get("plataforma") == "twitter"]
    if not rows:
        return
    labels = [r.get("autor_nombre") or "?" for r in rows]
    vals = [r["comentarios_troll"] for r in rows]
    fig, ax = plt.subplots(figsize=(8.27, 5))
    ax.barh(labels[::-1], vals[::-1], color=COLORS["derecha_o_troll"])
    ax.set_xlabel("Comentarios troll clasificados")
    ax.set_title("Top 10 trolls recurrentes — Twitter/X")
    fig.tight_layout()
    _footer(fig, page_num)
    pdf.savefig(fig)
    plt.close(fig)


def chart_rafagas_dia(pdf: PdfPages, data: dict, page_num: int) -> None:
    rows = data.get("trolls_rafagas_dia", [])[:10]
    if not rows:
        return
    labels = [f"{r['dia'][:10]}\n{r['cuenta_slug']}" for r in rows]
    autores = [r["autores_con_rafaga"] for r in rows]
    coment = [r["comentarios_en_rafagas"] for r in rows]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(8.27, 5))
    ax.bar(x - 0.2, autores, 0.4, label="Autores con ráfaga", color="#60a5fa")
    ax.bar(x + 0.2, coment, 0.4, label="Comentarios en ráfagas", color=COLORS["derecha_o_troll"])
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7, rotation=30, ha="right")
    ax.set_title("Días con más autores distintos en ráfaga (≥3 trolls/autor/día)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    _footer(fig, page_num)
    pdf.savefig(fig)
    plt.close(fig)


def chart_pico_trolls(pdf: PdfPages, con, page_num: int) -> None:
    rows = con.sql(
        """
        SELECT CAST(dia AS DATE) AS dia, COUNT(*) AS trolls,
               COUNT(DISTINCT autor_key) AS autores_id,
               COUNT(DISTINCT cuenta_slug) AS cuentas
        FROM gold.v_comentario_narrativa
        WHERE es_troll AND cuenta_slug IS NOT NULL AND dia IS NOT NULL
        GROUP BY 1 ORDER BY trolls DESC LIMIT 12
        """
    ).df()
    if rows.empty:
        return
    fig, ax = plt.subplots(figsize=(8.27, 5))
    labels = [str(d)[:10] for d in rows["dia"]]
    ax.bar(labels, rows["trolls"], color=COLORS["derecha_o_troll"], alpha=0.85, label="Trolls total")
    ax2 = ax.twinx()
    ax2.plot(labels, rows["autores_id"], color="#60a5fa", marker="o", label="Autores identificados")
    ax.set_title("Picos diarios de comentarios troll (cuentas trackeadas)")
    ax.set_ylabel("Comentarios troll")
    ax2.set_ylabel("Autores distintos (identificados)")
    plt.xticks(rotation=45, ha="right", fontsize=8)
    fig.tight_layout()
    _footer(fig, page_num)
    pdf.savefig(fig)
    plt.close(fig)


def page_html_refs(pdf: PdfPages, page_num: int) -> None:
    base = _redes_dir().resolve()
    lines = [
        "Los reportes HTML permiten exploración interactiva (zoom, filtros, tooltips).",
        "Abrir en navegador desde la carpeta local:",
        "",
        f"  {base}",
        "",
    ]
    for title, fname in HTML_REPORTS:
        path = base / fname
        status = "✓ disponible" if path.exists() else "(no generado aún)"
        lines.append(f"• {title}")
        lines.append(f"  {fname}  {status}")
        lines.append("")
    lines.extend(
        [
            "Regenerar HTML:",
            "  uv run python scripts/python/generate_redes_gold_report.py",
            "  uv run python scripts/python/generate_trolls_grafo_report.py",
            "",
            "Regenerar PDF:",
            "  uv run python scripts/python/generate_redes_pdf_report.py",
        ]
    )
    page_text(pdf, "Anexos — reportes HTML interactivos", "\n".join(lines), page_num)


BUNDLE_README = """\
# Análisis completo — PDF consolidado

KPIs, gráficos estáticos y referencias a reportes HTML interactivos.

| Archivo | Rol |
|---------|-----|
| `report.pdf` | Documento principal |

Generado: {generated}
Regenerar: `uv run --with matplotlib python scripts/python/generate_redes_pdf_report.py`
"""


def main() -> int:
    out_dir = db.get_report_bundle(REPORT_PROJECT, "analisis-completo")
    con = db.connect_for_ingest(release_mcp=True)
    data = load_data(con)

    pdf_path = out_dir / "report.pdf"
    page = 1

    with PdfPages(pdf_path) as pdf:
        page_cover(pdf, data.get("generated", date.today().isoformat()))
        page += 1

        resumen = data.get("sentimiento_resumen", [])
        total = sum(r.get("comentarios_clasificados", 0) for r in resumen)
        exec_text = f"""
Alcance: {total:,} comentarios clasificados (LLM) sobre cuentas PTS trackeadas en Facebook y Twitter/X.

Hallazgos principales:
• Tono dominante: ~80–85% derecha_o_troll en todas las cuentas con datos clasificados.
• Myriam Bregman concentra el mayor volumen absoluto (FB + TW).
• Pico de trolls identificados: 4-jun-2026 (8.459 comentarios troll, 3 cuentas objetivo).
• Christian Castillo: sin comentarios clasificados en la base actual.
• Facebook: autores de comentarios casi anónimos (user_id en <0,04% de trolls).

Metodología: medallion silver → vistas gold (sentimiento, narrativa, trolls, grafo).
Clasificación: apoyo_izquierda, derecha_o_troll, neutral, ambiguo, inclasificable.
Ráfaga: ≥3 comentarios troll del mismo autor el mismo día contra la misma cuenta.
co_rafaga: dos autores con ráfaga el mismo día contra la misma cuenta (sincronía, no coordinación probada).
        """
        page_text(pdf, "1. Resumen ejecutivo", exec_text, page)
        page += 1

        trows = [
            [
                r["cuenta_nombre"],
                f"{r.get('comentarios_clasificados', 0):,}",
                f"{r.get('pct_apoyo', 0)}%",
                f"{r.get('pct_troll', 0)}%",
                str(r.get("primer_comentario", ""))[:10],
                str(r.get("ultimo_comentario", ""))[:10],
            ]
            for r in resumen
        ]
        page_table(
            pdf,
            "2. Sentimiento por cuenta",
            ["Cuenta", "Clasificados", "% apoyo", "% troll", "Desde", "Hasta"],
            trows,
            page,
        )
        page += 1

        chart_sentimiento_cuentas(pdf, data, page)
        page += 1
        chart_sentimiento_temporal(pdf, data, page)
        page += 1

        narr_rows = []
        for r in data.get("narrativa_distribucion", []):
            if r.get("cuenta_slug") in ("myriambregman", "nicolasdelcano", "ptsarg"):
                narr_rows.append(
                    [
                        r["cuenta_slug"],
                        r["narrativa"],
                        f"{r.get('comentarios', 0):,}",
                        f"{r.get('pct_narrativa', 0)}%",
                    ]
                )
                if len(narr_rows) >= 15:
                    break
        page_table(pdf, "3. Narrativas (muestra)", ["Cuenta", "Narrativa", "N", "%"], narr_rows[:15], page)
        page += 1
        chart_narrativa(pdf, data, page)
        page += 1

        troll_rows = [
            [
                str(r.get("ranking", "")),
                r.get("autor_nombre") or "—",
                r.get("plataforma", ""),
                str(r.get("comentarios_troll", "")),
                str(r.get("dias_activos", "")),
                str(r.get("cuentas_slug", ""))[:40],
            ]
            for r in data.get("trolls_top10", [])
            if r.get("plataforma") == "twitter"
        ]
        page_table(
            pdf,
            "4. Top trolls Twitter/X",
            ["#", "Autor", "Plat.", "Trolls", "Días", "Cuentas"],
            troll_rows,
            page,
        )
        page += 1
        chart_trolls_top(pdf, data, page)
        page += 1

        raf_txt = """
Ráfaga individual: un autor identificado publica ≥3 comentarios clasificados como derecha_o_troll
el mismo día contra la misma cuenta objetivo.

co_rafaga (grafo): arista entre dos autores que cumplieron ráfaga el mismo día contra la misma cuenta.
Indica sincronía temporal (posible reacción al mismo estímulo mediático), NO prueba de coordinación.

Ejemplo 31-may-2026 · myriambregman: del_mendez77364 (19 trolls), martinezmerce18 (5), mirian11970 (5)
comparten co_rafaga. del_mendez operó 13:35–22:40; martinez y mirian en ventana 17:55–21:21.

Multi-objetivo: autores que atacan ≥2 cuentas trackeadas (turca1985, PelusonOfpink, gordomasterX).
        """
        page_text(pdf, "5. Ráfagas y co-rafaga", raf_txt, page)
        page += 1

        raf_dia_rows = [
            [
                r["dia"][:10],
                r["cuenta_slug"],
                r["plataforma"],
                str(r["autores_con_rafaga"]),
                str(int(r["comentarios_en_rafagas"])),
                str(r.get("max_comentarios_un_autor", "")),
            ]
            for r in data.get("trolls_rafagas_dia", [])[:12]
        ]
        page_table(
            pdf,
            "5b. Días con autores en ráfaga",
            ["Día", "Cuenta", "Plat.", "Autores", "Coment.", "Máx/autor"],
            raf_dia_rows,
            page,
        )
        page += 1
        chart_rafagas_dia(pdf, data, page)
        page += 1

        chart_pico_trolls(pdf, con, page)
        page += 1

        grafo_txt = """
Grafo de entidades (gold.grafo_*_trolls):
• Nodos autor (rojo), cuenta objetivo (verde), narrativa (violeta), cohorte-día (azul).
• ataca: autor → cuenta · co_rafaga: autor ↔ autor · usa_narrativa · en_cohorte.

Relaciones observables: hub hacia myriambregman; cohorte 31-may; puentes multi-objetivo;
narrativas compartidas (spam/enlaces, insulto) sin implicar misma persona.

Ver grafo interactivo en HTML (Anexo) para explorar nodos y filtros por tipo de arista.
        """
        page_text(pdf, "6. Grafo de trolls", grafo_txt, page)
        page += 1

        limit_txt = """
Limitaciones:
• Clasificación LLM sobre muestra parcial (FB ~22%, TW replies top tweets).
• FB: casi sin user_id en comentarios → ranking trolls FB muy incompleto.
• Christian Castillo sin datos clasificados.
• Narrativa: heurística SQL sobre resumen LLM, no re-análisis de texto crudo.
• co_rafaga no usa post_id ni ventana horaria estricta.

Vistas gold: v_sentimiento_*, v_narrativa_*, v_trolls_*, grafo_vertices/edges_*.
SQL: scripts/sql/ingest_redes_gold.sql
        """
        page_text(pdf, "7. Límites y reproducibilidad", limit_txt, page)
        page += 1

        page_html_refs(pdf, page)

    con.close()
    readme_path = out_dir / "README.md"
    readme_path.write_text(
        BUNDLE_README.format(generated=data.get("generated", date.today().isoformat())),
        encoding="utf-8",
    )
    print(f"Bundle: {out_dir}/")
    print(f"  report.pdf")
    print(f"Páginas: ~{page}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
