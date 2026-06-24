"""
Parse HTB wireup PDF into bronze.htb_wireups as JSON.

Extracts text and images from PDF, sends images to DeepSeek vision API
for description, extracts commands via DeepSeek chat, identifies MITRE
techniques, and stores structured data in DuckDB.

Usage:
    uv run python scripts/python/parse_htb_wireup.py
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pymupdf

sys.path.insert(0, str(Path("scripts/python").resolve()))
import db

# ---------------------------------------------------------------------------
# Env loader (lightweight, no dotenv dep)
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
PDF_PATH = db.get_landing_path() / "htb-wireups" / "overwatch-medium-20052026.pdf"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"
BRONZE_TABLE = "bronze.htb_wireups"

RATE_LIMIT_DELAY = 0.5

SECTION_KEYS = [
    "enumeracion",
    "explotacion",
    "escalada",
    "post_explotacion",
    "flags",
]

PAGE_SECTION_MAP: dict[int, str] = {
    1: "__overview__",
    2: "enumeracion",
    3: "enumeracion",
    4: "enumeracion",
    5: "explotacion",
    6: "explotacion",
    7: "explotacion",
    8: "escalada",
    9: "escalada",
    10: "escalada",
    11: "escalada",
    12: "escalada",
    13: "flags",
}

# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def extract_pdf(pdf_path: Path) -> list[dict]:
    doc = pymupdf.open(pdf_path)
    pages = []
    for i in range(doc.page_count):
        page = doc[i]
        text = page.get_text().strip()
        images = []
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            ext = base_image["ext"]
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            images.append({
                "index": img_index,
                "ext": ext,
                "b64": b64,
                "size_kb": round(len(image_bytes) / 1024, 1),
            })
        pages.append({
            "page_num": i + 1,
            "text": text,
            "images": images,
            "section": PAGE_SECTION_MAP.get(i + 1, "unknown"),
        })
    doc.close()
    return pages

# ---------------------------------------------------------------------------
# DeepSeek API
# ---------------------------------------------------------------------------

def _deepseek(messages: list[dict], max_tokens: int = 1024,
              max_retries: int = 2) -> str | None:
    if not DEEPSEEK_API_KEY:
        print("  ⚠ DEEPSEEK_API_KEY not set")
        return None
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.05,
    }
    for attempt in range(max_retries):
        try:
            resp = httpx.post(
                f"{DEEPSEEK_BASE}/chat/completions",
                headers=headers, json=payload, timeout=90,
            )
            if resp.status_code == 429:
                backoff = 2 ** attempt
                print(f"  ⏳ rate limited, retry in {backoff}s")
                time.sleep(backoff)
                continue
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            err = e.response.text[:300]
            print(f"  ❌ HTTP {e.response.status_code}: {err}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return None
        except Exception as e:
            print(f"  ❌ {e}")
            return None
    return None


def _infer_screenshot_from_context(context: str) -> str:
    prompt = (
        "The text below is from a page of a Hack The Box wireup. "
        "Based on this text, infer what screenshot is most likely shown "
        "on this page (terminal output, tool UI, config file, etc.). "
        "Answer briefly in Spanish. Text:\n"
        f"{context[:1500]}"
    )
    result = _deepseek(
        [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        max_tokens=128,
    )
    return result or "[Screenshot sin descripción disponible]"


def describe_image(img: dict, context: str) -> str:
    prompt = (
        "This is a screenshot from a Hack The Box writeup. "
        "Describe briefly in Spanish what is shown: what command output, "
        "tool interface, or technical detail is visible."
    )
    content: list[dict] = [
        {"type": "text", "text": prompt},
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/{img['ext']};base64,{img['b64']}"
            },
        },
    ]
    result = _deepseek([{"role": "user", "content": content}])
    if result:
        return result
    return _infer_screenshot_from_context(context)


def extract_commands(text: str) -> list[str]:
    if not text.strip():
        return []
    prompt = (
        "Extract all shell commands (bash, PowerShell, cmd) from this HTB "
        "wireup text. Return a JSON array of strings with full commands and "
        "arguments. Example: [\"nmap -p- target\", \"smbclient -L target\"]. "
        "Return ONLY the JSON array.\n\n"
        f"---\n{text[:3000]}"
    )
    result = _deepseek(
        [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        max_tokens=512,
    )
    if not result:
        return _fallback_commands(text)
    return _parse_json_array(result) or _fallback_commands(text)


def extract_techniques(text: str) -> list[str]:
    if not text.strip():
        return []
    prompt = (
        "Identify MITRE ATT&CK technique IDs relevant to this HTB wireup "
        "text. Return a JSON array of IDs. Example: [\"T1046\", \"T1135\"]. "
        "Return ONLY the JSON array.\n\n"
        f"---\n{text[:3000]}"
    )
    result = _deepseek(
        [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        max_tokens=256,
    )
    return _parse_json_array(result) if result else []


def _parse_json_array(s: str | None) -> list[str] | None:
    if not s:
        return None
    s = s.strip()
    # try direct parse
    try:
        val = json.loads(s)
        if isinstance(val, list):
            return [str(v) for v in val]
    except json.JSONDecodeError:
        pass
    # try to extract [...] block
    m = re.search(r'\[.*?\]', s, re.DOTALL)
    if m:
        try:
            val = json.loads(m.group())
            if isinstance(val, list):
                return [str(v) for v in val]
        except json.JSONDecodeError:
            pass
    return None


def _fallback_commands(text: str) -> list[str]:
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("$ "):
            lines.append(line[2:].strip())
        elif line.startswith("> "):
            lines.append(line[2:].strip())
        elif line.startswith("PS> "):
            lines.append(line[4:].strip())
        elif line.startswith("PS C:\\> "):
            lines.append(line[8:].strip())
    return lines

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("HTB Wireup Parser → bronze.htb_wireups")
    print("=" * 60)

    if not PDF_PATH.exists():
        print(f"❌ PDF not found: {PDF_PATH}")
        return 1

    # 1. Extract PDF
    print(f"\n📄 Reading PDF: {PDF_PATH.name}")
    pages = extract_pdf(PDF_PATH)
    total_imgs = sum(len(p["images"]) for p in pages)
    print(f"   {len(pages)} pages, {total_imgs} images")

    # 2. Group by section
    raw: dict[str, dict] = {k: {"texts": [], "images": []} for k in SECTION_KEYS}
    for p in pages:
        sec = p["section"]
        if sec == "__overview__" or sec not in raw:
            continue
        raw[sec]["texts"].append(p["text"])
        for img in p["images"]:
            raw[sec]["images"].append({**img, "page": p["page_num"]})

    # 3. Process images
    print("\n🖼 Describing images via DeepSeek…")
    all_descs: list[dict] = []
    total = sum(len(s["images"]) for s in raw.values())
    done = 0
    for sec_name in SECTION_KEYS:
        sec = raw[sec_name]
        ctx = sec["texts"][0] if sec["texts"] else ""
        for img in sec["images"]:
            done += 1
            print(f"   [{done}/{total}] p.{img['page']} img#{img['index']} ({sec_name})")
            desc = describe_image(img, ctx)
            all_descs.append({
                "section": sec_name,
                "page": img["page"],
                "description": desc,
            })
            time.sleep(RATE_LIMIT_DELAY)

    # 4. Extract commands + techniques per section
    print("\n🔍 Extracting commands and MITRE techniques via DeepSeek…")
    sections_out: list[dict] = []
    for sec_name in SECTION_KEYS:
        sec = raw[sec_name]
        if not sec["texts"] and not sec["images"]:
            continue
        combined = "\n".join(sec["texts"])
        print(f"   {sec_name}: {len(combined)} chars")
        commands = extract_commands(combined)
        techniques = extract_techniques(combined)
        time.sleep(RATE_LIMIT_DELAY)
        imgs = [d for d in all_descs if d["section"] == sec_name]
        sections_out.append({
            "name": sec_name,
            "commands": commands,
            "techniques": techniques,
            "screenshots": imgs,
        })

    # 5. Extract machine info and flags
    machine = "Overwatch"
    difficulty = "Medium"
    flags: dict[str, str] = {}
    for section in sections_out:
        for cmd in section["commands"]:
            if "user.txt" in cmd.lower():
                flags["user"] = cmd.split()[-1]
            if "root.txt" in cmd.lower():
                flags["root"] = cmd.split()[-1]

    # 6. Build final JSON
    parsed = {
        "machine": machine,
        "difficulty": difficulty,
        "sections": sections_out,
        "flags": flags,
    }
    parsed_json = json.dumps(parsed, ensure_ascii=False, indent=2)

    print(f"\n📦 Structure: {[s['name'] for s in sections_out]}")
    print(f"   Commands: {sum(len(s['commands']) for s in sections_out)}")
    print(f"   Techniques: {sum(len(s['techniques']) for s in sections_out)}")
    print(f"   Screenshots described: {len(all_descs)}")

    # 7. Insert into DuckDB
    print(f"\n💾 Storing in {BRONZE_TABLE}…")
    con = db.connect()
    try:
        con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
        con.execute(f"""
            CREATE OR REPLACE TABLE {BRONZE_TABLE} (
                id INTEGER PRIMARY KEY,
                machine VARCHAR,
                difficulty VARCHAR,
                parsed_json JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        now = datetime.now(timezone.utc).isoformat()
        con.execute(
            f"INSERT INTO {BRONZE_TABLE} VALUES (1, ?, ?, ?::JSON, ?)",
            [machine, difficulty, parsed_json, now],
        )
        print("✅ Inserted 1 row")

        row = con.sql(
            f"SELECT machine, difficulty, "
            f"json_array_length(parsed_json->'$.sections') AS n_sections "
            f"FROM {BRONZE_TABLE}"
        ).fetchone()
        print(f"📊 Validation: machine={row[0]}, difficulty={row[1]}, "
              f"sections={row[2]}")
    finally:
        con.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
