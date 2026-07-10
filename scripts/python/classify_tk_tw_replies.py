"""Batch-classify twikit replies + cluster hater/apoyo narratives via LLM.

Uses CHAT_MODEL if set, else LLM_MODEL (OpenAI-compatible).

Usage:
    uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_tk_tw_classification.sql
    uv run python scripts/python/classify_tk_tw_replies.py --batch-size 50 --cluster-haters
    uv run python scripts/python/classify_tk_tw_replies.py --cluster-apoyo
    uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_tk_hater_narrativa.sql
    uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_tk_apoyo_narrativa.sql

Requires: LLM_API_KEY (or DEEPSEEK_API_KEY) in .env; uv sync --extra llm
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SQL_CLASS = REPO_ROOT / "scripts" / "sql" / "ingest_tk_tw_classification.sql"
SQL_GOLD = REPO_ROOT / "scripts" / "sql" / "ingest_tk_hater_narrativa.sql"
SQL_GOLD_APOYO = REPO_ROOT / "scripts" / "sql" / "ingest_tk_apoyo_narrativa.sql"

CRITERIA_LABELS = {
    "1": "apoyo_izquierda",
    "2": "derecha_o_troll",
    "3": "neutral",
    "INCLASIFICABLE": "inclasificable",
    "1,2": "ambiguo",
}

BATCH_SYSTEM = """Sos un analista de redes sociales argentino/latinoamericano.
Clasificá CADA comentario de la lista según free_criteria EXACTOS:
- "1" = apoyo a la izquierda / no troll
- "2" = muy de derecha o troll (insultos, desinformación, provocación)
- "3" = neutral
- "INCLASIFICABLE" = vacío, emoji solo, off-topic
- "1,2" = genuinamente ambiguo (usar raramente)

Además asigná "narrativa": slug snake_case corto (≤4 tokens) que capture el tema
del comentario (ej: insulto_hipocresia, acusacion_corrupcion, referencia_milei,
feminismo_ataque, conspiranoia, apoyo_movilizacion, spam_enlace, sin_contenido).

Respondé SOLO JSON válido (sin markdown):
{"items":[{"id":"<reply_id>","free_criteria":"2","resumen":"≤8 palabras","narrativa":"slug"}]}

Debés devolver UN item por cada id recibido, con el mismo id."""

CONSOLIDATE_SYSTEM = """Sos un analista de narrativas de odio/trolling en X (Argentina).
Dada una lista de etiquetas narrativa_raw con conteos y ejemplos, consolidá en
10–20 clusters canónicos.

Respondé SOLO JSON:
{"clusters":[
  {"label":"snake_case","descripcion":"1 frase","sources":["narrativa_raw_a","narrativa_raw_b"]}
]}

Reglas:
- Cada narrativa_raw de entrada debe aparecer en exactamente un sources[].
- label en snake_case, estable y periodístico.
- Preferí fusionar rarezas en clusters cercanos; no inventes sources inexistentes."""

CONSOLIDATE_APOYO_SYSTEM = """Sos un analista de narrativas de apoyo/defensa en X (Argentina).
Dada una lista de etiquetas narrativa_raw de comentarios POSITIVOS o en defensa
(apoyo a la izquierda / a la figura monitoreada) con conteos y ejemplos, consolidá
en 10–20 clusters canónicos de apoyo.

Respondé SOLO JSON:
{"clusters":[
  {"label":"snake_case","descripcion":"1 frase","sources":["narrativa_raw_a","narrativa_raw_b"]}
]}

Reglas:
- Cada narrativa_raw de entrada debe aparecer en exactamente un sources[].
- label en snake_case, estable y periodístico (ej: apoyo_movilizacion, defensa_figura,
  solidaridad_partido, critica_adversario, felicitacion).
