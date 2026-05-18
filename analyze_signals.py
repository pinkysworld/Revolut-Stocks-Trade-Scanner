"""Per-signal attribution for the swing scoring model.

For every signal that `compute_score` can emit, this measures the realized
forward return on bars where that signal fired, versus the all-bars baseline.
The difference (lift) shows which signals carry predictive edge and which are
noise that should be dropped or down-weighted.

Output: a table sorted by lift, plus a per-asset-class breakdown for the
signals that matter. Reuses the scanner's own scoring code, so it attributes
the real model, not a re-implementation.

Usage:
    python analyze_signals.py [hold_days] [window_bars]
"""
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

import revolut_scanner_v13 as rs

HOLD = int(sys.argv[1]) if len(sys.argv) > 1 else 10
WINDOW = int(sys.argv[2]) if len(sys.argv) > 2 else 500
CLASSES = ["stock", "etf", "equity_cfd", "index_cfd", "commodity_cfd", "crypto"]


def main():
    regime = rs.load_regime()
    btc_regime, btc_close = rs.load_btc_regime()
    assets = rs.load_assets()

    fired = defaultdict(list)       # (scope, signal) -> forward returns when fired
    baseline = defaultdict(list)    # scope -> forward returns, all bars
    crit = rs.CRIT_COLS

    for ticker, name, cls, currency in assets:
        if cls not in CLASSES:
            continue
        df = rs.load_and_enrich(ticker, regime, btc_regime, btc_close, asset_class=cls)
        if df is None or len(df) < 260:
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
            _, sig = rs.compute_score(last, prev, asset_class=cls)
            baseline[cls].append(fwd)
            baseline["ALL"].append(fwd)
            for s in sig:
                base = s.split("(")[0]  # strip "(+5.1%)" suffix on BTC-RS signals
                fired[(cls, base)].append(fwd)
                fired[("ALL", base)].append(fwd)

    all_base = np.mean(baseline["ALL"]) if baseline["ALL"] else float("nan")
    signals = sorted({sig for (scope, sig) in fired if scope == "ALL"})

    print(f"PER-SIGNAL ATTRIBUTION — {HOLD}-day forward return, last {WINDOW} bars")
    print(f"All-bars baseline forward return: {all_base:+.3f}%   "
          f"(samples: {len(baseline['ALL'])})")
    print("=" * 100)
    print(f"  {'signal':<30}{'fired':>8}{'avg fwd':>10}{'baseline':>10}{'lift':>9}  verdict")
    print("-" * 100)

    table = []
    for sig in signals:
        vals = fired[("ALL", sig)]
        if len(vals) < 30:
            continue
        avg = float(np.mean(vals))
        lift = avg - all_base
        table.append((sig, len(vals), avg, lift))
    table.sort(key=lambda x: x[3], reverse=True)

    for sig, cnt, avg, lift in table:
        if lift > 0.15:
            verdict = "KEEP — clear edge"
        elif lift > 0.05:
            verdict = "weak +"
        elif lift > -0.05:
            verdict = "NOISE — ~0 lift"
        else:
            verdict = "HARMFUL — negative lift"
        print(f"  {sig:<30}{cnt:>8}{avg:>+9.3f}%{all_base:>+9.3f}%{lift:>+8.3f}%  {verdict}")

    print("\n" + "=" * 100)
    print("PER-ASSET-CLASS LIFT (signal forward return − that class's baseline)")
    print("-" * 100)
    header = f"  {'signal':<30}" + "".join(f"{c.split('_')[0][:7]:>9}" for c in CLASSES)
    print(header)
    class_base = {c: (np.mean(baseline[c]) if baseline[c] else float("nan")) for c in CLASSES}
    print(f"  {'(class baseline)':<30}" + "".join(f"{class_base[c]:>+8.2f}" for c in CLASSES))
    print("-" * 100)
    for sig, _, _, _ in table:
        cells = []
        for c in CLASSES:
            vals = fired.get((c, sig), [])
            if len(vals) >= 20 and np.isfinite(class_base[c]):
                cells.append(f"{np.mean(vals) - class_base[c]:>+8.2f}")
            else:
                cells.append(f"{'·':>8}")
        print(f"  {sig:<30}" + "".join(cells))
    print("  (positive = signal beats that class's baseline; '·' = <20 samples)")


if __name__ == "__main__":
    main()
