"""Paper-trading forward test for every Revolut-scanner track.

Validates *detection ability* and *predicted-move calibration* across all
asset classes and tracks by replaying each track's entry rule over a held-out
window of recent history and resolving the trades against the price action
that actually followed.

For every (asset class, track) it reports:
  * detection edge  — realized forward return when the score fires vs the
    all-bars baseline (does the score actually discriminate?);
  * calibration     — the scanner's predicted move vs the realized move
    (is the +X% forecast trustworthy?);
  * trading outcome — path-dependent TP/SL paper-trade result.

It also prints a per-score-bucket table so miscalibration is visible directly.

Usage:
    python paper_trade.py [daily|intraday] [test_window_bars]

The harness reuses the scanner's own functions, so it tests the real
detection logic — not a re-implementation.
"""
import sys

import numpy as np
import pandas as pd

import revolut_scanner_v13 as rs

MODE = sys.argv[1] if len(sys.argv) > 1 else "daily"
WINDOW = int(sys.argv[2]) if len(sys.argv) > 2 else (160 if MODE == "daily" else 600)

# Daily tracks: (label, score-series builder, hold bars, score threshold, SL vol frac)
DAILY_TRACKS = [
    ("swing-10d", "swing", 10, rs.MIN_SCORE_FOR_REC, rs.STOP_LOSS_VOL_FRAC),
    ("week-5d", "swing", 5, rs.WEEK_MIN_SCORE, rs.STOP_LOSS_VOL_FRAC),
    ("daytrade-2d", "daytrade", 2, rs.DAYTRADE_SCORE_THRESHOLD, rs.DAYTRADE_STOP_LOSS_VOL_FRAC),
]
ASSET_CLASSES = ["stock", "etf", "equity_cfd", "index_cfd", "commodity_cfd", "crypto"]


def predicted_move(score, atr_pct_frac, hold_days, cls):
    """Replicates the scanner's predicted-move projection for a track."""
    conf = rs.calibrated_confidence(int(score), cls)
    vol_2w = atr_pct_frac * np.sqrt(rs.HOLD_TRADING_DAYS) * 100.0
    scaled_vol = vol_2w * np.sqrt(hold_days / rs.HOLD_TRADING_DAYS)
    return conf * scaled_vol * rs.pred_scale_for(cls), scaled_vol


def resolve(entry, sl, tp, highs, lows, closes, i, hold):
    """Path-dependent TP/SL exit; conservative (SL wins same-day ties)."""
    for j in range(i + 1, i + 1 + hold):
        if lows[j] <= sl:
            return "SL", sl, j
        if highs[j] >= tp:
            return "TP", tp, j
    return "TIME", closes[i + hold], i + hold


def test_track(cls, track_label, kind, hold, score_min, sl_frac, enriched):
    score_buckets = {}          # score -> list of raw forward returns
    trades = []
    baseline_fwd = []           # forward return of every eligible bar (no score filter)

    for ticker, df in enriched:
        if kind == "swing":
            scores = rs.precompute_scores(df, asset_class=cls)
        else:
            scores = rs.precompute_daytrade_scores(df)
        closes = df["Close"].values
        highs = df["High"].values
        lows = df["Low"].values
        atrp = df["ATRpct"].values
        ret7 = df["ret7"].values if "ret7" in df.columns else np.full(len(df), np.nan)
        n = len(df)
        start = max(220, n - WINDOW)
        end = n - hold - 1
        last_exit = start - 1
        for i in range(start, end):
            entry = closes[i]
            if not (np.isfinite(entry) and entry > 0):
                continue
            fwd = (closes[i + hold] - entry) / entry * 100.0
            if np.isfinite(fwd):
                baseline_fwd.append(fwd)
            s = scores.iloc[i]
            if not np.isfinite(s):
                continue
            score_buckets.setdefault(int(s), []).append(fwd)
            if i <= last_exit or s < score_min:
                continue
            if cls == "crypto" and np.isfinite(ret7[i]) and ret7[i] * 100 >= rs.CRYPTO_OVEREXTENSION_PCT:
                continue
            ap = atrp[i]
            if not (np.isfinite(ap) and ap > 0):
                continue
            pred, scaled_vol = predicted_move(s, ap, hold, cls)
            sl, tp, rr = rs.trade_levels(entry, scaled_vol, pred, sl_frac)
            if not np.isfinite(rr) or rr < rs.MIN_RR_RATIO:
                continue
            outcome, exit_price, exit_bar = resolve(entry, sl, tp, highs, lows, closes, i, hold)
            gross = (exit_price - entry) / entry * 100.0
            trades.append({
                "ticker": ticker, "cls": cls, "track": track_label, "score": int(s),
                "predicted_pct": pred, "raw_fwd_pct": fwd, "outcome": outcome,
                "tpsl_gross_pct": gross, "rr": rr,
            })
            last_exit = exit_bar
    return trades, baseline_fwd, score_buckets


