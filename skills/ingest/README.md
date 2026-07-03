# Ingest

Medallion pattern: landing → bronze → silver → gold.

**Router:** [`ingest-data`](ingest-data/SKILL.md)

## Model-invoked

| Zone | Schema | Skill |
|------|--------|-------|
| Bronze | `bronze.*` | [`ingest-data-bronze`](bronze/ingest-data-bronze/SKILL.md) |
| Silver | `silver.*` | [`ingest-data-silver`](silver/ingest-data-silver/SKILL.md) |
| Gold | `gold.*` | [`ingest-data-gold`](gold/ingest-data-gold/SKILL.md) |

## Sub-scope: Bronze formats

Format-specific SQL templates live in [`bronze/references/`](bronze/references/).

Legacy Facebook/Twitter CSV dumps: [`references/redes-legacy-csv.md`](references/redes-legacy-csv.md).

After gold → use [`statistical-report`](../analyze/reports/statistical-report/SKILL.md) or other analyze skills.
