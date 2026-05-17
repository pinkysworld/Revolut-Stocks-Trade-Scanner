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


def _as_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(numeric):
        return None
    return numeric


def _first_text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _format_number(value: Any, decimals: int = 2, signed: bool = False) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if pd.isna(numeric):
        return "n/a"
    return f"{numeric:+.{decimals}f}" if signed else f"{numeric:.{decimals}f}"


def _format_pct(value: Any, decimals: int = 2) -> str:
    text = _format_number(value, decimals=decimals, signed=True)
    return f"{text}%" if text != "n/a" else text


def _format_money(value: Any, currency: str = "EUR", decimals: int = 2) -> str:
    text = _format_number(value, decimals=decimals, signed=True)
    return f"{text} {currency}" if text != "n/a" else text


def _format_price(value: Any, currency: str = "", decimals: int = 4) -> str:
    text = _format_number(value, decimals=decimals, signed=False)
    return f"{text} {currency}".strip() if text != "n/a" else text


def _format_regime(value: Any) -> str:
    numeric = _as_float(value)
    if numeric is None:
        return "n/a"
    return f"{int(round(numeric)):+d}"


def _hold_label(row: Mapping[str, Any]) -> str:
    hold_days = row.get("hold_days")
    hold_hours = row.get("hold_hours")
    if hold_hours not in (None, ""):
        try:
            return f"{int(float(hold_hours))}h"
        except (TypeError, ValueError):
            return str(hold_hours)
    if hold_days not in (None, ""):
        try:
            return f"{int(float(hold_days))}d"
        except (TypeError, ValueError):
            return str(hold_days)
    return "n/a"


def _dashboard_track_title(track_name: str) -> str:
    titles = {
        "swing": "Mixed swing",
        "week": "Mixed week",
        "stock_swing": "Stock swing",
        "stock_week": "Stock week",
        "crypto_weekly": "Crypto weekly",
        "crypto_weekly_trade_suggestions": "Crypto trade tickets",
        "daytrade": "Mixed daytrade",
        "stock_daytrade": "Stock daytrade",
        "crypto_daytrade": "Crypto daytrade",
        "crypto_mean_reversion": "Crypto mean reversion",
        "stock_intraday": "Stock intraday",
        "crypto_intraday": "Crypto intraday",
    }
    return titles.get(track_name, track_name.replace("_", " ").title())


def _dashboard_track_subtitle(track_name: str) -> str:
    subtitles = {
        "swing": "Two-week non-crypto setups filtered for score, reward:risk, fees, and OOS strength.",
        "week": "Five-day non-crypto ideas with clean market, move, fee, and ROI context.",
        "stock_swing": "Regular stock swings with full backtest and recent split context.",
        "stock_week": "Cash stock ideas sized for a five-day hold.",
        "crypto_weekly": "Weekly crypto setups with BTC-relative context and fee-aware targets.",
        "crypto_weekly_trade_suggestions": "Ready-to-place crypto tickets with entry, target, stop, and sizing.",
        "daytrade": "One-to-three-day non-crypto ideas with fee and ROI checks.",
        "stock_daytrade": "Cash stock daytrade setups with sizing and recent test split.",
        "crypto_daytrade": "Short-hold crypto setups with BTC-relative context and fee checks.",
        "crypto_mean_reversion": "Oversold crypto bounce candidates with RSI and ATR context.",
        "stock_intraday": "Hourly stock setups with daily, daytrade, and intraday score alignment.",
        "crypto_intraday": "Hourly crypto setups with BTC-relative and multi-timeframe context.",
    }
    return subtitles.get(track_name, "Recommendation candidates for the current run.")


def _hold_metric_label(track_name: str) -> str:
    if "daytrade" in track_name or "intraday" in track_name:
        return "Suggested hold"
    return "Hold"


def _score_metric(track_name: str, row: Mapping[str, Any]) -> tuple[str, str] | None:
    if track_name in {"daytrade", "stock_daytrade", "crypto_daytrade"}:
        return ("Swing/day score", f"{row.get('score', 'n/a')} / {row.get('daytrade_score', 'n/a')}")
    if track_name in {"stock_intraday", "crypto_intraday"}:
        return (
            "Daily / day / intra score",
            f"{row.get('score', 'n/a')} / {row.get('daytrade_score', 'n/a')} / {row.get('intraday_score', 'n/a')}",
        )
    if row.get("score") is not None:
        return ("Signal score", str(row.get("score")))
    return None


