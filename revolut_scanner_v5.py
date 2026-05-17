"""
Revolut Germany — Bullish Scanner v5
=====================================
Adds to v4:
  • OUT-OF-SAMPLE (OOS) VALIDATION — splits history into TRAIN (first 70%)
    and TEST (last 30%). Finds the best (threshold, hold_days) per asset
    class using ONLY the train segment, then checks whether those exact
    parameters still produced positive returns on the unseen test segment.
    This is the single most important test of whether the sweep found a
    real edge or just got lucky.

Everything from v4 is retained: scoring, fees-aware profit calculator,
baseline backtest, correlation-diversified picks, full parameter sweep,
CSV exports.

REALITY CHECK
-------------
Even passing OOS validation does NOT guarantee future profitability. Markets
change, regimes shift, and any strategy you can find with public data is
already known to better-resourced traders. OOS is a necessary but not
sufficient test. Paper-trade for 6–8 weeks before risking real money.

Install:  pip install yfinance pandas numpy
Run:      python revolut_scanner_v5.py
"""

import os
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# =================== USER CONFIG ===================
STOCK_FEE_OPEN_EUR     = 1.0
STOCK_FEE_CLOSE_EUR    = 1.0
EQUITY_CFD_FEE_PCT     = 0.0025
EQUITY_CFD_FEE_MIN_EUR = 0.01
CFD_BASE_RATE_USD      = 0.045
CFD_BASE_RATE_EUR      = 0.025
CFD_MARKUP             = 0.03

HOLD_TRADING_DAYS  = 10
HOLD_CALENDAR_DAYS = 14
LOOKBACK           = "3y"      # ↑ to 3y for richer train/test split
TOP_N              = 20
UNITS_PER_TRADE    = 1

SCORE_THRESHOLD    = 5
CORR_MAX           = 0.75
CORR_LOOKBACK_DAYS = 60
OUTDIR             = "."

# --- Parameter sweep ---
SWEEP_THRESHOLDS      = [3, 4, 5, 6, 7]
SWEEP_HOLDS           = [3, 5, 10, 15, 20]
MIN_TRADES_FOR_REPORT = 10

# --- Out-of-sample ---
TRAIN_FRACTION    = 0.70         # 70% train / 30% test
MIN_TEST_TRADES   = 8            # need at least this many test trades for verdict

