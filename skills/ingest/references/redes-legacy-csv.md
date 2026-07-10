# Legacy redes CSV dumps (Facebook)

External CSV exports under `data/landing/redes/`. **Separate** from SociaVault (`sv_*`) and twikit (`tk_tw_*`).

| Platform | Landing path | Bronze SQL | Silver SQL |
|----------|--------------|------------|------------|
| Facebook | `data/landing/redes/data-fb/` | `scripts/sql/ingest_fb_redes.sql` | `scripts/sql/ingest_fb_silver.sql` |

```bash
uv run python scripts/python/db.py mcp-stop
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_fb_redes.sql
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/ingest_fb_silver.sql
```

Dictionary files (`Diccionario de Datos y Aclaraciones.txt`) are **not** ingested.

---

## Twitter (`tw_*`) — RETIRED

Legacy Twitter CSV tables (`bronze/silver.tw_*`) and `ingest_twitter*.sql` were **removed**.

Use the **twikit** pipeline instead:

- Skill: [`scrape-twikit-twitter`](../../collect/twikit/scrape-twikit-twitter/SKILL.md)
- Mapping: [`twitter-legacy-to-twikit.md`](twitter-legacy-to-twikit.md)
- Drop leftover tables (if any): `scripts/sql/drop_legacy_twitter.sql`

---

## Facebook (`fb_*`)

| Table | User handle column |
|-------|-------------------|
| `silver.fb_fanpage` | **`descripcion`** (page name, not user handle) |
| `silver.fb_comment` | **`user_name`** (comment author; often sparse in source) |
| `silver.fb_comment_classification` | no author column — join to `silver.fb_comment` |

Facebook does **not** use `username`; the equivalent is `user_name`.

Gold redes views (`redes-gold`) are **Facebook-only**. Twitter analytics use `gold.v_tk_hater_*` / `gold.tk_troll_blacklist`.

---

## SociaVault vs legacy FB vs twikit

| | Legacy `fb_*` | Twikit `tk_tw_*` | SociaVault `sv_*` |
|--|---------------|------------------|-------------------|
| Source | External CSV dump | Session scrape | Paid API |
| Twitter | retired | **canonical** | deprecated for Twitter |
| Facebook | yes | — | `sv_fb_*` |

Do not mix tables across pipelines without explicit joins on platform + user id.

---

## Related

- Gold: skill [`redes-gold`](../gold/redes-gold/SKILL.md) (FB-only)
- Reports: skill [`redes-analysis`](../../analyze/reports/redes-analysis/SKILL.md)
- Twitter: skill [`scrape-twikit-twitter`](../../collect/twikit/scrape-twikit-twitter/SKILL.md)
