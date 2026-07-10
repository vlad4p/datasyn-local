# Landing zone

Raw files **before** DuckDB. Do not edit originals in place.

**Privacy:** everything in this folder stays on your machine. It is **gitignored**
(including subfolders like `redes/`). Never commit CSV, JSON, exports, or scrapes.
Commit only ingest SQL, skills, or scripts — see [`data-privacy`](../skills/engineering/data-privacy/SKILL.md).

## Collect skills

| Source | Skill |
|--------|-------|
| Generic web fetch | [`web-scraping`](../skills/collect/web-scraping/SKILL.md) |
| SociaVault (FB, TW, IG, TT) | [`scrape-sociavault`](../skills/collect/sociavault/scrape-sociavault/SKILL.md) |

Landing path conventions: [`collect/references/landing-paths.md`](../skills/collect/references/landing-paths.md).

## Ingest

Use the **`ingest-data`** skill ([`skills/ingest/ingest-data/SKILL.md`](../skills/ingest/ingest-data/SKILL.md)): DuckDB SQL only — CSV, TSV, JSON, JSONL, Parquet, XLSX, etc.

Bronze format templates: [`ingest/bronze/references/formats.md`](../skills/ingest/bronze/references/formats.md).

Example ask to your agent:

> Ingest `data/landing/my_file.csv` as table `my_table` using read_csv_auto.

Vocabulary: [`CONTEXT.md`](../CONTEXT.md).
