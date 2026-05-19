"""Earnings-based fundamental features for stocks.

yfinance's `get_earnings_dates()` returns recent quarterly EPS estimate / actual
/ surprise. This module caches that per ticker and derives point-in-time-ish
features: days since the last report, days to the next, and the most recent
prior earnings surprise. The surprise was public on its report date, so using
"most recent prior surprise" as a feature on later bars does not look ahead.

Earnings only exist for individual equities — ETFs, CFDs, indices and crypto
return empty features.
"""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

CACHE_PATH = os.path.join(os.path.dirname(__file__), os.pardir, ".yf_cache", "earnings.json")


def fetch_earnings_calendar(ticker, yf_module):
    """Best-effort list of {date, surprise} for a ticker's reported quarters.

    Returns [] on any failure (yfinance fundamental endpoints are flaky).
    """
    try:
        ed = yf_module.Ticker(ticker).get_earnings_dates(limit=24)
    except Exception:
        return []
    if ed is None or len(ed) == 0:
        return []
    rows = []
    for ts, row in ed.iterrows():
        try:
            stamp = pd.Timestamp(ts)
            if stamp.tzinfo is not None:
                stamp = stamp.tz_convert("UTC").tz_localize(None)
            surprise = row.get("Surprise(%)")
            rows.append({
                "date": stamp.strftime("%Y-%m-%d"),
                "surprise": float(surprise) if pd.notna(surprise) else None,
            })
        except Exception:
            continue
    rows.sort(key=lambda r: r["date"])
    return rows


def _load_cache():
    try:
        with open(CACHE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_cache(cache):
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, indent=0, sort_keys=True)
    except Exception:
        pass


def resolve_earnings(tickers, yf_module, max_workers=8):
    """Fetch + permanently cache earnings calendars. Returns {ticker: [rows]}."""
    cache = _load_cache()
    todo = sorted(set(tickers) - set(cache))
    if todo:
        workers = max(1, min(max_workers, len(todo)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = pool.map(lambda t: fetch_earnings_calendar(t, yf_module), todo)
            for ticker, rows in zip(todo, results):
                cache[ticker] = rows
        _save_cache(cache)
    return cache


def earnings_features(calendar, asof):
    """For a calendar and an as-of date, return a dict of point-in-time features.

    days_since_earnings  — calendar days since the last reported quarter
    last_surprise_pct    — EPS surprise % of that most-recent prior report
    days_to_earnings     — calendar days until the next scheduled report
    """
    blank = {"days_since_earnings": None, "last_surprise_pct": None,
             "days_to_earnings": None}
    if not calendar:
        return dict(blank)
    asof = pd.Timestamp(asof)
    if asof.tzinfo is not None:
        asof = asof.tz_convert("UTC").tz_localize(None)
    past = [r for r in calendar if pd.Timestamp(r["date"]) <= asof]
    future = [r for r in calendar if pd.Timestamp(r["date"]) > asof]
    out = dict(blank)
    if past:
        last = past[-1]
        out["days_since_earnings"] = int((asof - pd.Timestamp(last["date"])).days)
        out["last_surprise_pct"] = last["surprise"]
    if future:
        out["days_to_earnings"] = int((pd.Timestamp(future[0]["date"]) - asof).days)
    return out
