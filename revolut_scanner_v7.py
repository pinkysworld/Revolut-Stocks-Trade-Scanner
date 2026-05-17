"""
Revolut Germany — Bullish Scanner v7
=====================================
Adds to v6:
  • CONCRETE TRADING RECOMMENDATIONS — printed at the bottom, ranked by
    expected 2-week net ROI. Recommendations are ONLY generated for:
        - Asset classes that passed out-of-sample validation (verdict=ROBUST)
        - Instruments with a current bullish signal score ≥ MIN_SCORE_FOR_REC
        - Trades where the predicted net P/L (after fees) is positive
    Each recommendation includes entry price, expected ROI %, suggested
    take-profit and stop-loss prices, upside/downside scenarios, and a
    star rating. If no asset class is ROBUST today, no recommendation
    is made — sometimes the right move is not to trade.

Everything from v6 is retained (full screen output, heatmaps, scan, sweep,
OOS validation, CSV exports).

Tip: redirect to a file or pipe through a pager:
    python revolut_scanner_v7.py > report.txt
    python revolut_scanner_v7.py | less -R

Install:  pip install yfinance pandas numpy
Run:      python revolut_scanner_v7.py
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
LOOKBACK           = "3y"
UNITS_PER_TRADE    = 1

SCORE_THRESHOLD    = 5
CORR_MAX           = 0.75
CORR_LOOKBACK_DAYS = 60
OUTDIR             = "."
INSTRUMENTS_CSV    = os.path.join(os.path.dirname(__file__), "revolut_instruments.csv")

# --- Parameter sweep ---
SWEEP_THRESHOLDS      = [3, 4, 5, 6, 7]
SWEEP_HOLDS           = [3, 5, 10, 15, 20]
MIN_TRADES_FOR_REPORT = 10

# --- Out-of-sample ---
TRAIN_FRACTION    = 0.70
MIN_TEST_TRADES   = 8

# --- Screen output ---
N_BEST_TRADES  = 15     # show top N winning historical trades
N_WORST_TRADES = 10     # show bottom N losing historical trades

# --- Concrete trading recommendations ---
N_RECOMMENDATIONS    = 5    # how many recommendations to print
N_STOCK_RECOMMENDATIONS = 5 # separate cash-stock ideas, not CFDs
N_DAYTRADE_RECOMMENDATIONS = 5
MIN_SCORE_FOR_REC    = 4    # current scan score must be at least this
DAYTRADE_SCORE_THRESHOLD = 5
MIN_STOCK_BT_TRADES  = 10   # minimum historical stock signals before showing a stock idea
DAYTRADE_HOLDS       = [1, 2, 3]
MIN_DAYTRADE_TRADES  = 20
MIN_DAYTRADE_TEST_TRADES = 6
ALLOW_WEAK_CLASSES   = False # if True, also accept WEAK verdict, not just ROBUST
STOP_LOSS_VOL_FRAC   = 0.5   # stop-loss = entry - this × 2-week vol
DAYTRADE_STOP_LOSS_VOL_FRAC = 0.6
TAKE_PROFIT_AT_PRED  = True  # take-profit at predicted move (vs at +1 vol)

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
    ("^FTSE","FTSE 100 CFD","index_cfd","USD"),
    ("^N225","Nikkei 225 CFD","index_cfd","USD"),
    ("GC=F","Gold CFD","commodity_cfd","USD"),
    ("SI=F","Silver CFD","commodity_cfd","USD"),
    ("CL=F","WTI Crude Oil CFD","commodity_cfd","USD"),
    ("NG=F","Natural Gas CFD","commodity_cfd","USD"),
    ("HG=F","Copper CFD","commodity_cfd","USD"),
]

ASSET_CLASSES = ["stock", "etf", "equity_cfd", "index_cfd",
                 "commodity_cfd"]

def load_assets():
    if not os.path.exists(INSTRUMENTS_CSV):
        return ASSETS

    df = pd.read_csv(INSTRUMENTS_CSV)
    required = ["ticker", "name", "asset_class", "currency"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{INSTRUMENTS_CSV} is missing columns: {', '.join(missing)}")

    if "enabled" in df.columns:
        enabled = df["enabled"].fillna(True).astype(str).str.lower()
        df = df[enabled.isin(["true", "1", "yes", "y"])]

    assets = []
    seen = set()
    for row in df.itertuples(index=False):
        ticker = str(getattr(row, "ticker")).strip()
        name = str(getattr(row, "name")).strip()
        asset_class = str(getattr(row, "asset_class")).strip()
        currency = str(getattr(row, "currency")).strip().upper()
        key = (ticker, asset_class, name)
        if not ticker or not name or key in seen:
            continue
        seen.add(key)
        assets.append((ticker, name, asset_class, currency))

    stock_tickers = {ticker for ticker, _, asset_class, _ in assets
                     if asset_class == "stock"}
    equity_cfd_tickers = {ticker for ticker, _, asset_class, _ in assets
                          if asset_class == "equity_cfd"}
    for ticker, name, asset_class, currency in list(assets):
        if asset_class == "equity_cfd" and ticker not in stock_tickers:
            stock_name = name.removesuffix(" CFD").strip()
            assets.append((ticker, stock_name, "stock", currency))
            stock_tickers.add(ticker)
        elif asset_class == "stock" and ticker not in equity_cfd_tickers:
            assets.append((ticker, f"{name} CFD", "equity_cfd", currency))
            equity_cfd_tickers.add(ticker)

    return assets

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

def rolling_position(close, low, high):
    rng = (high - low).replace(0, np.nan)
    return ((close - low) / rng).clip(0, 1)

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
CRIT_COLS = ["Close","Open","High","Low","SMA20","SMA50","SMA200",
             "EMA8","EMA21","RSI","MACD","MACDsig","MACDhist",
             "ATR","ATRpct","BBL","BBH","ret3","ret5","ret20",
             "SMA20slope","HH20","RangePos","VolRatio"]

DAYTRADE_CRIT_COLS = ["Close","Open","High","Low","EMA8","EMA21","RSI",
                      "RSI2","MACDhist","ATR","ATRpct","ret1","ret2",
                      "ret3","RangePos","VolRatio"]

def compute_score(last, prev):
    sig, score = [], 0
    if last["Close"] > last["SMA20"]:                    score += 1; sig.append("above_SMA20")
    if last["Close"] > last["SMA50"]:                    score += 1; sig.append("above_SMA50")
    if last["Close"] > last["SMA200"]:                   score += 1; sig.append("above_SMA200")
    if last["SMA50"]  > last["SMA200"]:                  score += 1; sig.append("sma50>sma200")
    if last["EMA8"] > last["EMA21"] and last["Close"] > last["EMA8"]:
        score += 1; sig.append("short_trend_aligned")
    if last["SMA20slope"] > 0:                            score += 1; sig.append("sma20_rising")
    if last["Close"] > last["HH20"]:                      score += 2; sig.append("20d_breakout")
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
    if prev["Close"] <= prev["BBH"] and last["Close"] > last["BBH"]:
        score += 1; sig.append("bb_upper_breakout")
    if (prev["Close"] < prev["Open"] and last["Close"] > last["Open"]
            and last["Open"]  < prev["Close"] and last["Close"] > prev["Open"]):
        score += 1; sig.append("bullish_engulfing")
    if last["RangePos"] >= 0.70:                          score += 1; sig.append("close_near_high")
    if last["VolRatio"] >= 1.30:                          score += 1; sig.append("volume_confirmation")
    if 0.005 < last["ret5"] < 0.06:                      score += 1; sig.append("healthy_5d_momentum")
    if last["ret20"] < -0.12:                             score -= 1; sig.append("weak_20d_trend")
    if last["ATRpct"] > 0.08:                             score -= 1; sig.append("very_high_volatility")
    return score, sig

def precompute_scores(df):
    out = np.full(len(df), np.nan)
    rows = df[CRIT_COLS].to_dict("records")
    for i in range(1, len(df)):
        last, prev = rows[i], rows[i-1]
        if any(pd.isna(last[c]) or pd.isna(prev[c]) for c in CRIT_COLS):
            continue
        s, _ = compute_score(last, prev)
        out[i] = s
    return pd.Series(out, index=df.index)

def compute_daytrade_score(last, prev):
    sig, score = [], 0
    if last["Close"] > last["EMA8"] > last["EMA21"]:      score += 2; sig.append("ema8_trend")
    if prev["EMA8"] <= prev["EMA21"] and last["EMA8"] > last["EMA21"]:
        score += 2; sig.append("fresh_ema_cross")
    if last["MACDhist"] > 0 and last["MACDhist"] > prev["MACDhist"]:
        score += 1; sig.append("macd_hist_rising")
    if 40 <= last["RSI"] <= 70:                           score += 1; sig.append("rsi_daytrade_zone")
    if last["RSI2"] < 15 and last["Close"] > prev["Close"]:
        score += 2; sig.append("short_oversold_bounce")
    if 0.002 < last["ret1"] < 0.04:                       score += 1; sig.append("positive_1d_momentum")
    if 0.004 < last["ret3"] < 0.08:                       score += 1; sig.append("positive_3d_momentum")
    if last["RangePos"] >= 0.65:                          score += 1; sig.append("close_near_day_high")
    if last["VolRatio"] >= 1.20:                          score += 1; sig.append("volume_expansion")
    if last["ATRpct"] < 0.015:                            score -= 1; sig.append("too_quiet")
    if last["ATRpct"] > 0.09:                             score -= 1; sig.append("too_volatile")
    if last["ret1"] > 0.06 or last["RSI"] > 82:           score -= 2; sig.append("overextended")
    return score, sig

def precompute_daytrade_scores(df):
    out = np.full(len(df), np.nan)
    rows = df[DAYTRADE_CRIT_COLS].to_dict("records")
    for i in range(1, len(df)):
        last, prev = rows[i], rows[i-1]
        if any(pd.isna(last[c]) or pd.isna(prev[c]) for c in DAYTRADE_CRIT_COLS):
            continue
        s, _ = compute_daytrade_score(last, prev)
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
    df["EMA8"], df["EMA21"] = ema(c,8), ema(c,21)
    df["SMA20"], df["SMA50"], df["SMA200"] = sma(c,20), sma(c,50), sma(c,200)
    df["RSI"] = rsi(c)
    df["RSI2"] = rsi(c, 2)
    m, ms, mh = macd(c)
    df["MACD"], df["MACDsig"], df["MACDhist"] = m, ms, mh
    df["ATR"] = atr(df)
    df["ATRpct"] = df["ATR"] / c
    bbl, bbm, bbh = bollinger(c)
    df["BBL"], df["BBM"], df["BBH"] = bbl, bbm, bbh
    df["ret5"] = c.pct_change(5)
    df["ret1"] = c.pct_change(1)
    df["ret2"] = c.pct_change(2)
    df["ret3"] = c.pct_change(3)
    df["ret20"] = c.pct_change(20)
    df["SMA20slope"] = df["SMA20"] / df["SMA20"].shift(5) - 1
    df["HH20"] = df["High"].shift(1).rolling(20).max()
    df["RangePos"] = rolling_position(c, df["Low"], df["High"])
    if "Volume" in df.columns:
        vol20 = df["Volume"].replace(0, np.nan).rolling(20).mean()
        df["VolRatio"] = (df["Volume"] / vol20).replace([np.inf, -np.inf], np.nan).fillna(1.0)
    else:
        df["VolRatio"] = 1.0
    return df

# =================== CURRENT SCAN ===================
def current_analysis(df, ticker, name, asset_class, currency):
    last, prev = df.iloc[-1], df.iloc[-2]
    if last[CRIT_COLS].isna().any() or prev[CRIT_COLS].isna().any():
        return None
    score, sig = compute_score(last, prev)
    day_score, day_sig = compute_daytrade_score(last, prev)
    atr_pct = float(last["ATR"] / last["Close"])
    vol_2w  = atr_pct * np.sqrt(HOLD_TRADING_DAYS) * 100.0
    confidence = max(0, min(score, 10)) / 10.0
    pred_move  = confidence * vol_2w * 0.7
    return {"ticker": ticker, "name": name, "asset_class": asset_class,
            "currency": currency, "price": float(last["Close"]),
            "score": int(score), "rsi": float(last["RSI"]),
            "daytrade_score": int(day_score), "atr_pct": atr_pct * 100.0,
            "range_pos": float(last["RangePos"]), "vol_ratio": float(last["VolRatio"]),
            "vol_2w_pct": vol_2w, "predicted_move_pct": pred_move,
            "signals": ", ".join(sig), "daytrade_signals": ", ".join(day_sig)}

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

# =================== SIMULATION ===================
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
    if test_n < MIN_TEST_TRADES or test_avg is None or np.isnan(test_avg):
        return "INSUFFICIENT"
    if test_avg <= 0: return "OVERFIT"
    if train_avg is None or train_avg <= 0: return "?"
    return "ROBUST" if (test_avg / train_avg) >= 0.5 else "WEAK"

# =================== HEATMAP PRINTER ===================
def print_heatmap(sweep_df, asset_class, metric_col, label):
    """Print a 5×5 grid of (threshold × hold) for the given metric.
    Cells with insufficient trades show '—'."""
    sub = sweep_df[sweep_df["asset_class"] == asset_class]
    if sub.empty:
        print(f"  No data for {asset_class}"); return
    n_col = "train_n" if "train" in metric_col else ("test_n" if "test" in metric_col else "full_n")
    min_trades = MIN_TEST_TRADES if "test" in metric_col else MIN_TRADES_FOR_REPORT

    print(f"\n  {asset_class:<14} — {label} (aggregated across all tickers in class)")
    header = "    " + " "*7 + "".join(f"{f'h={h}':>9}" for h in SWEEP_HOLDS)
    print(header)
    for thr in SWEEP_THRESHOLDS:
        row = f"    thr={thr:<3}"
        for hold in SWEEP_HOLDS:
            rs = sub[(sub.threshold==thr) & (sub.hold_days==hold)]
            n_tot = int(rs[n_col].sum())
            if n_tot < min_trades:
                row += f"{'—':>9}"
            else:
                w = rs[n_col].values.astype(float)
                val = float(np.nansum(rs[metric_col].values * w) / w.sum())
                row += f"{val:>+9.2f}"
        print(row)

# =================== TRADING RECOMMENDATIONS ===================
def build_recommendations(scan_rows, oos_results, oos_lookup):
    """Filter scan candidates to those in OOS-validated asset classes with
    a strong current signal, then rank by expected ROI %."""
    robust = {r["asset_class"] for r in oos_results if r.get("verdict") == "ROBUST"}
    weak   = {r["asset_class"] for r in oos_results if r.get("verdict") == "WEAK"}
    accept = robust | (weak if ALLOW_WEAK_CLASSES else set())

    recs = []
    for r in scan_rows:
        if r["asset_class"] not in accept: continue
        if r["score"] < MIN_SCORE_FOR_REC: continue
        if r["predicted_net_eur"] <= 0:    continue
        if r["notional"] <= 0:             continue

        roi_pct  = r["predicted_net_eur"] / r["notional"] * 100
        # Risk-management levels
        sl_pct = -r["vol_2w_pct"] * STOP_LOSS_VOL_FRAC
        tp_pct = r["predicted_move_pct"] if TAKE_PROFIT_AT_PRED else r["vol_2w_pct"]
        sl_price = r["price"] * (1 + sl_pct / 100)
        tp_price = r["price"] * (1 + tp_pct / 100)
        risk_per_unit   = r["price"] - sl_price
        reward_per_unit = tp_price - r["price"]
        rr_ratio = reward_per_unit / risk_per_unit if risk_per_unit > 0 else np.nan

        # Pull OOS-validated params for this asset class (best hold period etc.)
        oos = oos_lookup.get(r["asset_class"], {})
        recs.append({
            **r,
            "expected_roi_pct": roi_pct,
            "stop_loss_price":  sl_price,
            "take_profit_price": tp_price,
            "risk_reward":      rr_ratio,
            "oos_best_thr":     oos.get("thr"),
            "oos_best_hold":    oos.get("hold"),
            "oos_test_winrate": oos.get("vw"),
            "oos_test_avg":     oos.get("va"),
        })
    recs.sort(key=lambda x: x["expected_roi_pct"], reverse=True)
    return recs[:N_RECOMMENDATIONS], robust, weak

def add_trade_levels(r):
    roi_pct  = r["predicted_net_eur"] / r["notional"] * 100
    sl_pct = -r["vol_2w_pct"] * STOP_LOSS_VOL_FRAC
    tp_pct = r["predicted_move_pct"] if TAKE_PROFIT_AT_PRED else r["vol_2w_pct"]
    sl_price = r["price"] * (1 + sl_pct / 100)
    tp_price = r["price"] * (1 + tp_pct / 100)
    risk_per_unit = r["price"] - sl_price
    reward_per_unit = tp_price - r["price"]
    return {
        **r,
        "expected_roi_pct": roi_pct,
        "stop_loss_price": sl_price,
        "take_profit_price": tp_price,
        "risk_reward": reward_per_unit / risk_per_unit if risk_per_unit > 0 else np.nan,
    }

def build_stock_recommendations(scan_rows, bt_summary):
    bt_lookup = {
        (s["ticker"], s["asset_class"]): s
        for s in bt_summary
        if s["asset_class"] == "stock"
    }

    recs = []
    for r in scan_rows:
        if r["asset_class"] != "stock":       continue
        if r["score"] < MIN_SCORE_FOR_REC:    continue
        if r["predicted_net_eur"] <= 0:       continue
        if r["notional"] <= 0:                continue

        bt = bt_lookup.get((r["ticker"], r["asset_class"]), {})
        if bt.get("n", 0) < MIN_STOCK_BT_TRADES: continue
        if bt.get("avg", -999) <= 0:              continue

        rec = add_trade_levels(r)
        rec.update({
            "bt_trades": bt.get("n"),
            "bt_win_rate": bt.get("win_rate"),
            "bt_avg": bt.get("avg"),
            "bt_total": bt.get("total"),
        })
        recs.append(rec)

    recs.sort(key=lambda x: (x["expected_roi_pct"], x["bt_avg"]), reverse=True)
    return recs[:N_STOCK_RECOMMENDATIONS]

def project_daytrade(row, hold_days):
    notional = row["price"] * UNITS_PER_TRADE
    open_fee, close_fee = fees_open_close(row["asset_class"], notional)
    cal_days = max(1, int(round(hold_days * 1.4)))
    overnight = overnight_cost(row["asset_class"], notional, row["currency"], cal_days)
    fees = open_fee + close_fee + overnight
    confidence = max(0, min(row["daytrade_score"], 10)) / 10.0
    scaled_vol = row["vol_2w_pct"] * np.sqrt(hold_days / HOLD_TRADING_DAYS)
    predicted_move_pct = confidence * scaled_vol * 0.7
    gross = notional * predicted_move_pct / 100.0
    sl_pct = -scaled_vol * DAYTRADE_STOP_LOSS_VOL_FRAC
    tp_pct = predicted_move_pct
    stop_loss_price = row["price"] * (1 + sl_pct / 100)
    take_profit_price = row["price"] * (1 + tp_pct / 100)
    risk_per_unit = row["price"] - stop_loss_price
    reward_per_unit = take_profit_price - row["price"]
    return {
        **row,
        "hold_days": hold_days,
        "daytrade_vol_pct": scaled_vol,
        "daytrade_predicted_move_pct": predicted_move_pct,
        "daytrade_calendar_days": cal_days,
        "daytrade_fees_eur": fees,
        "daytrade_breakeven_pct": fees / notional * 100 if notional > 0 else np.nan,
        "daytrade_predicted_net_eur": gross - fees,
        "daytrade_expected_roi_pct": (gross - fees) / notional * 100 if notional > 0 else np.nan,
        "daytrade_stop_loss_price": stop_loss_price,
        "daytrade_take_profit_price": take_profit_price,
        "daytrade_risk_reward": reward_per_unit / risk_per_unit if risk_per_unit > 0 else np.nan,
    }

def build_daytrade_recommendations(scan_rows, enriched, day_scores_map):
    scan_lookup = {
        (r["ticker"], r["asset_class"]): r
        for r in scan_rows
        if r["daytrade_score"] >= DAYTRADE_SCORE_THRESHOLD and r["notional"] > 0
    }
    recs = []
    for key, r in scan_lookup.items():
        df, currency, _name = enriched.get(key, (None, None, None))
        scores = day_scores_map.get(key)
        if df is None or scores is None:
            continue

        n = len(df)
        warmup = 200
        split = warmup + int((n - warmup) * TRAIN_FRACTION)
        best = None
        for hold in DAYTRADE_HOLDS:
            full = simulate(df, scores, r["asset_class"], currency, DAYTRADE_SCORE_THRESHOLD, hold, warmup, n)
            test = simulate(df, scores, r["asset_class"], currency, DAYTRADE_SCORE_THRESHOLD, hold, split, n)
            fs, ts = summarize(full), summarize(test)
            if fs["n"] < MIN_DAYTRADE_TRADES:
                continue
            if ts["n"] < MIN_DAYTRADE_TEST_TRADES:
                continue
            if fs["avg"] <= 0 or ts["avg"] <= 0:
                continue

            candidate = project_daytrade(r, hold)
            if candidate["daytrade_predicted_net_eur"] <= 0:
                continue
            candidate.update({
                "daytrade_bt_trades": fs["n"],
                "daytrade_bt_win_rate": fs["win_rate"],
                "daytrade_bt_avg": fs["avg"],
                "daytrade_bt_median": fs["median"],
                "daytrade_test_trades": ts["n"],
                "daytrade_test_win_rate": ts["win_rate"],
                "daytrade_test_avg": ts["avg"],
            })
            if best is None or candidate["daytrade_expected_roi_pct"] > best["daytrade_expected_roi_pct"]:
                best = candidate

        if best is not None:
            recs.append(best)

    recs.sort(key=lambda x: (x["daytrade_expected_roi_pct"], x["daytrade_test_avg"]), reverse=True)
    return recs[:N_DAYTRADE_RECOMMENDATIONS]

def print_recommendations(recs, robust, weak):
    BAR = "="*135
    print("\n" + BAR)
    print(" 🎯 CONCRETE TRADING RECOMMENDATIONS — ranked by expected 2-week net ROI")
    print(BAR)

    print(f"\n  Filter applied:")
    print(f"   1. Asset class must have OOS verdict = ROBUST"
          f"{' or WEAK' if ALLOW_WEAK_CLASSES else ''}")
    print(f"   2. Current scan score must be ≥ {MIN_SCORE_FOR_REC}")
    print(f"   3. Predicted net profit after fees must be > 0")
    print(f"\n  Robust asset classes today: "
          f"{', '.join(sorted(robust)) if robust else '(none — no asset class survived OOS)'}")
    if weak:
        print(f"  Weak classes (excluded): {', '.join(sorted(weak))}")

    if not robust and not (ALLOW_WEAK_CLASSES and weak):
        print()
        print("  ╔" + "═"*70 + "╗")
        print("  ║  NO RECOMMENDATIONS                                                  ║")
        print("  ║  No asset class passed out-of-sample validation in this run.         ║")
        print("  ║  The honest interpretation: there is no detectable edge to trade.    ║")
        print("  ║  Sit this period out, or extend LOOKBACK to gather more evidence.    ║")
        print("  ╚" + "═"*70 + "╝")
        return

    if not recs:
        print()
        print("  ╔" + "═"*70 + "╗")
        print("  ║  NO CANDIDATES TODAY                                                 ║")
        print("  ║  Asset classes are OOS-validated, but no instrument currently        ║")
        print("  ║  shows a bullish signal strong enough to meet the criteria.          ║")
        print("  ║  Re-run in 3–7 days when fresh signals may have formed.              ║")
        print("  ╚" + "═"*70 + "╝")
        return

    for i, r in enumerate(recs, 1):
        stars = "★" * min(5, max(1, r["score"] - 2)) + "☆" * max(0, 5 - min(5, max(1, r["score"] - 2)))
        print()
        print(f"  ── #{i}  {stars}   {r['name']}  ({r['ticker']} · {r['asset_class']}) " + "─"*30)
        print(f"     Direction:           LONG (BUY 1 piece)")
        print(f"     Entry price:         {r['price']:>10.4f} {r['currency']}")
        print(f"     Signal score:        {r['score']}     RSI: {r['rsi']:.1f}")
        sig_short = (r['signals'][:100] + '...') if len(r['signals']) > 100 else r['signals']
        print(f"     Active signals:      {sig_short}")
        print()
        print(f"     ─ 2-week projection (1 piece, after all fees) ─")
        print(f"     Predicted move:      {r['predicted_move_pct']:>+7.2f}%")
        print(f"     Total fees:          {r['total_fees']:>7.2f} EUR  "
              f"(open {r['open_fee']:.2f} + close {r['close_fee']:.2f} + overnight {r['overnight']:.2f})")
        print(f"     Break-even move:     {r['breakeven_pct']:>+7.2f}%")
        print(f"     ▶ EXPECTED NET ROI:  {r['expected_roi_pct']:>+7.2f}%   "
              f"→ {r['predicted_net_eur']:>+7.2f} EUR per piece")
        print(f"     Upside (+1 vol):     {r['bull_case_net_eur']:>+7.2f} EUR     "
              f"Downside (-1 vol): {r['bear_case_net_eur']:>+7.2f} EUR")
        print()
        print(f"     ─ Suggested risk-management orders ─")
        print(f"     Take-profit price:   {r['take_profit_price']:>10.4f} {r['currency']}  "
              f"({r['predicted_move_pct']:+.2f}% above entry)")
        print(f"     Stop-loss price:     {r['stop_loss_price']:>10.4f} {r['currency']}  "
              f"({-r['vol_2w_pct']*STOP_LOSS_VOL_FRAC:+.2f}% below entry)")
        if not np.isnan(r["risk_reward"]):
            print(f"     Reward:risk ratio:   {r['risk_reward']:.2f} : 1")
        if r.get("oos_best_hold"):
            print()
            print(f"     ─ OOS evidence for this asset class ─")
            print(f"     Best historical params: threshold={r['oos_best_thr']}, "
                  f"hold={r['oos_best_hold']} trading days")
            wr = r['oos_test_winrate']; ag = r['oos_test_avg']
            if not np.isnan(wr):
                print(f"     Test-set win rate:   {wr:.1f}%    "
                      f"Test-set avg return: {ag:+.2f}%")

    # ===== Final advice =====
    print()
    print("  " + "─"*120)
    print("  IMPORTANT NOTES BEFORE PLACING THESE ORDERS")
    print("  " + "─"*120)
    print("  • These are MODEL-BASED projections, not guarantees. Even the best OOS-validated")
    print("    setups won historically 55–65% of the time. Expect ~1 in 3 trades to lose money.")
    print("  • The OOS-optimal hold period was often longer than 2 weeks (15–20 trading days).")
    print("    If a trade is working at day 10, consider letting it run rather than forcing exit.")
    print("  • Position sizing: never put more than 5–10% of your account in any one trade.")
    print("    With CFDs, that means leverage-adjusted exposure, not just margin posted.")
    print("  • ENTER THE STOP-LOSS IN REVOLUT FIRST, before the entry order if possible.")
    print("    A stop-loss only works if you actually place it.")
    print("  • For CFDs, check the actual bid/ask spread in the app before entering — the")
    print("    spread is a hidden fee not modelled here.")
    print("  • If you would lose sleep over the downside scenario shown, the position is too big.")
    print("  • This is NOT financial advice. CFDs are leveraged; most retail CFD traders lose money.")
    print("    You are responsible for every euro you risk.")

def print_stock_recommendations(recs):
    BAR = "="*135
    print("\n" + BAR)
    print(" CASH STOCK RECOMMENDATIONS — regular stocks only, no CFDs")
    print(BAR)
    print(f"\n  Filter applied:")
    print(f"   1. Asset class must be stock")
    print(f"   2. Current scan score must be ≥ {MIN_SCORE_FOR_REC}")
    print(f"   3. Predicted net profit after stock fees must be > 0")
    print(f"   4. Individual stock backtest must have ≥ {MIN_STOCK_BT_TRADES} trades and positive avg return")

    if not recs:
        print()
        print("  No stock candidates passed the stock-specific filter today.")
        return

    for i, r in enumerate(recs, 1):
        stars = "*" * min(5, max(1, r["score"] - 2))
        print()
        print(f"  #{i} {stars:<5} {r['name']} ({r['ticker']})")
        print(f"     Entry price:         {r['price']:>10.4f} {r['currency']}")
        print(f"     Signal score:        {r['score']}     RSI: {r['rsi']:.1f}")
        sig_short = (r['signals'][:100] + '...') if len(r['signals']) > 100 else r['signals']
        print(f"     Active signals:      {sig_short}")
        print(f"     Predicted move:      {r['predicted_move_pct']:>+7.2f}%")
        print(f"     Fees:                {r['total_fees']:>7.2f} EUR")
        print(f"     Expected net ROI:    {r['expected_roi_pct']:>+7.2f}%   "
              f"-> {r['predicted_net_eur']:>+7.2f} EUR per share")
        print(f"     Take-profit price:   {r['take_profit_price']:>10.4f} {r['currency']}")
        print(f"     Stop-loss price:     {r['stop_loss_price']:>10.4f} {r['currency']}")
        if not np.isnan(r["risk_reward"]):
            print(f"     Reward:risk ratio:   {r['risk_reward']:.2f} : 1")
        print(f"     Stock backtest:      {int(r['bt_trades'])} trades, "
              f"{r['bt_win_rate']:.1f}% win rate, avg {r['bt_avg']:+.2f}%")

def print_daytrade_recommendations(recs):
    BAR = "="*135
    print("\n" + BAR)
    print(" DAY TRADING RECOMMENDATIONS — 1 to 3 trading days, fees included")
    print(BAR)
    print(f"\n  Filter applied:")
    print(f"   1. Current day-trade score must be ≥ {DAYTRADE_SCORE_THRESHOLD}")
    print(f"   2. Best hold must be one of {DAYTRADE_HOLDS} trading days")
    print(f"   3. Historical short-hold backtest must have ≥ {MIN_DAYTRADE_TRADES} trades and positive avg return")
    print(f"   4. Recent test split must have ≥ {MIN_DAYTRADE_TEST_TRADES} trades and positive avg return")
    print(f"   5. Projected net profit must stay positive after open/close/overnight fees")

    if not recs:
        print()
        print("  No 1-3 day candidates passed the fee-aware day-trading filter today.")
        return

    for i, r in enumerate(recs, 1):
        label = "share" if r["asset_class"] == "stock" else "piece"
        print()
        print(f"  #{i} {r['name']} ({r['ticker']} · {r['asset_class']})")
        print(f"     Suggested hold:      {int(r['hold_days'])} trading day(s)")
        print(f"     Entry price:         {r['price']:>10.4f} {r['currency']}")
        print(f"     Swing/day score:     {r['score']} / {r['daytrade_score']}     RSI: {r['rsi']:.1f}")
        sig_short = (r['daytrade_signals'][:100] + '...') if len(r['daytrade_signals']) > 100 else r['daytrade_signals']
        print(f"     Active signals:      {sig_short}")
        print(f"     Short-hold vol:      {r['daytrade_vol_pct']:>+7.2f}%")
        print(f"     Predicted move:      {r['daytrade_predicted_move_pct']:>+7.2f}%")
        print(f"     Fees:                {r['daytrade_fees_eur']:>7.2f} EUR")
        print(f"     Break-even move:     {r['daytrade_breakeven_pct']:>+7.2f}%")
        print(f"     Expected net ROI:    {r['daytrade_expected_roi_pct']:>+7.2f}%   "
              f"-> {r['daytrade_predicted_net_eur']:>+7.2f} EUR per {label}")
        print(f"     Take-profit price:   {r['daytrade_take_profit_price']:>10.4f} {r['currency']}")
        print(f"     Stop-loss price:     {r['daytrade_stop_loss_price']:>10.4f} {r['currency']}")
        if not np.isnan(r["daytrade_risk_reward"]):
            print(f"     Reward:risk ratio:   {r['daytrade_risk_reward']:.2f} : 1")
        print(f"     Full backtest:       {int(r['daytrade_bt_trades'])} trades, "
              f"{r['daytrade_bt_win_rate']:.1f}% win rate, avg {r['daytrade_bt_avg']:+.2f}%")
        print(f"     Recent test split:   {int(r['daytrade_test_trades'])} trades, "
              f"{r['daytrade_test_win_rate']:.1f}% win rate, avg {r['daytrade_test_avg']:+.2f}%")

# =================== MAIN ===================
def main():
    os.makedirs(OUTDIR, exist_ok=True)
    assets = load_assets()
    print(f"Loading {len(assets)} instruments ({LOOKBACK} of history)...")
    if os.path.exists(INSTRUMENTS_CSV):
        print(f"Instrument universe loaded from {INSTRUMENTS_CSV}")

    enriched, scores_map, day_scores_map, returns = {}, {}, {}, {}
    scan_rows, all_trades, bt_summary = [], [], []

    for ticker, name, cls, cur in assets:
        df = load_and_enrich(ticker)
        if df is None: continue
        enriched[(ticker, cls)] = (df, cur, name)
        returns[(ticker, cls)] = df["ret1"].tail(CORR_LOOKBACK_DAYS)
        scores = precompute_scores(df)
        scores_map[(ticker, cls)] = scores
        day_scores_map[(ticker, cls)] = precompute_daytrade_scores(df)

        row = current_analysis(df, ticker, name, cls, cur)
        if row is not None: scan_rows.append(project_pnl(row))

        tr = simulate(df, scores, cls, cur, SCORE_THRESHOLD, HOLD_TRADING_DAYS)
        for t in tr: t.update({"ticker":ticker,"asset_class":cls})
        all_trades.extend(tr)
        s = summarize(tr); s.update({"ticker":ticker,"name":name,"asset_class":cls})
        bt_summary.append(s)

    scan_rows.sort(key=lambda x: x["predicted_net_eur"], reverse=True)

    BAR = "="*135

    # ============== FULL CURRENT SCAN ==============
    print("\n" + BAR)
    print(f" Revolut Bullish Scanner v7 — {datetime.now():%Y-%m-%d %H:%M}")
    print(f" FULL CURRENT SCAN — all {len(scan_rows)} successfully analysed instruments")
    print(BAR)
    print(f"{'#':<3}{'Instrument':<26}{'Class':<14}{'Price':>10}{'Score':>6}{'DSc':>5}"
          f"{'RSI':>6}{'BE%':>7}{'Pred%':>7}{'Fees€':>8}{'Pred€':>9}{'Bull€':>9}{'Bear€':>9}")
    print("-"*135)
    for i, r in enumerate(scan_rows, 1):
        print(f"{i:<3}{r['name'][:25]:<26}{r['asset_class']:<14}"
              f"{r['price']:>10.2f}{r['score']:>6}{r['daytrade_score']:>5}{r['rsi']:>6.1f}"
              f"{r['breakeven_pct']:>7.2f}{r['predicted_move_pct']:>7.2f}"
              f"{r['total_fees']:>8.2f}{r['predicted_net_eur']:>9.2f}"
              f"{r['bull_case_net_eur']:>9.2f}{r['bear_case_net_eur']:>9.2f}")

    # ============== DIVERSIFIED PICKS ==============
    returns_df = pd.DataFrame(returns)
    picks = diversified_picks(scan_rows, returns_df, n=5)
    print("\n" + BAR)
    print(f" DIVERSIFIED PICKS — top 5 with pairwise |correlation| < {CORR_MAX}")
    print(BAR)
    print(f"{'#':<3}{'Instrument':<26}{'Class':<14}{'Score':>6}{'Pred%':>7}{'Pred€':>9}")
    for i, r in enumerate(picks, 1):
        print(f"{i:<3}{r['name'][:25]:<26}{r['asset_class']:<14}"
              f"{r['score']:>6}{r['predicted_move_pct']:>7.2f}{r['predicted_net_eur']:>9.2f}")

    # ============== BASELINE BACKTEST AGGREGATE ==============
    all_rets = [t["ret_pct"] for t in all_trades]
    print("\n" + BAR)
    print(f" BASELINE BACKTEST AGGREGATE — score ≥ {SCORE_THRESHOLD}, "
          f"hold {HOLD_TRADING_DAYS}d, {LOOKBACK} history")
    print(BAR)
    if all_trades:
        wins = sum(1 for r in all_rets if r > 0)
        print(f"  Trades: {len(all_trades)}   Win rate: {wins/len(all_rets)*100:5.2f}%   "
              f"Avg: {np.mean(all_rets):+5.3f}%   Median: {np.median(all_rets):+5.3f}%   "
              f"Σ Net: {sum(t['net_pl_eur'] for t in all_trades):+,.2f} EUR")

    # ============== FULL PER-TICKER BACKTEST ==============
    print("\n" + BAR)
    print(" FULL PER-TICKER BACKTEST — every instrument with ≥1 historical signal")
    print(BAR)
    bt_summary_sorted = sorted(bt_summary,
                               key=lambda s: (s["n"] >= 3, s["avg"] or -99),
                               reverse=True)
    print(f"  {'Ticker':<10}{'Name':<22}{'Class':<14}{'N':>4}"
          f"{'Win%':>7}{'Avg%':>8}{'Med%':>8}{'Best%':>8}{'Worst%':>8}{'Total€':>11}")
    print("  " + "-"*100)
    for s in bt_summary_sorted:
        if s["n"] == 0: continue
        print(f"  {s['ticker']:<10}{s['name'][:21]:<22}{s['asset_class']:<14}"
              f"{s['n']:>4}{s['win_rate']:>7.1f}{s['avg']:>+8.2f}"
              f"{s['median']:>+8.2f}{s['best']:>+8.2f}{s['worst']:>+8.2f}"
              f"{s['total']:>+11.2f}")

    # ============== BEST & WORST INDIVIDUAL TRADES ==============
    sorted_trades = sorted(all_trades, key=lambda t: t["ret_pct"], reverse=True)
    print("\n" + BAR)
    print(f" TOP {N_BEST_TRADES} HISTORICAL TRADES (baseline params)")
    print(BAR)
    print(f"  {'Ticker':<10}{'Class':<14}{'Entry date':<12}{'Exit date':<12}"
          f"{'Score':>6}{'Entry':>10}{'Exit':>10}{'Ret%':>9}{'NetEUR':>10}")
    print("  " + "-"*100)
    for t in sorted_trades[:N_BEST_TRADES]:
        print(f"  {t['ticker']:<10}{t['asset_class']:<14}"
              f"{t['entry_date']:<12}{t['exit_date']:<12}{t['score']:>6}"
              f"{t['entry']:>10.2f}{t['exit']:>10.2f}"
              f"{t['ret_pct']:>+9.2f}{t['net_pl_eur']:>+10.2f}")
    print(f"\n WORST {N_WORST_TRADES} HISTORICAL TRADES (baseline params)")
    print("  " + "-"*100)
    print(f"  {'Ticker':<10}{'Class':<14}{'Entry date':<12}{'Exit date':<12}"
          f"{'Score':>6}{'Entry':>10}{'Exit':>10}{'Ret%':>9}{'NetEUR':>10}")
    print("  " + "-"*100)
    for t in sorted_trades[-N_WORST_TRADES:][::-1]:
        print(f"  {t['ticker']:<10}{t['asset_class']:<14}"
              f"{t['entry_date']:<12}{t['exit_date']:<12}{t['score']:>6}"
              f"{t['entry']:>10.2f}{t['exit']:>10.2f}"
              f"{t['ret_pct']:>+9.2f}{t['net_pl_eur']:>+10.2f}")

    # ============== PARAMETER SWEEP (TRAIN + TEST + FULL) ==============
    print("\n" + BAR)
    print(" PARAMETER SWEEP — TRAIN (first 70%) / TEST (last 30%)")
    print(BAR)

    sweep_rows = []
    for (tk, cls), (df, cur, name) in enriched.items():
        scores = scores_map[(tk, cls)]
        n = len(df); warmup = 200
        split = warmup + int((n - warmup) * TRAIN_FRACTION)
        for thr in SWEEP_THRESHOLDS:
            for hold in SWEEP_HOLDS:
                train = simulate(df, scores, cls, cur, thr, hold, warmup, split)
                test  = simulate(df, scores, cls, cur, thr, hold, split, n)
                full  = simulate(df, scores, cls, cur, thr, hold, warmup, n)
                ts, vs, fs = summarize(train), summarize(test), summarize(full)
                sweep_rows.append({
                    "ticker": tk, "name": name, "asset_class": cls,
                    "threshold": thr, "hold_days": hold,
                    "train_n": ts["n"], "train_win": ts["win_rate"],
                    "train_avg": ts["avg"], "train_total": ts["total"],
                    "test_n": vs["n"], "test_win": vs["win_rate"],
                    "test_avg": vs["avg"], "test_total": vs["total"],
                    "full_n": fs["n"], "full_win": fs["win_rate"],
                    "full_avg": fs["avg"], "full_total": fs["total"],
                })
    sweep_df = pd.DataFrame(sweep_rows)

    # ============== OOS VERDICT PER ASSET CLASS ==============
    print("\n  OOS VERDICT — best train params and how they performed on unseen test data")
    print("  " + "-"*120)
    print(f"  {'Asset class':<16}{'Thr':>4}{'Hold':>5}  |"
          f"{'Tr N':>5}{'Tr Win%':>9}{'Tr Avg%':>9}  |"
          f"{'Te N':>5}{'Te Win%':>9}{'Te Avg%':>9}  {'Verdict':<14}")
    print("  " + "-"*120)
    oos_results = []
    for cls in ASSET_CLASSES:
        sub = sweep_df[sweep_df["asset_class"] == cls]
        if sub.empty: continue
        agg = []
        for thr in SWEEP_THRESHOLDS:
            for hold in SWEEP_HOLDS:
                rs = sub[(sub.threshold==thr) & (sub.hold_days==hold)]
                tn = int(rs["train_n"].sum())
                if tn < MIN_TRADES_FOR_REPORT: continue
                w = rs["train_n"].values.astype(float)
                if w.sum() == 0: continue
                tw = float(np.nansum(rs["train_win"].values * w) / w.sum())
                ta = float(np.nansum(rs["train_avg"].values * w) / w.sum())
                vn = int(rs["test_n"].sum())
                ws = rs["test_n"].values.astype(float)
                vw = float(np.nansum(rs["test_win"].values * ws) / ws.sum()) if ws.sum()>0 else np.nan
                va = float(np.nansum(rs["test_avg"].values * ws) / ws.sum()) if ws.sum()>0 else np.nan
                agg.append({"thr":thr,"hold":hold,"tn":tn,"tw":tw,"ta":ta,
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

    # ============== SWEEP HEATMAPS (per asset class) ==============
    print("\n" + BAR)
    print(" SWEEP HEATMAPS — avg %/trade for every (threshold × hold) combination")
    print(" Read these to spot PLATEAUS (multiple nearby cells profitable = real edge)")
    print(" versus PEAKS (only one cell profitable = noise/overfitting).")
    print(BAR)
    for cls in ASSET_CLASSES:
        print(f"\n  ── {cls.upper()} ──")
        print_heatmap(sweep_df, cls, "train_avg", "TRAIN avg %/trade")
        print_heatmap(sweep_df, cls, "test_avg",  "TEST  avg %/trade")

    # ============== ALL ROBUST STRATEGIES ==============
    valid = sweep_df[(sweep_df["train_n"] >= MIN_TRADES_FOR_REPORT) &
                     (sweep_df["test_n"]  >= MIN_TEST_TRADES) &
                     (sweep_df["train_avg"] > 0) &
                     (sweep_df["test_avg"]  > 0)].copy()
    print("\n" + BAR)
    if not valid.empty:
        valid = valid.sort_values("test_avg", ascending=False)
        print(f" ALL {len(valid)} ROBUST STRATEGIES — profitable on BOTH train AND test")
        print(BAR)
        print(f"  {'Ticker':<10}{'Class':<14}{'Thr':>4}{'Hold':>5}  |"
              f"{'Tr N':>5}{'Tr Win%':>9}{'Tr Avg%':>9}  |"
              f"{'Te N':>5}{'Te Win%':>9}{'Te Avg%':>9}")
        print("  " + "-"*100)
        for _, r in valid.iterrows():
            print(f"  {r['ticker']:<10}{r['asset_class']:<14}"
                  f"{int(r['threshold']):>4}{int(r['hold_days']):>5}  |"
                  f"{int(r['train_n']):>5}{r['train_win']:>9.1f}{r['train_avg']:>+9.2f}  |"
                  f"{int(r['test_n']):>5}{r['test_win']:>9.1f}{r['test_avg']:>+9.2f}")
    else:
        print(" NO ROBUST STRATEGIES — nothing was profitable on BOTH train and test.")
        print(BAR)

    # ============== CONCRETE TRADING RECOMMENDATIONS ==============
    oos_lookup = {r["asset_class"]: r for r in oos_results}
    recs, robust_set, weak_set = build_recommendations(scan_rows, oos_results, oos_lookup)
    print_recommendations(recs, robust_set, weak_set)
    stock_recs = build_stock_recommendations(scan_rows, bt_summary)
    print_stock_recommendations(stock_recs)
    daytrade_recs = build_daytrade_recommendations(scan_rows, enriched, day_scores_map)
    print_daytrade_recommendations(daytrade_recs)

    # ============== CSV EXPORTS ==============
    pd.DataFrame(scan_rows).to_csv(os.path.join(OUTDIR,"scan_results.csv"), index=False)
    pd.DataFrame(all_trades).to_csv(os.path.join(OUTDIR,"backtest_trades.csv"), index=False)
    pd.DataFrame(bt_summary).to_csv(os.path.join(OUTDIR,"backtest_summary.csv"), index=False)
    sweep_df.to_csv(os.path.join(OUTDIR,"sweep_results.csv"), index=False)
    pd.DataFrame(oos_results).to_csv(os.path.join(OUTDIR,"oos_verdict.csv"), index=False)
    if recs:
        # Strip non-serialisable fields and save
        rec_clean = [{k: v for k, v in r.items() if k != "signals"} | {"signals": r["signals"]}
                     for r in recs]
        pd.DataFrame(rec_clean).to_csv(os.path.join(OUTDIR,"recommendations.csv"), index=False)
    if stock_recs:
        stock_clean = [{k: v for k, v in r.items() if k != "signals"} | {"signals": r["signals"]}
                       for r in stock_recs]
        pd.DataFrame(stock_clean).to_csv(os.path.join(OUTDIR,"stock_recommendations.csv"), index=False)
    if daytrade_recs:
        daytrade_clean = [{k: v for k, v in r.items() if k != "signals"} | {"signals": r["signals"]}
                          for r in daytrade_recs]
        pd.DataFrame(daytrade_clean).to_csv(os.path.join(OUTDIR,"daytrade_recommendations.csv"), index=False)

    print("\n" + BAR)
    print(" CSVs ALSO written to disk:")
    print("   scan_results.csv   backtest_trades.csv   backtest_summary.csv")
    print("   sweep_results.csv  oos_verdict.csv      recommendations.csv")
    print("   stock_recommendations.csv")
    print("   daytrade_recommendations.csv")
    print("\n" + BAR)
    print(" VERDICT LEGEND")
    print("   ROBUST       Test avg > 0 AND ≥ 50% of train avg → worth paper-testing")
    print("   WEAK         Test still > 0 but much smaller than train → marginal")
    print("   OVERFIT      Test ≤ 0 → train win was chance/regime-luck")
    print("   INSUFFICIENT Too few test trades to judge")
    print()
    print(" Even ROBUST is not a green light. Markets change. Paper-trade for 6–8 weeks")
    print(" before any real money. CFDs are leveraged; most retail CFD traders lose money.")
    print(" NOT financial advice.")

if __name__ == "__main__":
    main()
