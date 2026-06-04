# Action traces

JSONL logs of CLI and agent actions (one JSON object per line).

## Files

- `traces_YYYYMMDD.jsonl` — append-only daily files

## Record shape

```json
{
  "trace_id": "uuid",
  "event_id": "uuid",
  "timestamp": "2026-06-04T12:00:00+00:00",
  "session_id": "optional-cursor-session",
  "event": "ingest.complete",
  "actor": "agent|cli|mcp",
  "source": "prompt|make|scripts/ingest.py",
  "status": "ok|error|start",
  "data": { "table": "sales", "rows": 100 }
}
```

## From Python

```python
from src.trace import log_event

log_event("analysis.hypothesis", actor="agent", source="user-prompt", data={"note": "..."})
```

## Environment

- `DATASYN_SESSION_ID` — group traces from one Cursor chat
- `DATASYN_TRACE_ID` — reuse one trace id across related events

Trace files are gitignored; this README and `.gitkeep` stay in the repo.