# (ticker, display_name, asset_class, currency)
ASSETS = [
    ("SAP.DE","SAP","stock","EUR"),     ("SIE.DE","Siemens","stock","EUR"),
    ("ALV.DE","Allianz","stock","EUR"), ("BMW.DE","BMW","stock","EUR"),
    ("MBG.DE","Mercedes-Benz","stock","EUR"), ("VOW3.DE","Volkswagen Pf.","stock","EUR"),
    ("DTE.DE","Deutsche Telekom","stock","EUR"), ("ADS.DE","Adidas","stock","EUR"),
    ("BAS.DE","BASF","stock","EUR"),    ("BAYN.DE","Bayer","stock","EUR"),
    ("DBK.DE","Deutsche Bank","stock","EUR"), ("IFX.DE","Infineon","stock","EUR"),
    ("RHM.DE","Rheinmetall","stock","EUR"), ("RWE.DE","RWE","stock","EUR"),
    ("DHL.DE","DHL Group","stock","EUR"), ("AIR.DE","Airbus","stock","EUR"),
    ("AAPL","Apple","stock","USD"),     ("MSFT","Microsoft","stock","USD"),
    ("NVDA","NVIDIA","stock","USD"),    ("GOOGL","Alphabet","stock","USD"),
    ("AMZN","Amazon","stock","USD"),    ("META","Meta","stock","USD"),
    ("TSLA","Tesla","stock","USD"),     ("AMD","AMD","stock","USD"),
    ("AVGO","Broadcom","stock","USD"),  ("NFLX","Netflix","stock","USD"),
    ("JPM","JPMorgan","stock","USD"),   ("KO","Coca-Cola","stock","USD"),
    ("COST","Costco","stock","USD"),
    ("VWCE.DE","Vanguard FTSE All-World","etf","EUR"),
    ("EUNL.DE","iShares Core MSCI World","etf","EUR"),
    ("CSPX.AS","iShares Core S&P 500","etf","USD"),
    ("EQQQ.DE","Invesco Nasdaq-100","etf","EUR"),
    ("EXS1.DE","iShares Core DAX","etf","EUR"),
    ("AAPL","Apple CFD","equity_cfd","USD"),  ("NVDA","NVIDIA CFD","equity_cfd","USD"),
    ("TSLA","Tesla CFD","equity_cfd","USD"),  ("MSFT","Microsoft CFD","equity_cfd","USD"),
    ("AMD","AMD CFD","equity_cfd","USD"),     ("META","Meta CFD","equity_cfd","USD"),
    ("SAP.DE","SAP CFD","equity_cfd","EUR"),  ("SIE.DE","Siemens CFD","equity_cfd","EUR"),
    ("^GSPC","S&P 500 CFD","index_cfd","USD"),
    ("^NDX","Nasdaq 100 CFD","index_cfd","USD"),
    ("^GDAXI","DAX 40 CFD","index_cfd","EUR"),
    ("^STOXX50E","Euro Stoxx 50 CFD","index_cfd","EUR"),
    ("^FTSE","FTSE 100 CFD","index_cfd","USD"),
    ("^N225","Nikkei 225 CFD","index_cfd","USD"),
    ("GC=F","Gold CFD","commodity_cfd","USD"),
    ("SI=F","Silver CFD","commodity_cfd","USD"),
    ("CL=F","WTI Crude Oil CFD","commodity_cfd","USD"),
    ("NG=F","Natural Gas CFD","commodity_cfd","USD"),
    ("HG=F","Copper CFD","commodity_cfd","USD"),
    ("EURUSD=X","EUR/USD CFD","forex_cfd","USD"),
    ("GBPUSD=X","GBP/USD CFD","forex_cfd","USD"),
    ("USDJPY=X","USD/JPY CFD","forex_cfd","USD"),
    ("AUDUSD=X","AUD/USD CFD","forex_cfd","USD"),
]

# =================== INDICATORS ===================
def sma(s, n): return s.rolling(n).mean()
def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def rsi(s, n=14):
    d = s.diff()
    g = d.clip(lower=0).rolling(n).mean()
    l = (-d.clip(upper=0)).rolling(n).mean()
    rs = g / l.replace(0, np.nan)
    return 100 - 100 / (1 + rs)
def macd(s, fast=12, slow=26, signal=9):
    line = ema(s, fast) - ema(s, slow); sig = ema(line, signal)
    return line, sig, line - sig
def atr(df, n=14):
    h,l,c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()
def bollinger(s, n=20, k=2):
    mid = sma(s,n); sd = s.rolling(n).std()
    return mid - k*sd, mid, mid + k*sd

# =================== FEES ===================
def fees_open_close(asset_class, notional):
    if asset_class in ("stock","etf"):
        return STOCK_FEE_OPEN_EUR, STOCK_FEE_CLOSE_EUR
    if asset_class == "equity_cfd":
        f = max(notional * EQUITY_CFD_FEE_PCT, EQUITY_CFD_FEE_MIN_EUR)
        return f, f
    return 0.0, 0.0

def overnight_cost(asset_class, notional, currency, days):
    if asset_class in ("stock","etf"): return 0.0
    base = CFD_BASE_RATE_USD if currency == "USD" else CFD_BASE_RATE_EUR
    return notional * (base + CFD_MARKUP) * days / 360.0

# =================== SCORING ===================
CRIT_COLS = ["Close","SMA50","SMA200","RSI","MACD","MACDsig",
             "MACDhist","ATR","BBL","ret5"]