def _position_sizing_metric(track_name: str, row: Mapping[str, Any]) -> tuple[str, str] | None:
    asset_class = _first_text(row, "asset_class")
    units = row.get("crypto_units", row.get("daytrade_units", row.get("intraday_units", row.get("stock_week_units", row.get("units")))))
    notional = _metric(row, "notional", "daytrade_notional", "intraday_notional", "stock_week_notional", "notional_eur")
    if units in (None, "") or notional <= 0:
        return None
    try:
        units_value = float(units)
    except (TypeError, ValueError):
        return None
    unit_label = "shares" if asset_class == "stock" else "units"
    if asset_class == "stock":
        units_text = str(int(round(units_value)))
    else:
        units_text = _format_number(units_value, decimals=8)
    if track_name == "crypto_weekly_trade_suggestions":
        return ("Position sizing", f"BUY {units_text} {unit_label} = ~€{notional:.2f}")
    return ("Position sizing", f"BUY {units_text} {unit_label} = ~€{notional:.2f}")


def _signal_context_metric(track_name: str, row: Mapping[str, Any]) -> tuple[str, str] | None:
    rsi = row.get("rsi")
    adx = row.get("adx")
    regime = row.get("regime")
    if rsi is None and adx is None and regime is None:
        return None
    if track_name in {"stock_intraday", "crypto_intraday"}:
        return (
            "Hourly RSI / ADX / regime",
            f"{_format_number(rsi, decimals=1)} / {_format_number(adx, decimals=1)} / {_format_regime(regime)}",
        )
    return (
        "RSI / ADX / regime",
        f"{_format_number(rsi, decimals=1)} / {_format_number(adx, decimals=1)} / {_format_regime(regime)}",
    )


def _btc_relative_metric(track_name: str, row: Mapping[str, Any]) -> tuple[str, str] | None:
    if not track_name.startswith("crypto"):
        return None
    if row.get("vs_btc_7d_pct") is None and row.get("vs_btc_30d_pct") is None and row.get("ret7_pct") is None:
        return None
    return (
        "BTC relative",
        f"7d {_format_pct(row.get('vs_btc_7d_pct'))} / 30d {_format_pct(row.get('vs_btc_30d_pct'))} / ret7 {_format_pct(row.get('ret7_pct'))}",
    )


def _recommendation_metric_rows(track_name: str, row: Mapping[str, Any]) -> list[tuple[str, str]]:
    currency = _first_text(row, "currency") or "EUR"
    metrics = [
        ("Market", _first_text(row, "market_note", "market_status") or "n/a"),
    ]
    # LIVE entry price with optional drift-from-scan and freshness timestamp
    decimals = 6 if row.get("asset_class") == "crypto" else 4
    raw_price = row.get("price", row.get("entry_price"))
    scan_price = row.get("close_at_scan")
    price_str = _format_price(raw_price, currency, decimals=decimals)
    raw_price_num = _as_float(raw_price)
    scan_price_num = _as_float(scan_price)
    if raw_price_num is not None and scan_price_num is not None and scan_price_num > 0:
        drift = (raw_price_num / scan_price_num - 1) * 100
        if abs(drift) >= 0.05:
            price_str = f"{price_str} ({drift:+.2f}% vs scan)"
    as_of = row.get("live_price_as_of")
    if as_of:
        price_str = f"{price_str}  ·  as of {as_of}"
    metrics.append(("LIVE entry price", price_str))
    metrics.append((_hold_metric_label(track_name), _hold_label(row)))

    if track_name == "crypto_weekly_trade_suggestions":
        metrics.extend([
            ("Action", _first_text(row, "action") or "BUY"),
            ("Size", f"€{_format_number(row.get('notional_eur'), decimals=2)}"),
            ("Units", _format_number(row.get("units"), decimals=8)),
            ("Expected net ROI", _format_money(row.get("expected_net_eur"), "EUR")),
            ("Max loss @ SL", _format_money(row.get("max_loss_if_sl_eur"), "EUR")),
            ("Reward:risk ratio", _format_number(row.get("risk_reward"), decimals=2)),
        ])
        return metrics

    if track_name == "swing":
        metrics.append(("Direction", "LONG (BUY 1 piece)"))

    score_metric = _score_metric(track_name, row)
    if score_metric is not None:
        metrics.append(score_metric)

    sizing_metric = _position_sizing_metric(track_name, row)
    if sizing_metric is not None and track_name != "swing":
        metrics.append(sizing_metric)

    signal_context = _signal_context_metric(track_name, row)
    if signal_context is not None:
        metrics.append(signal_context)

    btc_relative = _btc_relative_metric(track_name, row)
    if btc_relative is not None:
        metrics.append(btc_relative)

    expected_move = _metric(row, "predicted_move_pct", "daytrade_predicted_move_pct", "intraday_predicted_move_pct")
    expected_roi = _metric(row, "expected_roi_pct", "daytrade_expected_roi_pct", "intraday_expected_roi_pct")
    expected_net = _metric(row, "predicted_net_eur", "daytrade_predicted_net_eur", "intraday_predicted_net_eur", "expected_net_eur")
    risk_reward = _metric(row, "risk_reward", "daytrade_risk_reward", "intraday_risk_reward")
    take_profit = row.get("take_profit_price", row.get("daytrade_take_profit_price", row.get("intraday_take_profit_price")))
    stop_loss = row.get("stop_loss_price", row.get("daytrade_stop_loss_price", row.get("intraday_stop_loss_price")))
    fees = _metric(row, "total_fees", "daytrade_fees_eur", "intraday_fees_eur")
    breakeven = _metric(row, "breakeven_pct", "daytrade_breakeven_pct", "intraday_breakeven_pct")

    metrics.extend([
        ("Expected move", _format_pct(expected_move)),
        ("Expected net ROI", _format_pct(expected_roi)),
        ("Expected net", _format_money(expected_net, "EUR")),
        ("Take-profit price", _format_price(take_profit, currency, decimals=6 if row.get("asset_class") == "crypto" else 4)),
        ("Stop-loss price", _format_price(stop_loss, currency, decimals=6 if row.get("asset_class") == "crypto" else 4)),
        ("Reward:risk ratio", _format_number(risk_reward, decimals=2)),
    ])

    if fees > 0:
        metrics.append(("Fees / break-even", f"{_format_money(fees, 'EUR')} / {_format_pct(breakeven)}"))

    if row.get("confidence_tier"):
        metrics.append(("Confidence", f"{row.get('confidence_tier')} ({row.get('confidence_points', 0)} pts)"))
    if row.get("portfolio_reason") and row.get("portfolio_reason") != "ok":
        metrics.append(("Portfolio note", str(row.get("portfolio_reason"))))
    elif row.get("portfolio_accept") is not None:
        metrics.append(("Portfolio note", "accepted" if row.get("portfolio_accept") else "flagged"))

    return metrics


