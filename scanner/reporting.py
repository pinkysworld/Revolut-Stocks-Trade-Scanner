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
        "swing": "CONCRETE TRADING RECOMMENDATIONS — 2-week net ROI (mixed asset classes, excl. crypto)",
        "week": "MIXED WEEK RECOMMENDATIONS — clean 5-day setups across non-crypto tracks",
        "stock_swing": "CASH STOCK SWING RECOMMENDATIONS — regular stocks only",
        "stock_week": "STOCK WEEK RECOMMENDATIONS — cash stocks, 5-day hold",
        "crypto_weekly": "CRYPTO WEEKLY RECOMMENDATIONS — fee-aware weekly crypto setups",
        "crypto_weekly_trade_suggestions": "CRYPTO WEEKLY TRADE SUGGESTIONS — actionable BUY / TP / SL rows",
        "daytrade": "DAYTRADE RECOMMENDATIONS (mixed, excl. crypto) — 1-3 trading days",
        "stock_daytrade": "STOCK DAYTRADE RECOMMENDATIONS — cash stocks only",
        "crypto_daytrade": "CRYPTO DAYTRADE RECOMMENDATIONS — 1-3 day hold",
        "crypto_mean_reversion": "CRYPTO MEAN-REVERSION BOUNCES — oversold bounce track",
        "stock_intraday": "STOCK INTRADAY RECOMMENDATIONS — hourly stock setups",
        "crypto_intraday": "CRYPTO INTRADAY RECOMMENDATIONS — hourly crypto setups",
    }
    return titles.get(track_name, track_name.replace("_", " ").title())