def compute_score(last, prev):
    sig, score = [], 0
    if last["Close"] > last["SMA50"]:                    score += 1; sig.append("above_SMA50")
    if last["Close"] > last["SMA200"]:                   score += 1; sig.append("above_SMA200")
    if last["SMA50"]  > last["SMA200"]:                  score += 1; sig.append("sma50>sma200")
    if prev["SMA50"] <= prev["SMA200"] and last["SMA50"] > last["SMA200"]:
        score += 2; sig.append("fresh_golden_cross")
    if 45 <= last["RSI"] <= 65:                          score += 1; sig.append("rsi_healthy")
    if prev["RSI"] < 30 <= last["RSI"]:                  score += 2; sig.append("rsi_oversold_reversal")
    if last["RSI"] > 75:                                 score -= 1; sig.append("rsi_overbought")
    if prev["MACD"] < prev["MACDsig"] and last["MACD"] > last["MACDsig"]:
        score += 2; sig.append("macd_bullish_cross")
    if last["MACDhist"] > 0 and last["MACDhist"] > prev["MACDhist"]:
        score += 1; sig.append("macd_hist_rising")
    if prev["Close"] < prev["BBL"] and last["Close"] > last["BBL"]:
        score += 1; sig.append("bb_lower_bounce")
    if (prev["Close"] < prev["Open"] and last["Close"] > last["Open"]
            and last["Open"]  < prev["Close"] and last["Close"] > prev["Open"]):
        score += 1; sig.append("bullish_engulfing")
    if 0.005 < last["ret5"] < 0.06:                      score += 1; sig.append("healthy_5d_momentum")
    return score, sig

def precompute_scores(df):
    out = np.full(len(df), np.nan)
    rows = df[CRIT_COLS + ["Open"]].to_dict("records")
    for i in range(1, len(df)):
        last, prev = rows[i], rows[i-1]
        if any(pd.isna(last[c]) or pd.isna(prev[c]) for c in CRIT_COLS):
            continue
        s, _ = compute_score(last, prev)
        out[i] = s
    return pd.Series(out, index=df.index)

# =================== DATA LOAD ===================
def load_and_enrich(ticker):
    try:
        df = yf.download(ticker, period=LOOKBACK, progress=False, auto_adjust=True)
    except Exception:
        return None
    if df is None or df.empty or len(df) < 220:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    c = df["Close"]
    df["SMA20"], df["SMA50"], df["SMA200"] = sma(c,20), sma(c,50), sma(c,200)
    df["RSI"] = rsi(c)
    m, ms, mh = macd(c)
    df["MACD"], df["MACDsig"], df["MACDhist"] = m, ms, mh
    df["ATR"] = atr(df)
    bbl, bbm, bbh = bollinger(c)
    df["BBL"], df["BBM"], df["BBH"] = bbl, bbm, bbh
    df["ret5"] = c.pct_change(5)
    df["ret1"] = c.pct_change(1)
    return df

# =================== CURRENT SCAN ===================
def current_analysis(df, ticker, name, asset_class, currency):
    last, prev = df.iloc[-1], df.iloc[-2]
    if last[CRIT_COLS].isna().any() or prev[CRIT_COLS].isna().any():
        return None
    score, sig = compute_score(last, prev)
    atr_pct = float(last["ATR"] / last["Close"])
    vol_2w  = atr_pct * np.sqrt(HOLD_TRADING_DAYS) * 100.0
    confidence = max(0, min(score, 10)) / 10.0
    pred_move  = confidence * vol_2w * 0.7
    return {"ticker": ticker, "name": name, "asset_class": asset_class,
            "currency": currency, "price": float(last["Close"]),
            "score": int(score), "rsi": float(last["RSI"]),
            "vol_2w_pct": vol_2w, "predicted_move_pct": pred_move,
            "signals": ", ".join(sig)}

