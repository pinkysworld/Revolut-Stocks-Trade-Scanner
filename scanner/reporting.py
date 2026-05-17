from __future__ import annotations

import html
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import pandas as pd


def _safe_slug(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_-]+", "_", (value or "").strip()).strip("_")
    return clean[:48]


def build_run_context(outdir: str, run_label: str = "", iteration: int = 0, snapshot_runs: bool = True) -> Dict[str, Any]:
    started = datetime.now()
    run_id = started.strftime("%Y%m%d_%H%M%S")
    suffix = []
    label = _safe_slug(run_label)
    if label:
        suffix.append(label)
    if iteration:
        suffix.append(f"iter{iteration:03d}")
    snapshot_name = "_".join([run_id] + suffix) if suffix else run_id
    snapshot_dir = Path(outdir).resolve() / "runs" / snapshot_name if snapshot_runs else None
    if snapshot_dir is not None:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
    return {
        "run_id": run_id,
        "started_at": started.isoformat(timespec="seconds"),
        "snapshot_dir": str(snapshot_dir) if snapshot_dir is not None else "",
        "snapshot_name": snapshot_name,
        "run_label": run_label,
        "iteration": iteration,
    }


def write_dataframe_export(
    df: pd.DataFrame,
    outdir: str,
    filename: str,
    *,
    snapshot_dir: str = "",
    allow_empty: bool = True,
) -> str | None:
    if df is None:
        return None
    if df.empty and not allow_empty:
        return None
    output_dir = Path(outdir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    df.to_csv(output_path, index=False)
    if snapshot_dir:
        snapshot_path = Path(snapshot_dir) / filename
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(snapshot_path, index=False)
    return str(output_path)


def write_text_export(text: str, outdir: str, filename: str, *, snapshot_dir: str = "") -> str:
    output_dir = Path(outdir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename
    output_path.write_text(text, encoding="utf-8")
    if snapshot_dir:
        snapshot_path = Path(snapshot_dir) / filename
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(text, encoding="utf-8")
    return str(output_path)


def write_json_export(data: Mapping[str, Any], outdir: str, filename: str, *, snapshot_dir: str = "") -> str:
    return write_text_export(json.dumps(data, indent=2, default=str), outdir, filename, snapshot_dir=snapshot_dir)


def _metric(row: Mapping[str, Any], *keys: str) -> float:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if pd.isna(numeric):
            continue
        return numeric
    return 0.0


def assign_confidence_tier(row: Mapping[str, Any], track_name: str = "") -> Dict[str, Any]:
    score = _metric(row, "score", "daytrade_score", "intraday_score")
    expected_roi = _metric(row, "expected_roi_pct", "daytrade_expected_roi_pct", "intraday_expected_roi_pct")
    risk_reward = _metric(row, "risk_reward", "daytrade_risk_reward", "intraday_risk_reward")
    test_avg = _metric(row, "test_avg", "daytrade_test_avg", "intraday_test_avg")
    bt_avg = _metric(row, "bt_avg", "daytrade_bt_avg", "intraday_bt_avg")

    points = 0
    if score >= 7:
        points += 2
    elif score >= 5:
        points += 1
    if expected_roi >= 8:
        points += 2
    elif expected_roi >= 4:
        points += 1
    if risk_reward >= 2.0:
        points += 2
    elif risk_reward >= 1.35:
        points += 1
    if test_avg >= 1.0:
        points += 2
    elif test_avg > 0:
        points += 1
    if bt_avg >= 1.0:
        points += 1
    if "crypto" in track_name and row.get("asset_class") == "crypto":
        points = max(0, points - 1)

    tier = "speculative"
    if points >= 6:
        tier = "high"
    elif points >= 3:
        tier = "medium"

    out = dict(row)
    out["confidence_points"] = points
    out["confidence_tier"] = tier
    return out


def annotate_confidence_tiers(track_rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    return {
        track_name: [assign_confidence_tier(row, track_name) for row in rows]
        for track_name, rows in track_rows.items()
    }


def build_rejection_report(
    scan_rows: Sequence[Mapping[str, Any]],
    track_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    robust_set: Iterable[str] = (),
    weak_set: Iterable[str] = (),
    allow_weak_classes: bool = False,
    portfolio_plan_rows: Sequence[Mapping[str, Any]] = (),
    config: Mapping[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    config = dict(config or {})
    accepted_lookup = {
        (track_name, str(row.get("ticker")), str(row.get("asset_class"))): row
        for track_name, rows in track_rows.items()
        for row in rows
        if row.get("portfolio_accept", True)
    }
    portfolio_rejections = {
        (str(row.get("track")), str(row.get("ticker")), str(row.get("asset_class"))): str(row.get("portfolio_reason", "portfolio_limit"))
        for row in portfolio_plan_rows
        if not row.get("portfolio_accept", False)
    }

    accepted_classes = set(robust_set) | (set(weak_set) if allow_weak_classes else set())
    mixed_non_crypto = {row.get("asset_class") for row in scan_rows if row.get("asset_class") != "crypto"}
    if accepted_classes:
        mixed_non_crypto &= accepted_classes

    track_specs = {
        "swing": {
            "classes": mixed_non_crypto,
            "score_key": "score",
            "min_score": config.get("MIN_SCORE_FOR_REC", 0),
            "exclude_classes": {"crypto"},
        },
        "week": {
            "classes": mixed_non_crypto,
            "score_key": "score",
            "min_score": config.get("MIN_SCORE_FOR_REC", 0),
            "exclude_classes": {"crypto"},
        },
        "stock_swing": {
            "classes": {"stock"},
            "score_key": "score",
            "min_score": config.get("MIN_SCORE_FOR_REC", 0),
        },
        "stock_week": {
            "classes": {"stock"},
            "score_key": "score",
            "min_score": config.get("MIN_SCORE_FOR_REC", 0),
        },
        "daytrade": {
            "classes": {cls for cls in mixed_non_crypto if cls != "crypto"},
            "score_key": "daytrade_score",
            "min_score": config.get("DAYTRADE_SCORE_THRESHOLD", 0),
            "exclude_classes": {"crypto"},
        },
        "stock_daytrade": {
            "classes": {"stock"},
            "score_key": "daytrade_score",
            "min_score": config.get("DAYTRADE_SCORE_THRESHOLD", 0),
        },
        "crypto_weekly": {
            "classes": {"crypto"},
            "score_key": "score",
            "min_score": config.get("CRYPTO_WEEKLY_MIN_SCORE", 0),
        },
        "crypto_daytrade": {
            "classes": {"crypto"},
            "score_key": "daytrade_score",
            "min_score": config.get("DAYTRADE_SCORE_THRESHOLD", 0),
        },
        "crypto_mean_reversion": {
            "classes": {"crypto"},
            "score_key": "score",
            "min_score": 0,
        },
        "stock_intraday": {
            "classes": {"stock"},
            "score_key": "daytrade_score",
            "min_score": config.get("STOCK_INTRADAY_SCORE_THRESHOLD", 0),
        },
        "crypto_intraday": {
            "classes": {"crypto"},
            "score_key": "daytrade_score",
            "min_score": config.get("CRYPTO_INTRADAY_SCORE_THRESHOLD", 0),
        },
    }

    rows: List[Dict[str, Any]] = []
    for track_name, spec in track_specs.items():
        for row in scan_rows:
            ticker = str(row.get("ticker"))
            asset_class = str(row.get("asset_class"))
            key = (track_name, ticker, asset_class)
            accepted = key in accepted_lookup
            reason = "accepted" if accepted else "additional_builder_gate_or_ranked_out"
            if not accepted and key in portfolio_rejections:
                reason = f"portfolio:{portfolio_rejections[key]}"
            elif asset_class in set(spec.get("exclude_classes", set())):
                reason = "dedicated_track_elsewhere"
            elif spec.get("classes") and asset_class not in set(spec.get("classes", [])):
                reason = "asset_class_mismatch"
            else:
                score_key = str(spec.get("score_key", "score"))
                if _metric(row, score_key) < float(spec.get("min_score", 0) or 0):
                    reason = f"{score_key}_below_threshold"
                elif _metric(row, "notional", "crypto_notional") <= 0:
                    reason = "non_positive_notional"
                elif _metric(row, "predicted_net_eur") <= 0:
                    reason = "non_positive_expected_net"
                elif track_name == "crypto_weekly" and _metric(row, "predicted_move_pct") < float(config.get("CRYPTO_WEEKLY_MIN_PREDICTED_PCT", 0) or 0):
                    reason = "predicted_move_below_floor"
                elif track_name == "crypto_mean_reversion" and _metric(row, "rsi") > float(config.get("CRYPTO_MR_RSI2_MAX", 999) or 999):
                    reason = "not_oversold_enough"
            rows.append({
                "track": track_name,
                "ticker": ticker,
                "asset_class": asset_class,
                "accepted": accepted,
                "reason": reason,
                "score": _metric(row, "score"),
                "daytrade_score": _metric(row, "daytrade_score"),
                "predicted_net_eur": _metric(row, "predicted_net_eur"),
            })
    return rows


def build_run_summary(
    run_context: Mapping[str, Any],
    track_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    quality_summary: Mapping[str, Any],
    risk_summary: Mapping[str, Any],
    rejection_rows: Sequence[Mapping[str, Any]],
    output_files: Mapping[str, str],
    *,
    asset_count: int,
    failed_count: int,
) -> Dict[str, Any]:
    track_counts = {track: len(rows) for track, rows in track_rows.items()}
    top_picks = []
    for track, rows in track_rows.items():
        for row in list(rows)[:2]:
            top_picks.append({
                "track": track,
                "ticker": row.get("ticker"),
                "asset_class": row.get("asset_class"),
                "expected_roi_pct": _metric(row, "expected_roi_pct", "daytrade_expected_roi_pct", "intraday_expected_roi_pct"),
                "confidence_tier": row.get("confidence_tier", ""),
            })
    rejection_counter = Counter(str(row.get("reason", "unknown")) for row in rejection_rows if not row.get("accepted"))
    return {
        "run_id": run_context.get("run_id"),
        "started_at": run_context.get("started_at"),
        "snapshot_dir": run_context.get("snapshot_dir"),
        "asset_count": asset_count,
        "failed_count": failed_count,
        "track_counts": track_counts,
        "quality": quality_summary,
        "portfolio": dict(risk_summary),
        "rejections": dict(rejection_counter),
        "output_files": dict(output_files),
        "top_picks": top_picks[:10],
    }


def _render_table(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> str:
    if not rows:
        return "<p class=\"empty\">No rows.</p>"
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body_parts = []
    for row in rows:
        cells = []
        for column in columns:
            value = row.get(column, "")
            if isinstance(value, float):
                cells.append(f"<td>{value:.2f}</td>")
            else:
                cells.append(f"<td>{html.escape(str(value))}</td>")
        body_parts.append("<tr>" + "".join(cells) + "</tr>")
    return "<table><thead><tr>" + head + "</tr></thead><tbody>" + "".join(body_parts) + "</tbody></table>"


def render_html_dashboard(
    run_summary: Mapping[str, Any],
    track_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    quality_rows: Sequence[Mapping[str, Any]],
    rejection_rows: Sequence[Mapping[str, Any]],
    risk_summary: Mapping[str, Any],
    oos_results: Sequence[Mapping[str, Any]],
) -> str:
    rejection_counts = Counter(str(row.get("reason", "unknown")) for row in rejection_rows if not row.get("accepted"))
    track_rows_summary = [
        {"track": track, "count": len(rows)}
        for track, rows in track_rows.items()
    ]
    quality_issues = [row for row in quality_rows if row.get("status") not in ("ok",)]
    oos_rows = [
        {
            "asset_class": row.get("asset_class"),
            "thr": row.get("thr"),
            "hold": row.get("hold"),
            "verdict": row.get("verdict"),
            "test_avg": row.get("va"),
        }
        for row in oos_results
    ]

    sections = []
    sections.append(
        "<section class=\"hero\">"
        f"<p class=\"eyebrow\">Revolut scanner</p><h1>Run {html.escape(str(run_summary.get('run_id', '')))}</h1>"
        f"<p class=\"lede\">{html.escape(str(run_summary.get('started_at', '')))} · assets {run_summary.get('asset_count', 0)} · failed {run_summary.get('failed_count', 0)}</p>"
        "</section>"
    )
    sections.append(
        "<section><h2>Track counts</h2>" + _render_table(track_rows_summary, ["track", "count"]) + "</section>"
    )
    top_rows = []
    for track, rows in track_rows.items():
        for row in list(rows)[:5]:
            top_rows.append({
                "track": track,
                "ticker": row.get("ticker"),
                "asset_class": row.get("asset_class"),
                "confidence_tier": row.get("confidence_tier"),
                "expected_roi_pct": _metric(row, "expected_roi_pct", "daytrade_expected_roi_pct", "intraday_expected_roi_pct"),
                "portfolio_accept": row.get("portfolio_accept", True),
            })
    sections.append(
        "<section><h2>Top ideas</h2>" + _render_table(top_rows, ["track", "ticker", "asset_class", "confidence_tier", "expected_roi_pct", "portfolio_accept"]) + "</section>"
    )
    sections.append(
        "<section><h2>Portfolio guardrails</h2>" + _render_table([
            {"accepted_positions": risk_summary.get("accepted_positions", 0),
             "rejected_positions": risk_summary.get("rejected_positions", 0),
             "total_risk_eur": risk_summary.get("total_risk_eur", 0.0),
             "total_crypto_notional_eur": risk_summary.get("total_crypto_notional_eur", 0.0)}
        ], ["accepted_positions", "rejected_positions", "total_risk_eur", "total_crypto_notional_eur"]) + "</section>"
    )
    sections.append(
        "<section><h2>Data quality</h2>" + _render_table(quality_issues[:20], ["ticker", "asset_class", "status", "bars", "stale_days", "note"]) + "</section>"
    )
    sections.append(
        "<section><h2>Rejections</h2>" + _render_table(
            [{"reason": reason, "count": count} for reason, count in rejection_counts.most_common(15)],
            ["reason", "count"],
        ) + "</section>"
    )
    sections.append(
        "<section><h2>OOS verdicts</h2>" + _render_table(oos_rows, ["asset_class", "thr", "hold", "verdict", "test_avg"]) + "</section>"
    )

    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Revolut Scanner Dashboard</title>
  <style>
    :root {{
      --ink: #1f2430;
      --muted: #5f6574;
      --panel: rgba(255,255,255,0.82);
      --border: rgba(31,36,48,0.12);
      --accent: #b8442c;
      --accent-soft: #f2dfd6;
      --bg-a: #f7ead7;
      --bg-b: #d7e4f2;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: "Avenir Next", "Trebuchet MS", sans-serif;
      background: radial-gradient(circle at top left, rgba(184,68,44,0.16), transparent 30%), linear-gradient(135deg, var(--bg-a), var(--bg-b));
      min-height: 100vh;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 56px; }}
    section {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 20px 22px;
      margin-bottom: 18px;
      box-shadow: 0 18px 60px rgba(31,36,48,0.08);
      backdrop-filter: blur(14px);
    }}
    .hero {{ padding: 30px 24px; }}
    .eyebrow {{ text-transform: uppercase; letter-spacing: 0.18em; color: var(--accent); font-size: 12px; margin: 0 0 8px; }}
    h1, h2 {{ font-family: ui-serif, Georgia, "Times New Roman", serif; margin: 0 0 10px; }}
    h1 {{ font-size: clamp(2rem, 5vw, 3.4rem); line-height: 0.95; }}
    h2 {{ font-size: 1.35rem; }}
    .lede {{ color: var(--muted); margin: 0; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.94rem; }}
    th, td {{ padding: 10px 8px; text-align: left; border-bottom: 1px solid var(--border); }}
    th {{ color: var(--muted); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em; }}
    tbody tr:hover {{ background: rgba(184,68,44,0.05); }}
    .empty {{ color: var(--muted); margin: 0; }}
    @media (max-width: 760px) {{
      main {{ padding: 18px 12px 36px; }}
      section {{ padding: 16px; border-radius: 16px; overflow-x: auto; }}
      table {{ min-width: 520px; }}
    }}
  </style>
</head>
<body>
  <main>
    {''.join(sections)}
  </main>
</body>
</html>
"""
