"""Live recommendation journal — closes the loop on the scanner.

The scanner makes recommendations but, on its own, never learns whether they
worked. This module persists every surfaced recommendation to a ledger
(`journal.csv`) and later scores each one against the price path that actually
followed (take-profit hit, stop-loss hit, or timed out at the hold horizon),
producing a real, honest track record.

Deliberately self-contained: it takes a price-history callable for scoring
rather than importing the scanner, so there is no circular dependency.
"""
from __future__ import annotations

import csv
import os
from datetime import datetime

import pandas as pd

JOURNAL_COLUMNS = [
    "logged_at", "date", "track", "ticker", "name", "asset_class", "currency",
    "entry_price", "take_profit", "stop_loss", "hold_days",
    "predicted_move_pct", "expected_roi_pct", "win_probability", "score",
    "risk_reward", "status", "exit_date", "exit_price", "outcome",
    "realized_pct", "days_held",
]


def _get(rec, *keys, default=None):
    for k in keys:
        v = rec.get(k)
        if v is not None and not (isinstance(v, float) and pd.isna(v)):
            return v
    return default


def load_journal(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    except Exception:
        return []


def save_journal(path, rows):
    try:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=JOURNAL_COLUMNS)
            writer.writeheader()
            for r in rows:
                writer.writerow({c: r.get(c, "") for c in JOURNAL_COLUMNS})
    except Exception:
        pass


def _entry_from_rec(track, rec, now):
    hold_days = rec.get("hold_days")
    if hold_days is None and rec.get("hold_hours") is not None:
        # approximate an hourly hold as trading days (~6.5h/session)
        hold_days = max(1, round(float(rec["hold_hours"]) / 6.5))
    return {
        "logged_at": now.isoformat(timespec="seconds"),
        "date": now.date().isoformat(),
        "track": track,
        "ticker": rec.get("ticker", ""),
        "name": rec.get("name", ""),
        "asset_class": rec.get("asset_class", ""),
        "currency": rec.get("currency", ""),
        "entry_price": rec.get("close_at_scan") or rec.get("price"),
        "take_profit": _get(rec, "take_profit_price", "daytrade_take_profit_price",
                            "intraday_take_profit_price"),
        "stop_loss": _get(rec, "stop_loss_price", "daytrade_stop_loss_price",
                          "intraday_stop_loss_price"),
        "hold_days": hold_days,
        "predicted_move_pct": _get(rec, "predicted_move_pct",
                                   "daytrade_predicted_move_pct",
                                   "intraday_predicted_move_pct"),
        "expected_roi_pct": _get(rec, "expected_roi_pct", "daytrade_expected_roi_pct",
                                 "intraday_expected_roi_pct"),
        "win_probability": rec.get("win_probability"),
        "score": rec.get("score"),
        "risk_reward": _get(rec, "risk_reward", "daytrade_risk_reward",
                            "intraday_risk_reward"),
        "status": "open",
        "exit_date": "", "exit_price": "", "outcome": "",
        "realized_pct": "", "days_held": "",
    }


def append_recommendations(path, track_recs, now=None):
    """Append newly-surfaced recommendations to the ledger.

    Deduped so a position is logged once: skipped if (track, ticker) is already
    open, or already logged today. Returns the number of new entries written.
    """
    now = now or datetime.now()
    existing = load_journal(path)
    open_keys = {(r["track"], r["ticker"]) for r in existing if r.get("status") == "open"}
    today = now.date().isoformat()
    today_keys = {(r["track"], r["ticker"]) for r in existing if r.get("date") == today}

    new_rows = []
    for track, recs in track_recs.items():
        for rec in recs or []:
            key = (track, rec.get("ticker", ""))
            if not key[1] or key in open_keys or key in today_keys:
                continue
            entry = _entry_from_rec(track, rec, now)
            if entry["entry_price"] in (None, "") or entry["take_profit"] in (None, ""):
                continue
            new_rows.append(entry)
            today_keys.add(key)
            open_keys.add(key)

    if new_rows:
        save_journal(path, existing + new_rows)
    return len(new_rows)


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def score_open_entries(path, price_history_fn, now=None):
    """Resolve still-open entries against the price path since their entry.

    Conservative: if a bar's range touches both stop and target, the stop is
    assumed to have hit first. Returns the full (updated) ledger.
    """
    now = now or datetime.now()
    rows = load_journal(path)
    changed = False
    history_cache = {}

    for r in rows:
        if r.get("status") != "open":
            continue
        entry = _f(r.get("entry_price"))
        tp = _f(r.get("take_profit"))
        sl = _f(r.get("stop_loss"))
        if entry is None or tp is None or sl is None or entry <= 0:
            continue
        ticker = r["ticker"]
        if ticker not in history_cache:
            try:
                history_cache[ticker] = price_history_fn(ticker)
            except Exception:
                history_cache[ticker] = None
        df = history_cache[ticker]
        if df is None or df.empty:
            continue
        entry_date = pd.Timestamp(r["date"])
        idx = pd.to_datetime(df.index).tz_localize(None) if getattr(df.index, "tz", None) else pd.to_datetime(df.index)
        future = df[idx > entry_date]
        if future.empty:
            continue
        hold = int(_f(r.get("hold_days")) or 10)
        window = future.iloc[:hold]

        outcome, exit_price, exit_ts = None, None, None
        for ts, bar in window.iterrows():
            low, high = bar.get("Low"), bar.get("High")
            if pd.notna(low) and low <= sl:
                outcome, exit_price, exit_ts = "SL", sl, ts
                break
            if pd.notna(high) and high >= tp:
                outcome, exit_price, exit_ts = "TP", tp, ts
                break
        if outcome is None:
            if len(future) >= hold:  # hold horizon elapsed without hitting a barrier
                outcome, exit_price, exit_ts = "TIME", float(window.iloc[-1]["Close"]), window.index[-1]
            else:
                continue  # genuinely still open — not enough bars yet

        exit_ts = pd.Timestamp(exit_ts)
        r["status"] = "closed"
        r["outcome"] = outcome
        r["exit_price"] = round(float(exit_price), 6)
        r["exit_date"] = exit_ts.date().isoformat()
        r["realized_pct"] = round((exit_price - entry) / entry * 100.0, 3)
        r["days_held"] = int((exit_ts - entry_date).days)
        changed = True

    if changed:
        save_journal(path, rows)
    return rows


def summarize_journal(rows):
    """Aggregate stats overall and per track from a scored ledger."""
    closed = [r for r in rows if r.get("status") == "closed"]
    open_n = sum(1 for r in rows if r.get("status") == "open")

    def stats(subset):
        rets = [_f(r.get("realized_pct")) for r in subset]
        rets = [x for x in rets if x is not None]
        if not rets:
            return None
        wins = sum(1 for x in rets if x > 0)
        outcomes = [r.get("outcome") for r in subset]
        return {
            "n": len(rets),
            "win_rate": wins / len(rets) * 100.0,
            "avg_realized": sum(rets) / len(rets),
            "total_realized": sum(rets),
            "tp": outcomes.count("TP"),
            "sl": outcomes.count("SL"),
            "time": outcomes.count("TIME"),
        }

    per_track = {}
    for track in sorted({r.get("track", "") for r in closed}):
        s = stats([r for r in closed if r.get("track") == track])
        if s:
            per_track[track] = s

    return {
        "total_logged": len(rows),
        "open": open_n,
        "closed": len(closed),
        "overall": stats(closed),
        "per_track": per_track,
    }
