#!/usr/bin/env python3
"""Generate interactive twikit hater-clusters report (Chart.js, self-contained HTML).

Output: reports/twikit-myriam/hater-clusters/
  report.html, data.json, data/*.csv, README.md

Usage:
  uv run python scripts/python/reports/generate_tk_hater_clusters_report.py
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
BUNDLE = "hater-clusters"


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
    kpis = {
        "hater_replies": con.execute(
            "SELECT COUNT(*) FROM gold.tk_hater_narrativa_assignment"
        ).fetchone()[0],
        "clusters": con.execute(
            "SELECT COUNT(*) FROM gold.tk_hater_narrativa_cluster"
        ).fetchone()[0],
        "haters": con.execute(
            "SELECT COUNT(DISTINCT username) FROM gold.tk_hater_narrativa_assignment"
        ).fetchone()[0],
        "tweets_touched": con.execute(
            "SELECT COUNT(DISTINCT parent_tweet_id) FROM gold.tk_hater_narrativa_assignment"
        ).fetchone()[0],
        "dia_min": str(
            con.execute(
                "SELECT MIN(dia) FROM gold.v_tk_hater_narrativa_detalle"
            ).fetchone()[0]
        ),
        "dia_max": str(
            con.execute(
                "SELECT MAX(dia) FROM gold.v_tk_hater_narrativa_detalle"
            ).fetchone()[0]
        ),
        "classified_total": con.execute(
            "SELECT COUNT(*) FROM silver.tk_tw_reply_classification"
        ).fetchone()[0],
        "tw_users_total": con.execute(
            "SELECT COUNT(*) FROM silver.tk_tw_user"
        ).fetchone()[0],
        "tw_users_haters": con.execute(
            "SELECT COUNT(*) FROM silver.tk_tw_user WHERE is_hater"
        ).fetchone()[0],
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "account": "myriambregman",
        "source": "twikit",
    }

    _, clusters = _rows(
        con,
        """
        SELECT cluster_id, label, descripcion, n_replies, n_tweets, n_autores, pct_haters
        FROM gold.v_tk_hater_narrativa_resumen
        ORDER BY n_replies DESC
        """,
    )
    _, cluster_meta = _rows(
        con,
        """
        SELECT cluster_id, label, descripcion, n_replies, ejemplo_textos, run_id, created_at
        FROM gold.tk_hater_narrativa_cluster
        ORDER BY n_replies DESC NULLS LAST
        """,
    )
    _, temporal = _rows(
        con,
        """
        SELECT CAST(dia AS VARCHAR) AS dia, narrativa_cluster, n_replies
        FROM gold.v_tk_hater_narrativa_temporal
        ORDER BY dia, n_replies DESC
        """,
    )
    _, haters = _rows(
        con,
        """
        SELECT
          d.reply_username AS username,
          u.display_name,
          CAST(u.account_created_at AS VARCHAR) AS account_created_at,
          u.followers_count,
          u.following_count,
          u.statuses_count,
          u.is_hater,
          u.hater_replies_count AS catalog_hater_replies,
          u.source AS user_source,
          MIN(d.dia) AS first_day,
          MAX(d.dia) AS last_day,
          COUNT(*) AS n_replies,
          COUNT(DISTINCT d.parent_tweet_id) AS n_tweets,
          COUNT(DISTINCT d.narrativa_cluster) AS n_clusters,
          MODE(d.narrativa_cluster) AS top_cluster,
          SUM(COALESCE(d.like_count, 0)) AS likes_sum
        FROM gold.v_tk_hater_narrativa_detalle d
        LEFT JOIN silver.tk_tw_user u
          ON LOWER(TRIM(d.reply_username)) = LOWER(TRIM(u.username))
        WHERE d.reply_username IS NOT NULL
        GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9
        ORDER BY n_replies DESC
        """,
    )
    for h in haters:
        h["first_day"] = str(h["first_day"]) if h["first_day"] else None
        h["last_day"] = str(h["last_day"]) if h["last_day"] else None

    _, daily_h = _rows(
        con,
        """
        SELECT CAST(dia AS VARCHAR) AS dia, reply_username AS username, COUNT(*) AS n_replies
        FROM gold.v_tk_hater_narrativa_detalle
        WHERE reply_username IS NOT NULL AND dia IS NOT NULL
        GROUP BY 1, 2
        ORDER BY 1, 3 DESC
        """,
    )
    _, first_cohort = _rows(
        con,
        """
        WITH firsts AS (
          SELECT reply_username, MIN(dia) AS first_day
          FROM gold.v_tk_hater_narrativa_detalle
          WHERE reply_username IS NOT NULL
          GROUP BY 1
        )
        SELECT CAST(first_day AS VARCHAR) AS first_day, COUNT(*) AS n_haters
        FROM firsts
        GROUP BY 1
        ORDER BY 1
        """,
    )
    _, samples = _rows(
        con,
        """
        WITH ranked AS (
          SELECT
            narrativa_cluster, reply_username, reply_text, like_count,
            CAST(dia AS VARCHAR) AS dia, parent_tweet_id,
            ROW_NUMBER() OVER (
              PARTITION BY narrativa_cluster
              ORDER BY COALESCE(like_count, 0) DESC, created_at_ts DESC
            ) AS rn
          FROM gold.v_tk_hater_narrativa_detalle
          WHERE reply_text IS NOT NULL
        )
        SELECT narrativa_cluster, reply_username, reply_text, like_count, dia, parent_tweet_id
        FROM ranked WHERE rn <= 3
        ORDER BY narrativa_cluster, like_count DESC
        """,
    )
    _, class_mix = _rows(
        con,
        """
        SELECT criterio_label, COUNT(*) AS n
        FROM silver.tk_tw_reply_classification
        GROUP BY 1
        ORDER BY n DESC
        """,
    )
    _, users_summary = _rows(
        con,
        """
        SELECT source, COUNT(*) AS n_users,
               COUNT(*) FILTER (WHERE is_hater) AS n_haters,
               0 AS n_tracked
        FROM silver.tk_tw_user
        GROUP BY 1
        ORDER BY n_users DESC
        """,
    )

    top40 = [h["username"] for h in haters[:40]]
    top40_set = set(top40)
    daily_top = [r for r in daily_h if r["username"] in top40_set]

    return {
        "kpis": kpis,
        "clusters": clusters,
        "cluster_meta": cluster_meta,
        "temporal": temporal,
        "haters": haters[:200],
        "haters_all_count": len(haters),
        "daily_top": daily_top,
        "first_cohort": first_cohort,
        "samples": samples,
        "class_mix": class_mix,
        "users_summary": users_summary,
        "top_usernames": top40,
        "csv": {
            "clusters": clusters,
            "cluster_meta": cluster_meta,
            "temporal": temporal,
            "haters": haters,
            "daily_h": daily_h,
            "daily_top": daily_top,
            "first_cohort": first_cohort,
            "samples": samples,
            "class_mix": class_mix,
            "users_summary": users_summary,
        },
    }


def write_csvs(data_dir: Path, payload: dict[str, Any]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    mapping = {
        "clusters_resumen.csv": ("clusters", None),
        "clusters_meta.csv": ("cluster_meta", None),
        "narrativa_temporal.csv": ("temporal", None),
        "haters_resumen.csv": ("haters", None),
        "haters_diario.csv": ("daily_h", None),
        "haters_diario_top40.csv": ("daily_top", ["dia", "username", "n_replies"]),
        "haters_primera_aparicion.csv": ("first_cohort", None),
        "cluster_ejemplos.csv": ("samples", None),
        "clasificacion_mix.csv": ("class_mix", None),
        "tw_users_por_source.csv": ("users_summary", None),
    }
    csv_data = payload["csv"]
    for fname, (key, cols_override) in mapping.items():
        rows = csv_data[key]
        cols = cols_override or (list(rows[0].keys()) if rows else [])
        _write_csv(data_dir / fname, cols, rows)


def render_html(payload: dict[str, Any]) -> str:
    raw = json.dumps(
        {k: v for k, v in payload.items() if k != "csv"},
        ensure_ascii=False,
        default=_json_default,
    )
    raw = raw.replace("<", "\\u003c").replace(">", "\\u003e")

    return r'''<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Clusters de haters — @myriambregman (twikit)</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>
    :root {
      --bg: #0f1419; --surface: #1a2332; --surface2: #243044; --text: #e7ecf3;
      --muted: #8b9cb3; --accent: #5b8def; --border: #2d3a4f;
      --hot: #f07178; --ok: #3dd68c; --warn: #f5a524;
      --sidebar-w: 230px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: "Segoe UI", system-ui, sans-serif; background: var(--bg); color: var(--text); }
    .app { display: flex; min-height: 100vh; }
    nav {
      width: var(--sidebar-w); background: var(--surface); border-right: 1px solid var(--border);
      padding: 1rem 0; position: fixed; top: 0; bottom: 0; overflow-y: auto; z-index: 10;
    }
    nav h1 { font-size: 0.92rem; padding: 0 1rem 0.75rem; border-bottom: 1px solid var(--border); margin-bottom: 0.5rem; line-height: 1.35; }
    nav a {
      display: block; padding: 0.45rem 1rem; color: var(--muted); text-decoration: none;
      font-size: 0.85rem; border-left: 3px solid transparent;
    }
    nav a:hover, nav a.active { color: var(--text); background: rgba(91,141,239,0.08); border-left-color: var(--accent); }
    main { margin-left: var(--sidebar-w); flex: 1; padding: 1.5rem 1.75rem 3rem; max-width: 1180px; }
    section { display: none; margin-bottom: 2rem; }
    section.active { display: block; }
    section > h2 { font-size: 1.25rem; margin-bottom: 0.25rem; }
    section > .desc { color: var(--muted); font-size: 0.88rem; margin-bottom: 1rem; }
    .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.75rem; margin-bottom: 1.25rem; }
    .kpi { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 0.9rem 1rem; }
    .kpi .label { font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
    .kpi .value { font-size: 1.35rem; font-weight: 700; margin: 0.15rem 0; }
    .kpi .sub { font-size: 0.75rem; color: var(--muted); }
    .panel { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 1rem; margin-bottom: 1rem; }
    .chart-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; }
    .chart-box { position: relative; height: 320px; }
    .chart-box.tall { height: 400px; }
    .controls { display: flex; flex-wrap: wrap; gap: 0.6rem; align-items: center; margin-bottom: 0.85rem; }
    .controls label { font-size: 0.8rem; color: var(--muted); }
    select, input[type="search"] {
      background: var(--surface2); color: var(--text); border: 1px solid var(--border);
      border-radius: 6px; padding: 0.4rem 0.65rem; font-size: 0.85rem; min-width: 160px;
    }
    table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
    th, td { text-align: left; padding: 0.42rem 0.5rem; border-bottom: 1px solid var(--border); vertical-align: top; }
    th { color: var(--muted); font-size: 0.7rem; text-transform: uppercase; font-weight: 500; position: sticky; top: 0; background: var(--surface); }
    tr:hover td { background: rgba(255,255,255,0.02); }
    .scroll { max-height: 420px; overflow: auto; }
    .muted { color: var(--muted); }
    .chip {
      display: inline-block; padding: 0.12rem 0.45rem; border-radius: 999px;
      background: rgba(91,141,239,0.15); color: var(--accent); font-size: 0.72rem; font-weight: 600;
    }
    .chip.hot { background: rgba(240,113,120,0.18); color: var(--hot); }
    .sample { font-size: 0.8rem; line-height: 1.4; margin: 0.35rem 0; padding: 0.45rem 0.55rem; background: var(--surface2); border-radius: 6px; }
    .sample .meta { font-size: 0.72rem; color: var(--muted); margin-bottom: 0.2rem; }
    .limits { font-size: 0.86rem; color: var(--muted); line-height: 1.55; }
    .limits li { margin: 0.35rem 0 0.35rem 1.1rem; }
    footer { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border); color: var(--muted); font-size: 0.8rem; }
    @media (max-width: 768px) {
      nav { position: relative; width: 100%; }
      main { margin-left: 0; }
      .app { flex-direction: column; }
    }
  </style>
</head>
<body>
<div class="app">
  <nav>
    <h1>Haters · @myriambregman<br><span class="muted" style="font-weight:400;font-size:0.75rem">twikit clusters</span></h1>
    <a href="#resumen" data-sec="resumen" class="active">Resumen</a>
    <a href="#narrativas" data-sec="narrativas">Narrativas</a>
    <a href="#temporal" data-sec="temporal">Temporal</a>
    <a href="#arranque" data-sec="arranque">Arranque</a>
    <a href="#haters" data-sec="haters">Por hater</a>
    <a href="#cuentas" data-sec="cuentas">Cuentas TW</a>
    <a href="#ejemplos" data-sec="ejemplos">Ejemplos</a>
    <a href="#metodo" data-sec="metodo">Metodología</a>
  </nav>
  <main>
    <p class="muted" style="font-size:0.85rem;margin-bottom:1rem">
      Fuente: <code>gold.v_tk_hater_narrativa_*</code> + <code>silver.tk_tw_user</code> · Generado: <span id="gen-at"></span>
    </p>

    <section id="sec-resumen" class="active">
      <h2>Resumen</h2>
      <p class="desc">Replies clasificados como <code>derecha_o_troll</code> sobre posts de @myriambregman, agrupados en narrativas canónicas.</p>
      <div class="kpi-grid" id="kpis"></div>
      <div class="chart-row">
        <div class="panel"><h3 style="font-size:0.95rem;margin-bottom:0.6rem">Mix de clasificación (todos los replies)</h3><div class="chart-box"><canvas id="chart-mix"></canvas></div></div>
        <div class="panel"><h3 style="font-size:0.95rem;margin-bottom:0.6rem">Top 10 narrativas (haters)</h3><div class="chart-box"><canvas id="chart-top-clusters"></canvas></div></div>
      </div>
    </section>

    <section id="sec-narrativas">
      <h2>Narrativas / clusters</h2>
      <p class="desc">Catálogo de clusters LLM: volumen, autores distintos y % del total hater.</p>
      <div class="panel scroll">
        <table id="tbl-clusters"><thead>
          <tr><th>#</th><th>Cluster</th><th>Replies</th><th>%</th><th>Autores</th><th>Tweets</th><th>Descripción</th></tr>
        </thead><tbody></tbody></table>
      </div>
    </section>

    <section id="sec-temporal">
      <h2>Análisis temporal</h2>
      <p class="desc">Volumen diario de replies hater por narrativa. Filtrá un cluster o mirá el total.</p>
      <div class="controls">
        <label>Narrativa
          <select id="sel-cluster"><option value="__all__">Todas (stacked)</option></select>
        </label>
      </div>
      <div class="panel"><div class="chart-box tall"><canvas id="chart-temporal"></canvas></div></div>
    </section>

    <section id="sec-arranque">
      <h2>Cuándo empiezan a postear</h2>
      <p class="desc">Primera aparición (día del primer reply hater) por autor. Muestra oleadas de cuentas nuevas.</p>
      <div class="panel"><div class="chart-box"><canvas id="chart-first"></canvas></div></div>
      <div class="panel">
        <h3 style="font-size:0.95rem;margin-bottom:0.6rem">Haters más activos — primera vs última aparición</h3>
        <div class="scroll">
          <table id="tbl-first"><thead>
            <tr><th>Usuario</th><th>Cuenta creada</th><th>Primera</th><th>Última</th><th>Días span</th><th>Replies</th><th>Followers</th><th>Cluster dominante</th></tr>
          </thead><tbody></tbody></table>
        </div>
      </div>
    </section>

    <section id="sec-haters">
      <h2>Volumen diario por hater</h2>
      <p class="desc">Posts/comentarios hater por día para un autor (top 40 por volumen). También buscá en la tabla.</p>
      <div class="controls">
        <label>Hater
          <select id="sel-hater"></select>
        </label>
        <label>Buscar
          <input type="search" id="search-hater" placeholder="username…">
        </label>
      </div>
      <div class="panel"><div class="chart-box"><canvas id="chart-hater-daily"></canvas></div></div>
      <div class="panel">
        <div class="scroll">
          <table id="tbl-haters"><thead>
            <tr><th>Usuario</th><th>Replies</th><th>Tweets</th><th>Clusters</th><th>Creada</th><th>Primera</th><th>Última</th><th>Followers</th><th>Top cluster</th><th>Likes Σ</th></tr>
          </thead><tbody></tbody></table>
        </div>
      </div>
    </section>

    <section id="sec-cuentas">
      <h2>Catálogo silver.tk_tw_user</h2>
      <p class="desc">Cuentas Twitter twikit-only (perfiles + autores de replies) con flag <code>is_hater</code>.</p>
      <div class="panel"><div class="chart-box"><canvas id="chart-users-source"></canvas></div></div>
      <div class="panel scroll">
        <table id="tbl-users-source"><thead>
          <tr><th>Source</th><th>Users</th><th>Haters</th><th>Tracked</th></tr>
        </thead><tbody></tbody></table>
      </div>
    </section>

    <section id="sec-ejemplos">
      <h2>Ejemplos por narrativa</h2>
      <p class="desc">Hasta 3 replies con más likes por cluster (texto público scrapado).</p>
      <div class="controls">
        <label>Cluster
          <select id="sel-sample-cluster"></select>
        </label>
      </div>
      <div class="panel" id="samples-box"></div>
    </section>

    <section id="sec-metodo">
      <h2>Metodología y límites</h2>
      <div class="panel limits">
        <ul>
          <li><strong>Fuente:</strong> scrape twikit de @myriambregman → <code>silver.tk_tw_*</code>.</li>
          <li><strong>Clasificación:</strong> LLM sobre replies → <code>silver.tk_tw_reply_classification</code>; haters = <code>derecha_o_troll</code>.</li>
          <li><strong>Clusters:</strong> consolidación LLM de <code>narrativa_raw</code> → <code>gold.tk_hater_narrativa_*</code>.</li>
          <li><strong>Cuentas:</strong> <code>silver.tk_tw_user</code> (twikit-only); <code>is_hater</code> desde clasificaciones.</li>
          <li><strong>Cobertura:</strong> solo replies capturados en el scrape (no el 100% de la UI de X).</li>
          <li><strong>No es prueba de coordinación:</strong> sincronía temporal ≠ red organizada.</li>
          <li><strong>Privacidad:</strong> handles y textos sensibles; no commitear <code>reports/**</code>.</li>
        </ul>
      </div>
    </section>

    <footer>datasyn-local · reporte local gitignored · Chart.js</footer>
  </main>
</div>
<script>
const DATA = __DATA_JSON__;

const PALETTE = [
  "#f07178","#5b8def","#3dd68c","#f5a524","#c792ea","#89ddff",
  "#ffcb6b","#82aaff","#c3e88d","#f78c6c","#bb80b3","#80cbc4",
  "#ff9cac","#a6accd","#c792ea","#ff5370","#89ddff","#c3e88d",
  "#f78c6c","#82aaff","#c792ea","#ffcb6b","#3dd68c","#5b8def","#f07178"
];

let chartTemporal = null;
let chartHaterDaily = null;

function $(id) { return document.getElementById(id); }

function daySpan(a, b) {
  if (!a || !b) return "—";
  const d0 = new Date(a + "T00:00:00");
  const d1 = new Date(b + "T00:00:00");
  return Math.round((d1 - d0) / 86400000) + 1;
}

function shortDate(v) {
  if (!v) return "—";
  return String(v).slice(0, 10);
}

function navigate(sec) {
  document.querySelectorAll("section").forEach(s => s.classList.remove("active"));
  document.querySelectorAll("nav a").forEach(a => a.classList.remove("active"));
  const el = $("sec-" + sec);
  if (el) el.classList.add("active");
  const link = document.querySelector(`nav a[data-sec="${sec}"]`);
  if (link) link.classList.add("active");
}

document.querySelectorAll("nav a").forEach(a => {
  a.addEventListener("click", e => {
    e.preventDefault();
    navigate(a.dataset.sec);
  });
});

function renderKpis() {
  const k = DATA.kpis;
  $("gen-at").textContent = k.generated_at;
  const items = [
    ["Replies hater", k.hater_replies, `${k.classified_total} clasificados`],
    ["Clusters", k.clusters, "narrativas canónicas"],
    ["Autores hater", k.haters, "handles distintos"],
    ["Tweets tocados", k.tweets_touched, "posts con ≥1 hater"],
    ["tk_tw_user", k.tw_users_total, `${k.tw_users_haters} is_hater`],
    ["Rango", `${k.dia_min} →`, k.dia_max],
  ];
  $("kpis").innerHTML = items.map(([label, value, sub]) =>
    `<div class="kpi"><div class="label">${label}</div><div class="value">${value}</div><div class="sub">${sub}</div></div>`
  ).join("");
}

function renderMix() {
  const labels = DATA.class_mix.map(r => r.criterio_label);
  const values = DATA.class_mix.map(r => r.n);
  new Chart($("chart-mix"), {
    type: "doughnut",
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: ["#f07178","#8b9cb3","#5b8def","#3dd68c","#f5a524"] }]
    },
    options: { plugins: { legend: { position: "bottom", labels: { color: "#8b9cb3", boxWidth: 12 } } } }
  });
}

function renderTopClusters() {
  const top = DATA.clusters.slice(0, 10);
  new Chart($("chart-top-clusters"), {
    type: "bar",
    data: {
      labels: top.map(c => c.label),
      datasets: [{
        label: "Replies",
        data: top.map(c => c.n_replies),
        backgroundColor: PALETTE.slice(0, top.length)
      }]
    },
    options: {
      indexAxis: "y",
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#8b9cb3" }, grid: { color: "#2d3a4f" } },
        y: { ticks: { color: "#e7ecf3", font: { size: 10 } }, grid: { display: false } }
      }
    }
  });
}

function renderClusterTable() {
  const tb = $("tbl-clusters").querySelector("tbody");
  tb.innerHTML = DATA.clusters.map((c, i) => `
    <tr>
      <td>${i + 1}</td>
      <td><span class="chip hot">${c.label}</span></td>
      <td>${c.n_replies}</td>
      <td>${c.pct_haters}%</td>
      <td>${c.n_autores}</td>
      <td>${c.n_tweets}</td>
      <td class="muted">${c.descripcion || "—"}</td>
    </tr>`).join("");
}

function uniqueDays() {
  return [...new Set(DATA.temporal.map(r => r.dia))].sort();
}

function fillClusterSelects() {
  const labels = DATA.clusters.map(c => c.label);
  for (const id of ["sel-cluster", "sel-sample-cluster"]) {
    const sel = $(id);
    labels.forEach(l => {
      const o = document.createElement("option");
      o.value = l; o.textContent = l;
      sel.appendChild(o);
    });
  }
}

function renderTemporal() {
  const sel = $("sel-cluster").value;
  const days = uniqueDays();
  if (chartTemporal) chartTemporal.destroy();

  let datasets;
  if (sel === "__all__") {
    const topN = DATA.clusters.slice(0, 8).map(c => c.label);
    datasets = topN.map((label, i) => {
      const byDay = Object.fromEntries(
        DATA.temporal.filter(r => r.narrativa_cluster === label).map(r => [r.dia, r.n_replies])
      );
      return {
        label,
        data: days.map(d => byDay[d] || 0),
        backgroundColor: PALETTE[i],
        stack: "s"
      };
    });
  } else {
    const byDay = Object.fromEntries(
      DATA.temporal.filter(r => r.narrativa_cluster === sel).map(r => [r.dia, r.n_replies])
    );
    datasets = [{
      label: sel,
      data: days.map(d => byDay[d] || 0),
      backgroundColor: "#f07178",
      borderColor: "#f07178",
      fill: true,
      tension: 0.2
    }];
  }

  chartTemporal = new Chart($("chart-temporal"), {
    type: sel === "__all__" ? "bar" : "line",
    data: { labels: days, datasets },
    options: {
      plugins: { legend: { position: "bottom", labels: { color: "#8b9cb3", boxWidth: 10, font: { size: 10 } } } },
      scales: {
        x: { stacked: sel === "__all__", ticks: { color: "#8b9cb3", maxRotation: 45, font: { size: 9 } }, grid: { color: "#2d3a4f" } },
        y: { stacked: sel === "__all__", ticks: { color: "#8b9cb3" }, grid: { color: "#2d3a4f" }, beginAtZero: true }
      }
    }
  });
}

function renderFirstCohort() {
  new Chart($("chart-first"), {
    type: "bar",
    data: {
      labels: DATA.first_cohort.map(r => r.first_day),
      datasets: [{
        label: "Haters nuevos (1ª aparición)",
        data: DATA.first_cohort.map(r => r.n_haters),
        backgroundColor: "#5b8def"
      }]
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#8b9cb3", maxRotation: 45, font: { size: 9 } }, grid: { color: "#2d3a4f" } },
        y: { ticks: { color: "#8b9cb3" }, grid: { color: "#2d3a4f" }, beginAtZero: true }
      }
    }
  });

  const tb = $("tbl-first").querySelector("tbody");
  tb.innerHTML = DATA.haters.slice(0, 50).map(h => `
    <tr>
      <td>@${h.username}</td>
      <td>${shortDate(h.account_created_at)}</td>
      <td>${h.first_day}</td>
      <td>${h.last_day}</td>
      <td>${daySpan(h.first_day, h.last_day)}</td>
      <td>${h.n_replies}</td>
      <td>${h.followers_count ?? "—"}</td>
      <td><span class="chip">${h.top_cluster || "—"}</span></td>
    </tr>`).join("");
}

function fillHaterSelect() {
  const sel = $("sel-hater");
  DATA.top_usernames.forEach(u => {
    const o = document.createElement("option");
    o.value = u; o.textContent = "@" + u;
    sel.appendChild(o);
  });
}

function renderHaterDaily() {
  const user = $("sel-hater").value;
  const days = uniqueDays();
  const byDay = Object.fromEntries(
    DATA.daily_top.filter(r => r.username === user).map(r => [r.dia, r.n_replies])
  );
  if (chartHaterDaily) chartHaterDaily.destroy();
  chartHaterDaily = new Chart($("chart-hater-daily"), {
    type: "bar",
    data: {
      labels: days,
      datasets: [{
        label: "@" + user + " — replies/día",
        data: days.map(d => byDay[d] || 0),
        backgroundColor: "#f07178"
      }]
    },
    options: {
      plugins: { legend: { labels: { color: "#8b9cb3" } } },
      scales: {
        x: { ticks: { color: "#8b9cb3", maxRotation: 45, font: { size: 9 } }, grid: { color: "#2d3a4f" } },
        y: { ticks: { color: "#8b9cb3", stepSize: 1 }, grid: { color: "#2d3a4f" }, beginAtZero: true }
      }
    }
  });
}

function renderHatersTable(filter = "") {
  const q = filter.trim().toLowerCase();
  const rows = DATA.haters.filter(h => !q || (h.username || "").toLowerCase().includes(q));
  const tb = $("tbl-haters").querySelector("tbody");
  tb.innerHTML = rows.slice(0, 100).map(h => `
    <tr data-user="${h.username}" style="cursor:pointer">
      <td>@${h.username}</td>
      <td>${h.n_replies}</td>
      <td>${h.n_tweets}</td>
      <td>${h.n_clusters}</td>
      <td>${shortDate(h.account_created_at)}</td>
      <td>${h.first_day}</td>
      <td>${h.last_day}</td>
      <td>${h.followers_count ?? "—"}</td>
      <td><span class="chip">${h.top_cluster || "—"}</span></td>
      <td>${h.likes_sum}</td>
    </tr>`).join("");
  tb.querySelectorAll("tr").forEach(tr => {
    tr.addEventListener("click", () => {
      const u = tr.dataset.user;
      const sel = $("sel-hater");
      if ([...sel.options].some(o => o.value === u)) {
        sel.value = u;
        renderHaterDaily();
      }
    });
  });
}

function renderUsersSource() {
  const rows = DATA.users_summary || [];
  new Chart($("chart-users-source"), {
    type: "bar",
    data: {
      labels: rows.map(r => r.source),
      datasets: [
        { label: "Users", data: rows.map(r => r.n_users), backgroundColor: "#5b8def" },
        { label: "Haters", data: rows.map(r => r.n_haters), backgroundColor: "#f07178" }
      ]
    },
    options: {
      plugins: { legend: { labels: { color: "#8b9cb3" } } },
      scales: {
        x: { ticks: { color: "#8b9cb3" }, grid: { color: "#2d3a4f" } },
        y: { ticks: { color: "#8b9cb3" }, grid: { color: "#2d3a4f" }, beginAtZero: true }
      }
    }
  });
  $("tbl-users-source").querySelector("tbody").innerHTML = rows.map(r => `
    <tr>
      <td><span class="chip">${r.source}</span></td>
      <td>${r.n_users}</td>
      <td>${r.n_haters}</td>
      <td>${r.n_tracked}</td>
    </tr>`).join("");
}

function renderSamples() {
  const label = $("sel-sample-cluster").value;
  const rows = DATA.samples.filter(s => s.narrativa_cluster === label);
  const box = $("samples-box");
  if (!rows.length) {
    box.innerHTML = `<p class="muted">Sin ejemplos para este cluster.</p>`;
    return;
  }
  const meta = DATA.clusters.find(c => c.label === label);
  box.innerHTML = `
    <p style="margin-bottom:0.75rem"><span class="chip hot">${label}</span>
      ${meta ? `<span class="muted"> · ${meta.n_replies} replies · ${meta.pct_haters}%</span>` : ""}
    </p>
    <p class="muted" style="margin-bottom:0.75rem;font-size:0.85rem">${meta?.descripcion || ""}</p>
    ${rows.map(r => `
      <div class="sample">
        <div class="meta">@${r.reply_username} · ${r.dia || "—"} · ${r.like_count || 0} likes · tweet ${r.parent_tweet_id || ""}</div>
        <div>${(r.reply_text || "").replace(/</g, "&lt;")}</div>
      </div>`).join("")}`;
}

renderKpis();
renderMix();
renderTopClusters();
renderClusterTable();
fillClusterSelects();
renderTemporal();
$("sel-cluster").addEventListener("change", renderTemporal);
renderFirstCohort();
fillHaterSelect();
renderHaterDaily();
$("sel-hater").addEventListener("change", renderHaterDaily);
renderHatersTable();
$("search-hater").addEventListener("input", e => renderHatersTable(e.target.value));
renderUsersSource();
renderSamples();
$("sel-sample-cluster").addEventListener("change", renderSamples);
</script>
</body>
</html>
'''.replace("__DATA_JSON__", raw)


def write_readme(out: Path, payload: dict[str, Any]) -> None:
    k = payload["kpis"]
    out.write_text(
        f"""# Hater clusters — @myriambregman (twikit)

