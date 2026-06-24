"""
Build attack graph from bronze.htb_wireups → vertices & edges tables.
Enriches each MITRE technique with name, tactic, and description via
the MITRE ATT&CK API.

Usage:
    uv run python scripts/python/build_htb_graph.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path("scripts/python").resolve()))
import db

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
# Env loader (must run before config)
# ---------------------------------------------------------------------------

def _load_env(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())

_load_env()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"
BRONZE_TABLE = "bronze.htb_wireups"
VERTICES_TABLE = "bronze.htb_wireup_vertices"
EDGES_TABLE = "bronze.htb_wireup_edges"

RATE_LIMIT_DELAY = 0.3
BATCH_SIZE = 8

# ---------------------------------------------------------------------------
# MITRE enrichment via DeepSeek
# ---------------------------------------------------------------------------

def _deepseek_techniques(tech_ids: list[str]) -> dict[str, dict]:
    if not DEEPSEEK_API_KEY:
        print("  ⚠ DEEPSEEK_API_KEY not set")
        return {}
    ids_str = ", ".join(sorted(tech_ids))
    prompt = (
        f"For these MITRE ATT&CK technique IDs: {ids_str}\n"
        "Return a JSON array of objects, each with keys: "
        "id, name, tactic, description (brief, 1 sentence in Spanish). "
        "Return ONLY the JSON array."
    )
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        "max_tokens": 4096,
        "temperature": 0.05,
    }
    try:
        resp = httpx.post(
            f"{DEEPSEEK_BASE}/chat/completions",
            headers=headers, json=payload, timeout=90,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        data = json.loads(text)
        if isinstance(data, list):
            return {d["id"]: d for d in data if "id" in d}
    except Exception as e:
        print(f"  ⚠ DeepSeek enrichment error: {e}")
    return {}


def enrich_techniques(tech_ids: set[str]) -> dict[str, dict]:
    print(f"  Enriching {len(tech_ids)} techniques via DeepSeek…")
    enriched: dict[str, dict] = {}
    ids_list = sorted(tech_ids)

    for i in range(0, len(ids_list), BATCH_SIZE):
        batch = ids_list[i:i + BATCH_SIZE]
        print(f"    batch {i//BATCH_SIZE+1}/{(len(ids_list)+BATCH_SIZE-1)//BATCH_SIZE}: "
              f"{batch}")
        result = _deepseek_techniques(batch)
        for tid in batch:
            if tid in result:
                enriched[tid] = result[tid]
            else:
                enriched[tid] = {
                    "id": tid,
                    "name": tid,
                    "tactic": "unknown",
                    "description": "No disponible",
                }
        time.sleep(RATE_LIMIT_DELAY)

    return enriched

# ---------------------------------------------------------------------------
# Graph building
# ---------------------------------------------------------------------------

def build_graph() -> int:
    print("=" * 60)
    print("HTB Wireup Graph Builder → vertices & edges")
    print("=" * 60)

    con = db.connect()
    try:
        # 1. Read bronze data
        row = con.sql(
            f"SELECT machine, difficulty, parsed_json FROM {BRONZE_TABLE} LIMIT 1"
        ).fetchone()
        if not row:
            print("❌ No data in bronze.htb_wireups")
            return 1
        machine, difficulty, parsed_json = row
        parsed = json.loads(parsed_json) if isinstance(parsed_json, str) else parsed_json
        sections = parsed.get("sections", [])
        print(f"\n📦 Loaded: {machine} ({difficulty}), {len(sections)} sections")

        # 2. Collect all unique techniques per section (ordered)
        section_techniques: list[list[str]] = []
        all_techs: set[str] = set()
        for sec in sections:
            techs = sec.get("techniques", [])
            section_techniques.append(techs)
            all_techs.update(techs)

        print(f"   Unique techniques: {len(all_techs)}")
        for i, sec in enumerate(sections):
            print(f"   {sec['name']}: {section_techniques[i]}")

        if not all_techs:
            print("❌ No techniques found")
            return 1

        # 3. Enrich with MITRE
        print("\n🔍 Enriching with MITRE ATT&CK…")
        enriched = enrich_techniques(all_techs)
        print(f"   Enriched {len(enriched)} techniques")

        # 4. Build vertices
        vertices = []
        for tid in sorted(all_techs):
            info = enriched.get(tid, {})
            vertices.append({
                "technique_id": tid,
                "technique_name": info.get("name", tid),
                "tactic": info.get("tactic", "unknown"),
                "description": info.get("description", ""),
            })

        # 5. Build edges (sequential within + between sections)
        edges = []
        edge_order = 0
        prev_tech = None
        for sec_idx, sec in enumerate(sections):
            techs = section_techniques[sec_idx]
            for i in range(len(techs)):
                if i > 0:
                    edge_order += 1
                    edges.append({
                        "edge_order": edge_order,
                        "source_technique": techs[i - 1],
                        "target_technique": techs[i],
                        "section_from": sec["name"],
                        "section_to": sec["name"],
                    })
                # Cross-section: connect last tech of prev sec to first of this sec
                if i == 0 and prev_tech is not None and techs:
                    edge_order += 1
                    edges.append({
                        "edge_order": edge_order,
                        "source_technique": prev_tech,
                        "target_technique": techs[0],
                        "section_from": sections[sec_idx - 1]["name"],
                        "section_to": sec["name"],
                    })
                if i == len(techs) - 1 and techs:
                    prev_tech = techs[i]

        print(f"\n📊 Graph: {len(vertices)} vertices, {len(edges)} edges")

        # 6. Write to DuckDB
        con.execute("CREATE SCHEMA IF NOT EXISTS bronze")

        con.execute(f"DROP TABLE IF EXISTS {VERTICES_TABLE}")
        con.execute(f"""
            CREATE TABLE {VERTICES_TABLE} (
                id INTEGER PRIMARY KEY,
                technique_id VARCHAR,
                technique_name VARCHAR,
                tactic VARCHAR,
                description VARCHAR
            )
        """)
        for i, v in enumerate(vertices):
            con.execute(
                f"INSERT INTO {VERTICES_TABLE} VALUES (?, ?, ?, ?, ?)",
                [i + 1, v["technique_id"], v["technique_name"],
                 v["tactic"], v["description"]],
            )

        con.execute(f"DROP TABLE IF EXISTS {EDGES_TABLE}")
        con.execute(f"""
            CREATE TABLE {EDGES_TABLE} (
                id INTEGER PRIMARY KEY,
                source_technique VARCHAR,
                target_technique VARCHAR,
                edge_order INTEGER,
                section_from VARCHAR,
                section_to VARCHAR
            )
        """)
        for i, e in enumerate(edges):
            con.execute(
                f"INSERT INTO {EDGES_TABLE} VALUES (?, ?, ?, ?, ?, ?)",
                [i + 1, e["source_technique"], e["target_technique"],
                 e["edge_order"], e["section_from"], e["section_to"]],
            )

        print(f"✅ Written {len(vertices)} vertices to {VERTICES_TABLE}")
        print(f"✅ Written {len(edges)} edges to {EDGES_TABLE}")

        # 7. Validate
        print("\n📊 Validation:")
        v_count = con.sql(f"SELECT COUNT(*) FROM {VERTICES_TABLE}").fetchone()[0]
        e_count = con.sql(f"SELECT COUNT(*) FROM {EDGES_TABLE}").fetchone()[0]
        print(f"   Vertices: {v_count}")
        print(f"   Edges: {e_count}")

        # Sample edges
        print("\n   Edge samples:")
        for e in con.sql(
            f"SELECT source_technique, target_technique, section_from, "
            f"section_to FROM {EDGES_TABLE} ORDER BY edge_order LIMIT 10"
        ).fetchall():
            print(f"     {e[0]} → {e[1]}  ({e[2]} → {e[3]})")

        return 0
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(build_graph())
