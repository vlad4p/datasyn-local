# SociaVault count limits (`--last N`)

Scrapes by **count** (last N posts/tweets/videos), not by date range.

| User request | CLI |
|--------------|-----|
| últimos 10 tweets | `--last 10` (default if omitted: 10) |
| últimos 3 posts de FB | `--last 3` or `--max-posts 3` |
| últimos 20 videos TikTok | `--last 20` or `--max-videos 20` |

Algorithm ([`sociavault_limits.py`](../../../../scripts/python/scrape/sociavault/sociavault_limits.py)):

1. Paginate API until no cursor
2. Dedupe by platform ID
3. Sort by publish timestamp DESC
4. Take first N → `selected.json`
5. Fetch **all** comments/replies for selected items only
