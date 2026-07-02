"""Classify SociaVault comments/replies via LLM (legacy free_criteria schema).

Usage:
    uv run python scripts/python/classify_sv_comments.py --platform facebook --limit 100
    uv run python scripts/python/classify_sv_comments.py --platform all --limit 500 --dry-run

Requires: LLM_API_KEY (or DEEPSEEK_API_KEY) in .env.
Optional: LLM_PROVIDER (default deepseek), LLM_MODEL, LLM_BASE_URL.
OpenAI-compatible providers: deepseek (default), openai.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db

CRITERIA_LABELS = {
    "1": "apoyo_izquierda",
    "2": "derecha_o_troll",
    "3": "neutral",
    "INCLASIFICABLE": "inclasificable",
    "1,2": "ambiguo",
}

SYSTEM_PROMPT = """Sos un analista de redes sociales argentino/latinoamericano.
Clasificá cada comentario según estos criterios EXACTOS (free_criteria):
- "1" = No troll, apoyo a la izquierda
- "2" = Muy de derecha o troll (insultos, desinformación, provocación)
- "3" = Neutral (sin posición ideológica clara)
- "INCLASIFICABLE" = No se puede determinar (texto vacío, emoji solo, off-topic)
- "1,2" = Solo si genuinamente ambiguo entre apoyo y troll (usar raramente)

Respondé SOLO con JSON válido (sin markdown):
{"free_criteria": "...", "resumen": "..."}

