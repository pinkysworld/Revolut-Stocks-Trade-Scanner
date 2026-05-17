from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping
from urllib import parse, request


def build_notification_message(run_summary: Mapping[str, Any]) -> str:
    track_counts = run_summary.get("track_counts", {})
    lines = [
        f"Revolut scanner run {run_summary.get('run_id', '')}",
        f"Tracks with picks: {sum(1 for count in track_counts.values() if count)} / {len(track_counts)}",
        f"Accepted portfolio positions: {run_summary.get('portfolio', {}).get('accepted_positions', 0)}",
        f"Data issues: {run_summary.get('quality', {}).get('issue_count', 0)}",
    ]
    for track, count in track_counts.items():
        if count:
            lines.append(f"- {track}: {count}")
    top_picks = run_summary.get("top_picks", [])[:5]
    if top_picks:
        lines.append("Top ideas:")
        for row in top_picks:
            lines.append(
                f"- {row.get('track')}: {row.get('ticker')} ({row.get('asset_class')}) roi={row.get('expected_roi_pct', 0):.2f}% tier={row.get('confidence_tier', '')}"
            )
    dashboard_path = run_summary.get("output_files", {}).get("dashboard")
    if dashboard_path:
        lines.append(f"Dashboard: {dashboard_path}")
    return "\n".join(lines)


def _post_json(url: str, payload: Mapping[str, Any]) -> tuple[bool, str]:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=10) as response:
        return True, f"HTTP {response.status}"


def _send_telegram(token: str, chat_id: str, text: str) -> tuple[bool, str]:
    endpoint = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = request.Request(endpoint, data=payload, method="POST")
    with request.urlopen(req, timeout=10) as response:
        return True, f"HTTP {response.status}"


def send_notifications(
    message: str,
    *,
    webhook_url: str = "",
    telegram_token: str = "",
    telegram_chat_id: str = "",
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    if webhook_url:
        try:
            ok, detail = _post_json(webhook_url, {"text": message})
            results.append({"channel": "webhook", "ok": ok, "detail": detail})
        except Exception as exc:
            results.append({"channel": "webhook", "ok": False, "detail": str(exc)})
    if telegram_token and telegram_chat_id:
        try:
            ok, detail = _send_telegram(telegram_token, telegram_chat_id, message)
            results.append({"channel": "telegram", "ok": ok, "detail": detail})
        except Exception as exc:
            results.append({"channel": "telegram", "ok": False, "detail": str(exc)})
    return results