def _dashboard_track_subtitle(track_name: str) -> str:
    subtitles = {
        "swing": "Filter applied: OOS-robust non-crypto class, score above threshold, positive net after fees, and reward:risk above the configured floor.",
        "week": "Mirrors the console week section with clean hold, market, move, fee, ROI, and backtest context.",
        "stock_swing": "Mirrors the console stock swing section with full-backtest and recent test-split context.",
        "stock_week": "Shows the same clean stock-week card details as the terminal output, including sizing and backtest context.",
        "crypto_weekly": "Mirrors the weekly crypto console block with BTC-relative context, fees, ROI, and ATR-sized notionals.",
        "crypto_weekly_trade_suggestions": "Compact execution-oriented rows copied into card format, with the same disclaimer shown above.",
        "daytrade": "Mirrors the mixed non-crypto daytrade section with hold, fees, ROI, and test-split detail.",
        "stock_daytrade": "Cash stock daytrade cards with suggested hold, position sizing, ROI, and recent test split.",
        "crypto_daytrade": "Crypto daytrade cards with BTC-relative context, fees, ROI, and per-track backtest detail.",
        "crypto_mean_reversion": "Oversold bounce cards with RSI / ATR context and mean-reversion backtest detail.",
        "stock_intraday": "Hourly stock cards with daily/daytrade/intraday score alignment, fees, and hourly backtest detail.",
        "crypto_intraday": "Hourly crypto cards with BTC-relative context and multi-timeframe alignment markers where available.",
    }
    return subtitles.get(track_name, "Console recommendation section rendered in plain HTML.")


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
            f"{_format_number(rsi, decimals=1)} / {_format_number(adx, decimals=1)} / {regime:+d}" if regime is not None else f"{_format_number(rsi, decimals=1)} / {_format_number(adx, decimals=1)} / n/a",
        )
    return (
        "RSI / ADX / regime",
        f"{_format_number(rsi, decimals=1)} / {_format_number(adx, decimals=1)} / {regime:+d}" if regime is not None else f"{_format_number(rsi, decimals=1)} / {_format_number(adx, decimals=1)} / n/a",
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
        ("LIVE entry price", _format_price(row.get("price", row.get("entry_price")), currency, decimals=6 if row.get("asset_class") == "crypto" else 4)),
        (_hold_metric_label(track_name), _hold_label(row)),
    ]

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
        parts.append(
            "<div class=\"metric\">"
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
        badges.append(f"<span class=\"badge badge-tier\">{html.escape(str(row.get('confidence_tier')))}</span>")
    if live_status:
        badges.append(f"<span class=\"badge badge-live\">{html.escape(live_status)}</span>")
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
    extra_track_rows: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
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
    sections.append(
        "<section class=\"hero\">"
        f"<p class=\"eyebrow\">Revolut scanner</p><h1>Run {html.escape(str(run_summary.get('run_id', '')))}</h1>"
        f"<p class=\"lede\">{html.escape(str(run_summary.get('started_at', '')))} · assets {run_summary.get('asset_count', 0)} · failed {run_summary.get('failed_count', 0)}</p>"
        "</section>"
    )
    sections.append(
        "<section class=\"disclaimer\">"
        "<h2>Disclaimer</h2>"
        "<p class=\"lede\">Educational and research use only. Not financial advice, no guarantee of accuracy or profitability, and all trades remain your responsibility. Fees, spreads, liquidity, and market hours can change before execution.</p>"
        "</section>"
    )
    sections.append(
        "<section><h2>Track counts</h2>" + _render_table(track_rows_summary, ["track", "count"]) + "</section>"
    )
    top_rows = []
    for track, rows in dashboard_tracks.items():
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
    sections.append(_render_recommendation_sections(dashboard_tracks))

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
        .disclaimer {{ border-color: rgba(184,68,44,0.28); background: linear-gradient(135deg, rgba(242,223,214,0.98), rgba(255,255,255,0.9)); }}
    .eyebrow {{ text-transform: uppercase; letter-spacing: 0.18em; color: var(--accent); font-size: 12px; margin: 0 0 8px; }}
        h1, h2, h3 {{ font-family: ui-serif, Georgia, "Times New Roman", serif; margin: 0 0 10px; }}
    h1 {{ font-size: clamp(2rem, 5vw, 3.4rem); line-height: 0.95; }}
    h2 {{ font-size: 1.35rem; }}
        h3 {{ font-size: 1.15rem; }}
    .lede {{ color: var(--muted); margin: 0; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.94rem; }}
    th, td {{ padding: 10px 8px; text-align: left; border-bottom: 1px solid var(--border); }}
    th {{ color: var(--muted); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em; }}
    tbody tr:hover {{ background: rgba(184,68,44,0.05); }}
    .empty {{ color: var(--muted); margin: 0; }}
        .recommendation-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; margin-top: 18px; }}
        .rec-card {{ border: 1px solid var(--border); border-radius: 18px; padding: 16px; background: rgba(255,255,255,0.72); box-shadow: inset 0 1px 0 rgba(255,255,255,0.45); }}
        .card-badges {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }}
        .badge {{ display: inline-flex; align-items: center; border-radius: 999px; padding: 4px 10px; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; background: rgba(31,36,48,0.08); color: var(--ink); }}
        .badge-rank {{ background: var(--accent); color: white; }}
        .badge-tier {{ background: rgba(183,124,33,0.14); color: #7c5317; }}
        .badge-live {{ background: rgba(34,139,100,0.14); color: #17684b; }}
        .badge-aligned {{ background: rgba(11,108,163,0.14); color: #0f567d; }}
        .badge-flagged {{ background: rgba(184,68,44,0.14); color: #8a2f1f; }}
        .card-kicker {{ margin: 0 0 14px; color: var(--muted); }}
        .metric-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 12px; margin: 0; }}
        .metric {{ padding: 10px 12px; border-radius: 14px; background: rgba(31,36,48,0.04); }}
        .metric dt {{ margin: 0 0 4px; color: var(--muted); font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.08em; }}
        .metric dd {{ margin: 0; font-size: 0.98rem; font-weight: 600; }}
        .card-copy {{ margin: 14px 0 0; color: var(--ink); line-height: 1.45; }}
        .card-copy.warning {{ color: #8a2f1f; }}
    @media (max-width: 760px) {{
      main {{ padding: 18px 12px 36px; }}
      section {{ padding: 16px; border-radius: 16px; overflow-x: auto; }}
      table {{ min-width: 520px; }}
            .recommendation-grid {{ grid-template-columns: 1fr; }}
            .metric-grid {{ grid-template-columns: 1fr; }}
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
