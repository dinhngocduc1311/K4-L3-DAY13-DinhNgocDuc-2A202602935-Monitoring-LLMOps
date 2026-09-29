from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
import sys

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.metrics import percentile


def load_records(
    path: Path,
    minutes: int,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[dict]:
    cutoff = start or datetime.now(timezone.utc) - timedelta(minutes=minutes)
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
            timestamp = datetime.fromisoformat(record["ts"].replace("Z", "+00:00"))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
        if timestamp >= cutoff and (end is None or timestamp <= end):
            records.append(record)
    return records


def render_dashboard(
    records: list[dict], dashboard: dict, time_label: str | None = None
) -> str:
    requests = [record for record in records if record.get("event") == "request_received"]
    responses = [record for record in records if record.get("event") == "response_sent"]
    failures = [record for record in records if record.get("event") == "request_failed"]
    retrievals = [
        record for record in records if record.get("tool_name") == "retrieval"
        and record.get("tool_success") is not None
    ]
    latencies = [record["latency_ms"] for record in responses if "latency_ms" in record]
    ttfts = [record["ttft_ms"] for record in responses if "ttft_ms" in record]

    minute_buckets: dict[str, dict[str, float]] = defaultdict(
        lambda: {"requests": 0, "cost": 0.0}
    )
    for record in records:
        minute = str(record.get("ts", ""))[11:16]
        if record.get("event") == "request_received":
            minute_buckets[minute]["requests"] += 1
        if record.get("event") == "response_sent":
            minute_buckets[minute]["cost"] += float(record.get("cost_usd", 0))

    active_minutes = max(1, len([bucket for bucket in minute_buckets.values() if bucket["requests"]]))
    traffic_rate = len(requests) / active_minutes
    error_rate = len(failures) / len(requests) * 100 if requests else 0.0
    retrieval_success = (
        sum(record["tool_success"] is True for record in retrievals) / len(retrievals) * 100
        if retrievals
        else 0.0
    )
    total_cost = sum(float(record.get("cost_usd", 0)) for record in responses)
    tokens_in = sum(int(record.get("tokens_in", 0)) for record in responses)
    tokens_out = sum(int(record.get("tokens_out", 0)) for record in responses)
    quality = (
        sum(float(record.get("quality_score", 0)) for record in responses) / len(responses)
        if responses
        else 0.0
    )

    values = {
        "latency": percentile(latencies, 95),
        "traffic": traffic_rate,
        "errors": error_rate,
        "cost": total_cost,
        "tokens": tokens_in + tokens_out,
        "quality": quality,
    }
    details = {
        "latency": (
            f"<b>P50</b> {percentile(latencies, 50):.0f} ms · "
            f"<b>P95</b> {percentile(latencies, 95):.0f} ms · "
            f"<b>P99</b> {percentile(latencies, 99):.0f} ms · "
            f"<b>TTFT P95</b> {percentile(ttfts, 95):.0f} ms"
        ),
        "traffic": f"<b>{len(requests)}</b> requests · <b>{traffic_rate:.2f}</b> requests/min",
        "errors": (
            f"<b>Error rate</b> {error_rate:.2f}% · "
            f"<b>Retrieval success</b> {retrieval_success:.2f}% · "
            f"<b>Breakdown</b> {escape(str(dict(Counter(r.get('error_type', 'unknown') for r in failures))))}"
        ),
        "cost": (
            f"<b>Total</b> ${total_cost:.6f} · "
            f"<b>Per-minute</b> "
            + " · ".join(
                f"{escape(minute)}=${bucket['cost']:.4f}"
                for minute, bucket in sorted(minute_buckets.items())
                if bucket["cost"]
            )
        ),
        "tokens": f"<b>Input</b> {tokens_in:,} · <b>Output</b> {tokens_out:,}",
        "quality": f"<b>Mean quality score</b> {quality:.3f}",
    }

    cards = []
    for panel in dashboard["panels"]:
        panel_id = panel["id"]
        threshold = panel["threshold"]
        actual = values[panel_id]
        passed = actual <= threshold["value"] if threshold["operator"] == "lte" else actual >= threshold["value"]
        operator = "≤" if threshold["operator"] == "lte" else "≥"
        cards.append(
            f"<section class='panel {'ok' if passed else 'bad'}'>"
            f"<h2>{escape(panel['title'])}</h2>"
            f"<div class='details'>{details[panel_id]}</div>"
            f"<div class='threshold'>SLO/threshold: {escape(threshold['aggregation'])} "
            f"{operator} {threshold['value']} {escape(panel['unit'])}</div>"
            "</section>"
        )

    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="{dashboard['refresh_seconds']}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(dashboard['title'])}</title>
<style>
body {{ margin:0; padding:28px; font:16px system-ui; color:#e8eef8; background:#0b1220; }}
header {{ display:flex; justify-content:space-between; align-items:end; margin-bottom:20px; }}
h1 {{ margin:0 0 6px; font-size:28px; }} .meta {{ color:#91a4bf; font-size:13px; }}
main {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; }}
.panel {{ min-height:140px; padding:20px; border:1px solid #27364d; border-radius:14px; background:#121d2f; }}
.panel.ok {{ border-left:5px solid #33d17a; }} .panel.bad {{ border-left:5px solid #ff6b6b; }}
h2 {{ margin:0 0 22px; font-size:18px; }} .details {{ font-size:17px; line-height:1.8; }}
.threshold {{ margin-top:20px; padding-top:12px; border-top:1px solid #27364d; color:#9fb3cc; font-size:13px; }}
@media(max-width:800px) {{ main {{ grid-template-columns:1fr; }} }}
</style></head><body>
<header><div><h1>{escape(dashboard['title'])}</h1>
<div class="meta">Source: data/logs.jsonl · Time range: {escape(time_label or f"last {dashboard['time_range_minutes']} minutes")} · Refresh: {dashboard['refresh_seconds']} seconds</div></div>
<div class="meta">Generated {escape(generated_at)}</div></header>
<main>{''.join(cards)}</main></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the six-panel Day 13 dashboard")
    parser.add_argument("--logs", type=Path, default=REPO_ROOT / "data" / "logs.jsonl")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config" / "dashboard.yaml")
    parser.add_argument("--from-time", type=datetime.fromisoformat)
    parser.add_argument("--to-time", type=datetime.fromisoformat)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "submission" / "evidence" / "11-dashboard-overview.html",
    )
    args = parser.parse_args()
    if bool(args.from_time) != bool(args.to_time):
        parser.error("--from-time and --to-time must be used together")
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))["dashboard"]
    records = load_records(
        args.logs, config["time_range_minutes"], args.from_time, args.to_time
    )
    time_label = (
        f"{args.from_time.isoformat()} to {args.to_time.isoformat()}"
        if args.from_time
        else None
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        render_dashboard(records, config, time_label=time_label), encoding="utf-8"
    )
    print(f"Rendered {len(records)} records to {args.output}")


if __name__ == "__main__":
    main()
