#!/usr/bin/env python3
"""Generate HTML report from gold redes views with Chart.js charts."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402


def _query_records(con, sql: str) -> list[dict]:
    df = con.sql(sql).df()
    for col in df.columns:
        dtype = str(df[col].dtype).lower()
        if "datetime" in dtype or "timestamp" in dtype:
            df[col] = df[col].astype(str)
    return df.to_dict(orient="records")


def load_data(con) -> dict:
    return {
        "generated": date.today().isoformat(),
        "sentimiento_resumen": _query_records(
            con, "SELECT * FROM gold.v_sentimiento_resumen_cuenta ORDER BY cuenta_slug"
        ),
        "sentimiento_por_cuenta": _query_records(
            con,
            """
            SELECT cuenta_slug, cuenta_nombre, plataforma, posicion, comentarios, pct_dentro_cuenta
            FROM gold.v_sentimiento_por_cuenta
            ORDER BY cuenta_slug, plataforma, comentarios DESC
            """,
        ),
        "sentimiento_temporal": _query_records(
            con,
            """
            SELECT cuenta_slug, CAST(dia AS VARCHAR) AS dia, posicion, comentarios
            FROM gold.v_sentimiento_temporal
            WHERE cuenta_slug IS NOT NULL AND dia IS NOT NULL
            ORDER BY dia, cuenta_slug
            """,
        ),
        "narrativa_distribucion": _query_records(
            con,
            """
            SELECT cuenta_slug, plataforma, narrativa, comentarios, pct_narrativa
            FROM gold.v_narrativa_distribucion
            ORDER BY cuenta_slug, comentarios DESC
            """,
        ),
        "narrativa_temporal": _query_records(
            con,
            """
            SELECT cuenta_slug, CAST(semana AS VARCHAR) AS semana, narrativa, comentarios
            FROM gold.v_narrativa_temporal
            WHERE cuenta_slug IS NOT NULL
            ORDER BY semana, cuenta_slug
            """,
        ),
        "trolls_top10": _query_records(
            con,
            """
            SELECT plataforma, ranking, autor_nombre, autor_id, comentarios_troll,
                   dias_activos, CAST(cuentas_slug AS VARCHAR) AS cuentas_slug
            FROM gold.v_trolls_top10
            ORDER BY plataforma, ranking
            """,
        ),
        "trolls_temporal": _query_records(
            con,
            """
            SELECT plataforma, CAST(dia AS VARCHAR) AS dia, cuenta_slug,
                   comentarios_troll, autores_troll, spam_enlaces, insultos, conspiranoia
            FROM gold.v_trolls_temporal
            WHERE cuenta_slug IS NOT NULL
            ORDER BY dia
            """,
        ),
        "trolls_grupos": _query_records(
            con,
            """
            SELECT plataforma, autor_nombre, comentarios_troll, cuentas_distintas,
                   CAST(cuentas_objetivo AS VARCHAR) AS cuentas_objetivo
            FROM gold.v_trolls_grupos_multobjetivo
            ORDER BY comentarios_troll DESC
            LIMIT 15
            """,
        ),
        "trolls_rafagas": _query_records(
            con,
            """
            SELECT plataforma, autor_nombre, cuenta_slug, CAST(dia AS VARCHAR) AS dia,
                   comentarios_en_dia, minutos_span
            FROM gold.v_trolls_rafagas
            ORDER BY comentarios_en_dia DESC
            LIMIT 15
            """,
        ),
        "trolls_rafagas_resumen": _query_records(
            con, "SELECT * FROM gold.v_trolls_rafagas_resumen"
        ),
        "trolls_rafagas_dia": _query_records(
            con,
            """
            SELECT plataforma, cuenta_slug, CAST(dia AS VARCHAR) AS dia,
                   autores_con_rafaga, eventos_rafaga, comentarios_en_rafagas,
                   comentarios_por_autor, max_comentarios_un_autor, rafaga_mas_intensa_min
            FROM gold.v_trolls_rafagas_dia
            ORDER BY autores_con_rafaga DESC, comentarios_en_rafagas DESC
            LIMIT 30
            """,
        ),
        "trolls_rafagas_por_autor": _query_records(
            con,
            """
            SELECT plataforma, autor_nombre, dias_con_rafaga, comentarios_rafaga,
                   cuentas_objetivo, CAST(cuentas_slug AS VARCHAR) AS cuentas_slug,
                   CAST(primera_rafaga AS VARCHAR) AS primera_rafaga,
                   CAST(ultima_rafaga AS VARCHAR) AS ultima_rafaga,
                   promedio_comentarios_rafaga
            FROM gold.v_trolls_rafagas_por_autor
            ORDER BY comentarios_rafaga DESC
            LIMIT 20
            """,
        ),
        "trolls_rafagas_dia_temporal": _query_records(
            con,
            """
            SELECT CAST(dia AS VARCHAR) AS dia, plataforma,
                   SUM(autores_con_rafaga) AS autores_con_rafaga,
                   SUM(comentarios_en_rafagas) AS comentarios_en_rafagas
            FROM gold.v_trolls_rafagas_dia
            GROUP BY dia, plataforma
            ORDER BY dia
            """,
        ),
        "grafo_coocurrencia": _query_records(
            con,
            """
            SELECT source_id, target_id, cuenta_slug, peso_total, contenidos_distintos
            FROM gold.grafo_edges_agg_narrativa
            WHERE edge_type = 'narrativa_coocurrencia'
            ORDER BY peso_total DESC
            LIMIT 20
            """,
        ),
        "grafo_narrativa_cuenta": _query_records(
            con,
            """
            SELECT source_id, target_id, cuenta_slug, peso_total
            FROM gold.grafo_edges_agg_narrativa
            WHERE edge_type = 'narrativa_cuenta'
            ORDER BY peso_total DESC
            """,
        ),
    }


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Reporte Redes — Gold Analytics</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>
    :root {
      --bg: #0f1419;
      --surface: #1a2332;
      --surface2: #243044;
      --text: #e7ecf3;
      --muted: #8b9cb3;
      --accent: #5b8def;
      --apoyo: #3dd68c;
      --troll: #f07178;
      --neutral: #8b9cb3;
      --ambiguo: #f5a524;
      --border: #2d3a4f;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 2rem 1.5rem 4rem;
    }
    .wrap { max-width: 1200px; margin: 0 auto; }
    header { margin-bottom: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 1.5rem; }
    header h1 { font-size: 1.75rem; font-weight: 650; letter-spacing: -0.02em; }
    header p { color: var(--muted); margin-top: 0.5rem; font-size: 0.95rem; }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1rem;
      margin-bottom: 2rem;
    }
    .kpi {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.1rem 1.25rem;
    }
    .kpi .label { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
    .kpi .value { font-size: 1.6rem; font-weight: 700; margin: 0.25rem 0; }
    .kpi .sub { font-size: 0.85rem; color: var(--muted); }
    section { margin-bottom: 2.5rem; }
    section h2 {
      font-size: 1.15rem;
      font-weight: 600;
      margin-bottom: 0.35rem;
    }
    section .desc { color: var(--muted); font-size: 0.9rem; margin-bottom: 1rem; }
    .panel {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.25rem;
      margin-bottom: 1rem;
    }
    .chart-row {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
      gap: 1rem;
    }
    .chart-box { position: relative; height: 320px; }
    .chart-box.tall { height: 400px; }
    .controls { margin-bottom: 1rem; display: flex; gap: 0.75rem; flex-wrap: wrap; align-items: center; }
    select {
      background: var(--surface2);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.45rem 0.75rem;
      font-size: 0.9rem;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.88rem;
    }
    th, td {
      text-align: left;
      padding: 0.55rem 0.65rem;
      border-bottom: 1px solid var(--border);
    }
    th { color: var(--muted); font-weight: 500; font-size: 0.78rem; text-transform: uppercase; }
    tr:hover td { background: rgba(255,255,255,0.02); }
    .badge {
      display: inline-block;
      padding: 0.15rem 0.5rem;
      border-radius: 999px;
      font-size: 0.75rem;
      font-weight: 600;
    }
    .badge.tw { background: #1da1f2; color: #fff; }
    .badge.fb { background: #1877f2; color: #fff; }
    footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--border); color: var(--muted); font-size: 0.82rem; }
    .note { background: var(--surface2); border-left: 3px solid var(--accent); padding: 0.75rem 1rem; border-radius: 0 8px 8px 0; font-size: 0.88rem; color: var(--muted); margin-bottom: 1.5rem; }
    .method-box {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.25rem 1.35rem;
      margin-bottom: 2rem;
      font-size: 0.88rem;
      color: var(--muted);
    }
    .method-box h2 { font-size: 1.05rem; color: var(--text); margin-bottom: 0.75rem; }
    .method-box ol, .method-box ul { margin: 0.5rem 0 0.75rem 1.25rem; }
    .method-box li { margin-bottom: 0.35rem; }
    .method-box code { font-size: 0.82rem; color: var(--accent); }
    .method-flow {
      display: flex; flex-wrap: wrap; gap: 0.35rem; align-items: center;
      margin: 0.75rem 0; font-size: 0.8rem;
    }
    .method-flow span {
      background: var(--surface2); padding: 0.25rem 0.55rem; border-radius: 6px; border: 1px solid var(--border);
    }
    .method-flow .arrow { color: var(--muted); background: none; border: none; }
    .related { margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid var(--border); }
    .related a { color: var(--accent); text-decoration: none; }
    .related a:hover { text-decoration: underline; }
    details.guide {
      background: var(--surface2);
      border: 1px solid var(--border);
      border-radius: 10px;
      margin-bottom: 1rem;
      font-size: 0.86rem;
      color: var(--muted);
    }
    details.guide summary {
      cursor: pointer;
      padding: 0.65rem 1rem;
      color: var(--accent);
      font-weight: 600;
      list-style: none;
    }
    details.guide summary::-webkit-details-marker { display: none; }
    details.guide summary::before { content: "▸ "; }
    details.guide[open] summary::before { content: "▾ "; }
    .guide-body { padding: 0 1rem 1rem 1rem; line-height: 1.55; }
    .guide-body p { margin-bottom: 0.55rem; }
    .guide-body strong { color: var(--text); }
    .guide-body dl { margin: 0.5rem 0; }
    .guide-body dt { color: var(--text); font-weight: 600; margin-top: 0.4rem; }
    .guide-body dd { margin-left: 0; margin-bottom: 0.25rem; }
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>Análisis de comentarios — cuentas PTS</h1>
      <p>Sentimiento, narrativa, trolls y grafo · Fuente: <code>gold.*</code> · Generado: __GENERATED__</p>
    </header>

    <div class="note">
      Christian Castillo no tiene comentarios clasificados en la base actual. Facebook identifica pocos autores troll (solo <code>user_id</code> en ~0,04% de comentarios troll).
    </div>

    <div class="method-box">
      <h2>Metodología — cómo se procesó la información</h2>
      <div class="method-flow">
        <span>landing / CSV legacy</span><span class="arrow">→</span>
        <span>bronze.fb_* · tw_*</span><span class="arrow">→</span>
        <span>silver (limpieza)</span><span class="arrow">→</span>
        <span>clasificación LLM</span><span class="arrow">→</span>
        <span>gold (vistas agregadas)</span><span class="arrow">→</span>
        <span>este reporte</span>
      </div>
      <ol>
        <li><strong>Ingesta silver:</strong> comentarios FB (<code>silver.fb_comment</code>), replies TW (<code>silver.tw_tweets_replies</code>), cuentas trackeadas en <code>gold.v_cuentas_trackeadas</code> (Myriam, Del Caño, Castillo, PTSarg).</li>
        <li><strong>Clasificación de posición:</strong> cada comentario/reply recibe etiqueta LLM — <code>apoyo_izquierda</code>, <code>derecha_o_troll</code>, <code>neutral</code>, <code>ambiguo</code>, <code>inclasificable</code> — más un <code>resumen</code> textual.</li>
        <li><strong>Vista unificada:</strong> <code>gold.v_comentarios_clasificados</code> une FB+TW; <code>gold.v_comentario_narrativa</code> añade narrativa temática (heurística SQL sobre el resumen) y flag <code>es_troll</code>.</li>
        <li><strong>Agregados:</strong> sentimiento, narrativa, trolls y grafos se calculan en SQL (<code>scripts/sql/ingest_redes_gold.sql</code>). Este HTML embebe el JSON exportado el día de generación.</li>
      </ol>
      <p><strong>Cobertura:</strong> FB ~22% de comentarios clasificados; TW muestra de replies a tweets con alto volumen. No es un censo de toda la conversación en redes.</p>
      <div class="related">
        Reportes relacionados (interactivos):
        <a href="../trolls-grafo/report.html">Grafo de trolls (vis.js)</a> ·
        <a href="../analisis-completo/report.pdf">PDF consolidado</a>
      </div>
    </div>

    <div class="kpi-grid" id="kpi-grid"></div>

    <section>
      <h2>1. Sentimiento / posición por cuenta</h2>
      <p class="desc">Distribución de comentarios clasificados (LLM) por cuenta trackeada.</p>
      <details class="guide" open>
        <summary>Cómo interpretar · origen de datos</summary>
        <div class="guide-body">
          <p><strong>Análisis:</strong> mide la posición política inferida en comentarios/replies dirigidos a cada figura PTS, no el sentimiento del post original.</p>
          <p><strong>Procesamiento:</strong> <code>gold.v_sentimiento_por_cuenta</code> agrupa <code>gold.v_comentarios_clasificados</code> por <code>cuenta_slug</code>, plataforma y <code>posicion</code> (etiqueta LLM).</p>
          <p><strong>Lectura del gráfico:</strong> barras apiladas al 100% del volumen clasificado. Verde = apoyo izquierda; rojo = derecha/troll; gris/violeta = neutral o ambiguo. Compare alturas relativas entre cuentas, no valores absolutos sin mirar el total en KPIs.</p>
          <p><strong>Límite:</strong> mezcla FB (masivo, pocos autores identificados) con TW (muestra de replies). Christian Castillo puede no aparecer si no hay clasificados.</p>
        </div>
      </details>
      <div class="panel"><div class="chart-box"><canvas id="chartSentimientoCuenta"></canvas></div></div>
    </section>

    <section>
      <h2>2. Evolución temporal del tono</h2>
      <p class="desc">Comentarios por día — apoyo vs. derecha/troll.</p>
      <details class="guide">
        <summary>Cómo interpretar · origen de datos</summary>
        <div class="guide-body">
          <p><strong>Análisis:</strong> detecta picos de hostilidad o apoyo en el tiempo (eventos, posts virales, actos).</p>
          <p><strong>Procesamiento:</strong> <code>gold.v_sentimiento_temporal</code> — <code>COUNT(*)</code> por <code>dia</code>, <code>cuenta_slug</code> y <code>posicion</code>. Use el selector para cambiar cuenta.</p>
          <p><strong>Lectura:</strong> línea roja sube = más comentarios troll ese día; verde = más apoyo. Cruces bruscos suelen coincidir con publicaciones de la cuenta o noticias (ej. 31-may Myriam).</p>
          <p><strong>Límite:</strong> días sin datos = sin actividad clasificada, no necesariamente silencio real en la red.</p>
        </div>
      </details>
      <div class="controls">
        <label>Cuenta: <select id="selCuentaTemporal"></select></label>
      </div>
      <div class="panel"><div class="chart-box tall"><canvas id="chartSentimientoTemporal"></canvas></div></div>
    </section>

    <section>
      <h2>3. Narrativas dominantes</h2>
      <p class="desc">Temas inferidos del resumen LLM (heurística SQL).</p>
      <details class="guide">
        <summary>Cómo interpretar · origen de datos</summary>
        <div class="guide-body">
          <p><strong>Análisis:</strong> agrupa comentarios por <em>tema</em> (no solo posición), p. ej. insulto, spam/enlaces, Bolivia, feminismo.</p>
          <p><strong>Procesamiento:</strong> <code>gold.v_comentario_narrativa</code> asigna <code>narrativa</code> con reglas SQL sobre el campo <code>resumen</code> del clasificador (palabras clave + fallback a <code>posicion</code>). Distribución en <code>gold.v_narrativa_distribucion</code>; serie semanal en <code>gold.v_narrativa_temporal</code>.</p>
          <p><strong>Lectura:</strong> doughnut = mix temático global de la cuenta; barras apiladas = evolución semanal de temas. <code>critica_antizurda</code> suele dominar porque muchos trolls no matchean keywords específicas.</p>
          <p><strong>Límite:</strong> heurística, no topic modeling; un comentario = una narrativa principal.</p>
        </div>
      </details>
      <div class="controls">
        <label>Cuenta: <select id="selCuentaNarrativa"></select></label>
      </div>
      <div class="chart-row">
        <div class="panel"><div class="chart-box"><canvas id="chartNarrativa"></canvas></div></div>
        <div class="panel"><div class="chart-box"><canvas id="chartNarrativaTemporal"></canvas></div></div>
      </div>
    </section>

    <section>
      <h2>4. Top 10 trolls recurrentes (Twitter/X)</h2>
      <p class="desc">Autores con más comentarios <code>derecha_o_troll</code> identificados.</p>
      <details class="guide">
        <summary>Cómo interpretar · origen de datos</summary>
        <div class="guide-body">
          <p><strong>Análisis:</strong> ranking de handles TW con más replies clasificados como troll hacia cuentas trackeadas.</p>
          <p><strong>Procesamiento:</strong> <code>gold.v_trolls_top10</code> filtra <code>posicion = derecha_o_troll</code>, exige autor identificado (<code>reply_author_username</code>), cuenta por plataforma, top 10 por volumen.</p>
          <p><strong>Lectura:</strong> barra más larga = más comentarios troll en la muestra. No implica bot; puede ser usuario muy activo. FB casi no tiene autores identificados — este gráfico es representativo de TW.</p>
        </div>
      </details>
      <div class="panel"><div class="chart-box"><canvas id="chartTrollsTop"></canvas></div></div>
    </section>

    <section>
      <h2>5. Actividad troll en el tiempo</h2>
      <p class="desc">Volumen diario y autores distintos.</p>
      <details class="guide">
        <summary>Cómo interpretar · origen de datos</summary>
        <div class="guide-body">
          <p><strong>Análisis:</strong> relaciona volumen de trolls con diversidad de autores (¿pocos autores muy activos o muchos autores dispersos?).</p>
          <p><strong>Procesamiento:</strong> <code>gold.v_trolls_temporal</code> desde <code>gold.v_trolls_actividad</code> (solo trolls con autor identificado). Eje izq.: comentarios; eje der.: autores distintos por día.</p>
          <p><strong>Lectura:</strong> pico rojo + azul bajo = pocos autores generan mucho volumen (ráfaga). Pico rojo + azul alto = muchos autores distintos el mismo día (posible evento mediático).</p>
        </div>
      </details>
      <div class="controls">
        <label>Cuenta objetivo: <select id="selCuentaTroll"></select></label>
      </div>
      <div class="panel"><div class="chart-box tall"><canvas id="chartTrollsTemporal"></canvas></div></div>
    </section>

    <section>
      <h2>6. Trolls multi-objetivo y ráfagas</h2>
      <p class="desc">Autores que atacan varias cuentas; ráfaga = ≥3 comentarios troll del mismo autor el mismo día contra la misma cuenta.</p>
      <details class="guide">
        <summary>Cómo interpretar · origen de datos</summary>
        <div class="guide-body">
          <p><strong>Análisis:</strong> identifica trolls “puente” (varias cuentas PTS) y bursts individuales (spam en ráfaga).</p>
          <p><strong>Procesamiento:</strong> multi-objetivo = <code>gold.v_trolls_grupos_multobjetivo</code> (≥2 cuentas). Ráfaga = <code>gold.v_trolls_rafagas</code> (≥3 trolls/autor/día/cuenta). Tabla: <strong>N</strong> comentarios en el burst; <strong>Min</strong> minutos entre primero y último comentario del día (Min≈0 = ráfaga muy concentrada).</p>
          <p><strong>Lectura:</strong> multi-objetivo muestra actores que rotan entre figuras PTS; ráfagas individuales muestran el caso extremo (ej. 19 comentarios en un día).</p>
        </div>
      </details>
      <div class="kpi-grid" id="kpi-rafagas" style="margin-bottom:1rem;"></div>
      <div class="chart-row">
        <div class="panel">
          <h3 style="font-size:0.95rem;margin-bottom:0.75rem;">Multi-objetivo</h3>
          <div style="overflow-x:auto"><table id="tblGrupos"><thead><tr>
            <th>Autor</th><th>Plat.</th><th>Trolls</th><th>Cuentas</th><th>Objetivos</th>
          </tr></thead><tbody></tbody></table></div>
        </div>
        <div class="panel">
          <h3 style="font-size:0.95rem;margin-bottom:0.75rem;">Ráfagas individuales</h3>
          <p style="font-size:0.78rem;color:var(--muted);margin-bottom:0.5rem;">N = comentarios del autor ese día · Min = minutos entre 1.º y último</p>
          <div style="overflow-x:auto"><table id="tblRafagas"><thead><tr>
            <th>Autor</th><th>Día</th><th>N</th><th>Min</th><th>Cuenta</th>
          </tr></thead><tbody></tbody></table></div>
        </div>
      </div>
    </section>

    <section>
      <h2>6b. Autores distintos en ráfagas de trolls</h2>
      <p class="desc">Cuántos autores diferentes tuvieron ráfaga el mismo día (sincronía temporal, no coordinación probada).</p>
      <details class="guide">
        <summary>Cómo interpretar · origen de datos</summary>
        <div class="guide-body">
          <p><strong>Análisis:</strong> mide cohortes — varios autores con patrón de ráfaga el mismo día contra la misma cuenta.</p>
          <p><strong>Procesamiento:</strong> <code>gold.v_trolls_rafagas_dia</code> agrupa ráfagas por <code>dia + cuenta_slug</code> y cuenta autores distintos. <strong>Autores</strong> = handles con ≥3 trolls ese día; <strong>Eventos</strong> = filas de ráfaga; <strong>Máx/autor</strong> = burst más intenso del día.</p>
          <p><strong>Lectura:</strong> gráfico compara días/cuentas con más autores en ráfaga vs comentarios totales en esos bursts. 31-may myriambregman suele ser el pico (varios autores en paralelo).</p>
        </div>
      </details>
      <div class="chart-row">
        <div class="panel"><div class="chart-box tall"><canvas id="chartRafagasAutoresDia"></canvas></div></div>
        <div class="panel"><div class="chart-box tall"><canvas id="chartRafagasTemporal"></canvas></div></div>
      </div>
      <div class="chart-row">
        <div class="panel">
          <h3 style="font-size:0.95rem;margin-bottom:0.75rem;">Días con más autores en ráfaga</h3>
          <div style="overflow-x:auto"><table id="tblRafagasDia"><thead><tr>
            <th>Día</th><th>Cuenta</th><th>Plat.</th><th>Autores</th><th>Comentarios</th><th>Eventos</th><th>Máx/autor</th>
          </tr></thead><tbody></tbody></table></div>
        </div>
        <div class="panel">
          <h3 style="font-size:0.95rem;margin-bottom:0.75rem;">Autores recurrentes en ráfagas</h3>
          <div style="overflow-x:auto"><table id="tblRafagasAutores"><thead><tr>
            <th>Autor</th><th>Plat.</th><th>Días ráfaga</th><th>Comentarios</th><th>Cuentas</th><th>Prom/día</th>
          </tr></thead><tbody></tbody></table></div>
        </div>
      </div>
    </section>

    <section>
      <h2>7. Grafo de narrativas</h2>
      <p class="desc">Co-ocurrencia de narrativas en el mismo post/tweet; peso narrativa→cuenta.</p>
      <details class="guide">
        <summary>Cómo interpretar · origen de datos</summary>
        <div class="guide-body">
          <p><strong>Análisis:</strong> qué temas conviven en el mismo hilo (co-ocurrencia) y qué narrativas pesan más por cuenta objetivo.</p>
          <p><strong>Procesamiento:</strong> <code>gold.grafo_edges_agg_narrativa</code> — aristas <code>narrativa_coocurrencia</code> (mismo <code>contenido_padre_id</code>) y <code>narrativa_cuenta</code> (peso agregado).</p>
          <p><strong>Lectura:</strong> izquierda = pares de narrativas que aparecen juntas en posts; derecha = barras por cuenta (Myriam, Del Caño, PTS). Para exploración de <em>autores</em> troll use el <a href="../trolls-grafo/report.html" style="color:var(--accent)">grafo interactivo de trolls</a>.</p>
        </div>
      </details>
      <div class="chart-row">
        <div class="panel"><div class="chart-box tall"><canvas id="chartGrafoCooc"></canvas></div></div>
        <div class="panel"><div class="chart-box tall"><canvas id="chartGrafoNarrCuenta"></canvas></div></div>
      </div>
    </section>

    <footer>
      <p><strong>Regeneración:</strong> <code>uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_redes_gold.sql</code> → <code>uv run python scripts/python/generate_redes_gold_report.py</code></p>
      <p>Vistas gold: v_sentimiento_*, v_narrativa_*, v_trolls_*, grafo_* · Sin PII en agregados · PDF: <a href="../analisis-completo/report.pdf" style="color:var(--accent)">analisis-completo/report.pdf</a></p>
    </footer>
  </div>

  <script>
    const DATA = __DATA_JSON__;

    const COLORS = {
      apoyo_izquierda: '#3dd68c',
      derecha_o_troll: '#f07178',
      neutral: '#8b9cb3',
      ambiguo: '#f5a524',
      inclasificable: '#c084fc',
      critica_antizurda: '#f07178',
      apoyo_movilizacion: '#3dd68c',
      insulto_descalificacion: '#fb923c',
      spam_enlaces: '#60a5fa',
      conspiranoia: '#a78bfa',
      sin_contenido: '#64748b',
      neutral_ambiguo: '#94a3b8',
      otros: '#475569',
    };

    const charts = {};

    function colorPosicion(p) { return COLORS[p] || '#64748b'; }
    function colorNarrativa(n) { return COLORS[n] || '#64748b'; }
    function shortLabel(s) { return (s || '').replace('narrativa:', '').replace('cuenta:', ''); }

    Chart.defaults.color = '#8b9cb3';
    Chart.defaults.borderColor = '#2d3a4f';
    Chart.defaults.font.family = '"Segoe UI", system-ui, sans-serif';

    function renderKPIs() {
      const grid = document.getElementById('kpi-grid');
      const total = DATA.sentimiento_resumen.reduce((a, r) => a + r.comentarios_clasificados, 0);
      const cards = [
        { label: 'Comentarios clasificados', value: total.toLocaleString('es-AR'), sub: 'FB + TW · cuentas trackeadas' },
        ...DATA.sentimiento_resumen.map(r => ({
          label: r.cuenta_nombre,
          value: r.pct_troll + '% troll',
          sub: `${r.comentarios_clasificados.toLocaleString('es-AR')} comentarios · ${r.pct_apoyo}% apoyo`,
        })),
      ];
      grid.innerHTML = cards.map(c => `
        <div class="kpi"><div class="label">${c.label}</div><div class="value">${c.value}</div><div class="sub">${c.sub}</div></div>
      `).join('');
    }

    function renderSentimientoCuenta() {
      const cuentas = DATA.sentimiento_resumen.map(r => r.cuenta_nombre);
      const posiciones = ['apoyo_izquierda', 'derecha_o_troll', 'ambiguo', 'inclasificable', 'neutral'];
      const datasets = posiciones.map(pos => ({
        label: pos.replace(/_/g, ' '),
        data: DATA.sentimiento_resumen.map(r => {
          if (pos === 'ambiguo') return (r.ambiguo_inclasificable || 0) * (r.ambiguo_inclasificable ? 1 : 0);
          return r[pos] || 0;
        }),
        backgroundColor: colorPosicion(pos),
        stack: 's',
      }));
      // fix ambiguo split - use sentimiento_por_cuenta aggregated
      const byCuentaPos = {};
      DATA.sentimiento_por_cuenta.forEach(r => {
        const key = r.cuenta_slug + '|' + r.posicion;
        byCuentaPos[key] = (byCuentaPos[key] || 0) + r.comentarios;
      });
      const slugs = DATA.sentimiento_resumen.map(r => r.cuenta_slug);
      const posList = ['apoyo_izquierda', 'derecha_o_troll', 'inclasificable', 'ambiguo', 'neutral'];
      charts.sentCuenta = new Chart(document.getElementById('chartSentimientoCuenta'), {
        type: 'bar',
        data: {
          labels: cuentas,
          datasets: posList.map(pos => ({
            label: pos.replace(/_/g, ' '),
            data: slugs.map(s => byCuentaPos[s + '|' + pos] || 0),
            backgroundColor: colorPosicion(pos),
            stack: 'stack',
          })),
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'bottom' } },
          scales: {
            x: { stacked: true },
            y: { stacked: true, beginAtZero: true, ticks: { callback: v => v >= 1000 ? (v/1000)+'k' : v } },
          },
        },
      });
    }

    function fillSelect(id, values) {
      const sel = document.getElementById(id);
      sel.innerHTML = values.map(v => `<option value="${v}">${v}</option>`).join('');
    }

    function renderSentimientoTemporal(slug) {
      const rows = DATA.sentimiento_temporal.filter(r => r.cuenta_slug === slug);
      const dias = [...new Set(rows.map(r => r.dia))].sort();
      const apoyo = dias.map(d => rows.filter(r => r.dia === d && r.posicion === 'apoyo_izquierda').reduce((a,b)=>a+b.comentarios,0));
      const troll = dias.map(d => rows.filter(r => r.dia === d && r.posicion === 'derecha_o_troll').reduce((a,b)=>a+b.comentarios,0));
      if (charts.sentTemp) charts.sentTemp.destroy();
      charts.sentTemp = new Chart(document.getElementById('chartSentimientoTemporal'), {
        type: 'line',
        data: {
          labels: dias.map(d => d.slice(0, 10)),
          datasets: [
            { label: 'Apoyo izquierda', data: apoyo, borderColor: COLORS.apoyo_izquierda, backgroundColor: 'rgba(61,214,140,0.15)', fill: true, tension: 0.25 },
            { label: 'Derecha / troll', data: troll, borderColor: COLORS.derecha_o_troll, backgroundColor: 'rgba(240,113,120,0.12)', fill: true, tension: 0.25 },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          plugins: { legend: { position: 'bottom' } },
          scales: { y: { beginAtZero: true } },
        },
      });
    }

    function renderNarrativa(slug) {
      const rows = DATA.narrativa_distribucion.filter(r => r.cuenta_slug === slug);
      const top = rows.slice(0, 8);
      if (charts.narr) charts.narr.destroy();
      charts.narr = new Chart(document.getElementById('chartNarrativa'), {
        type: 'doughnut',
        data: {
          labels: top.map(r => r.narrativa.replace(/_/g, ' ')),
          datasets: [{ data: top.map(r => r.comentarios), backgroundColor: top.map(r => colorNarrativa(r.narrativa)) }],
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { boxWidth: 12 } } } },
      });

      const temp = DATA.narrativa_temporal.filter(r => r.cuenta_slug === slug);
      const semanas = [...new Set(temp.map(r => r.semana))].sort();
      const narrs = [...new Set(temp.map(r => r.narrativa))].slice(0, 5);
      if (charts.narrTemp) charts.narrTemp.destroy();
      charts.narrTemp = new Chart(document.getElementById('chartNarrativaTemporal'), {
        type: 'bar',
        data: {
          labels: semanas.map(s => s.slice(0, 10)),
          datasets: narrs.map(n => ({
            label: n.replace(/_/g, ' '),
            data: semanas.map(s => temp.filter(r => r.semana === s && r.narrativa === n).reduce((a,b)=>a+b.comentarios,0)),
            backgroundColor: colorNarrativa(n),
            stack: 'n',
          })),
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'bottom' } },
          scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } },
        },
      });
    }

    function renderTrollsTop() {
      const tw = DATA.trolls_top10.filter(r => r.plataforma === 'twitter');
      charts.trollsTop = new Chart(document.getElementById('chartTrollsTop'), {
        type: 'bar',
        data: {
          labels: tw.map(r => r.autor_nombre || r.autor_id),
          datasets: [{
            label: 'Comentarios troll',
            data: tw.map(r => r.comentarios_troll),
            backgroundColor: COLORS.derecha_o_troll,
          }],
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: { x: { beginAtZero: true } },
        },
      });
    }

    function renderTrollsTemporal(slug) {
      const rows = DATA.trolls_temporal.filter(r => r.cuenta_slug === slug && r.plataforma === 'twitter');
      const dias = [...new Set(rows.map(r => r.dia))].sort();
      if (charts.trollTemp) charts.trollTemp.destroy();
      charts.trollTemp = new Chart(document.getElementById('chartTrollsTemporal'), {
        type: 'line',
        data: {
          labels: dias.map(d => d.slice(0, 10)),
          datasets: [
            { label: 'Comentarios troll', data: dias.map(d => rows.filter(r=>r.dia===d).reduce((a,b)=>a+b.comentarios_troll,0)), borderColor: COLORS.derecha_o_troll, yAxisID: 'y', tension: 0.25 },
            { label: 'Autores distintos', data: dias.map(d => rows.filter(r=>r.dia===d).reduce((a,b)=>a+b.autores_troll,0)), borderColor: COLORS.spam_enlaces, yAxisID: 'y1', tension: 0.25 },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          scales: {
            y: { type: 'linear', position: 'left', beginAtZero: true },
            y1: { type: 'linear', position: 'right', beginAtZero: true, grid: { drawOnChartArea: false } },
          },
        },
      });
    }

    function renderRafagasKPIs() {
      const r = (DATA.trolls_rafagas_resumen && DATA.trolls_rafagas_resumen[0]) || {};
      const peak = (DATA.trolls_rafagas_dia || [])[0] || {};
      const cards = [
        { label: 'Autores con ráfaga', value: (r.autores_distintos_con_rafaga || 0).toLocaleString('es-AR'), sub: `${r.eventos_rafaga_total || 0} eventos · ${r.comentarios_en_rafagas_total || 0} comentarios` },
        { label: 'Pico autores/día', value: peak.autores_con_rafaga || '—', sub: peak.dia ? `${peak.dia.slice(0,10)} · ${peak.cuenta_slug || ''}` : '—' },
        { label: 'Cuentas afectadas', value: r.cuentas_objetivo_afectadas || 0, sub: `${(r.primer_dia_rafaga||'').slice(0,10)} → ${(r.ultimo_dia_rafaga||'').slice(0,10)}` },
      ];
      document.getElementById('kpi-rafagas').innerHTML = cards.map(c => `
        <div class="kpi"><div class="label">${c.label}</div><div class="value">${c.value}</div><div class="sub">${c.sub}</div></div>
      `).join('');
    }

    function renderRafagasAutores() {
      const top = (DATA.trolls_rafagas_dia || []).slice(0, 12);
      charts.rafagasAutoresDia = new Chart(document.getElementById('chartRafagasAutoresDia'), {
        type: 'bar',
        data: {
          labels: top.map(r => `${(r.dia||'').slice(0,10)} · ${r.cuenta_slug}`),
          datasets: [
            { label: 'Autores con ráfaga', data: top.map(r => r.autores_con_rafaga), backgroundColor: '#60a5fa' },
            { label: 'Comentarios en ráfagas', data: top.map(r => r.comentarios_en_rafagas), backgroundColor: '#f07178' },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'bottom' }, title: { display: true, text: 'Top días · cuenta (autores distintos vs comentarios)' } },
          scales: { y: { beginAtZero: true } },
        },
      });

      const temp = DATA.trolls_rafagas_dia_temporal || [];
      const dias = [...new Set(temp.map(r => r.dia))].sort();
      charts.rafagasTemporal = new Chart(document.getElementById('chartRafagasTemporal'), {
        type: 'line',
        data: {
          labels: dias.map(d => d.slice(0, 10)),
          datasets: [
            {
              label: 'Autores con ráfaga (TW)',
              data: dias.map(d => temp.filter(r => r.dia === d && r.plataforma === 'twitter').reduce((a,b) => a + b.autores_con_rafaga, 0)),
              borderColor: '#60a5fa',
              tension: 0.25,
            },
            {
              label: 'Comentarios ráfaga (TW)',
              data: dias.map(d => temp.filter(r => r.dia === d && r.plataforma === 'twitter').reduce((a,b) => a + b.comentarios_en_rafagas, 0)),
              borderColor: '#f07178',
              yAxisID: 'y1',
              tension: 0.25,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          plugins: { legend: { position: 'bottom' }, title: { display: true, text: 'Evolución diaria (Twitter)' } },
          scales: {
            y: { beginAtZero: true, title: { display: true, text: 'Autores' } },
            y1: { position: 'right', beginAtZero: true, grid: { drawOnChartArea: false }, title: { display: true, text: 'Comentarios' } },
          },
        },
      });

      document.querySelector('#tblRafagasDia tbody').innerHTML = (DATA.trolls_rafagas_dia || []).slice(0, 15).map(r => `
        <tr>
          <td>${(r.dia||'').slice(0,10)}</td>
          <td>${r.cuenta_slug}</td>
          <td><span class="badge ${r.plataforma === 'twitter' ? 'tw' : 'fb'}">${r.plataforma}</span></td>
          <td><strong>${r.autores_con_rafaga}</strong></td>
          <td>${r.comentarios_en_rafagas}</td>
          <td>${r.eventos_rafaga}</td>
          <td>${r.max_comentarios_un_autor}</td>
        </tr>`).join('');

      document.querySelector('#tblRafagasAutores tbody').innerHTML = (DATA.trolls_rafagas_por_autor || []).slice(0, 15).map(r => `
        <tr>
          <td>${r.autor_nombre || '—'}</td>
          <td><span class="badge ${r.plataforma === 'twitter' ? 'tw' : 'fb'}">${r.plataforma}</span></td>
          <td>${r.dias_con_rafaga}</td>
          <td>${r.comentarios_rafaga}</td>
          <td>${r.cuentas_objetivo}</td>
          <td>${r.promedio_comentarios_rafaga}</td>
        </tr>`).join('');
    }

    function renderTables() {
      document.querySelector('#tblGrupos tbody').innerHTML = DATA.trolls_grupos.map(r => `
        <tr>
          <td>${r.autor_nombre || '—'}</td>
          <td><span class="badge ${r.plataforma === 'twitter' ? 'tw' : 'fb'}">${r.plataforma}</span></td>
          <td>${r.comentarios_troll}</td>
          <td>${r.cuentas_distintas}</td>
          <td>${shortLabel(r.cuentas_objetivo)}</td>
        </tr>`).join('');
      document.querySelector('#tblRafagas tbody').innerHTML = DATA.trolls_rafagas.map(r => `
        <tr>
          <td>${r.autor_nombre || '—'}</td>
          <td>${(r.dia||'').slice(0,10)}</td>
          <td>${r.comentarios_en_dia}</td>
          <td>${r.minutos_span}</td>
          <td>${r.cuenta_slug}</td>
        </tr>`).join('');
    }

    function renderGrafo() {
      const cooc = DATA.grafo_coocurrencia.slice(0, 12);
      charts.grafoCooc = new Chart(document.getElementById('chartGrafoCooc'), {
        type: 'bar',
        data: {
          labels: cooc.map(r => shortLabel(r.source_id) + ' + ' + shortLabel(r.target_id)),
          datasets: [{ label: 'Co-ocurrencias', data: cooc.map(r => r.peso_total), backgroundColor: '#a78bfa' }],
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false }, title: { display: true, text: 'Narrativas en el mismo post' } },
          scales: { x: { beginAtZero: true } },
        },
      });

      const nc = DATA.grafo_narrativa_cuenta;
      const cuentas = [...new Set(nc.map(r => r.cuenta_slug))];
      const narrs = [...new Set(nc.map(r => shortLabel(r.source_id)))];
      charts.grafoNC = new Chart(document.getElementById('chartGrafoNarrCuenta'), {
        type: 'bar',
        data: {
          labels: narrs,
          datasets: cuentas.map((c, i) => ({
            label: c,
            data: narrs.map(n => {
              const row = nc.find(r => r.cuenta_slug === c && shortLabel(r.source_id) === n);
              return row ? row.peso_total : 0;
            }),
            backgroundColor: ['#f07178','#3dd68c','#60a5fa'][i % 3],
          })),
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'bottom' }, title: { display: true, text: 'Peso narrativa → cuenta' } },
          scales: { y: { beginAtZero: true, ticks: { callback: v => v >= 1000 ? (v/1000)+'k' : v } } },
        },
      });
    }

    function init() {
      renderKPIs();
      renderSentimientoCuenta();
      const cuentas = DATA.sentimiento_resumen.map(r => r.cuenta_slug);
      fillSelect('selCuentaTemporal', cuentas);
      fillSelect('selCuentaNarrativa', cuentas);
      fillSelect('selCuentaTroll', cuentas);
      renderSentimientoTemporal(cuentas[0]);
      renderNarrativa(cuentas[0]);
      renderTrollsTop();
      renderTrollsTemporal(cuentas[0]);
      renderRafagasKPIs();
      renderTables();
      renderRafagasAutores();
      renderGrafo();
      document.getElementById('selCuentaTemporal').addEventListener('change', e => renderSentimientoTemporal(e.target.value));
      document.getElementById('selCuentaNarrativa').addEventListener('change', e => renderNarrativa(e.target.value));
      document.getElementById('selCuentaTroll').addEventListener('change', e => renderTrollsTemporal(e.target.value));
    }
    init();
  </script>
</body>
</html>
"""


BUNDLE_README = """\
# Gold report — dashboard PTS

Dashboard Chart.js: sentimiento, narrativa, trolls, ráfagas.

| Archivo | Rol |
|---------|-----|
| `report.html` | Vista principal (datos embebidos) |
| `data.json` | Export JSON desde gold.* |

Generado: {generated}
Regenerar: `uv run python scripts/python/generate_redes_gold_report.py`
"""


def main() -> int:
    con = db.connect_for_ingest(release_mcp=True)
    data = load_data(con)
    con.close()

    generated = data["generated"]
    out_dir = db.get_report_bundle("redes", "gold-report")

    json_path = out_dir / "data.json"
    html_path = out_dir / "report.html"
    readme_path = out_dir / "README.md"

    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    html = (
        HTML_TEMPLATE.replace("__GENERATED__", generated)
        .replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
    )
    html_path.write_text(html, encoding="utf-8")
    readme_path.write_text(BUNDLE_README.format(generated=generated), encoding="utf-8")

    print(f"Bundle: {out_dir}/")
    print(f"  report.html")
    print(f"  data.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
