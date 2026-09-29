from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx

from app import audit, logging_config
from app.main import app


def test_chat_response_log_exposes_quality_for_dashboard(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(audit, 'AUDIT_LOG_PATH', tmp_path / 'audit.jsonl')
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.post(
                "/chat",
                json={
                    "user_id": "student-01",
                    "session_id": "session-01",
                    "feature": "qa",
                    "message": "Explain observability",
                },
            )

    response = asyncio.run(send_request())

    assert response.status_code == 200
    correlation_id = response.headers["x-request-id"]
    assert re.fullmatch(r"req-[0-9a-f]{8}", correlation_id)
    assert response.json()["correlation_id"] == correlation_id
    assert float(response.headers["x-response-time-ms"]) >= 0
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    request_event = next(event for event in events if event["event"] == "request_received")
    response_event = next(event for event in events if event["event"] == "response_sent")
    assert request_event["correlation_id"] == response_event["correlation_id"] == correlation_id
    assert {"user_id_hash", "session_id", "feature", "model", "env"} <= request_event.keys()
    assert response_event["quality_score"] == response.json()["quality_score"]
    assert response_event["ttft_ms"] == response.json()["ttft_ms"]
    assert response_event["tool_name"] == "retrieval"
    assert response_event["tool_success"] is True
    audit_event = json.loads(audit.AUDIT_LOG_PATH.read_text(encoding='utf-8'))
    assert audit_event['event'] == 'chat_completed'
    assert audit_event['correlation_id'] == correlation_id
    assert audit_event['outcome'] == 'success'


def test_supplied_request_id_is_propagated(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(audit, 'AUDIT_LOG_PATH', tmp_path / 'audit.jsonl')
    monkeypatch.setattr(logging_config, "LOG_PATH", tmp_path / "logs.jsonl")

    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/chat",
                headers={"x-request-id": "req-deadbeef"},
                json={
                    "user_id": "student-02",
                    "session_id": "session-02",
                    "feature": "qa",
                    "message": "Explain observability",
                },
            )

    response = asyncio.run(send_request())

    assert response.headers["x-request-id"] == "req-deadbeef"
    assert response.json()["correlation_id"] == "req-deadbeef"