def project_pnl(row, units=UNITS_PER_TRADE):
    notional = row["price"] * units
    of, cf = fees_open_close(row["asset_class"], notional)
    ov     = overnight_cost(row["asset_class"], notional, row["currency"], HOLD_CALENDAR_DAYS)
    fees   = of + cf + ov
    gross  = notional * row["predicted_move_pct"] / 100.0
    bull_g = notional * row["vol_2w_pct"] / 100.0
    row.update({"notional": notional, "open_fee": of, "close_fee": cf, "overnight": ov,
                "total_fees": fees,
                "breakeven_pct": fees/notional*100 if notional>0 else np.nan,
                "predicted_net_eur": gross - fees,
                "bull_case_net_eur":  bull_g - fees,
                "bear_case_net_eur": -bull_g - fees})
    return row

# =================== SIMULATION (with index range) ===================
def simulate(df, scores, asset_class, currency, threshold, hold,
             start_idx=200, end_idx=None):
    if end_idx is None: end_idx = len(df)
    closes = df["Close"].values
    scores_arr = scores.values
    dates = df.index
    trades = []
    last_exit = start_idx - 1
    cal_days = max(1, int(round(hold * 1.4)))
    for i in range(start_idx, end_idx - hold):
        if i <= last_exit: continue
        s = scores_arr[i]
        if not np.isfinite(s) or s < threshold: continue
        entry = closes[i]; exit_ = closes[i + hold]
        if not (np.isfinite(entry) and np.isfinite(exit_) and entry > 0): continue
        notional = entry * UNITS_PER_TRADE
        of, cf  = fees_open_close(asset_class, notional)
        ov      = overnight_cost(asset_class, notional, currency, cal_days)
        fees    = of + cf + ov
        net     = (exit_ - entry) * UNITS_PER_TRADE - fees
        trades.append({"entry_date": dates[i].strftime("%Y-%m-%d"),
                       "exit_date":  dates[i+hold].strftime("%Y-%m-%d"),
                       "score": int(s), "entry": entry, "exit": exit_,
                       "fees_eur": fees, "net_pl_eur": net,
                       "ret_pct": net / notional * 100.0})
        last_exit = i + hold
    return trades

def summarize(trades):
    if not trades:
        return {"n":0, "win_rate":np.nan, "avg":np.nan, "median":np.nan,
                "total":0.0, "best":np.nan, "worst":np.nan}
    r = np.array([t["ret_pct"] for t in trades])
    return {"n": len(trades),
            "win_rate": float((r > 0).mean() * 100),
            "avg": float(r.mean()), "median": float(np.median(r)),
            "total": float(sum(t["net_pl_eur"] for t in trades)),
            "best": float(r.max()), "worst": float(r.min())}

# =================== DIVERSIFIED PICKS ===================
def diversified_picks(rows, returns_df, max_corr=CORR_MAX, n=5):
    picks = []
    for r in rows:
        key = (r["ticker"], r["asset_class"])
        if key not in returns_df.columns: continue
        if not picks: picks.append(r); continue
        try:
            worst = max(abs(returns_df[key].corr(returns_df[(p["ticker"], p["asset_class"])]))
                        for p in picks)
        except Exception:
            continue
        if pd.isna(worst) or worst < max_corr:
            picks.append(r)
        if len(picks) >= n: break
    return picks

# =================== VERDICT ===================
def verdict(train_avg, test_n, test_avg):
    if test_n < MIN_TEST_TRADES:
        return "INSUFFICIENT"
    if test_avg is None or np.isnan(test_avg):
        return "INSUFFICIENT"
    if test_avg <= 0:
        return "OVERFIT"
    if train_avg is None or train_avg <= 0:
        return "?"
    ratio = test_avg / train_avg
    if ratio >= 0.5:
        return "ROBUST"
    return "WEAK"