def _backtest_summaries(track_name: str, row: Mapping[str, Any]) -> list[tuple[str, str]]:
    if track_name == "crypto_weekly_trade_suggestions":
        return []
    options = [
        ("Full backtest", "bt_trades", "bt_win_rate", "bt_avg", "Recent test split", "test_trades", "test_win_rate", "test_avg"),
        ("5-day full backtest", "week_bt_trades", "week_bt_win_rate", "week_bt_avg", "5-day test split", "week_test_trades", "week_test_win_rate", "week_test_avg"),
        ("Full backtest", "daytrade_bt_trades", "daytrade_bt_win_rate", "daytrade_bt_avg", "Recent test split", "daytrade_test_trades", "daytrade_test_win_rate", "daytrade_test_avg"),
        ("Full backtest", "stock_dt_full_trades", "stock_dt_full_win_rate", "stock_dt_full_avg", "Test split", "stock_dt_test_trades", "stock_dt_test_win_rate", "stock_dt_test_avg"),
        ("Full backtest", "crypto_dt_full_trades", "crypto_dt_full_win_rate", "crypto_dt_full_avg", "Test split", "crypto_dt_test_trades", "crypto_dt_test_win_rate", "crypto_dt_test_avg"),
        ("MR backtest", "mr_full_trades", "mr_full_win_rate", "mr_full_avg", "MR test split", "mr_test_trades", "mr_test_win_rate", "mr_test_avg"),
        ("Hourly backtest", "intraday_bt_trades", "intraday_bt_win_rate", "intraday_bt_avg", "Hourly test split", "intraday_test_trades", "intraday_test_win_rate", "intraday_test_avg"),
    ]
    for full_label, full_n, full_win, full_avg, test_label, test_n, test_win, test_avg in options:
        if row.get(full_n) is None:
            continue
        full = f"{int(float(row.get(full_n, 0)))} trades, {_format_number(row.get(full_win), decimals=1)}% win rate, avg {_format_pct(row.get(full_avg))}"
        entries = [(full_label, full)]
        if row.get(test_n) is not None:
            test = f"{int(float(row.get(test_n, 0)))} trades, {_format_number(row.get(test_win), decimals=1)}% win rate, avg {_format_pct(row.get(test_avg))}"
            entries.append((test_label, test))
        return entries
    return []


def _signals_label(track_name: str) -> str:
    if track_name in {"stock_intraday", "crypto_intraday"}:
        return "Hourly signals"
    return "Active signals"


def _render_metric_list(metrics: Sequence[tuple[str, str]]) -> str:
    if not metrics:
        return "<p class=\"empty\">No metrics.</p>"
    parts = []
    for label, value in metrics:
        cls = " ".join(part for part in (_metric_value_class(value), _metric_label_class(label)) if part)
        div_class = f"metric {cls}".strip()
        parts.append(
            f"<div class=\"{div_class}\">"
            f"<dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd>"
            "</div>"
        )
    return "<dl class=\"metric-grid\">" + "".join(parts) + "</dl>"


