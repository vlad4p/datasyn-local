"""Assign La Nación pol/soc articles to nearest hater narrative clusters via LLM.

Affinity = thematic closeness of the article to an existing attack-frame cluster
(from gold.tk_hater_narrativa_cluster), not proof of causation.

Usage:
    uv run python scripts/python/classify/classify_lanacion_to_hater_clusters.py
    uv run python scripts/python/classify/classify_lanacion_to_hater_clusters.py --limit 20 --dry-run
    uv run python scripts/python/db.py run-sql --ingest \\
      --file scripts/sql/news/ingest_contexto_ln_hater_afinidade.sql

Requires: LLM_API_KEY (or DEEPSEEK_API_KEY) in .env; uv sync --extra llm
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import db  # noqa: E402

REPO_ROOT = db.PROJECT_ROOT
SCORE_FLOOR = 0.35
SIN_AFINIDAD = "sin_afinidad"

SYSTEM = """Sos un analista político argentino.
Te dan un catálogo de clusters de narrativas hostiles (marcos de ataque en X)
y una lista de artículos de La Nación (política/sociedad).

Para CADA artículo elegí el cluster_label del catálogo con mayor afinidad temática
al contenido de la nota (no al tono del odio). Ejemplos:
- nota sobre corrupción / causas judiciales → acusaciones_corrupcion_delincuencia
- nota sobre Milei / medidas del gobierno → criticas_gobierno_milei
- nota sobre protestas / piquetes → descalificacion_de_protestas_y_movilizaciones
- nota internacional Medio Oriente → temas_internacionales
Si ningún cluster encaja con afinidad razonable, usá score bajo (<0.35).

Respondé SOLO JSON válido:
{"items":[{"id":"<id>","cluster_label":"<label_del_catalogo>","score":0.0}]}

Reglas:
- UN item por cada id recibido, mismo id.
- cluster_label DEBE ser exactamente uno de los labels del catálogo.
- score float 0..1 (confianza de afinidad)."""

LLM_PROVIDERS: dict[str, dict[str, str]] = {
    "deepseek": {"base_url": "https://api.deepseek.com", "model": "deepseek-chat"},
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
}


class LlmConfig(NamedTuple):
    provider: str
    api_key: str
    model: str
    base_url: str


def resolve_llm_config() -> LlmConfig:
    provider = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()
    defaults = LLM_PROVIDERS.get(provider, LLM_PROVIDERS["deepseek"])
    api_key = (
        os.getenv("LLM_API_KEY", "").strip() or os.getenv("DEEPSEEK_API_KEY", "").strip()
    )
    model = (
        os.getenv("CHAT_MODEL", "").strip()
        or os.getenv("LLM_MODEL", defaults["model"]).strip()
    )
    base_url = os.getenv("LLM_BASE_URL", defaults["base_url"]).strip()
    return LlmConfig(provider=provider, api_key=api_key, model=model, base_url=base_url)


def _parse_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _chunk(rows: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [rows[i : i + size] for i in range(0, len(rows), size)]


def _ensure_table(con) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS gold")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS gold.ln_hecho_hater_cluster (
          url VARCHAR PRIMARY KEY,
          fecha DATE,
          seccion VARCHAR,
          titulo VARCHAR,
          cluster_id VARCHAR,
          cluster_label VARCHAR,
          score DOUBLE,
          run_id VARCHAR,
          assigned_at TIMESTAMP DEFAULT current_timestamp
        )
        """
    )


def _fetch_clusters(con) -> list[dict[str, Any]]:
    return con.sql(
        """
        SELECT cluster_id, label, descripcion, n_replies
        FROM gold.tk_hater_narrativa_cluster
        ORDER BY n_replies DESC NULLS LAST, label
        """
    ).fetchdf().to_dict("records")


def _fetch_articles(con, limit: int | None) -> list[dict[str, Any]]:
    lim = f"LIMIT {int(limit)}" if limit and limit > 0 else ""
    return con.sql(
        f"""
        SELECT
          url,
          fecha,
          seccion,
          titulo,
          left(coalesce(cuerpo_md, ''), 1200) AS cuerpo
        FROM silver.lanacion_articulos
        WHERE fecha IS NOT NULL
          AND seccion IN ('politica', 'seguridad', 'editoriales', 'opinion')
          AND url IS NOT NULL
        ORDER BY fecha DESC, url
        {lim}
        """
    ).fetchdf().to_dict("records")


