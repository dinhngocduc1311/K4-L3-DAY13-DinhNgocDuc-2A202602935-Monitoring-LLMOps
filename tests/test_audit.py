import json
from pathlib import Path

from app.audit import query_audit_events, write_audit_event


def test_audit_schema_redaction_retention_and_query(tmp_path: Path) -> None:
    path = tmp_path / 'audit.jsonl'
    for index, outcome in enumerate(('success', 'failure', 'success'), start=1):
        write_audit_event(
            event='chat_completed' if outcome == 'success' else 'chat_failed',
            correlation_id=f'req-audit00{index}',
            actor_id='student@vinuni.edu.vn',
            action='chat',
            resource='qa',
            outcome=outcome,
            details={'contact': '090 123 4567'},
            path=path,
            retention_records=2,
        )

    records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    assert len(records) == 2
    assert records[0]['schema_version'] == 1
    assert records[0]['actor_id_hash'] != 'student@vinuni.edu.vn'
    assert records[0]['details']['contact'] == '[REDACTED_PHONE_VN]'
    assert [record['correlation_id'] for record in records] == [
        'req-audit002',
        'req-audit003',
    ]
    assert query_audit_events(path, outcome='failure') == [records[0]]