def _render_recommendation_card(track_name: str, row: Mapping[str, Any], rank: int) -> str:
    title = _first_text(row, "name", "ticker") or "Unnamed"
    ticker = _first_text(row, "ticker") or "n/a"
    asset_class = _first_text(row, "asset_class") or "n/a"
    live_status = _first_text(row, "live_status")
    signals = _first_text(row, "signals", "daytrade_signals", "intraday_signals")
    backtests = _backtest_summaries(track_name, row)
    badges = [f"<span class=\"badge badge-rank\">#{rank}</span>"]
    if asset_class and asset_class != "n/a":
        badges.append(f"<span class=\"badge\">{html.escape(asset_class)}</span>")
    if row.get("confidence_tier"):
        tier = str(row.get("confidence_tier", "")).lower()
        tier_cls = f"badge-tier-{tier}" if tier in ("high", "medium", "speculative") else "badge-tier-speculative"
        badges.append(f"<span class=\"badge {tier_cls}\">{html.escape(str(row.get('confidence_tier')))}</span>")
    if live_status:
        ls_map = {"NEW": "new", "UPDATED": "updated", "TP HIT": "tp-hit", "SL HIT": "sl-hit"}
        live_cls = f"badge-live-{ls_map.get(live_status, 'live')}"
        badges.append(f"<span class=\"badge {live_cls}\">{html.escape(live_status)}</span>")
    if row.get("mtf_aligned"):
        badges.append("<span class=\"badge badge-aligned\">aligned</span>")
    if row.get("portfolio_accept") is False:
        badges.append("<span class=\"badge badge-flagged\">portfolio flagged</span>")

    extras = []
    if signals:
        extras.append(f"<p class=\"card-copy\"><strong>{html.escape(_signals_label(track_name))}:</strong> {html.escape(signals)}</p>")
    for label, text in backtests:
        extras.append(f"<p class=\"card-copy\"><strong>{html.escape(label)}:</strong> {html.escape(text)}</p>")
    if row.get("earnings_warning"):
        extras.append(f"<p class=\"card-copy warning\"><strong>Earnings warning:</strong> {html.escape(str(row.get('earnings_warning')))}</p>")

    return (
        "<article class=\"rec-card\">"
        f"<div class=\"card-badges\">{''.join(badges)}</div>"
        f"<h3>{html.escape(title)}</h3>"
        f"<p class=\"card-kicker\">{html.escape(ticker)} · {html.escape(asset_class)} · {_hold_label(row)}</p>"
        + _render_metric_list(_recommendation_metric_rows(track_name, row))
        + "".join(extras)
        + "</article>"
    )


def _render_recommendation_sections(track_rows: Mapping[str, Sequence[Mapping[str, Any]]]) -> str:
    ordered_tracks = [
        "swing",
        "week",
        "stock_swing",
        "stock_week",
        "crypto_weekly_trade_suggestions",
        "crypto_weekly",
        "daytrade",
        "stock_daytrade",
        "crypto_daytrade",
        "crypto_mean_reversion",
        "stock_intraday",
        "crypto_intraday",
    ]
    sections = []
    for track_name in ordered_tracks:
        rows = list(track_rows.get(track_name, []))
        cards = "".join(_render_recommendation_card(track_name, row, rank) for rank, row in enumerate(rows, 1))
        content = cards or "<p class=\"empty\">No recommendations in this track for the current run.</p>"
        sections.append(
            "<section class=\"recommendation-section\">"
            f"<h2>{html.escape(_dashboard_track_title(track_name))}</h2>"
            f"<p class=\"lede\">{html.escape(_dashboard_track_subtitle(track_name))}</p>"
            f"<div class=\"recommendation-grid\">{content}</div>"
            "</section>"
        )
    return "".join(sections)


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


def _cell_class(column: str, value: Any) -> str:
    """Return a CSS class for semantic table cell coloring."""
    col = column.lower()
    if isinstance(value, float) and value == value:  # not NaN
        pct_cols = {
            "expected_roi_pct", "daytrade_expected_roi_pct", "intraday_expected_roi_pct",
            "test_avg", "bt_avg", "predicted_net_eur",
        }
        if col in pct_cols:
            return "val-pos" if value > 0 else ("val-neg" if value < 0 else "")
    if isinstance(value, str):
        v = value.strip()
        if v.upper() == "ROBUST":
            return "verdict-robust"
        if v.upper() == "WEAK":
            return "verdict-weak"
        if v.upper() == "OVERFIT":
            return "verdict-overfit"
        if v.lower() == "high":
            return "tier-high"
        if v.lower() == "medium":
            return "tier-medium"
        if v.lower() == "speculative":
            return "tier-speculative"
    return ""


def _metric_value_class(value: str) -> str:
    """Return a CSS class for metric card value coloring."""
    v = value.strip()
    if v.startswith("+") and v not in ("+0.00%", "+0.00 EUR", "+0.00"):
        return "m-pos"
    if v.startswith("-") and v not in ("-0.00%", "-0.00 EUR", "-0.00"):
        return "m-neg"
    return ""


def _metric_label_class(label: str) -> str:
    text = label.lower()
    if "entry price" in text:
        return "metric-entry"
    if "expected net roi" in text or "reward:risk" in text:
        return "metric-priority"
    if "stop-loss" in text or "max loss" in text:
        return "metric-risk"
    return ""


