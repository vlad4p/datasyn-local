"""Append-only JSON trace logs for agent and CLI actions (.logs/)."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.db import get_logs_path

_TRACE_ID: str | None = None


def trace_id() -> str:
    global _TRACE_ID
    if _TRACE_ID is None:
        _TRACE_ID = os.getenv("DATASYN_TRACE_ID") or str(uuid.uuid4())
    return _TRACE_ID


def session_id() -> str | None:
    return os.getenv("DATASYN_SESSION_ID")


def log_event(
    event: str,
    *,
    actor: str = "agent",
    source: str | None = None,
    status: str = "ok",
    data: dict[str, Any] | None = None,
    error: str | None = None,
) -> Path:
    """Append one trace record as JSONL under .logs/traces_YYYYMMDD.jsonl."""
    logs_dir = get_logs_path()
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"traces_{datetime.now(timezone.utc):%Y%m%d}.jsonl"

    record: dict[str, Any] = {
        "trace_id": trace_id(),
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "actor": actor,
        "status": status,
    }
    if session_id():
        record["session_id"] = session_id()
    if source:
        record["source"] = source
    if data:
        record["data"] = data
    if error:
        record["error"] = error

    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return log_file


def log_span(event: str, **kwargs: Any):
    """Context manager: log start and end (or error) for a multi-step action."""

    class _Span:
        def __enter__(self):
            log_event(f"{event}.start", status="start", **kwargs)
            return self

        def __exit__(self, exc_type, exc, _tb):
            if exc_type is not None:
                log_event(
                    f"{event}.error",
                    status="error",
                    error=str(exc),
                    **{k: v for k, v in kwargs.items() if k in ("actor", "source", "data")},
                )
                return False
            log_event(f"{event}.end", **kwargs)
            return False

    return _Span()
