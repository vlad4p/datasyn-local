# Landing path conventions

| Source type | Typical path |
|-------------|--------------|
| Generic scrape | `data/landing/<domain>/` |
| SociaVault | `data/landing/redes/sociavault/<platform>/` |
| Twikit (X session) | `data/landing/redes/twikit/twitter/` |
| Legacy redes CSV (FB/TW) | `data/landing/redes/data-fb/`, `data/landing/redes/data-tw/` |
| Manual export | `data/landing/<project>/` |

Rules:

- Never mutate landing files after collection
- Landing is gitignored — commit only ingest SQL/skills
- Inspect with `head`, `file`, or DuckDB `read_* LIMIT 5` before bronze ingest
