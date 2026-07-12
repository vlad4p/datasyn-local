---
name: host-quack
description: >-
  Host local datasyn.duckdb as a Quack HTTP warehouse so other DuckDB clients
  can query it remotely. Use when the user asks to serve, expose, or share the
  local DuckDB over Quack (not MCP config alone, not attach-to-fleet only).
disable-model-invocation: true
---

# Host local DuckDB via Quack

Serve **this repo’s** `data/duckdb/datasyn.duckdb` over the [Quack](https://duckdb.org/docs/current/quack/overview) HTTP protocol.

| Role | Command | Skill |
|------|---------|--------|
| **Host** (this skill) | `db.py quack-host` | `host-quack` |
| **Client → remote/fleet** | `db.py quack-check` / `quack-sql` / `quack-serve` (MCP) | [`configure-duckdb-mcp`](../configure-duckdb-mcp/SKILL.md) |

`quack-serve` is **not** the warehouse host — it is an MCP stdio bridge that *attaches* to a remote Quack.

---

## When to use

- Share local silver/gold with another machine or process over Quack
- Run a laptop warehouse on `127.0.0.1:9495` without touching the fleet (`:9494`)
- Debug Quack client tooling against a known local DB

---

## File lock (important)

DuckDB allows **one writer process** on the file. While `quack-host` runs it owns `datasyn.duckdb`.

| Want to… | Do this |
|----------|---------|
| Start host | Host stops `mcp-serve` first (or fails if MCP won’t die) |
| Local MCP / classic ingest | `db.py quack-host-stop` first |
| Query the host from another DuckDB | Keep host running; use client `QUACK_HOST`/`PORT` |

```bash
uv run python scripts/python/db.py quack-host-status
uv run python scripts/python/db.py quack-host-stop
```

---

## Env (`.env` — never commit)

```bash
# Host bind (defaults)
# QUACK_BIND_URI=quack:127.0.0.1:9495
# QUACK_ALLOW_OTHER_HOSTNAME=false
QUACK_TOKEN=…              # stable token for clients (recommended)

# Clients of THIS host (point client vars at the bind)
# QUACK_HOST=127.0.0.1
# QUACK_PORT=9495
# QUACK_DISABLE_SSL=true
```

**LAN** (same pattern as datasyn-duckdb):

```bash
QUACK_BIND_URI=quack:0.0.0.0:9494
QUACK_ALLOW_OTHER_HOSTNAME=true
QUACK_TOKEN=…   # required for anything beyond localhost
```

Prefer a TLS reverse proxy for non-local exposure ([Quack reverse proxy](https://duckdb.org/docs/current/quack/setup/reverse_proxy)).

---

## Start / stop

```bash
# Foreground (blocks)
uv run python scripts/python/db.py quack-host
# or
./scripts/sh/quack-host.sh

uv run python scripts/python/db.py quack-host-status
uv run python scripts/python/db.py quack-host-stop
uv run python scripts/python/db.py quack-info   # client + host settings
```

On start: installs/loads `quack`, opens the local DB RW, runs `CALL quack_serve(...)`. If `QUACK_TOKEN` is unset, Quack may auto-generate a token (printed once — set it in `.env` for stability).

---

## Client access

Point client env at the host bind, then:

```bash
QUACK_HOST=127.0.0.1 QUACK_PORT=9495 \
  uv run python scripts/python/db.py quack-sql "SELECT count(*) FROM silver.identidad"
```

Prefer **`quack-sql` / `quack_query`** for non-`main` schemas and when `ATTACH` fails.

### ATTACH caveat (Quack beta)

`ATTACH 'quack:…' AS alias` can fail with `Catalog "alias" does not exist` against rich warehouses that have tables with computed `DEFAULT` expressions ([duckdb/duckdb-quack#132](https://github.com/duckdb/duckdb-quack/issues/132)). The host is still up — use:

```sql
SELECT * FROM quack_query(
  'quack:127.0.0.1:9495',
  'SELECT count(*) FROM silver.identidad',
  token := '…',
  disable_ssl := true
);
```

Non-`main` scans after a successful ATTACH still need `.query()` ([#144](https://github.com/duckdb/duckdb-quack/issues/144)).

---

## Agent checklist

1. Confirm user wants to **host** local DB (not only attach to fleet).
2. Check `quack-host-status` / `mcp-status` — stop the other lock holder if needed.
3. Start `quack-host`; report bind URI (no token in chat if avoidable — say “token set” / length).
4. For ingest afterward: `quack-host-stop` then `run-sql --ingest`.
5. Never commit `.env`, tokens, or `.duckdb` (skill `data-privacy`).
