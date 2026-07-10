# Landing path conventions

| Source type | Typical path |
|-------------|--------------|
| Generic scrape | `data/landing/<domain>/` |
| SociaVault | `data/landing/redes/sociavault/<platform>/` |
| Twikit (X session) | `data/landing/redes/twikit/twitter/` |
| Legacy redes CSV (FB) | `data/landing/redes/data-fb/` |
| Twikit Twitter/X | `data/landing/redes/twikit/twitter/` |
| Legacy Twitter CSV | **retired** (`data-tw/` historical only) |
| Manual export | `data/landing/<project>/` |

Rules:

- Never mutate landing files after collection
- Landing is gitignored — commit only ingest SQL/skills
- Inspect with `head`, `file`, or DuckDB `read_* LIMIT 5` before bronze ingest
