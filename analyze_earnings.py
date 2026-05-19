"""Measure whether earnings surprise predicts forward returns (PEAD test).

Post-earnings-announcement drift — stocks that beat estimates keep drifting up
for weeks — is one of the most robust documented anomalies. This checks whether
it shows up in this universe before any earnings feature is wired into the
scanner.

For every stock bar it computes the most recent prior earnings surprise and the
days since that report, then buckets the forward return. If positive-surprise
stocks (especially soon after the report) show higher forward returns, an
earnings feature is worth integrating.

Usage:
    python test_earnings_signal.py [hold_days]
"""
import sys

import numpy as np
import pandas as pd
import yfinance as yf

import revolut_scanner_v13 as rs
from scanner.fundamentals import earnings_features, resolve_earnings

HOLD = int(sys.argv[1]) if len(sys.argv) > 1 else 40
WINDOW = 500


def main():
    regime = rs.load_regime()
    assets = [a for a in rs.load_assets() if a[2] == "stock"]
    tickers = sorted({a[0] for a in assets})
    print(f"Resolving earnings calendars for {len(tickers)} stocks (cached)...")
    cal = resolve_earnings(tickers, yf)
    with_data = sum(1 for t in tickers if cal.get(t))
    print(f"  {with_data}/{len(tickers)} stocks have earnings data")

    # bucket -> list of forward returns
    buckets = {"beat": [], "miss": [], "inline": [], "no_data": []}
    fresh_beat, fresh_base = [], []   # beats within 15 days of the report

    for ticker, name, cls, currency in assets:
        calendar = cal.get(ticker) or []
        df = rs.load_and_enrich(ticker, regime, asset_class="stock")
        if df is None or len(df) < 280:
            continue
        closes = df["Close"].values
        n = len(df)
        start = max(220, n - WINDOW)
        for i in range(start, n - HOLD):
            entry, exit_ = closes[i], closes[i + HOLD]
            if not (np.isfinite(entry) and np.isfinite(exit_) and entry > 0):
                continue
            fwd = (exit_ - entry) / entry * 100.0
            feat = earnings_features(calendar, df.index[i])
            surp = feat["last_surprise_pct"]
            since = feat["days_since_earnings"]
            if surp is None:
                buckets["no_data"].append(fwd)
                continue
            if surp > 1.0:
                buckets["beat"].append(fwd)
            elif surp < -1.0:
                buckets["miss"].append(fwd)
            else:
                buckets["inline"].append(fwd)
            if since is not None and since <= 15:
                fresh_base.append(fwd)
                if surp > 1.0:
                    fresh_beat.append(fwd)

    print(f"\nEARNINGS-SURPRISE → {HOLD}-day forward return")
    print("=" * 60)
    allf = [f for b in buckets.values() for f in b]
    base = np.mean(allf) if allf else float("nan")
    print(f"  all stock bars baseline : {base:+.3f}%   (n={len(allf)})")
    for label in ("beat", "inline", "miss", "no_data"):
        vals = buckets[label]
        if len(vals) < 30:
            print(f"  {label:<9} n={len(vals):<7} (too few)")
            continue
        m = np.mean(vals)
        print(f"  {label:<9} n={len(vals):<7} avg {m:+.3f}%   lift {m-base:+.3f}%")

    if len(fresh_beat) >= 30:
        fb, fbase = np.mean(fresh_beat), np.mean(fresh_base)
        print(f"\n  beats within 15d of report : {fb:+.3f}%   "
              f"vs all-fresh {fbase:+.3f}%   lift {fb-fbase:+.3f}%   (n={len(fresh_beat)})")

    beat = buckets["beat"]
    miss = buckets["miss"]
    if len(beat) >= 30 and len(miss) >= 30:
        spread = np.mean(beat) - np.mean(miss)
        verdict = ("PEAD PRESENT — earnings surprise is worth integrating"
                   if spread > 0.3 else
                   "WEAK — small beat/miss spread" if spread > 0.1 else
                   "NO PEAD — earnings surprise adds nothing here")
        print(f"\n  beat − miss spread: {spread:+.3f}%")
        print(f"  VERDICT: {verdict}")


if __name__ == "__main__":
    main()