Ejemplo JSON:
{"free_criteria": "2", "resumen": "Insulto directo; troll"}
El resumen debe ser muy breve (≤8 palabras)."""

LLM_PROVIDERS: dict[str, dict[str, str]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
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
        os.getenv("LLM_API_KEY", "").strip()
        or os.getenv("DEEPSEEK_API_KEY", "").strip()
    )
    model = os.getenv("LLM_MODEL", defaults["model"]).strip()
    base_url = os.getenv("LLM_BASE_URL", defaults["base_url"]).strip()
    return LlmConfig(provider=provider, api_key=api_key, model=model, base_url=base_url)


@dataclass(frozen=True)
class PlatformConfig:
    name: str
    content_table: str
    classification_table: str
    content_id_col: str
    parent_id_col: str
    parent_class_col: str
    text_col: str
    origen: str


PLATFORMS: dict[str, PlatformConfig] = {
    "facebook": PlatformConfig(
        name="facebook",
        content_table="silver.sv_fb_comment",
        classification_table="silver.sv_fb_comment_classification",
        content_id_col="comment_id",
        parent_id_col="post_id",
        parent_class_col="post_id",
        text_col="comentario",
        origen="SV_FB",
    ),
    "instagram": PlatformConfig(
        name="instagram",
        content_table="silver.sv_ig_comment",
        classification_table="silver.sv_ig_comment_classification",
        content_id_col="comment_id",
        parent_id_col="post_id",
        parent_class_col="post_id",
        text_col="comentario",
        origen="SV_IG",
    ),
    "tiktok": PlatformConfig(
        name="tiktok",
        content_table="silver.sv_tt_comment",
        classification_table="silver.sv_tt_comment_classification",
        content_id_col="comment_id",
        parent_id_col="video_id",
        parent_class_col="video_id",
        text_col="comentario",
        origen="SV_TT",
    ),
    "twitter": PlatformConfig(
        name="twitter",
        content_table="silver.sv_tw_reply",
        classification_table="silver.sv_tw_reply_classification",
        content_id_col="reply_id",
        parent_id_col="in_reply_to_tweet_id_str",
        parent_class_col="tweet_id",
        text_col="text",
        origen="SV_TW",
    ),
}


def criteria_to_label(code: str) -> str:
    return CRITERIA_LABELS.get(code.strip(), "otro")


def _ensure_schema(con) -> None:
    sql_path = (
        Path(__file__).resolve().parent.parent / "sql" / "ingest_sociavault_classification.sql"
    )
    con.execute(sql_path.read_text())


def _fetch_unclassified(con, cfg: PlatformConfig, limit: int) -> list[dict]:
    id_col = cfg.content_id_col
    query = f"""
        SELECT c.{id_col} AS content_id,
               c.{cfg.parent_id_col} AS parent_id,
               c.{cfg.text_col} AS text
        FROM {cfg.content_table} c
        LEFT JOIN {cfg.classification_table} cl ON c.{id_col} = cl.{id_col}
        WHERE cl.{id_col} IS NULL
          AND c.{cfg.text_col} IS NOT NULL
          AND LENGTH(TRIM(c.{cfg.text_col})) > 0
        LIMIT {limit}
    """
    return con.sql(query).fetchdf().to_dict("records")


def _parse_llm_json(raw: str) -> dict:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _call_llm(client, model: str, text: str) -> tuple[str, str]:
    user_msg = f"Comentario (clasificar en JSON):\n{text[:2000]}"
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.1,
        max_tokens=256,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    data = _parse_llm_json(raw)
    criteria = str(data.get("free_criteria", "INCLASIFICABLE")).strip()
    resumen = str(data.get("resumen", "")).strip()[:200]
    if criteria not in CRITERIA_LABELS:
        # Try to extract digit from response
        match = re.search(r"[123]|INCLASIFICABLE|1,2", criteria)
        criteria = match.group(0) if match else "INCLASIFICABLE"
    return criteria, resumen


def _insert_classification(
    con,
    cfg: PlatformConfig,
    content_id: str,
    parent_id: str | None,
    free_criteria: str,
    resumen: str,
) -> None:
    classification_id = str(uuid.uuid4())
    label = criteria_to_label(free_criteria)
    id_col = cfg.content_id_col

    con.execute(
        f"""
        INSERT INTO {cfg.classification_table} (
          classification_id, {cfg.parent_class_col}, platform, {id_col},
          origen, free_criteria, criterio_label, resumen, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, current_timestamp, current_timestamp)
        """,
        [
            classification_id,
            parent_id,
            cfg.name,
            content_id,
            cfg.origen,
            free_criteria,
            label,
            resumen,
        ],
    )


def classify_platform(
    platform: str,
    *,
    limit: int,
    dry_run: bool,
    rate_limit: float,
) -> int:
    cfg = PLATFORMS[platform]
    load_dotenv()

    llm = resolve_llm_config()
    if not llm.api_key and not dry_run:
        print(
            "LLM_API_KEY (or DEEPSEEK_API_KEY) not set in .env",
            file=sys.stderr,
        )
        return 1

    con = db.connect_for_ingest(release_mcp=True)
    try:
        _ensure_schema(con)
        try:
            rows = _fetch_unclassified(con, cfg, limit)
        except Exception as exc:
            if "does not exist" in str(exc):
                print(f"Table missing for {platform}; run silver ingest first.", file=sys.stderr)
                return 0
            raise

        if not rows:
            print(f"No unclassified {platform} comments.")
            return 0

        print(
            f"Classifying {len(rows)} {platform} comment(s) "
            f"via {llm.provider} ({llm.model})..."
        )
        if dry_run:
            for row in rows[:3]:
                print(f"  [dry-run] {row['content_id']}: {str(row['text'])[:60]}...")
            return 0

        try:
            from openai import OpenAI
        except ImportError:
            print("Install LLM extra: uv sync --extra llm", file=sys.stderr)
            return 1

        client = OpenAI(api_key=llm.api_key, base_url=llm.base_url)
        classified = 0
        for row in rows:
            try:
                criteria, resumen = _call_llm(client, llm.model, str(row["text"]))
                _insert_classification(
                    con,
                    cfg,
                    str(row["content_id"]),
                    str(row["parent_id"]) if row.get("parent_id") else None,
                    criteria,
                    resumen,
                )
                classified += 1
                if rate_limit > 0:
                    time.sleep(rate_limit)
            except Exception as exc:
                print(f"  Error on {row['content_id']}: {exc}", file=sys.stderr)
        print(f"Classified {classified}/{len(rows)} {platform} comment(s).")
        return 0
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify SociaVault comments via LLM")
    parser.add_argument(
        "--platform",
        required=True,
        choices=[*PLATFORMS.keys(), "all"],
        help="Platform to classify",
    )
    parser.add_argument("--limit", type=int, default=500, help="Max comments per platform")
    parser.add_argument("--dry-run", action="store_true", help="List comments without calling LLM")
    parser.add_argument("--rate-limit", type=float, default=0.5, help="Seconds between LLM calls")
    args = parser.parse_args()

    platforms = list(PLATFORMS.keys()) if args.platform == "all" else [args.platform]
    rc = 0
    for platform in platforms:
        result = classify_platform(
            platform,
            limit=args.limit,
            dry_run=args.dry_run,
            rate_limit=args.rate_limit,
        )
        if result != 0:
            rc = result
    return rc


if __name__ == "__main__":
    sys.exit(main())
