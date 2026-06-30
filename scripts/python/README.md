# Python scripts

| Script | Usage |
|--------|--------|
| `db.py` | DuckDB connection, paths, MCP (`INSTALL`/`LOAD`/`PRAGMA mcp_server_start`) |
| `sociavault_client.py` | SociaVault REST API client (`SOCIAVAULT_API_KEY` in `.env`) |
| `sociavault_scrape_common.py` | Shared landing paths, manifest, ingest helpers |
| `scrape_sociavault_facebook.py` | Scrape Facebook page → `data/landing/redes/sociavault/facebook/` |
| `scrape_sociavault_twitter.py` | Scrape X/Twitter account → `data/landing/redes/sociavault/twitter/` |
| `scrape_sociavault_instagram.py` | Scrape Instagram account → `data/landing/redes/sociavault/instagram/` |
| `scrape_sociavault_tiktok.py` | Scrape TikTok account → `data/landing/redes/sociavault/tiktok/` |

```bash
uv run python scripts/python/db.py info
uv run python scripts/python/db.py mcp-check
uv run python scripts/python/db.py mcp-config
uv run python scripts/python/db.py mcp-serve   # Cursor MCP (stdio)
```

SociaVault scrape (requires `.env` with `SOCIAVAULT_API_KEY`):

```bash
# Last 10 tweets + all replies + full pipeline
uv run python scripts/python/scrape_sociavault_twitter.py \
  --handle myriambregman --last 10 --fetch-replies --ingest-full

uv run python scripts/python/scrape_sociavault_facebook.py \
  --url "https://www.facebook.com/example" --last 5 --fetch-comments

./scripts/sh/scrape_sociavault.sh twitter myriambregman --last 10 --fetch-replies
```

Import from repo root in other Python code:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path("scripts/python").resolve()))
import db

con = db.connect()
```

Skills: [`scrape-sociavault`](../../skills/scrape-sociavault/SKILL.md)
