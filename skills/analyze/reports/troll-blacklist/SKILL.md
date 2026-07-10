---
name: troll-blacklist
description: >-
  Build an auditable twikit-only troll blacklist (block/watch tiers) from reply
  behaviour, risk scores, and graph bridges. Exports CSV for manual X blocking
  — never auto-blocks. Use when the user asks for a troll blacklist, block list,
  or cuentas a bloquear from twikit data.
---

# Troll blacklist (twikit)

**Output:** `reports/twikit-myriam/troll-blacklist/`  
**Table:** `gold.tk_troll_blacklist`  
**Rules:** [`references/blacklist-rules.md`](references/blacklist-rules.md)  
**Privacy:** [`data-privacy`](../../../engineering/data-privacy/SKILL.md) — never commit `reports/**`

> **No auto-block on X.** Export is a reviewable list + criteria only.

---

## When to use

| User asks | Action |
|-----------|--------|
| Blacklist / lista de bloqueo / trolls a bloquear | Run SQL + report script |
| Criterios / score / tiers | Point to `blacklist-rules.md` |
| Solo CSV de usernames | Use `blacklist_block.csv` |

---

## Pipeline

```
silver.tk_tw_reply + tk_tw_reply_classification
(+ gold.tk_hater_profile_risk / grafo bridge if enriched)
        ↓  ingest_tk_troll_blacklist.sql
gold.tk_troll_blacklist
        ↓  generate_tk_troll_blacklist_report.py
reports/twikit-myriam/troll-blacklist/
```

### 1. Build table (writes — stop MCP)

```bash
uv run python scripts/python/db.py mcp-stop
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_tk_troll_blacklist.sql
```

### 2. Export report

```bash
uv run python scripts/python/generate_tk_troll_blacklist_report.py
```

### 3. Explore (MCP)

```sql
SELECT tier, COUNT(*) FROM gold.tk_troll_blacklist GROUP BY 1;
SELECT username, score, reasons, tier
FROM gold.tk_troll_blacklist
WHERE tier = 'block'
ORDER BY score DESC
LIMIT 20;
```

---

## Outputs

| File | Content |
|------|---------|
| `blacklist.csv` | block + watch with score, reasons, metrics |
| `blacklist_block.csv` | `username,user_id` for tier `block` only |
| `report.md` / `report.html` | Summary + samples |
| `data.json` | KPIs + top rows |

---

## Related

- Collect: [`scrape-twikit-twitter`](../../../collect/twikit/scrape-twikit-twitter/SKILL.md)
- Mapping legacy→twikit: [`twitter-legacy-to-twikit.md`](../../../ingest/references/twitter-legacy-to-twikit.md)
- Profile risk graph: `scripts/sql/ingest_tk_hater_profile_graph.sql`