# =================== MAIN ===================
def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print(f"Loading {len(ASSETS)} instruments ({LOOKBACK} of history)...")

    enriched, scores_map, returns = {}, {}, {}
    scan_rows, all_trades, bt_summary = [], [], []

    for ticker, name, cls, cur in ASSETS:
        df = load_and_enrich(ticker)
        if df is None: continue
        enriched[(ticker, cls)] = (df, cur, name)
        returns[(ticker, cls)] = df["ret1"].tail(CORR_LOOKBACK_DAYS)
        scores = precompute_scores(df)
        scores_map[(ticker, cls)] = scores

        row = current_analysis(df, ticker, name, cls, cur)
        if row is not None: scan_rows.append(project_pnl(row))

        tr = simulate(df, scores, cls, cur, SCORE_THRESHOLD, HOLD_TRADING_DAYS)
        for t in tr: t.update({"ticker":ticker,"asset_class":cls})
        all_trades.extend(tr)
        s = summarize(tr); s.update({"ticker":ticker,"name":name,"asset_class":cls})
        bt_summary.append(s)

    scan_rows.sort(key=lambda x: x["predicted_net_eur"], reverse=True)

    # ============== CURRENT SCAN ==============
    print("\n" + "="*135)
    print(f" Revolut Bullish Scanner v5 — {datetime.now():%Y-%m-%d %H:%M}")
    print("="*135)
    print(f"{'#':<3}{'Instrument':<26}{'Class':<14}{'Price':>10}{'Score':>6}"
          f"{'BE%':>7}{'Pred%':>7}{'Fees€':>8}{'Pred€':>9}{'Bull€':>9}{'Bear€':>9}")
    print("-"*135)
    for i, r in enumerate(scan_rows[:TOP_N], 1):
        print(f"{i:<3}{r['name'][:25]:<26}{r['asset_class']:<14}"
              f"{r['price']:>10.2f}{r['score']:>6}"
              f"{r['breakeven_pct']:>7.2f}{r['predicted_move_pct']:>7.2f}"
              f"{r['total_fees']:>8.2f}{r['predicted_net_eur']:>9.2f}"
              f"{r['bull_case_net_eur']:>9.2f}{r['bear_case_net_eur']:>9.2f}")

    # ============== DIVERSIFIED PICKS ==============
    returns_df = pd.DataFrame(returns)
    picks = diversified_picks(scan_rows, returns_df, n=5)
    print("\n" + "="*135)
    print(f" DIVERSIFIED PICKS — top 5 with pairwise |correlation| < {CORR_MAX}")
    print("="*135)
    print(f"{'#':<3}{'Instrument':<26}{'Class':<14}{'Score':>6}{'Pred%':>7}{'Pred€':>9}")
    for i, r in enumerate(picks, 1):
        print(f"{i:<3}{r['name'][:25]:<26}{r['asset_class']:<14}"
              f"{r['score']:>6}{r['predicted_move_pct']:>7.2f}{r['predicted_net_eur']:>9.2f}")

    # ============== BASELINE BACKTEST ==============
    all_rets = [t["ret_pct"] for t in all_trades]
    print("\n" + "="*135)
    print(f" BASELINE BACKTEST — score ≥ {SCORE_THRESHOLD}, hold {HOLD_TRADING_DAYS}d, "
          f"{LOOKBACK} history")
    print("="*135)
    if all_trades:
        wins = sum(1 for r in all_rets if r > 0)
        print(f"  Trades: {len(all_trades)}   Win rate: {wins/len(all_rets)*100:5.2f}%   "
              f"Avg: {np.mean(all_rets):+5.3f}%   Median: {np.median(all_rets):+5.3f}%   "
              f"Σ Net: {sum(t['net_pl_eur'] for t in all_trades):+,.2f} EUR")

    # ============== PARAMETER SWEEP (TRAIN + TEST + FULL) ==============
    # Compute split point per ticker (since data lengths may vary)
    print("\n" + "="*135)
    print(" PARAMETER SWEEP — split into TRAIN (first 70%) and TEST (last 30%)")
    print("="*135)

    sweep_rows = []
    for (tk, cls), (df, cur, name) in enriched.items():
        scores = scores_map[(tk, cls)]
        n = len(df)
        warmup = 200
        split = warmup + int((n - warmup) * TRAIN_FRACTION)
        for thr in SWEEP_THRESHOLDS:
            for hold in SWEEP_HOLDS:
                train = simulate(df, scores, cls, cur, thr, hold,
                                 start_idx=warmup, end_idx=split)
                test  = simulate(df, scores, cls, cur, thr, hold,
                                 start_idx=split, end_idx=n)
                full  = simulate(df, scores, cls, cur, thr, hold,
                                 start_idx=warmup, end_idx=n)
                ts, vs, fs = summarize(train), summarize(test), summarize(full)
                sweep_rows.append({
                    "ticker": tk, "name": name, "asset_class": cls,
                    "threshold": thr, "hold_days": hold,
                    # train
                    "train_n": ts["n"], "train_win": ts["win_rate"],
                    "train_avg": ts["avg"], "train_total": ts["total"],
                    # test
                    "test_n": vs["n"], "test_win": vs["win_rate"],
                    "test_avg": vs["avg"], "test_total": vs["total"],
                    # full period (for reference)
                    "full_n": fs["n"], "full_win": fs["win_rate"],
                    "full_avg": fs["avg"], "full_total": fs["total"],
                })
    sweep_df = pd.DataFrame(sweep_rows)

    # ============== OOS VALIDATION — per asset class ==============
    print("\n  Find best (threshold, hold) on TRAIN data → test those exact params on TEST data")
    print("  " + "-"*120)
    print(f"  {'Asset class':<16}{'Thr':>4}{'Hold':>5}  |"
          f"{'Tr N':>5}{'Tr Win%':>9}{'Tr Avg%':>9}  |"
          f"{'Te N':>5}{'Te Win%':>9}{'Te Avg%':>9}  {'Verdict':<14}")
    print("  " + "-"*120)

    oos_results = []
    for cls in ["stock","etf","equity_cfd","index_cfd","commodity_cfd","forex_cfd"]:
        sub = sweep_df[sweep_df["asset_class"] == cls]
        if sub.empty: continue

        # Aggregate TRAIN stats across all tickers in the class for each (thr,hold)
        # Best = highest trade-weighted train avg, with min trades requirement.
        agg = []
        for thr in SWEEP_THRESHOLDS:
            for hold in SWEEP_HOLDS:
                rs = sub[(sub.threshold==thr) & (sub.hold_days==hold)]
                tn = rs["train_n"].sum()
                if tn < MIN_TRADES_FOR_REPORT: continue
                w = rs["train_n"].values.astype(float)
                if w.sum() == 0: continue
                tw  = float(np.nansum(rs["train_win"].values * w) / w.sum())
                ta  = float(np.nansum(rs["train_avg"].values * w) / w.sum())
                vn  = int(rs["test_n"].sum())
                ws  = rs["test_n"].values.astype(float)
                if ws.sum() > 0:
                    vw = float(np.nansum(rs["test_win"].values * ws) / ws.sum())
                    va = float(np.nansum(rs["test_avg"].values * ws) / ws.sum())
                else:
                    vw, va = np.nan, np.nan
                agg.append({"thr":thr,"hold":hold,"tn":int(tn),"tw":tw,"ta":ta,
                            "vn":vn,"vw":vw,"va":va})
        if not agg: continue
        best = max(agg, key=lambda a: a["ta"])
        v = verdict(best["ta"], best["vn"], best["va"])
        oos_results.append({"asset_class":cls, **best, "verdict":v})

        vw_str = f"{best['vw']:>9.1f}" if not np.isnan(best['vw']) else f"{'—':>9}"
        va_str = f"{best['va']:>+9.2f}" if not np.isnan(best['va']) else f"{'—':>9}"
        print(f"  {cls:<16}{best['thr']:>4}{best['hold']:>5}  |"
              f"{best['tn']:>5}{best['tw']:>9.1f}{best['ta']:>+9.2f}  |"
              f"{best['vn']:>5}{vw_str}{va_str}  {v:<14}")

    # ============== TOP ROBUST STRATEGIES — both train & test positive ==============
    valid = sweep_df[(sweep_df["train_n"] >= MIN_TRADES_FOR_REPORT) &
                     (sweep_df["test_n"]  >= MIN_TEST_TRADES) &
                     (sweep_df["train_avg"] > 0) &
                     (sweep_df["test_avg"]  > 0)].copy()
    if not valid.empty:
        valid = valid.sort_values("test_avg", ascending=False).head(15)
        print("\n  Top 15 ROBUST (ticker, thr, hold) — profitable on BOTH train and test")
        print("  " + "-"*120)
        print(f"  {'Ticker':<10}{'Class':<14}{'Thr':>4}{'Hold':>5}  |"
              f"{'Tr N':>5}{'Tr Avg%':>9}  |"
              f"{'Te N':>5}{'Te Win%':>9}{'Te Avg%':>9}")
        print("  " + "-"*120)
        for _, r in valid.iterrows():
            print(f"  {r['ticker']:<10}{r['asset_class']:<14}"
                  f"{int(r['threshold']):>4}{int(r['hold_days']):>5}  |"
                  f"{int(r['train_n']):>5}{r['train_avg']:>+9.2f}  |"
                  f"{int(r['test_n']):>5}{r['test_win']:>9.1f}{r['test_avg']:>+9.2f}")
    else:
        print("\n  No (ticker, thr, hold) combination was profitable on BOTH train and test")
        print("  with at least the minimum trade counts. That is itself a strong signal —")
        print("  no robust edge was found across these instruments and parameters.")

    # ============== CSV EXPORTS ==============
    pd.DataFrame(scan_rows).to_csv(os.path.join(OUTDIR,"scan_results.csv"), index=False)
    pd.DataFrame(all_trades).to_csv(os.path.join(OUTDIR,"backtest_trades.csv"), index=False)
    pd.DataFrame(bt_summary).to_csv(os.path.join(OUTDIR,"backtest_summary.csv"), index=False)
    sweep_df.to_csv(os.path.join(OUTDIR,"sweep_results.csv"), index=False)
    pd.DataFrame(oos_results).to_csv(os.path.join(OUTDIR,"oos_verdict.csv"), index=False)

    print("\n" + "="*135)
    print(" CSV exports:")
    print("   • scan_results.csv     — current ranked scan")
    print("   • backtest_trades.csv  — every simulated trade at baseline params")
    print("   • backtest_summary.csv — per-ticker baseline stats")
    print("   • sweep_results.csv    — full sweep with train / test / full columns")
    print("   • oos_verdict.csv      — best-per-asset-class with OOS verdict")
    print("\n" + "="*135)
    print(" VERDICT LEGEND")
    print(" ──────────────")
    print("   ROBUST       Test avg/trade still > 0 AND ≥ 50% of train avg → worth paper-testing")
    print("   WEAK         Test still profitable but much weaker than train → marginal")
    print("   OVERFIT      Test was unprofitable → the train win was likely chance/regime-luck")
    print("   INSUFFICIENT Too few test trades to judge → extend LOOKBACK or paper-trade")
    print()
    print(" Even ROBUST is not a green light. It only means the strategy survived ONE test on")
    print(" historical data. Markets evolve. Always paper-trade for 6–8 weeks before going live.")
    print(" CFDs are leveraged products; most retail CFD traders lose money. NOT financial advice.")

if __name__ == "__main__":
    main()
