from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.audit import AUDIT_LOG_PATH, query_audit_events


def main() -> None:
    parser = argparse.ArgumentParser(description='Query the Day 13 audit JSONL')
    parser.add_argument('--path', type=Path, default=AUDIT_LOG_PATH)
    parser.add_argument('--event')
    parser.add_argument('--correlation-id')
    parser.add_argument('--outcome')
    args = parser.parse_args()
    records = query_audit_events(
        args.path,
        event=args.event,
        correlation_id=args.correlation_id,
        outcome=args.outcome,
    )
    print(f'Matched {len(records)} audit event(s)')
    for record in records:
        print(json.dumps(record, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
