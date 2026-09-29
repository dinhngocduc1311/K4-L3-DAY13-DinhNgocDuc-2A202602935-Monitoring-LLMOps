from datetime import datetime, timezone
from pathlib import Path

import yaml

from scripts.render_dashboard import load_records, render_dashboard


def test_runtime_dashboard_renders_six_panels_with_thresholds() -> None:
    config = yaml.safe_load(Path("config/dashboard.yaml").read_text(encoding="utf-8"))["dashboard"]
    records = [
        {"event": "request_received", "ts": "2026-09-29T08:00:00Z"},
        {
            "event": "response_sent",
            "ts": "2026-09-29T08:00:01Z",
            "latency_ms": 250,
            "ttft_ms": 50,
            "cost_usd": 0.002,
            "tokens_in": 30,
            "tokens_out": 100,
            "quality_score": 0.9,
            "tool_name": "retrieval",
            "tool_success": True,
        },
    ]

    html = render_dashboard(records, config)

    assert all(panel["title"] in html for panel in config["panels"])
    assert html.count("SLO/threshold:") == 6
    assert "Time range: last 60 minutes" in html


def test_load_records_can_isolate_incident_window(tmp_path: Path) -> None:
    logs = tmp_path / "logs.jsonl"
    logs.write_text(
        '\n'.join(
            [
                '{"ts":"2026-09-29T09:00:00Z","event":"response_sent"}',
                '{"ts":"2026-09-29T09:10:00Z","event":"response_sent"}',
            ]
        ),
        encoding="utf-8",
    )

    records = load_records(
        logs,
        60,
        datetime(2026, 9, 29, 9, 5, tzinfo=timezone.utc),
        datetime(2026, 9, 29, 9, 15, tzinfo=timezone.utc),
    )

    assert [record["ts"] for record in records] == ["2026-09-29T09:10:00Z"]
