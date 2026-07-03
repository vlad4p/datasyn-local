# SociaVault shared infrastructure

| Component | Path |
|-----------|------|
| API client | [`sociavault_client.py`](../../../../scripts/python/sociavault_client.py) |
| Count limits | [`sociavault_limits.py`](../../../../scripts/python/sociavault_limits.py) |
| Scrape helpers | [`sociavault_scrape_common.py`](../../../../scripts/python/sociavault_scrape_common.py) |
| Orchestrator | [`scrape_sociavault.sh`](../../../../scripts/sh/scrape_sociavault.sh) |

Example:

```bash
uv run python scripts/python/scrape_sociavault_twitter.py \
  --handle myriambregman \
  --last 10 \
  --fetch-replies \
  --ingest-full
```

Shell wrapper:

```bash
./scripts/sh/scrape_sociavault.sh twitter myriambregman --last 10 --fetch-replies
```