- Preferí fusionar rarezas en clusters cercanos; no inventes sources inexistentes."""

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


def criteria_to_label(code: str) -> str:
    return CRITERIA_LABELS.get(code.strip(), "otro")


def _slug(value: str) -> str:
    s = re.sub(r"[^a-z0-9_]+", "_", (value or "").lower().strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return (s or "otros")[:64]


def _parse_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        clusters: list[dict[str, Any]] = []
        for m in re.finditer(
            r'\{\s*"label"\s*:\s*"[^"]+"\s*,\s*"descripcion"\s*:\s*"[^"]*"\s*,\s*"sources"\s*:\s*\[[^\]]*\]\s*\}',
            text,
            re.DOTALL,
        ):
            try:
                clusters.append(json.loads(m.group(0)))
            except json.JSONDecodeError:
                continue
        if clusters:
            return {"clusters": clusters}
        raise


def _ensure_schemas(con) -> None:
    con.execute(SQL_CLASS.read_text())
    con.execute(SQL_GOLD.read_text())


def _fetch_unclassified(con, limit: int | None) -> list[dict[str, Any]]:
    lim = f"LIMIT {int(limit)}" if limit and limit > 0 else ""
    return con.sql(
        f"""
        SELECT
          CAST(r.reply_id AS VARCHAR) AS reply_id,
          CAST(r.parent_tweet_id AS VARCHAR) AS parent_tweet_id,
          CAST(r.username AS VARCHAR) AS username,
          CAST(r.text AS VARCHAR) AS text
        FROM silver.tk_tw_reply AS r
        LEFT JOIN silver.tk_tw_reply_classification AS cl
          ON CAST(r.reply_id AS VARCHAR) = cl.reply_id
        WHERE cl.reply_id IS NULL
          AND r.text IS NOT NULL
          AND LENGTH(TRIM(CAST(r.text AS VARCHAR))) > 0
        ORDER BY r.created_at_ts NULLS LAST
        {lim}
        """
    ).fetchdf().to_dict("records")


def _chunk(rows: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [rows[i : i + size] for i in range(0, len(rows), size)]


def _call_batch(
    client: Any,
    model: str,
    batch: list[dict[str, Any]],
    *,
    text_chars: int,
) -> list[dict[str, Any]]:
    payload = [
        {
            "id": str(r["reply_id"]),
            "text": str(r["text"] or "")[:text_chars].replace("\n", " "),
        }
        for r in batch
    ]
    user_msg = (
        f"Clasificá estos {len(payload)} comentarios. Devolvé JSON con items[].\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": BATCH_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.1,
        max_tokens=min(8000, 120 * len(payload) + 500),
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    data = _parse_json(raw)
    items = data.get("items")
    if not isinstance(items, list):
        # tolerate top-level list
        if isinstance(data, list):
            items = data
        else:
            items = []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rid = str(item.get("id") or "").strip()
        if not rid:
            continue
        criteria = str(item.get("free_criteria", "INCLASIFICABLE")).strip()
        if criteria not in CRITERIA_LABELS:
            m = re.search(r"1,2|[123]|INCLASIFICABLE", criteria)
            criteria = m.group(0) if m else "INCLASIFICABLE"
        out.append(
            {
                "reply_id": rid,
                "free_criteria": criteria,
                "resumen": str(item.get("resumen", "")).strip()[:200],
                "narrativa_raw": _slug(str(item.get("narrativa", "otros"))),
            }
        )
    return out


def _upsert_classifications(
    con,
    rows_by_id: dict[str, dict[str, Any]],
    results: list[dict[str, Any]],
) -> int:
    n = 0
    for item in results:
        src = rows_by_id.get(item["reply_id"])
        if not src:
            continue
        label = criteria_to_label(item["free_criteria"])
        # Upsert: delete then insert (DuckDB MERGE needs matching schema)
        con.execute(
            "DELETE FROM silver.tk_tw_reply_classification WHERE reply_id = ?",
            [item["reply_id"]],
        )
        con.execute(
            """
            INSERT INTO silver.tk_tw_reply_classification (
              classification_id, reply_id, parent_tweet_id, platform, origen,
              free_criteria, criterio_label, resumen, narrativa_raw,
              created_at, updated_at
            ) VALUES (?, ?, ?, 'twitter', 'TK_TW', ?, ?, ?, ?, current_timestamp, current_timestamp)
            """,
            [
                str(uuid.uuid4()),
                item["reply_id"],
                src.get("parent_tweet_id"),
                item["free_criteria"],
                label,
                item["resumen"],
                item["narrativa_raw"],
            ],
        )
        n += 1
    return n


def classify_batches(
    *,
    batch_size: int,
    text_chars: int,
    limit: int | None,
    dry_run: bool,
    rate_limit: float,
    max_retries: int,
) -> int:
    load_dotenv(REPO_ROOT / ".env")
    llm = resolve_llm_config()
    if not llm.api_key and not dry_run:
        print("LLM_API_KEY (or DEEPSEEK_API_KEY) not set in .env", file=sys.stderr)
        return 1

    con = db.connect_for_ingest(release_mcp=True)
    try:
        _ensure_schemas(con)
        rows = _fetch_unclassified(con, limit)
        if not rows:
            print("No unclassified tk_tw_reply rows.")
            return 0

        print(
            f"Classifying {len(rows)} replies in batches of {batch_size} "
            f"via {llm.provider}/{llm.model} (CHAT_MODEL/LLM_MODEL)…"
        )
        if dry_run:
            for row in rows[:5]:
                print(f"  [dry-run] {row['reply_id']}: {str(row['text'])[:70]}…")
            return 0

        try:
            from openai import OpenAI
        except ImportError:
            print("Install LLM extra: uv sync --extra llm", file=sys.stderr)
            return 1

        client = OpenAI(api_key=llm.api_key, base_url=llm.base_url, timeout=180.0)
        rows_by_id = {str(r["reply_id"]): r for r in rows}
        pending = list(rows)
        classified_total = 0

        for attempt in range(max_retries + 1):
            if not pending:
                break
            batches = _chunk(pending, batch_size)
            still_missing: list[dict[str, Any]] = []
            for bi, batch in enumerate(batches, 1):
                print(
                    f"  batch {bi}/{len(batches)} (n={len(batch)}, attempt={attempt})",
                    flush=True,
                )
                try:
                    results = _call_batch(
                        client, llm.model, batch, text_chars=text_chars
                    )
                    got = {r["reply_id"] for r in results}
                    n = _upsert_classifications(con, rows_by_id, results)
                    classified_total += n
                    for row in batch:
                        if str(row["reply_id"]) not in got:
                            still_missing.append(row)
                    print(
                        f"    upserted {n}; missing {len(batch) - len(got)}",
                        flush=True,
                    )
                except Exception as exc:
                    print(f"    batch error: {exc}", file=sys.stderr, flush=True)
                    still_missing.extend(batch)
                if rate_limit > 0:
                    time.sleep(rate_limit)
            pending = still_missing
            if pending and attempt < max_retries:
                print(f"  retrying {len(pending)} missing ids…", flush=True)

        if pending:
            print(
                f"WARNING: {len(pending)} replies still unclassified.",
                file=sys.stderr,
                flush=True,
            )
        print(f"Classified {classified_total} reply row(s).", flush=True)
        return 0
    finally:
        con.close()


def _fetch_hater_rows(con) -> list[dict[str, Any]]:
    rows = con.sql(
        """
        SELECT
          CAST(cl.reply_id AS VARCHAR) AS reply_id,
          CAST(cl.parent_tweet_id AS VARCHAR) AS parent_tweet_id,
          CAST(cl.narrativa_raw AS VARCHAR) AS narrativa_raw,
          CAST(cl.resumen AS VARCHAR) AS resumen,
          CAST(r.username AS VARCHAR) AS username,
          CAST(r.text AS VARCHAR) AS text
        FROM silver.tk_tw_reply_classification AS cl
        LEFT JOIN silver.tk_tw_reply AS r ON cl.reply_id = CAST(r.reply_id AS VARCHAR)
        WHERE cl.criterio_label = 'derecha_o_troll'
          AND cl.narrativa_raw IS NOT NULL
          AND LENGTH(TRIM(cl.narrativa_raw)) > 0
        QUALIFY ROW_NUMBER() OVER (PARTITION BY cl.reply_id ORDER BY r.created_at_ts NULLS LAST) = 1
        """
    ).fetchdf().to_dict("records")
    return rows


def _fetch_apoyo_rows(con) -> list[dict[str, Any]]:
    rows = con.sql(
        """
        SELECT
          CAST(cl.reply_id AS VARCHAR) AS reply_id,
          CAST(cl.parent_tweet_id AS VARCHAR) AS parent_tweet_id,
          CAST(cl.narrativa_raw AS VARCHAR) AS narrativa_raw,
          CAST(cl.resumen AS VARCHAR) AS resumen,
          CAST(r.username AS VARCHAR) AS username,
          CAST(r.text AS VARCHAR) AS text
        FROM silver.tk_tw_reply_classification AS cl
        LEFT JOIN silver.tk_tw_reply AS r ON cl.reply_id = CAST(r.reply_id AS VARCHAR)
        WHERE cl.criterio_label = 'apoyo_izquierda'
          AND cl.narrativa_raw IS NOT NULL
          AND LENGTH(TRIM(cl.narrativa_raw)) > 0
        QUALIFY ROW_NUMBER() OVER (PARTITION BY cl.reply_id ORDER BY r.created_at_ts NULLS LAST) = 1
        """
    ).fetchdf().to_dict("records")
    return rows


def _build_label_stats(haters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for row in haters:
        label = _slug(str(row.get("narrativa_raw") or "otros"))
        b = buckets.setdefault(label, {"narrativa_raw": label, "n": 0, "examples": []})
        b["n"] += 1
        if len(b["examples"]) < 3:
            ex = str(row.get("text") or row.get("resumen") or "")[:160]
            if ex:
                b["examples"].append(ex)
    return sorted(buckets.values(), key=lambda x: -x["n"])


def _mapping_from_clusters(
    clusters: list[Any],
    stats: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    mapping: dict[str, dict[str, str]] = {}
    for cl in clusters:
        if not isinstance(cl, dict):
            continue
        label = _slug(str(cl.get("label") or "otros"))
        desc = str(cl.get("descripcion") or "").strip()[:300]
        sources = cl.get("sources") or []
        if not isinstance(sources, list):
            continue
        for src in sources:
            mapping[_slug(str(src))] = {"label": label, "descripcion": desc}
    for s in stats:
        key = s["narrativa_raw"]
        if key not in mapping:
            mapping[key] = {
                "label": key,
                "descripcion": f"Narrativa: {key.replace('_', ' ')}",
            }
    return mapping


def _llm_consolidate_chunk(
    client: Any,
    model: str,
    stats: list[dict[str, Any]],
    *,
    target_clusters: int,
    system_prompt: str = CONSOLIDATE_SYSTEM,
) -> dict[str, dict[str, str]]:
    """Consolidate one chunk of narrativa_raw stats via LLM."""
    payload = [
        {
            "narrativa_raw": s["narrativa_raw"],
            "n": s["n"],
            "examples": [ex[:80] for ex in (s.get("examples") or [])[:2]],
        }
        for s in stats
    ]
    user_msg = (
        f"Consolidá estas {len(payload)} etiquetas en ~{target_clusters} clusters "
        f"(máx {target_clusters + 5}). Cada narrativa_raw debe aparecer en exactamente un sources[].\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.1,
        max_tokens=8000,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    try:
        data = _parse_json(raw)
    except json.JSONDecodeError as exc:
        print(f"    consolidate JSON error: {exc}; identity fallback", flush=True)
        return {
            s["narrativa_raw"]: {
                "label": s["narrativa_raw"],
                "descripcion": f"Narrativa: {s['narrativa_raw'].replace('_', ' ')}",
            }
            for s in stats
        }
    return _mapping_from_clusters(data.get("clusters") or [], stats)


def _consolidate_labels(
    client: Any,
    model: str,
    stats: list[dict[str, Any]],
    *,
    system_prompt: str = CONSOLIDATE_SYSTEM,
) -> dict[str, dict[str, str]]:
    """Return map narrativa_raw -> {label, descripcion}.

    Large label sets are consolidated in chunks, then a second pass merges
    intermediate labels into ~10–20 canonical clusters.
    """
    if not stats:
        return {}
    if len(stats) <= 20:
        return {
            s["narrativa_raw"]: {
                "label": s["narrativa_raw"],
                "descripcion": f"Narrativa: {s['narrativa_raw'].replace('_', ' ')}",
            }
            for s in stats
        }

    chunk_size = 80
    chunks = _chunk(stats, chunk_size)
    print(f"  consolidating {len(stats)} labels in {len(chunks)} chunk(s)…", flush=True)
    raw_to_mid: dict[str, dict[str, str]] = {}
    for i, chunk in enumerate(chunks, 1):
        print(f"    consolidate chunk {i}/{len(chunks)} (n={len(chunk)})", flush=True)
        try:
            part = _llm_consolidate_chunk(
                client,
                model,
                chunk,
                target_clusters=min(12, max(6, len(chunk) // 8)),
                system_prompt=system_prompt,
            )
        except Exception as exc:
            print(f"    chunk error: {exc}; identity fallback", flush=True)
            part = {
                s["narrativa_raw"]: {
                    "label": s["narrativa_raw"],
                    "descripcion": f"Narrativa: {s['narrativa_raw'].replace('_', ' ')}",
                }
                for s in chunk
            }
        raw_to_mid.update(part)

    mid_buckets: dict[str, dict[str, Any]] = {}
    for s in stats:
        raw = s["narrativa_raw"]
        mid = raw_to_mid.get(raw, {"label": raw, "descripcion": ""})
        lab = mid["label"]
        b = mid_buckets.setdefault(
            lab,
            {
                "narrativa_raw": lab,
                "n": 0,
                "examples": [],
                "descripcion": mid.get("descripcion") or "",
            },
        )
        b["n"] += s["n"]
        for ex in s.get("examples") or []:
            if len(b["examples"]) < 2:
                b["examples"].append(ex[:80])

    mid_stats = sorted(mid_buckets.values(), key=lambda x: -x["n"])
    if len(mid_stats) <= 20:
        mid_to_final = {
            s["narrativa_raw"]: {
                "label": s["narrativa_raw"],
                "descripcion": s.get("descripcion")
                or f"Narrativa: {s['narrativa_raw'].replace('_', ' ')}",
            }
            for s in mid_stats
        }
    else:
        print(f"  final merge of {len(mid_stats)} intermediate labels…", flush=True)
        try:
            mid_to_final = _llm_consolidate_chunk(
                client,
                model,
                mid_stats,
                target_clusters=16,
                system_prompt=system_prompt,
            )
        except Exception as exc:
            print(f"  final merge error: {exc}; keep intermediate", flush=True)
            mid_to_final = {
                s["narrativa_raw"]: {
                    "label": s["narrativa_raw"],
                    "descripcion": s.get("descripcion")
                    or f"Narrativa: {s['narrativa_raw'].replace('_', ' ')}",
                }
                for s in mid_stats
            }

    out: dict[str, dict[str, str]] = {}
    for s in stats:
        raw = s["narrativa_raw"]
        mid = raw_to_mid.get(raw, {"label": raw})["label"]
        final = mid_to_final.get(
            mid,
            {"label": mid, "descripcion": f"Narrativa: {mid.replace('_', ' ')}"},
        )
        out[raw] = {
            "label": final["label"],
            "descripcion": final.get("descripcion")
            or f"Narrativa: {final['label'].replace('_', ' ')}",
        }
    return out


def cluster_haters(*, dry_run: bool, rate_limit: float) -> int:
    load_dotenv(REPO_ROOT / ".env")
    llm = resolve_llm_config()
    if not llm.api_key and not dry_run:
        print("LLM_API_KEY (or DEEPSEEK_API_KEY) not set in .env", file=sys.stderr)
        return 1

    con = db.connect_for_ingest(release_mcp=True)
    try:
        _ensure_schemas(con)
        haters = _fetch_hater_rows(con)
        if not haters:
            print("No derecha_o_troll rows to cluster. Run classification first.")
            return 0

        stats = _build_label_stats(haters)
        print(f"Hater replies: {len(haters)}; narrativa_raw labels: {len(stats)}")
        if dry_run:
            for s in stats[:15]:
                print(f"  {s['n']:4d}  {s['narrativa_raw']}")
            return 0

        try:
            from openai import OpenAI
        except ImportError:
            print("Install LLM extra: uv sync --extra llm", file=sys.stderr)
            return 1

        client = OpenAI(api_key=llm.api_key, base_url=llm.base_url, timeout=180.0)
        mapping = _consolidate_labels(client, llm.model, stats)
        if rate_limit > 0:
            time.sleep(rate_limit)

        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        # Build cluster catalog
        by_label: dict[str, dict[str, Any]] = {}
        for raw, meta in mapping.items():
            lab = meta["label"]
            entry = by_label.setdefault(
                lab,
                {
                    "label": lab,
                    "descripcion": meta["descripcion"],
                    "sources": [],
                    "n": 0,
                    "examples": [],
                },
            )
            entry["sources"].append(raw)
            if not entry["descripcion"] and meta["descripcion"]:
                entry["descripcion"] = meta["descripcion"]

        for row in haters:
            raw = _slug(str(row.get("narrativa_raw") or "otros"))
            lab = mapping.get(raw, {"label": raw})["label"]
            by_label[lab]["n"] += 1
            if len(by_label[lab]["examples"]) < 3:
                ex = str(row.get("text") or "")[:120]
                if ex:
                    by_label[lab]["examples"].append(ex)

        con.execute("DELETE FROM gold.tk_hater_narrativa_assignment")
        con.execute("DELETE FROM gold.tk_hater_narrativa_cluster")

        label_to_id: dict[str, str] = {}
        for lab, entry in sorted(by_label.items(), key=lambda x: -x[1]["n"]):
            cid = hashlib.md5(f"{run_id}:{lab}".encode()).hexdigest()[:16]
            label_to_id[lab] = cid
            con.execute(
                """
                INSERT INTO gold.tk_hater_narrativa_cluster (
                  cluster_id, label, descripcion, n_replies, ejemplo_textos, run_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, current_timestamp)
                """,
                [
                    cid,
                    lab,
                    entry["descripcion"],
                    entry["n"],
                    " | ".join(entry["examples"])[:1000],
                    run_id,
                ],
            )

        for row in haters:
            raw = _slug(str(row.get("narrativa_raw") or "otros"))
            lab = mapping.get(raw, {"label": raw})["label"]
            cid = label_to_id[lab]
            con.execute(
                """
                INSERT INTO gold.tk_hater_narrativa_assignment (
                  reply_id, cluster_id, narrativa_raw, parent_tweet_id, username, run_id, assigned_at
                ) VALUES (?, ?, ?, ?, ?, ?, current_timestamp)
                """,
                [
                    row["reply_id"],
                    cid,
                    raw,
                    row.get("parent_tweet_id"),
                    row.get("username"),
                    run_id,
                ],
            )

        # Refresh views (DDL is idempotent)
        con.execute(SQL_GOLD.read_text())
        print(
            f"Clusters: {len(label_to_id)} | assignments: {len(haters)} | run_id={run_id}"
        )
        top = con.sql(
            """
            SELECT label, n_replies, pct_haters
            FROM gold.v_tk_hater_narrativa_resumen
            ORDER BY n_replies DESC
            LIMIT 10
            """
        ).fetchall()
        for label, n, pct in top:
            print(f"  {n:4d} ({pct:5.1f}%)  {label}")
        return 0
    finally:
        con.close()


def cluster_apoyo(*, dry_run: bool, rate_limit: float) -> int:
    load_dotenv(REPO_ROOT / ".env")
    llm = resolve_llm_config()
    if not llm.api_key and not dry_run:
        print("LLM_API_KEY (or DEEPSEEK_API_KEY) not set in .env", file=sys.stderr)
        return 1

    con = db.connect_for_ingest(release_mcp=True)
    try:
        _ensure_schemas(con)
        # Ensure apoyo gold DDL exists before writes
        con.execute(SQL_GOLD_APOYO.read_text())
        rows = _fetch_apoyo_rows(con)
        if not rows:
            print("No apoyo_izquierda rows to cluster. Run classification first.")
            return 0

        stats = _build_label_stats(rows)
        print(f"Apoyo replies: {len(rows)}; narrativa_raw labels: {len(stats)}")
        if dry_run:
            for s in stats[:15]:
                print(f"  {s['n']:4d}  {s['narrativa_raw']}")
            return 0

        try:
            from openai import OpenAI
        except ImportError:
            print("Install LLM extra: uv sync --extra llm", file=sys.stderr)
            return 1

        client = OpenAI(api_key=llm.api_key, base_url=llm.base_url, timeout=180.0)
        mapping = _consolidate_labels(
            client, llm.model, stats, system_prompt=CONSOLIDATE_APOYO_SYSTEM
        )
        if rate_limit > 0:
            time.sleep(rate_limit)

        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        by_label: dict[str, dict[str, Any]] = {}
        for raw, meta in mapping.items():
            lab = meta["label"]
            entry = by_label.setdefault(
                lab,
                {
                    "label": lab,
                    "descripcion": meta["descripcion"],
                    "sources": [],
                    "n": 0,
                    "examples": [],
                },
            )
            entry["sources"].append(raw)
            if not entry["descripcion"] and meta["descripcion"]:
                entry["descripcion"] = meta["descripcion"]

        for row in rows:
            raw = _slug(str(row.get("narrativa_raw") or "otros"))
            lab = mapping.get(raw, {"label": raw})["label"]
            by_label[lab]["n"] += 1
            if len(by_label[lab]["examples"]) < 3:
                ex = str(row.get("text") or "")[:120]
                if ex:
                    by_label[lab]["examples"].append(ex)

        con.execute("DELETE FROM gold.tk_apoyo_narrativa_assignment")
        con.execute("DELETE FROM gold.tk_apoyo_narrativa_cluster")

        label_to_id: dict[str, str] = {}
        for lab, entry in sorted(by_label.items(), key=lambda x: -x[1]["n"]):
            cid = hashlib.md5(f"{run_id}:{lab}".encode()).hexdigest()[:16]
            label_to_id[lab] = cid
            con.execute(
                """
                INSERT INTO gold.tk_apoyo_narrativa_cluster (
                  cluster_id, label, descripcion, n_replies, ejemplo_textos, run_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, current_timestamp)
                """,
                [
                    cid,
                    lab,
                    entry["descripcion"],
                    entry["n"],
                    " | ".join(entry["examples"])[:1000],
                    run_id,
                ],
            )

        for row in rows:
            raw = _slug(str(row.get("narrativa_raw") or "otros"))
            lab = mapping.get(raw, {"label": raw})["label"]
            cid = label_to_id[lab]
            con.execute(
                """
                INSERT INTO gold.tk_apoyo_narrativa_assignment (
                  reply_id, cluster_id, narrativa_raw, parent_tweet_id, username, run_id, assigned_at
                ) VALUES (?, ?, ?, ?, ?, ?, current_timestamp)
                """,
                [
                    row["reply_id"],
                    cid,
                    raw,
                    row.get("parent_tweet_id"),
                    row.get("username"),
                    run_id,
                ],
            )

        con.execute(SQL_GOLD_APOYO.read_text())
        print(
            f"Apoyo clusters: {len(label_to_id)} | assignments: {len(rows)} | run_id={run_id}"
        )
        top = con.sql(
            """
            SELECT label, n_replies, pct_apoyo
            FROM gold.v_tk_apoyo_narrativa_resumen
            ORDER BY n_replies DESC
            LIMIT 10
            """
        ).fetchall()
        for label, n, pct in top:
            print(f"  {n:4d} ({pct:5.1f}%)  {label}")
        return 0
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch-classify twikit replies and cluster hater/apoyo narratives"
    )
    parser.add_argument("--batch-size", type=int, default=50, help="Comments per LLM request")
    parser.add_argument("--text-chars", type=int, default=280, help="Max chars per comment")
    parser.add_argument("--limit", type=int, default=None, help="Max unclassified replies")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rate-limit", type=float, default=0.4, help="Sleep between batches")
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument(
        "--cluster-haters",
        action="store_true",
        help="After classify (or alone if already classified), build gold hater narrative clusters",
    )
    parser.add_argument(
        "--cluster-apoyo",
        action="store_true",
        help="Build gold apoyo (support) narrative clusters from apoyo_izquierda replies",
    )
    parser.add_argument(
        "--cluster-only",
        action="store_true",
        help="Skip classification; only run clustering (--cluster-haters and/or --cluster-apoyo)",
    )
    args = parser.parse_args()

    if args.batch_size < 1:
        print("--batch-size must be >= 1", file=sys.stderr)
        return 1

    rc = 0
    if not args.cluster_only:
        rc = classify_batches(
            batch_size=args.batch_size,
            text_chars=args.text_chars,
            limit=args.limit,
            dry_run=args.dry_run,
            rate_limit=args.rate_limit,
            max_retries=args.max_retries,
        )
        if rc != 0:
            return rc

    if args.cluster_haters or (args.cluster_only and not args.cluster_apoyo):
        rc = cluster_haters(dry_run=args.dry_run, rate_limit=args.rate_limit)
        if rc != 0:
            return rc

    if args.cluster_apoyo:
        rc = cluster_apoyo(dry_run=args.dry_run, rate_limit=args.rate_limit)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