def _call_batch(
    client: Any,
    model: str,
    batch: list[dict[str, Any]],
    catalog: list[dict[str, str]],
) -> list[dict[str, Any]]:
    payload = [
        {
            "id": str(i),
            "titulo": str(r.get("titulo") or "")[:200],
            "seccion": str(r.get("seccion") or ""),
            "fecha": str(r.get("fecha") or "")[:10],
            "texto": str(r.get("cuerpo") or "")[:900].replace("\n", " "),
        }
        for i, r in enumerate(batch)
    ]
    user_msg = (
        "Catálogo de clusters (elegí SOLO estos labels):\n"
        + json.dumps(catalog, ensure_ascii=False)
        + f"\n\nClasificá estos {len(payload)} artículos. Devolvé JSON con items[].\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.1,
        max_tokens=min(8000, 80 * len(payload) + 800),
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    data = _parse_json(raw)
    items = data.get("items")
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        out.append(
            {
                "id": str(it.get("id", "")),
                "cluster_label": str(it.get("cluster_label") or "").strip(),
                "score": float(it.get("score") or 0.0),
            }
        )
    return out


def run(
    *,
    batch_size: int,
    limit: int | None,
    dry_run: bool,
    rate_limit: float,
) -> int:
    load_dotenv(REPO_ROOT / ".env")
    llm = resolve_llm_config()
    if not llm.api_key and not dry_run:
        print("LLM_API_KEY (or DEEPSEEK_API_KEY) not set in .env", file=sys.stderr)
        return 1

    con = db.connect_for_ingest(release_mcp=True)
    try:
        _ensure_table(con)
        clusters = _fetch_clusters(con)
        if not clusters:
            print(
                "No hater clusters in gold.tk_hater_narrativa_cluster. "
                "Run classify_tk_tw_replies.py --cluster-haters first.",
                file=sys.stderr,
            )
            return 1

        articles = _fetch_articles(con, limit)
        if not articles:
            print("No La Nación pol/soc articles in silver.lanacion_articulos.")
            return 0

        label_to_id = {str(c["label"]): str(c["cluster_id"]) for c in clusters}
        catalog = [
            {
                "label": str(c["label"]),
                "descripcion": str(c.get("descripcion") or "")[:180],
            }
            for c in clusters
        ]

        print(
            f"Articles: {len(articles)}; clusters: {len(clusters)}; "
            f"batch_size={batch_size} via {llm.provider}/{llm.model}"
        )
        if dry_run:
            for a in articles[:5]:
                print(f"  {a['fecha']} [{a['seccion']}] {(a.get('titulo') or '')[:70]}")
            print(f"  … dry-run (no LLM / no writes)")
            return 0

        try:
            from openai import OpenAI
        except ImportError:
            print("Install LLM extra: uv sync --extra llm", file=sys.stderr)
            return 1

        client = OpenAI(api_key=llm.api_key, base_url=llm.base_url, timeout=180.0)
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        batches = _chunk(articles, batch_size)
        assignments: list[dict[str, Any]] = []

        for bi, batch in enumerate(batches, 1):
            print(f"  batch {bi}/{len(batches)} (n={len(batch)})", flush=True)
            try:
                items = _call_batch(client, llm.model, batch, catalog)
            except Exception as exc:
                print(f"    batch error: {exc}", file=sys.stderr, flush=True)
                items = []

            by_id = {str(it["id"]): it for it in items}
            for i, art in enumerate(batch):
                it = by_id.get(str(i), {})
                label = str(it.get("cluster_label") or "").strip()
                try:
                    score = float(it.get("score") or 0.0)
                except (TypeError, ValueError):
                    score = 0.0
                score = max(0.0, min(1.0, score))
                if label not in label_to_id or score < SCORE_FLOOR:
                    label = SIN_AFINIDAD
                    cid = None
                else:
                    cid = label_to_id[label]
                assignments.append(
                    {
                        "url": art["url"],
                        "fecha": art["fecha"],
                        "seccion": art["seccion"],
                        "titulo": art["titulo"],
                        "cluster_id": cid,
                        "cluster_label": label,
                        "score": score,
                        "run_id": run_id,
                    }
                )
            if rate_limit > 0 and bi < len(batches):
                time.sleep(rate_limit)

        con.execute("DELETE FROM gold.ln_hecho_hater_cluster")
        con.executemany(
            """
            INSERT INTO gold.ln_hecho_hater_cluster (
              url, fecha, seccion, titulo, cluster_id, cluster_label, score, run_id, assigned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
            """,
            [
                [
                    a["url"],
                    a["fecha"],
                    a["seccion"],
                    a["titulo"],
                    a["cluster_id"],
                    a["cluster_label"],
                    a["score"],
                    a["run_id"],
                ]
                for a in assignments
            ],
        )
        by_lab: dict[str, int] = {}
        for a in assignments:
            by_lab[a["cluster_label"]] = by_lab.get(a["cluster_label"], 0) + 1
        print(f"✅ Wrote {len(assignments)} rows to gold.ln_hecho_hater_cluster (run_id={run_id})")
        for lab, n in sorted(by_lab.items(), key=lambda x: -x[1])[:12]:
            print(f"  {n:4d}  {lab}")
        return 0
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assign LN pol/soc articles to hater narrative clusters"
    )
    parser.add_argument("--batch-size", type=int, default=12, help="Articles per LLM request")
    parser.add_argument("--limit", type=int, default=0, help="Max articles (0=all)")
    parser.add_argument("--dry-run", action="store_true", help="List articles, no LLM/writes")
    parser.add_argument("--rate-limit", type=float, default=0.4, help="Sleep between batches")
    args = parser.parse_args(argv)
    if args.batch_size < 1:
        print("--batch-size must be >= 1", file=sys.stderr)
        return 1
    return run(
        batch_size=args.batch_size,
        limit=args.limit or None,
        dry_run=args.dry_run,
        rate_limit=args.rate_limit,
    )


if __name__ == "__main__":
    sys.exit(main())