Reporte interactivo de narrativas hater sobre replies scrapados con twikit.

## Abrir

```bash
open reports/twikit-myriam/hater-clusters/report.html
# o regenerar:
uv run python scripts/python/reports/generate_tk_hater_clusters_report.py
```

## Datos (snapshot)

| KPI | Valor |
|-----|------:|
| Replies hater | {k['hater_replies']} |
| Clusters | {k['clusters']} |
| Autores | {k['haters']} |
| Tweets tocados | {k['tweets_touched']} |
| silver.tk_tw_user | {k['tw_users_total']} ({k['tw_users_haters']} is_hater) |
| Rango | {k['dia_min']} → {k['dia_max']} |
| Generado | {k['generated_at']} |

## Archivos

- `report.html` — dashboard Chart.js (self-contained)
- `data.json` — payload embebido
- `data/*.csv` — exports para Excel / reuso

## Fuente

- `gold.v_tk_hater_narrativa_*`
- `silver.tk_tw_user` (catálogo twikit-only + `is_hater`)
- Clasificación: `silver.tk_tw_reply_classification` (`derecha_o_troll`)
- Scrape: twikit → `silver.tk_tw_reply`

## Límites

- Cobertura parcial de replies (lo capturado por el scrape).
- Clusters LLM — no ground truth.
- No implica coordinación entre cuentas.
""",
        encoding="utf-8",
    )


def main() -> int:
    con = db.connect()
    out = db.get_report_bundle(PROJECT, BUNDLE)
    data_dir = out / "data"

    payload = export_payload(con)
    write_csvs(data_dir, payload)

    public = {k: v for k, v in payload.items() if k != "csv"}
    (out / "data.json").write_text(
        json.dumps(public, ensure_ascii=False, default=_json_default, indent=2),
        encoding="utf-8",
    )
    (out / "report.html").write_text(render_html(payload), encoding="utf-8")
    write_readme(out / "README.md", payload)

    print(f"Wrote {out / 'report.html'}")
    print(
        f"KPIs: haters={payload['kpis']['hater_replies']} "
        f"clusters={payload['kpis']['clusters']} "
        f"tw_users={payload['kpis']['tw_users_total']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
