"""Data-driven calibration of the compute_score thresholds.

After harmful signals were removed from compute_score the score range shrank,
so the thresholds (SCORE_THRESHOLD, MIN_SCORE_FOR_REC, WEEK_MIN_SCORE,
CRYPTO_WEEKLY_MIN_SCORE) were lowered by a first guess. This script re-fits
them against data.

For each asset class it reports the score distribution and, for every
candidate threshold, the pass rate and the forward-return lift of bars at or
above that threshold. A good threshold is the lowest score whose bars still
show clear positive lift with a usable pass rate (roughly 10-40%).

Usage:
    python calibrate_thresholds.py [hold_days] [window_bars]
"""
import sys

import numpy as np
import pandas as pd

import revolut_scanner_v13 as rs

HOLD = int(sys.argv[1]) if len(sys.argv) > 1 else 10
WINDOW = int(sys.argv[2]) if len(sys.argv) > 2 else 500
CLASSES = ["stock", "etf", "equity_cfd", "index_cfd", "commodity_cfd", "crypto"]


def main():
    regime = rs.load_regime()
    btc_regime, btc_close = rs.load_btc_regime()
    crit = rs.CRIT_COLS
    data = {c: [] for c in CLASSES}

    for ticker, name, cls, currency in rs.load_assets():
        if cls not in CLASSES:
            continue
        df = rs.load_and_enrich(ticker, regime, btc_regime, btc_close, asset_class=cls)
        if df is None or len(df) < 280:
            continue
        closes = df["Close"].values
        extra = [c for c in ("vs_btc_7d", "vs_btc_30d") if c in df.columns]
        rows = df[crit + extra].to_dict("records")
        n = len(df)
        start = max(220, n - WINDOW)
        for i in range(start, n - HOLD):
            last, prev = rows[i], rows[i - 1]
            if any(pd.isna(last[c]) or pd.isna(prev[c]) for c in crit):
                continue
            fwd = (closes[i + HOLD] - closes[i]) / closes[i] * 100.0
            if not np.isfinite(fwd):
                continue
            s, _ = rs.compute_score(last, prev, asset_class=cls)
            data[cls].append((s, fwd))

    print(f"COMPUTE_SCORE THRESHOLD CALIBRATION — {HOLD}-day forward return")
    print("=" * 70)
    for cls in CLASSES:
        pts = data[cls]
        if len(pts) < 200:
            print(f"\n{cls}: too few samples ({len(pts)})")
            continue
        scores = np.array([s for s, _ in pts], dtype=float)
        fwds = np.array([f for _, f in pts], dtype=float)
        base = float(fwds.mean())
        print(f"\n=== {cls}  (n={len(pts)}, baseline fwd {base:+.3f}%) ===")
        pcts = {p: np.percentile(scores, p) for p in (10, 50, 75, 90)}
        print(f"  score distribution: p10={pcts[10]:.0f}  p50={pcts[50]:.0f}  "
              f"p75={pcts[75]:.0f}  p90={pcts[90]:.0f}  max={scores.max():.0f}")
        print(f"  {'thr':>4}{'pass%':>9}{'avg fwd':>11}{'lift':>10}")
        suggestion = None
        for thr in range(0, int(scores.max()) + 1):
            mask = scores >= thr
            if mask.sum() < 30:
                continue
            pr = mask.mean() * 100
            avg = float(fwds[mask].mean())
            lift = avg - base
            mark = ""
            if suggestion is None and lift > 0.10 and 8 <= pr <= 45:
                suggestion = thr
                mark = "  <- suggested"
            print(f"  {thr:>4}{pr:>8.1f}%{avg:>+10.3f}%{lift:>+9.3f}%{mark}")
        if suggestion is not None:
            print(f"  suggested rec threshold for {cls}: {suggestion}")
        else:
            print(f"  no threshold gives clear positive lift for {cls}")


if __name__ == "__main__":
    main()
