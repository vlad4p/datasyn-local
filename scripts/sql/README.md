# SQL scripts

DuckDB ingest / DDL / gold views, grouped by domain. Run via:

```bash
uv run python scripts/python/db.py mcp-stop
uv run python scripts/python/db.py run-sql --ingest --file scripts/sql/<domain>/<file>.sql
# Basename also works (searches scripts/sql/**):
uv run python scripts/python/db.py run-sql --ingest --file ingest_identidades.sql
```

```text
scripts/sql/
  twikit/       # Twitter/X (twikit) bronze/silver/gold
  sociavault/   # SociaVault platforms + entities/classification
  redes/        # Legacy Facebook redes CSV → gold
  monitor/      # Identidades + social-monitor gold
  news/         # La Nación + LN×TW context
  boletin/      # Boletín Oficial ingest
  ops/          # One-shot maintenance (e.g. drop legacy tw_*)
```

| Folder | Typical files |
|--------|----------------|
| `twikit/` | `ingest_twikit_twitter*.sql`, `ingest_tk_*.sql`, profile enrich |
| `sociavault/` | `ingest_sociavault_<platform>*.sql`, entities, classification |
| `redes/` | `ingest_fb_*.sql`, `ingest_redes_gold.sql`, network/entidades |
| `monitor/` | `ingest_identidades.sql`, `ingest_social_monitor_gold.sql` |
| `news/` | `ingest_lanacion_silver.sql`, `ingest_contexto_ln_*.sql` |
| `boletin/` | `ingest_boletin.sql` |
| `ops/` | `drop_legacy_twitter.sql` |

Skills route which file to run; prefer skill docs over calling SQL ad hoc.
