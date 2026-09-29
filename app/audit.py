from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from .pii import hash_user_id, scrub_text

AUDIT_LOG_PATH = Path(os.getenv('AUDIT_LOG_PATH', 'data/audit.jsonl'))
_WRITE_LOCK = Lock()


def _retention_records() -> int:
    try:
        return max(1, int(os.getenv('AUDIT_RETENTION_RECORDS', '1000')))
    except ValueError:
        return 1000


def _scrub(value: Any) -> Any:
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, dict):
        return {key: _scrub(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def write_audit_event(
    *,
    event: str,
    correlation_id: str,
    actor_id: str,
    action: str,
    resource: str,
    outcome: str,
    details: dict[str, Any] | None = None,
    path: Path | None = None,
    retention_records: int | None = None,
) -> dict[str, Any]:
    limit = max(1, retention_records or _retention_records())
    record: dict[str, Any] = {}
    record.update(
        schema_version=1,
        ts=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        event=event,
        correlation_id=correlation_id,
        actor_id_hash=hash_user_id(actor_id),
        action=action,
        resource=resource,
        outcome=outcome,
        details=_scrub(details or {}),
    )
    target = path or AUDIT_LOG_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(record, ensure_ascii=False, separators=(',', ':'))
    # ponytail: bounded rewrite; use rotation/database above 1000 records.
    with _WRITE_LOCK:
        lines = target.read_text(encoding='utf-8').splitlines() if target.exists() else []
        target.write_text('\n'.join([*lines, rendered][-limit:]) + '\n', encoding='utf-8')
    return record


def query_audit_events(
    path: Path | None = None,
    *,
    event: str | None = None,
    correlation_id: str | None = None,
    outcome: str | None = None,
) -> list[dict[str, Any]]:
    target = path or AUDIT_LOG_PATH
    if not target.exists():
        return []
    matches = []
    for line in target.read_text(encoding='utf-8').splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event and record.get('event') != event:
            continue
        if correlation_id and record.get('correlation_id') != correlation_id:
            continue
        if outcome and record.get('outcome') != outcome:
            continue
        matches.append(record)
    return matches