def fmt_row(cls, track, trades, baseline):
    if not trades:
        return (f"  {cls:<14}{track:<13}{'—':>7}  "
                f"{'no trades triggered':<40}")
    pred = np.array([t["predicted_pct"] for t in trades])
    rawf = np.array([t["raw_fwd_pct"] for t in trades])
    gross = np.array([t["tpsl_gross_pct"] for t in trades])
    base = np.mean(baseline) if baseline else float("nan")
    edge = rawf.mean() - base
    win = (gross > 0).mean() * 100
    cal = rawf.mean() / pred.mean() if pred.mean() else float("nan")
    return (f"  {cls:<14}{track:<13}{len(trades):>7}  "
            f"pred {pred.mean():>+6.2f}%  realized {rawf.mean():>+6.2f}%  "
            f"base {base:>+6.2f}%  edge {edge:>+6.2f}%  "
            f"cal {cal:>+5.2f}x  win {win:>4.1f}%  TP/SL {gross.mean():>+6.2f}%")


def run_intraday():
    """Hourly-bar forward test for the crypto and stock intraday tracks."""
    regime = rs.load_regime()
    assets = rs.load_assets()
    hold = 12  # hours — mid of the scanner's [4,8,12,24] holds
    specs = [
        ("crypto", rs.load_and_enrich_intraday, rs.CRYPTO_INTRADAY_SCORE_THRESHOLD, 25),
        ("stock", rs.load_and_enrich_intraday_stock, rs.STOCK_INTRADAY_SCORE_THRESHOLD, 20),
    ]
    print("\nLegend: pred=scanner forecast  realized=actual fwd return  base=all-bars avg  "
          "edge=realized−base  cal=realized/pred")
    print("-" * 118)
    all_trades = []
    for cls, enrich_fn, score_min, cap in specs:
        tickers = [a[0] for a in assets if a[2] == cls][:cap]
        trades, baseline = [], []
        for ticker in tickers:
            df = enrich_fn(ticker, regime) if cls == "crypto" else enrich_fn(ticker, regime)
            if df is None or len(df) < 400:
                continue
            scores = rs.precompute_intraday_scores(df)
            closes, highs, lows = df["Close"].values, df["High"].values, df["Low"].values
            atrp = df["ATRpct"].values
            n = len(df)
            start = max(320, n - WINDOW)
            last_exit = start - 1
            for i in range(start, n - hold - 1):
                entry = closes[i]
                if not (np.isfinite(entry) and entry > 0):
                    continue
                fwd = (closes[i + hold] - entry) / entry * 100.0
                if np.isfinite(fwd):
                    baseline.append(fwd)
                s = scores.iloc[i]
                if not np.isfinite(s) or i <= last_exit or s < score_min:
                    continue
                ap = atrp[i]
                if not (np.isfinite(ap) and ap > 0):
                    continue
                conf = rs.calibrated_confidence(int(s), cls)
                vol = ap * np.sqrt(hold) * 100.0
                pred = conf * vol * rs.pred_scale_for(cls)
                sl, tp, rr = rs.trade_levels(entry, vol, pred, rs.INTRADAY_STOP_LOSS_VOL_FRAC)
                if not np.isfinite(rr) or rr < rs.MIN_RR_RATIO:
                    continue
                outcome, exit_price, exit_bar = resolve(entry, sl, tp, highs, lows, closes, i, hold)
                trades.append({"ticker": ticker, "cls": cls, "track": "intraday-12h",
                               "score": int(s), "predicted_pct": pred, "raw_fwd_pct": fwd,
                               "outcome": outcome,
                               "tpsl_gross_pct": (exit_price - entry) / entry * 100.0, "rr": rr})
                last_exit = exit_bar
        all_trades.extend(trades)
        print(fmt_row(cls, "intraday-12h", trades, baseline))
    if all_trades:
        import csv
        with open("paper_trades_intraday.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(all_trades[0].keys()))
            w.writeheader()
            w.writerows(all_trades)
        print(f"\n{len(all_trades)} intraday paper trades written to paper_trades_intraday.csv")


def main():
    print(f"PAPER-TRADE FORWARD TEST — mode={MODE}, held-out window={WINDOW} bars")
    print("=" * 118)
    if MODE == "intraday":
        run_intraday()
        return

    regime = rs.load_regime()
    btc_regime, btc_close = rs.load_btc_regime()
    assets = rs.load_assets()

    # Enrich each asset class once, reuse across that class's tracks.
    enriched_by_class = {}
    for cls in ASSET_CLASSES:
        rows = []
        for ticker, name, ac, currency in assets:
            if ac != cls:
                continue
            df = rs.load_and_enrich(ticker, regime, btc_regime, btc_close, asset_class=cls)
            if df is not None and len(df) >= 260:
                rows.append((ticker, df))
        enriched_by_class[cls] = rows
        print(f"  enriched {cls:<14} {len(rows)} instruments")

    print("\nLegend: pred=scanner forecast  realized=actual fwd return  base=all-bars avg  "
          "edge=realized−base  cal=realized/pred  TP/SL=path-resolved net of nothing")
    print("-" * 118)

    all_trades = []
    all_buckets = {}  # (cls, kind) -> buckets
    for track_label, kind, hold, score_min, sl_frac in DAILY_TRACKS:
        print(f"\n[{track_label}]  threshold score >= {score_min}, hold {hold} bars")
        for cls in ASSET_CLASSES:
            trades, baseline, buckets = test_track(
                cls, track_label, kind, hold, score_min, sl_frac, enriched_by_class[cls])
            all_trades.extend(trades)
            all_buckets[(cls, kind, hold)] = buckets
            print(fmt_row(cls, track_label, trades, baseline))

    # Score-bucket calibration table — swing scoring, 10-day forward return.
    print("\n" + "=" * 118)
    print("SCORE DISCRIMINATION — avg 10-day forward return by raw swing score (all bars, no filter)")
    print("-" * 118)
    print(f"  {'asset class':<14}" + "".join(f"s{sv:>2}    " for sv in range(0, 13)))
    for cls in ASSET_CLASSES:
        buckets = all_buckets.get((cls, "swing", 10), {})
        cells = []
        for sv in range(0, 13):
            vals = buckets.get(sv, [])
            cells.append(f"{np.mean(vals):>+5.1f}" if len(vals) >= 20 else "   . ")
        print(f"  {cls:<14}" + "  ".join(cells))
    print("  (cells with <20 samples shown as '.'; rising left→right = score has predictive edge)")

    if all_trades:
        import csv
        with open("paper_trades_all.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(all_trades[0].keys()))
            w.writeheader()
            w.writerows(all_trades)
        print(f"\n{len(all_trades)} paper trades written to paper_trades_all.csv")


if __name__ == "__main__":
    main()