def _render_track_pills(rows: Sequence[Mapping[str, Any]]) -> str:
    """Render track row counts as badge pills instead of a table."""
    parts = []
    for row in rows:
        count = int(row.get("count", 0))
        track = html.escape(_dashboard_track_title(str(row.get("track", ""))))
        count_class = "pc" if count > 0 else "pc-zero"
        parts.append(
            f"<span class=\"track-pill\">{track}"
            f"<span class=\"{count_class}\">{count}</span></span>"
        )
    return "<div class=\"track-pills\">" + "".join(parts) + "</div>"


def _render_table(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> str:
    if not rows:
        return "<p class=\"empty\">No rows.</p>"
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body_parts = []
    for row in rows:
        cells = []
        for column in columns:
            value = row.get(column, "")
            cls = _cell_class(column, value)
            cls_attr = f" class=\"{cls}\"" if cls else ""
            if isinstance(value, float) and value == value:
                cells.append(f"<td{cls_attr}>{value:.2f}</td>")
            else:
                cells.append(f"<td{cls_attr}>{html.escape(str(value))}</td>")
        body_parts.append("<tr>" + "".join(cells) + "</tr>")
    return "<div class=\"table-wrap\"><table><thead><tr>" + head + "</tr></thead><tbody>" + "".join(body_parts) + "</tbody></table></div>"


def render_html_dashboard(
    run_summary: Mapping[str, Any],
    track_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    quality_rows: Sequence[Mapping[str, Any]],
    rejection_rows: Sequence[Mapping[str, Any]],
    risk_summary: Mapping[str, Any],
    oos_results: Sequence[Mapping[str, Any]],
    extra_track_rows: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    refresh_secs: int = 0,
) -> str:
    dashboard_tracks = {track: list(rows) for track, rows in track_rows.items()}
    for track_name, rows in (extra_track_rows or {}).items():
        dashboard_tracks[track_name] = list(rows)

    rejection_counts = Counter(str(row.get("reason", "unknown")) for row in rejection_rows if not row.get("accepted"))
    track_rows_summary = [
        {"track": track, "count": len(rows)}
        for track, rows in dashboard_tracks.items()
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
    _asset_count = run_summary.get("asset_count", 0)
    _failed_count = run_summary.get("failed_count", 0)
    _total_recs = sum(len(rows) for rows in dashboard_tracks.values())
    _accepted_positions = risk_summary.get("accepted_positions", 0)
    _rejected_positions = risk_summary.get("rejected_positions", 0)
    _quality_issue_count = len(quality_issues)
    _rejection_count = sum(rejection_counts.values())
    _run_id = html.escape(str(run_summary.get("run_id", "")))
    _run_ts = html.escape(str(run_summary.get("started_at", "")))
    try:
        _refresh_secs = int(refresh_secs or 0)
    except (TypeError, ValueError):
        _refresh_secs = 0
    _refresh_label = f"Auto refresh every {max(1, round(_refresh_secs / 60))} min" if _refresh_secs > 0 else "Static snapshot"
    sections.append(
        "<section class=\"hero\">"
        "<div class=\"hero-copy\">"
        "<p class=\"eyebrow\">Revolut Scanner</p>"
        "<h1>Trading Dashboard</h1>"
        f"<p class=\"lede\">Run <strong>{_run_id}</strong> · {_run_ts} · {_refresh_label}</p>"
        "</div>"
        "<div class=\"hero-stats\">"
        f"<div class=\"stat\"><div class=\"stat-num\">{_asset_count}</div><div class=\"stat-label\">Assets scanned</div></div>"
        f"<div class=\"stat\"><div class=\"stat-num\">{_total_recs}</div><div class=\"stat-label\">Recommendations</div></div>"
        f"<div class=\"stat\"><div class=\"stat-num\">{_accepted_positions}</div><div class=\"stat-label\">Accepted positions</div></div>"
        f"<div class=\"stat\"><div class=\"stat-num\">{_quality_issue_count}</div><div class=\"stat-label\">Data issues</div></div>"
        "</div>"
        "</section>"
    )
    sections.append(
        "<section class=\"notice\">"
        "<strong>Educational use only.</strong> "
        "Not financial advice. Fees, spreads, liquidity, and market hours can change before execution."
        "</section>"
    )
    sections.append(
        "<section class=\"section-block\">"
        "<div class=\"section-heading\"><p class=\"eyebrow\">Coverage</p><h2>Track counts</h2></div>"
        + _render_track_pills(track_rows_summary)
        + "</section>"
    )
    top_rows = []
    for track, rows in dashboard_tracks.items():
        for row in list(rows)[:5]:
            top_rows.append({
                "track": _dashboard_track_title(track),
                "ticker": row.get("ticker"),
                "asset_class": row.get("asset_class"),
                "confidence_tier": row.get("confidence_tier"),
                "expected_roi_pct": _metric(row, "expected_roi_pct", "daytrade_expected_roi_pct", "intraday_expected_roi_pct"),
                "portfolio_accept": row.get("portfolio_accept", True),
            })
    sections.append(
        "<div class=\"panel-grid\">"
        "<section class=\"panel panel-wide\"><div class=\"section-heading\"><p class=\"eyebrow\">Ranked</p><h2>Top ideas</h2></div>"
        + _render_table(top_rows, ["track", "ticker", "asset_class", "confidence_tier", "expected_roi_pct", "portfolio_accept"])
        + "</section>"
        + "<section class=\"panel\"><div class=\"section-heading\"><p class=\"eyebrow\">Risk</p><h2>Portfolio guardrails</h2></div>"
        + _render_table([
            {"accepted_positions": risk_summary.get("accepted_positions", 0),
             "rejected_positions": risk_summary.get("rejected_positions", 0),
             "total_risk_eur": risk_summary.get("total_risk_eur", 0.0),
             "total_crypto_notional_eur": risk_summary.get("total_crypto_notional_eur", 0.0)}
        ], ["accepted_positions", "rejected_positions", "total_risk_eur", "total_crypto_notional_eur"])
        + "</section></div>"
    )
    sections.append(
        "<div class=\"panel-grid panel-grid-three\">"
        "<section class=\"panel\"><div class=\"section-heading\"><p class=\"eyebrow\">Data</p><h2>Data quality</h2></div>"
        + _render_table(quality_issues[:20], ["ticker", "asset_class", "status", "bars", "stale_days", "note"])
        + "</section>"
        + f"<section class=\"panel\"><div class=\"section-heading\"><p class=\"eyebrow\">Filters</p><h2>Rejections</h2><span>{_rejection_count} total</span></div>"
        + _render_table(
            [{"reason": reason, "count": count} for reason, count in rejection_counts.most_common(15)],
            ["reason", "count"],
        )
        + "</section>"
        + f"<section class=\"panel\"><div class=\"section-heading\"><p class=\"eyebrow\">Validation</p><h2>OOS verdicts</h2><span>{_failed_count} failed downloads</span></div>"
        + _render_table(oos_rows, ["asset_class", "thr", "hold", "verdict", "test_avg"])
        + "</section></div>"
    )
    sections.append(_render_recommendation_sections(dashboard_tracks))

    _meta_refresh = (
        f'<meta http-equiv="refresh" content="{_refresh_secs}">'
        if _refresh_secs > 0 else ""
    )
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  {_meta_refresh}
  <title>Revolut Scanner — {_run_id}</title>
  <style>
    :root {{
            --ink: #18181b;
            --muted: #626975;
            --subtle: #8b95a1;
      --panel: #ffffff;
            --panel-alt: #f7f8fa;
            --border: #dfe3e8;
            --border-strong: #b9c0ca;
            --accent: #0f766e;
            --accent-strong: #115e59;
            --accent-soft: #e6f4f1;
            --coral: #e85d3f;
            --bg: #f4f6f8;
            --green: #128047;
            --green-bg: #e9f8ef;
            --green-border: rgba(18,128,71,0.22);
            --red: #c7352c;
            --red-bg: #fff0ee;
            --red-border: rgba(199,53,44,0.22);
            --amber: #b7791f;
            --amber-bg: #fff7df;
            --amber-border: rgba(183,121,31,0.25);
            --blue: #2b66b1;
            --blue-bg: #edf4ff;
            --blue-border: rgba(43,102,177,0.22);
            --r-sm: 4px;
            --r-md: 6px;
            --r-lg: 8px;
            --shadow-sm: 0 1px 2px rgba(24,24,27,0.06);
            --shadow-md: 0 10px 24px rgba(24,24,27,0.08);
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", "Helvetica Neue", sans-serif;
      font-size: 15px;
      background: var(--bg);
      min-height: 100vh;
      line-height: 1.5;
    }}
    .site-header {{
            background: rgba(255,255,255,0.94);
            color: var(--ink);
            padding: 0 24px;
      display: flex;
      align-items: center;
      gap: 12px;
            min-height: 46px;
      position: sticky;
      top: 0;
      z-index: 100;
            border-bottom: 1px solid rgba(223,227,232,0.9);
            backdrop-filter: blur(14px);
    }}
    .site-header .brand {{
      font-weight: 700;
            font-size: 0.82rem;
            letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
    .site-header .header-pill {{
            font-size: 0.72rem;
            font-weight: 700;
            padding: 3px 9px;
      border-radius: 999px;
            background: var(--accent-soft);
            color: var(--accent-strong);
    }}
    .site-header .run-meta {{
      font-size: 0.72rem;
            color: var(--muted);
      margin-left: auto;
    }}
        main {{ max-width: 1320px; margin: 0 auto; padding: 16px 24px 72px; }}
        section {{ margin-bottom: 12px; }}
    .hero {{
            display: grid;
            grid-template-columns: minmax(280px, 0.62fr) minmax(560px, 1.38fr);
            align-items: stretch;
            gap: 10px;
            padding: 0;
    }}
        .hero-copy {{
            background: var(--panel);
            border: 1px solid var(--border);
            border-left: 4px solid var(--accent);
            border-radius: var(--r-lg);
            padding: 12px 16px;
            box-shadow: var(--shadow-sm);
        }}
        .eyebrow {{
      font-size: 0.68rem;
      font-weight: 700;
            letter-spacing: 0.1em;
      text-transform: uppercase;
            color: var(--accent);
            margin-bottom: 5px;
    }}
    .hero h1 {{
            font-size: 1.25rem;
      font-weight: 800;
            color: var(--ink);
            margin-bottom: 5px;
            line-height: 1.2;
    }}
        .hero .lede {{ color: var(--muted); font-size: 0.8rem; }}
        .hero .lede strong {{ color: var(--ink); }}
        .hero-stats {{
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 8px;
        }}
        .stat {{
            background: var(--panel);
            border: 1px solid var(--border);
            border-top: 2px solid var(--accent);
            border-radius: var(--r-lg);
            padding: 10px 12px;
            box-shadow: var(--shadow-sm);
            min-height: 62px;
        }}
        .stat-num {{ font-size: 1.28rem; font-weight: 800; color: var(--ink); line-height: 1; }}
    .stat-label {{
            font-size: 0.62rem;
      text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--muted);
            margin-top: 5px;
    }}
        .notice {{
            background: var(--amber-bg);
            border-left: 4px solid var(--amber);
            border-radius: var(--r-lg);
            padding: 9px 14px;
            color: #6f4e16;
            font-size: 0.82rem;
        }}
        .notice strong {{ color: #7c4f0d; }}
        .section-block, .panel {{
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: var(--r-lg);
            padding: 13px 14px;
            box-shadow: var(--shadow-sm);
        }}
        .panel-grid {{
            display: grid;
            grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.9fr);
            gap: 14px;
            margin-bottom: 12px;
        }}
        .panel-grid-three {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
        .panel-wide {{ min-width: 0; }}
        .section-heading {{ position: relative; margin-bottom: 10px; padding-right: 120px; }}
        .section-heading h2 {{ margin-bottom: 0; }}
        .section-heading span {{ color: var(--muted); font-size: 0.78rem; white-space: nowrap; position: absolute; right: 0; top: 2px; }}
        h2 {{ font-size: 1.0rem; font-weight: 750; color: var(--ink); margin-bottom: 12px; }}
        h3 {{ font-size: 1.0rem; font-weight: 750; color: var(--ink); margin-bottom: 4px; line-height: 1.25; }}
    .lede {{ color: var(--muted); font-size: 0.85rem; }}
    .track-pills {{ display: flex; flex-wrap: wrap; gap: 7px; }}
    .track-pill {{
      display: inline-flex;
      align-items: center;
      gap: 7px;
            padding: 4px 10px 4px 9px;
            border-radius: var(--r-lg);
      background: var(--panel-alt);
      border: 1px solid var(--border);
      font-size: 0.78rem;
            color: var(--ink);
    }}
    .track-pill .pc {{
      font-size: 0.72rem; font-weight: 700; padding: 1px 7px;
            border-radius: 999px; background: var(--accent); color: white;
    }}
    .track-pill .pc-zero {{
      font-size: 0.72rem; font-weight: 600; padding: 1px 7px;
      border-radius: 999px; background: var(--border); color: var(--subtle);
    }}
        .table-wrap {{ width: 100%; overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
        thead {{ border-bottom: 1px solid var(--border-strong); }}
    th {{
            padding: 8px 10px; text-align: left; color: var(--muted);
      font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
            letter-spacing: 0.08em; white-space: nowrap;
    }}
        td {{ padding: 8px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }}
    tbody tr:last-child td {{ border-bottom: none; }}
        tbody tr:hover td {{ background: rgba(15,118,110,0.04); }}
    .val-pos {{ color: var(--green); font-weight: 600; }}
    .val-neg {{ color: var(--red); font-weight: 600; }}
    .verdict-robust {{ color: var(--green); font-weight: 700; }}
    .verdict-weak {{ color: var(--amber); font-weight: 700; }}
    .verdict-overfit {{ color: var(--red); font-weight: 600; }}
    .tier-high {{ color: var(--green); font-weight: 600; }}
    .tier-medium {{ color: var(--amber); font-weight: 600; }}
    .tier-speculative {{ color: var(--subtle); }}
    .empty {{ color: var(--subtle); font-size: 0.875rem; padding: 4px 0; }}
        .recommendation-section {{
            padding-top: 16px;
            border-top: 1px solid var(--border);
        }}
    .recommendation-section > h2 {{
            font-size: 1.12rem;
            font-weight: 800;
            color: var(--ink);
            margin-bottom: 4px;
    }}
        .recommendation-section > .lede {{ margin-bottom: 10px; max-width: 780px; }}
    .recommendation-grid {{
      display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 12px; margin-top: 10px;
    }}
    .rec-card {{
      background: var(--panel); border: 1px solid var(--border);
            border-radius: var(--r-lg); padding: 14px;
      box-shadow: var(--shadow-sm); display: flex; flex-direction: column;
            transition: box-shadow 0.15s, border-color 0.15s, transform 0.15s;
    }}
        .rec-card:hover {{ box-shadow: var(--shadow-md); border-color: var(--border-strong); transform: translateY(-1px); }}
        .card-badges {{ display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 11px; }}
    .badge {{
      display: inline-flex; align-items: center;
      padding: 2px 8px; border-radius: 999px;
      font-size: 0.66rem; font-weight: 700;
            text-transform: uppercase; letter-spacing: 0.06em;
      background: var(--panel-alt); border: 1px solid var(--border); color: var(--muted);
    }}
        .badge-rank {{ background: var(--accent-strong); color: white; border-color: transparent; }}
    .badge-tier-high {{ background: var(--green-bg); color: var(--green); border-color: var(--green-border); }}
    .badge-tier-medium {{ background: var(--amber-bg); color: var(--amber); border-color: var(--amber-border); }}
    .badge-tier-speculative {{ background: var(--panel-alt); color: var(--subtle); }}
    .badge-live-new {{ background: var(--green-bg); color: var(--green); border-color: var(--green-border); font-weight: 800; }}
    .badge-live-updated {{ background: var(--blue-bg); color: var(--blue); border-color: var(--blue-border); }}
    .badge-live-tp-hit {{ background: var(--green-bg); color: var(--green); border-color: var(--green-border); font-weight: 800; }}
    .badge-live-sl-hit {{ background: var(--red-bg); color: var(--red); border-color: var(--red-border); font-weight: 800; }}
    .badge-aligned {{ background: var(--blue-bg); color: var(--blue); border-color: var(--blue-border); }}
    .badge-flagged {{ background: var(--amber-bg); color: var(--amber); border-color: var(--amber-border); }}
    .card-kicker {{ font-size: 0.78rem; color: var(--muted); margin-bottom: 12px; }}
        .metric-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 7px; margin: 0 0 10px; }}
    .metric {{
            padding: 8px 10px; border-radius: var(--r-md);
      background: var(--panel-alt); border: 1px solid var(--border);
    }}
        .metric-entry {{ grid-column: 1 / -1; background: var(--accent-soft); border-color: rgba(15,118,110,0.22); }}
        .metric-priority {{ background: #f4fbf7; border-color: var(--green-border); }}
        .metric-risk {{ background: #fff7f6; border-color: var(--red-border); }}
    .metric dt {{
      font-size: 0.64rem; font-weight: 700; text-transform: uppercase;
            letter-spacing: 0.08em; color: var(--subtle); margin-bottom: 2px;
    }}
    .metric dd {{ font-size: 0.9rem; font-weight: 700; color: var(--ink); word-break: break-word; }}
    .metric.m-pos dd {{ color: var(--green); }}
    .metric.m-neg dd {{ color: var(--red); }}
    .metric.m-muted dd {{ color: var(--muted); font-weight: 400; font-size: 0.8rem; }}
    .card-copy {{ font-size: 0.8rem; color: var(--muted); line-height: 1.5; margin-top: 8px; }}
    .card-copy strong {{ color: var(--ink); }}
    .card-copy.warning {{ color: var(--red); }}
    .card-copy.warning strong {{ color: var(--red); }}
    @media (max-width: 760px) {{
            .site-header {{ padding: 0 14px; }}
            main {{ padding: 12px 12px 48px; }}
            .hero {{ grid-template-columns: 1fr; gap: 14px; padding-top: 10px; }}
            .hero h1 {{ font-size: 1.35rem; }}
            .hero-stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            .panel-grid, .panel-grid-three {{ grid-template-columns: 1fr; }}
            .section-block, .panel, .rec-card {{ padding: 14px; }}
            .section-heading {{ padding-right: 0; }}
            .section-heading span {{ position: static; display: block; margin-top: 3px; }}
            table {{ min-width: 560px; }}
      .recommendation-grid {{ grid-template-columns: 1fr; }}
      .metric-grid {{ grid-template-columns: 1fr; }}
            .metric-entry {{ grid-column: auto; }}
      th, td {{ padding: 6px 8px; }}
      .site-header .run-meta {{ display: none; }}
    }}
  </style>
</head>
<body>
  <header class=\"site-header\">
    <span class=\"brand\">Revolut Scanner</span>
    <span class=\"header-pill\">{_total_recs} recs</span>
    <span class=\"run-meta\">{_run_ts}</span>
  </header>
  <main>
    {''.join(sections)}
  </main>
</body>
</html>
"""
