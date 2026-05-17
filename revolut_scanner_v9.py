"""
Revolut Germany — Bullish Scanner v9
=====================================
What's new versus v8
--------------------
Live entry prices
  • Every recommendation that prints to screen now refreshes the entry price
    via yfinance fast_info / 1-minute history just before rendering.  v8 used
    the previous daily bar's close, which on US tickers is up to ~22 h stale
    and made the suggested entry / SL / TP look 1-2% off the live market.
  • SL / TP / notional are recomputed at the live price using the same %
    targets, so the printed orders are immediately actionable.
  • Each rec shows both the live "now" price and the scan-time close so the
    drift is visible.

Crypto
  • New asset class `crypto` with the major coins available on Revolut.
  • Realistic Revolut crypto fees (CRYPTO_FEE_PCT per side; default 1.49%
    which matches the Premium tier — Standard users should bump this to
    1.99%).  No overnight cost for crypto (24/7 spot exposure).
  • Position sized to a euro target (CRYPTO_NOTIONAL_EUR, default €500)
    rather than "1 coin" — buying 1 BTC at a €60k price obviously isn't
    realistic for a daytrade.
  • Crypto goes through the same swing + daytrade pipelines, with its own
    print sections and CSV exports.  Same OOS validation, R:R hygiene,
    and verdict gates apply.

Everything else from v8 (rolling_position fix, ADX, Donchian, regime
filter, calibrated confidence, R:R floor, absolute test-avg floor for
ROBUST verdict, OOS-validated stock recs, stock daytrade with notional
sizing) is retained.

Install:  pip install yfinance pandas numpy
Run:      python revolut_scanner_v9.py
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
CRYPTO_FEE_PCT         = 0.0149   # 1.49% per side (Revolut Premium). Standard ≈ 1.99%.

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
TRAIN_FRACTION       = 0.70
MIN_TEST_TRADES      = 8
ROBUST_MIN_TEST_AVG  = 0.30

# --- Screen output ---
N_BEST_TRADES  = 15
N_WORST_TRADES = 10

# --- Recommendations (2-week swing, mixed asset classes) ---
N_RECOMMENDATIONS    = 5
MIN_SCORE_FOR_REC    = 4
ALLOW_WEAK_CLASSES   = False
STOP_LOSS_VOL_FRAC   = 0.5
MIN_RR_RATIO         = 1.2

# --- Cash stock swing recommendations ---
N_STOCK_RECOMMENDATIONS = 5
MIN_STOCK_BT_TRADES     = 10
STOCK_REQUIRE_OOS       = True

# --- Mixed daytrade ---
N_DAYTRADE_RECOMMENDATIONS = 5
DAYTRADE_SCORE_THRESHOLD   = 5
DAYTRADE_HOLDS             = [1, 2, 3]
MIN_DAYTRADE_TRADES        = 20
MIN_DAYTRADE_TEST_TRADES   = 6
DAYTRADE_STOP_LOSS_VOL_FRAC = 0.6

# --- Cash stock daytrade ---
N_STOCK_DAYTRADE_RECOMMENDATIONS = 5
STOCK_DAYTRADE_NOTIONAL_EUR      = 1000.0
STOCK_DAYTRADE_MIN_NOTIONAL      = 250.0
MIN_STOCK_DAYTRADE_TRADES        = 15
MIN_STOCK_DAYTRADE_TEST_TRADES   = 5

# --- Crypto ---
N_CRYPTO_RECOMMENDATIONS          = 5
N_CRYPTO_DAYTRADE_RECOMMENDATIONS = 5
CRYPTO_NOTIONAL_EUR               = 500.0   # target euro per crypto trade
CRYPTO_MIN_NOTIONAL               = 100.0
CRYPTO_HOLD_TRADING_DAYS          = 10
CRYPTO_DAYTRADE_HOLDS             = [1, 2, 3]
CRYPTO_DAYTRADE_SCORE_THRESHOLD   = 5
MIN_CRYPTO_BT_TRADES              = 12
MIN_CRYPTO_TEST_TRADES            = 5
MIN_CRYPTO_DT_TRADES              = 15
MIN_CRYPTO_DT_TEST_TRADES         = 5
# Crypto fees are large — require a wider expected move
CRYPTO_MIN_PREDICTED_MOVE_PCT     = 4.0     # swing: predicted move must clear ~2× round-trip fees
CRYPTO_DT_MIN_PREDICTED_MOVE_PCT  = 3.5     # daytrade

TAKE_PROFIT_AT_PRED = True

# --- Regime filter ---
USE_REGIME_FILTER  = True
REGIME_BENCHMARK   = "^GSPC"

# --- Live entry-price refresh ---
REFRESH_LIVE_PRICES   = True
LIVE_PRICE_MAX_DRIFT  = 0.15  # ignore live quote if it differs by > 15% from scan close (probably bad data)

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
    # --- Crypto (24/7, EUR fees on Revolut) ---
    ("BTC-USD","Bitcoin","crypto","USD"),     ("ETH-USD","Ethereum","crypto","USD"),
    ("SOL-USD","Solana","crypto","USD"),      ("XRP-USD","XRP","crypto","USD"),
    ("ADA-USD","Cardano","crypto","USD"),     ("DOGE-USD","Dogecoin","crypto","USD"),
    ("AVAX-USD","Avalanche","crypto","USD"),  ("DOT-USD","Polkadot","crypto","USD"),
    ("LINK-USD","Chainlink","crypto","USD"),  ("MATIC-USD","Polygon","crypto","USD"),
    ("BNB-USD","BNB","crypto","USD"),         ("LTC-USD","Litecoin","crypto","USD"),
    ("ATOM-USD","Cosmos","crypto","USD"),     ("BCH-USD","Bitcoin Cash","crypto","USD"),
]

ASSET_CLASSES = ["stock", "etf", "equity_cfd", "index_cfd", "commodity_cfd", "crypto"]

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

    # Append crypto from defaults if CSV doesn't list any
    if not any(a[2] == "crypto" for a in assets):
        for a in ASSETS:
            if a[2] == "crypto":
                assets.append(a)

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
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def bollinger(s, n=20, k=2):
    mid = sma(s, n); sd = s.rolling(n).std()
    return mid - k*sd, mid, mid + k*sd

def rolling_position(close, high, low, n=20):
    hh = high.rolling(n).max()
    ll = low.rolling(n).min()
    rng = (hh - ll).replace(0, np.nan)
    return ((close - ll) / rng).clip(0, 1)

def adx(df, n=14):
    h, l, c = df["High"], df["Low"], df["Close"]
    up_move   = h.diff()
    down_move = -l.diff()
    plus_dm   = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm  = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm   = pd.Series(plus_dm,  index=h.index)
    minus_dm  = pd.Series(minus_dm, index=h.index)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr_n   = tr.rolling(n).mean().replace(0, np.nan)
    plus_di  = 100 * (plus_dm.rolling(n).mean()  / atr_n)
    minus_di = 100 * (minus_dm.rolling(n).mean() / atr_n)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.rolling(n).mean()

def donchian(high, low, n=20):
    return high.shift(1).rolling(n).max(), low.shift(1).rolling(n).min()

# =================== REGIME ===================
def load_regime():
    if not USE_REGIME_FILTER:
        return None
    try:
        df = yf.download(REGIME_BENCHMARK, period=LOOKBACK, progress=False, auto_adjust=True)
    except Exception:
        return None
    if df is None or df.empty or len(df) < 220:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    c = df["Close"]
    s50  = sma(c, 50)
    s200 = sma(c, 200)
    regime = pd.Series(0, index=c.index, dtype=int)
    regime[(c > s50) & (s50 > s200)] =  1
    regime[(c < s50) & (s50 < s200)] = -1
    return regime

# =================== LIVE PRICE ===================
def get_live_price(ticker, fallback):
    """Best-effort latest quote for ticker, falling back to the daily close.

    Tries fast_info first (single REST call, cheap), then a 1-minute history
    bar. Both calls are wrapped in broad try/except since yfinance attribute
    surfaces change between releases. Returns fallback on every failure."""
    if not REFRESH_LIVE_PRICES or fallback is None or fallback <= 0:
        return fallback
    try:
        t = yf.Ticker(ticker)
        fi = getattr(t, "fast_info", None)
        if fi is not None:
            for attr in ("last_price", "lastPrice", "regularMarketPrice"):
                try:
                    val = getattr(fi, attr, None)
                except Exception:
                    val = None
                if val is None:
                    try:
                        val = fi[attr] if hasattr(fi, "__getitem__") else None
                    except Exception:
                        val = None
                if val is not None and not pd.isna(val) and float(val) > 0:
                    price = float(val)
                    if abs(price - fallback) / fallback <= LIVE_PRICE_MAX_DRIFT:
                        return price
    except Exception:
        pass
    try:
        h = yf.download(ticker, period="2d", interval="1m",
                        progress=False, auto_adjust=True)
        if h is not None and not h.empty:
            if isinstance(h.columns, pd.MultiIndex):
                h.columns = h.columns.get_level_values(0)
            last = h["Close"].dropna()
            if len(last):
                price = float(last.iloc[-1])
                if price > 0 and abs(price - fallback) / fallback <= LIVE_PRICE_MAX_DRIFT:
                    return price
    except Exception:
        pass
    return fallback

# =================== FEES ===================
def fees_open_close(asset_class, notional):
    if asset_class in ("stock", "etf"):
        return STOCK_FEE_OPEN_EUR, STOCK_FEE_CLOSE_EUR
    if asset_class == "equity_cfd":
        f = max(notional * EQUITY_CFD_FEE_PCT, EQUITY_CFD_FEE_MIN_EUR)
        return f, f
    if asset_class == "crypto":
        f = notional * CRYPTO_FEE_PCT
        return f, f
    return 0.0, 0.0

def overnight_cost(asset_class, notional, currency, days):
    if asset_class in ("stock", "etf", "crypto"):
        return 0.0
    base = CFD_BASE_RATE_USD if currency == "USD" else CFD_BASE_RATE_EUR
    return notional * (base + CFD_MARKUP) * days / 360.0

# =================== SCORING ===================
CRIT_COLS = ["Close","Open","High","Low","SMA20","SMA50","SMA200",
             "EMA8","EMA21","RSI","MACD","MACDsig","MACDhist",
             "ATR","ATRpct","BBL","BBH","ret3","ret5","ret20",
             "SMA20slope","HH20","DonchH","RangePos","VolRatio",
             "ADX","ADXprev","Regime"]

DAYTRADE_CRIT_COLS = ["Close","Open","High","Low","EMA8","EMA21","RSI",
                      "RSI2","MACDhist","ATR","ATRpct","ret1","ret2",
                      "ret3","RangePos","VolRatio","ADX","Regime"]

def compute_score(last, prev):
    sig, score = [], 0
    if last["Close"] > last["SMA20"]:                    score += 1; sig.append("above_SMA20")
    if last["Close"] > last["SMA50"]:                    score += 1; sig.append("above_SMA50")
    if last["Close"] > last["SMA200"]:                   score += 1; sig.append("above_SMA200")
    if last["SMA50"]  > last["SMA200"]:                  score += 1; sig.append("sma50>sma200")
    if last["EMA8"] > last["EMA21"] and last["Close"] > last["EMA8"]:
        score += 1; sig.append("short_trend_aligned")
    if last["SMA20slope"] > 0:                            score += 1; sig.append("sma20_rising")
    if last["Close"] > last["HH20"] and last["VolRatio"] >= 1.30:
        score += 2; sig.append("20d_breakout_on_volume")
    elif last["Close"] > last["HH20"]:
        score += 1; sig.append("20d_breakout_no_vol")
    if last["Close"] > last["DonchH"]:
        score += 1; sig.append("donchian_breakout")
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
            and last["Open"] < prev["Close"] and last["Close"] > prev["Open"]):
        score += 1; sig.append("bullish_engulfing")
    if last["RangePos"] >= 0.80:                          score += 1; sig.append("near_20d_high")
    if last["VolRatio"] >= 1.30:                          score += 1; sig.append("volume_confirmation")
    if 0.005 < last["ret5"] < 0.06:                       score += 1; sig.append("healthy_5d_momentum")
    if last["ret20"] < -0.12:                             score -= 1; sig.append("weak_20d_trend")
    if last["ATRpct"] > 0.08:                             score -= 1; sig.append("very_high_volatility")
    if last["ADX"] > 25 and last["ADX"] > last["ADXprev"]:
        score += 1; sig.append("adx_rising_trend")
    elif last["ADX"] < 18:
        score -= 1; sig.append("no_trend_adx")
    if last["Regime"] == 1:                                score += 1; sig.append("macro_bullish")
    elif last["Regime"] == -1:                             score -= 1; sig.append("macro_bearish")
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
    if last["RangePos"] >= 0.75:                          score += 1; sig.append("near_20d_high")
    if last["VolRatio"] >= 1.20:                          score += 1; sig.append("volume_expansion")
    if last["ATRpct"] < 0.015:                            score -= 1; sig.append("too_quiet")
    if last["ATRpct"] > 0.09:                             score -= 1; sig.append("too_volatile")
    if last["ret1"] > 0.06 or last["RSI"] > 82:           score -= 2; sig.append("overextended")
    if last["ADX"] > 22:                                  score += 1; sig.append("adx_trending")
    elif last["ADX"] < 15:                                score -= 1; sig.append("adx_chop")
    if last["Regime"] == 1:                               score += 1; sig.append("macro_bullish")
    elif last["Regime"] == -1:                            score -= 1; sig.append("macro_bearish")
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
def load_and_enrich(ticker, regime_series=None):
    try:
        df = yf.download(ticker, period=LOOKBACK, progress=False, auto_adjust=True)
    except Exception:
        return None
    if df is None or df.empty or len(df) < 220:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    c = df["Close"]
    df["EMA8"], df["EMA21"] = ema(c, 8), ema(c, 21)
    df["SMA20"], df["SMA50"], df["SMA200"] = sma(c, 20), sma(c, 50), sma(c, 200)
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
    donch_h, _ = donchian(df["High"], df["Low"], 20)
    df["DonchH"] = donch_h
    df["RangePos"] = rolling_position(c, df["High"], df["Low"], n=20)
    df["ADX"] = adx(df, 14)
    df["ADXprev"] = df["ADX"].shift(1)
    if "Volume" in df.columns:
        vol20 = df["Volume"].replace(0, np.nan).rolling(20).mean()
        df["VolRatio"] = (df["Volume"] / vol20).replace([np.inf, -np.inf], np.nan).fillna(1.0)
    else:
        df["VolRatio"] = 1.0
    if regime_series is not None:
        df["Regime"] = regime_series.reindex(df.index, method="ffill").fillna(0).astype(int)
    else:
        df["Regime"] = 0
    return df

# =================== CURRENT SCAN ===================
def calibrated_confidence(score):
    return float(np.clip((score - 3) / 7.0, 0.0, 1.0))

def current_analysis(df, ticker, name, asset_class, currency):
    last, prev = df.iloc[-1], df.iloc[-2]
    if last[CRIT_COLS].isna().any() or prev[CRIT_COLS].isna().any():
        return None
    score, sig = compute_score(last, prev)
    day_score, day_sig = compute_daytrade_score(last, prev)
    atr_pct = float(last["ATR"] / last["Close"])
    vol_2w = atr_pct * np.sqrt(HOLD_TRADING_DAYS) * 100.0
    confidence = calibrated_confidence(score)
    pred_move = confidence * vol_2w * 0.7
    return {"ticker": ticker, "name": name, "asset_class": asset_class,
            "currency": currency, "price": float(last["Close"]),
            "score": int(score), "rsi": float(last["RSI"]),
            "adx": float(last["ADX"]) if pd.notna(last["ADX"]) else np.nan,
            "regime": int(last["Regime"]),
            "daytrade_score": int(day_score),
            "atr_pct": atr_pct * 100.0,
            "range_pos": float(last["RangePos"]),
            "vol_ratio": float(last["VolRatio"]),
            "vol_2w_pct": vol_2w,
            "predicted_move_pct": pred_move,
            "confidence": confidence,
            "signals": ", ".join(sig),
            "daytrade_signals": ", ".join(day_sig)}

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
             start_idx=200, end_idx=None, target_notional=None):
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
        if target_notional and asset_class in ("stock", "etf"):
            units = max(1, int(round(target_notional / entry)))
        elif target_notional and asset_class == "crypto":
            units = target_notional / entry  # fractional allowed
        else:
            units = UNITS_PER_TRADE
        notional = entry * units
        of, cf  = fees_open_close(asset_class, notional)
        ov      = overnight_cost(asset_class, notional, currency, cal_days)
        fees    = of + cf + ov
        net     = (exit_ - entry) * units - fees
        trades.append({"entry_date": dates[i].strftime("%Y-%m-%d"),
                       "exit_date":  dates[i+hold].strftime("%Y-%m-%d"),
                       "score": int(s), "entry": entry, "exit": exit_,
                       "units": units, "notional": notional,
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
    if test_avg <= 0:
        return "OVERFIT"
    if test_avg < ROBUST_MIN_TEST_AVG:
        return "WEAK"
    if train_avg is None or train_avg <= 0:
        return "?"
    return "ROBUST" if (test_avg / train_avg) >= 0.5 else "WEAK"

# =================== HEATMAP PRINTER ===================
def print_heatmap(sweep_df, asset_class, metric_col, label):
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

# =================== TRADE LEVELS ===================
def trade_levels(price, vol_pct, predicted_move_pct, sl_vol_frac, min_rr=MIN_RR_RATIO):
    """Compute SL/TP/R:R for a long entry, ensuring R:R ≥ min_rr where possible."""
    sl_pct = -vol_pct * sl_vol_frac
    base_tp_pct = predicted_move_pct if TAKE_PROFIT_AT_PRED else vol_pct
    min_tp_pct = min_rr * vol_pct * sl_vol_frac
    tp_pct = max(base_tp_pct, min_tp_pct)
    tp_price = price * (1 + tp_pct / 100.0)
    sl_price = price * (1 + sl_pct / 100.0)
    risk = price - sl_price
    reward = tp_price - price
    rr = reward / risk if risk > 0 else np.nan
    return sl_price, tp_price, rr

# =================== LIVE-PRICE REFRESH ===================
def _scale_levels(r, fields, ratio):
    for f in fields:
        if f in r and r[f] is not None and isinstance(r[f], (int, float)) and not pd.isna(r[f]):
            r[f] = r[f] * ratio

def refresh_swing_prices(recs, sl_vol_frac=STOP_LOSS_VOL_FRAC):
    """Pull live quote for each rec and recompute entry/SL/TP/notional/fees at it."""
    for r in recs:
        scan_close = r["price"]
        live = get_live_price(r["ticker"], scan_close)
        r["close_at_scan"] = scan_close
        r["price"] = live
        # Recompute notional / fees / projections at the live price
        units = UNITS_PER_TRADE
        notional = live * units
        of, cf = fees_open_close(r["asset_class"], notional)
        ov = overnight_cost(r["asset_class"], notional, r["currency"], HOLD_CALENDAR_DAYS)
        fees = of + cf + ov
        gross = notional * r["predicted_move_pct"] / 100.0
        bull_g = notional * r["vol_2w_pct"] / 100.0
        r["notional"] = notional
        r["open_fee"] = of; r["close_fee"] = cf; r["overnight"] = ov
        r["total_fees"] = fees
        r["breakeven_pct"] = fees / notional * 100 if notional > 0 else np.nan
        r["predicted_net_eur"] = gross - fees
        r["bull_case_net_eur"] = bull_g - fees
        r["bear_case_net_eur"] = -bull_g - fees
        r["expected_roi_pct"] = r["predicted_net_eur"] / notional * 100.0
        sl, tp, rr = trade_levels(live, r["vol_2w_pct"], r["predicted_move_pct"], sl_vol_frac)
        r["stop_loss_price"] = sl
        r["take_profit_price"] = tp
        r["risk_reward"] = rr
    return recs

def refresh_daytrade_prices(recs, sl_vol_frac=DAYTRADE_STOP_LOSS_VOL_FRAC,
                            stock_notional=None, crypto_notional=None):
    """Same idea as refresh_swing_prices, but for daytrade fields."""
    for r in recs:
        scan_close = r["price"]
        live = get_live_price(r["ticker"], scan_close)
        r["close_at_scan"] = scan_close
        r["price"] = live
        cls = r["asset_class"]
        if stock_notional and cls in ("stock", "etf"):
            units = max(1, int(round(stock_notional / live)))
        elif crypto_notional and cls == "crypto":
            units = crypto_notional / live  # fractional
        else:
            units = UNITS_PER_TRADE
        notional = live * units
        of, cf = fees_open_close(cls, notional)
        cal_days = max(1, int(round(r["hold_days"] * 1.4)))
        ov = overnight_cost(cls, notional, r["currency"], cal_days)
        fees = of + cf + ov
        gross = notional * r["daytrade_predicted_move_pct"] / 100.0
        r["daytrade_units"] = units
        r["daytrade_notional"] = notional
        r["daytrade_fees_eur"] = fees
        r["daytrade_breakeven_pct"] = fees / notional * 100 if notional > 0 else np.nan
        r["daytrade_predicted_net_eur"] = gross - fees
        r["daytrade_expected_roi_pct"] = (gross - fees) / notional * 100 if notional > 0 else np.nan
        sl, tp, rr = trade_levels(live, r["daytrade_vol_pct"],
                                  r["daytrade_predicted_move_pct"], sl_vol_frac)
        r["daytrade_stop_loss_price"] = sl
        r["daytrade_take_profit_price"] = tp
        r["daytrade_risk_reward"] = rr
    return recs

# =================== SWING RECOMMENDATIONS (mixed asset classes) ===================
def build_recommendations(scan_rows, oos_results, oos_lookup):
    robust = {r["asset_class"] for r in oos_results if r.get("verdict") == "ROBUST"}
    weak   = {r["asset_class"] for r in oos_results if r.get("verdict") == "WEAK"}
    accept = robust | (weak if ALLOW_WEAK_CLASSES else set())

    recs = []
    for r in scan_rows:
        if r["asset_class"] not in accept: continue
        if r["score"] < MIN_SCORE_FOR_REC:  continue
        if r["predicted_net_eur"] <= 0:     continue
        if r["notional"] <= 0:              continue

        sl_price, tp_price, rr = trade_levels(
            r["price"], r["vol_2w_pct"], r["predicted_move_pct"], STOP_LOSS_VOL_FRAC)
        if pd.isna(rr) or rr < MIN_RR_RATIO:
            continue

        roi_pct = r["predicted_net_eur"] / r["notional"] * 100.0
        oos = oos_lookup.get(r["asset_class"], {})
        recs.append({
            **r,
            "expected_roi_pct": roi_pct,
            "stop_loss_price": sl_price,
            "take_profit_price": tp_price,
            "risk_reward": rr,
            "oos_best_thr": oos.get("thr"),
            "oos_best_hold": oos.get("hold"),
            "oos_test_winrate": oos.get("vw"),
            "oos_test_avg": oos.get("va"),
        })
    recs.sort(key=lambda x: x["expected_roi_pct"], reverse=True)
    return recs[:N_RECOMMENDATIONS], robust, weak

# =================== STOCK SWING ===================
def run_per_ticker_oos(df, scores, asset_class, currency, threshold, hold, target_notional=None):
    n = len(df); warmup = 200
    if n - warmup < 30:
        return None
    split = warmup + int((n - warmup) * TRAIN_FRACTION)
    train = simulate(df, scores, asset_class, currency, threshold, hold, warmup, split, target_notional)
    test  = simulate(df, scores, asset_class, currency, threshold, hold, split, n, target_notional)
    full  = simulate(df, scores, asset_class, currency, threshold, hold, warmup, n, target_notional)
    return summarize(full), summarize(train), summarize(test)

def build_stock_recommendations(scan_rows, enriched, scores_map, robust_classes, weak_classes):
    if "stock" not in (robust_classes | (weak_classes if ALLOW_WEAK_CLASSES else set())):
        return []

    recs = []
    for r in scan_rows:
        if r["asset_class"] != "stock":    continue
        if r["score"] < MIN_SCORE_FOR_REC: continue
        if r["predicted_net_eur"] <= 0:    continue
        if r["notional"] <= 0:             continue

        key = (r["ticker"], r["asset_class"])
        df = enriched.get(key, (None,))[0]
        scores = scores_map.get(key)
        if df is None or scores is None: continue

        oos = run_per_ticker_oos(df, scores, r["asset_class"], r["currency"],
                                 SCORE_THRESHOLD, HOLD_TRADING_DAYS)
        if oos is None: continue
        full, train, test = oos
        if full["n"] < MIN_STOCK_BT_TRADES:  continue
        if full["avg"] is None or full["avg"] <= 0: continue
        if STOCK_REQUIRE_OOS:
            if test["n"] < MIN_TEST_TRADES: continue
            if test["avg"] is None or test["avg"] <= 0: continue
            if train["avg"] is None or train["avg"] <= 0: continue

        sl_price, tp_price, rr = trade_levels(
            r["price"], r["vol_2w_pct"], r["predicted_move_pct"], STOP_LOSS_VOL_FRAC)
        if pd.isna(rr) or rr < MIN_RR_RATIO:
            continue

        roi_pct = r["predicted_net_eur"] / r["notional"] * 100.0
        recs.append({
            **r,
            "expected_roi_pct": roi_pct,
            "stop_loss_price": sl_price,
            "take_profit_price": tp_price,
            "risk_reward": rr,
            "bt_trades": full["n"], "bt_win_rate": full["win_rate"],
            "bt_avg": full["avg"], "bt_total": full["total"],
            "test_trades": test["n"], "test_win_rate": test["win_rate"], "test_avg": test["avg"],
        })
    recs.sort(key=lambda x: (x["expected_roi_pct"], x["bt_avg"]), reverse=True)
    return recs[:N_STOCK_RECOMMENDATIONS]

# =================== CRYPTO SWING ===================
def build_crypto_recommendations(scan_rows, enriched, scores_map, robust_classes, weak_classes):
    """Cash crypto swing recs (10 trading days). Crypto fees are ~3% round-trip,
    so we also require predicted_move_pct ≥ CRYPTO_MIN_PREDICTED_MOVE_PCT."""
    if "crypto" not in (robust_classes | (weak_classes if ALLOW_WEAK_CLASSES else set())):
        return []

    recs = []
    for r in scan_rows:
        if r["asset_class"] != "crypto":   continue
        if r["score"] < MIN_SCORE_FOR_REC: continue
        if r["price"] <= 0:                continue
        if r["predicted_move_pct"] < CRYPTO_MIN_PREDICTED_MOVE_PCT: continue

        key = (r["ticker"], r["asset_class"])
        df = enriched.get(key, (None,))[0]
        scores = scores_map.get(key)
        if df is None or scores is None: continue

        oos = run_per_ticker_oos(df, scores, r["asset_class"], r["currency"],
                                 SCORE_THRESHOLD, CRYPTO_HOLD_TRADING_DAYS,
                                 target_notional=CRYPTO_NOTIONAL_EUR)
        if oos is None: continue
        full, train, test = oos
        if full["n"] < MIN_CRYPTO_BT_TRADES: continue
        if full["avg"] is None or full["avg"] <= 0: continue
        if test["n"] < MIN_CRYPTO_TEST_TRADES: continue
        if test["avg"] is None or test["avg"] <= 0: continue

        # Recompute projection at target notional
        notional = CRYPTO_NOTIONAL_EUR
        units = notional / r["price"]
        of, cf = fees_open_close("crypto", notional)
        fees = of + cf
        gross = notional * r["predicted_move_pct"] / 100.0
        bull_g = notional * r["vol_2w_pct"] / 100.0
        predicted_net_eur = gross - fees
        if predicted_net_eur <= 0: continue
        breakeven_pct = fees / notional * 100

        sl_price, tp_price, rr = trade_levels(
            r["price"], r["vol_2w_pct"], r["predicted_move_pct"], STOP_LOSS_VOL_FRAC)
        if pd.isna(rr) or rr < MIN_RR_RATIO:
            continue

        recs.append({
            **r,
            "crypto_units": units,
            "crypto_notional": notional,
            "open_fee": of, "close_fee": cf, "overnight": 0.0,
            "total_fees": fees,
            "breakeven_pct": breakeven_pct,
            "predicted_net_eur": predicted_net_eur,
            "bull_case_net_eur": bull_g - fees,
            "bear_case_net_eur": -bull_g - fees,
            "expected_roi_pct": predicted_net_eur / notional * 100,
            "stop_loss_price": sl_price,
            "take_profit_price": tp_price,
            "risk_reward": rr,
            "bt_trades": full["n"], "bt_win_rate": full["win_rate"],
            "bt_avg": full["avg"], "bt_total": full["total"],
            "test_trades": test["n"], "test_win_rate": test["win_rate"], "test_avg": test["avg"],
        })
    recs.sort(key=lambda x: (x["expected_roi_pct"], x["bt_avg"]), reverse=True)
    return recs[:N_CRYPTO_RECOMMENDATIONS]

# =================== MIXED DAYTRADE ===================
def project_daytrade(row, hold_days, target_notional=None):
    cls = row["asset_class"]
    if target_notional and cls in ("stock", "etf"):
        units = max(1, int(round(target_notional / row["price"])))
    elif target_notional and cls == "crypto":
        units = target_notional / row["price"]
    else:
        units = UNITS_PER_TRADE
    notional = row["price"] * units
    open_fee, close_fee = fees_open_close(cls, notional)
    cal_days = max(1, int(round(hold_days * 1.4)))
    overnight = overnight_cost(cls, notional, row["currency"], cal_days)
    fees = open_fee + close_fee + overnight
    confidence = calibrated_confidence(row["daytrade_score"])
    scaled_vol = row["vol_2w_pct"] * np.sqrt(hold_days / HOLD_TRADING_DAYS)
    predicted_move_pct = confidence * scaled_vol * 0.7
    gross = notional * predicted_move_pct / 100.0
    sl_price, tp_price, rr = trade_levels(
        row["price"], scaled_vol, predicted_move_pct, DAYTRADE_STOP_LOSS_VOL_FRAC)
    return {
        **row,
        "hold_days": hold_days,
        "daytrade_units": units,
        "daytrade_notional": notional,
        "daytrade_vol_pct": scaled_vol,
        "daytrade_predicted_move_pct": predicted_move_pct,
        "daytrade_calendar_days": cal_days,
        "daytrade_fees_eur": fees,
        "daytrade_breakeven_pct": fees / notional * 100 if notional > 0 else np.nan,
        "daytrade_predicted_net_eur": gross - fees,
        "daytrade_expected_roi_pct": (gross - fees) / notional * 100 if notional > 0 else np.nan,
        "daytrade_stop_loss_price": sl_price,
        "daytrade_take_profit_price": tp_price,
        "daytrade_risk_reward": rr,
    }

def build_daytrade_recommendations(scan_rows, enriched, day_scores_map):
    scan_lookup = {
        (r["ticker"], r["asset_class"]): r
        for r in scan_rows
        if r["daytrade_score"] >= DAYTRADE_SCORE_THRESHOLD and r["notional"] > 0
    }
    recs = []
    for key, r in scan_lookup.items():
        if r["asset_class"] == "crypto": continue  # crypto has its own dedicated module
        df, currency, _name = enriched.get(key, (None, None, None))
        scores = day_scores_map.get(key)
        if df is None or scores is None: continue

        n = len(df); warmup = 200
        if n - warmup < 30: continue
        split = warmup + int((n - warmup) * TRAIN_FRACTION)
        best = None
        for hold in DAYTRADE_HOLDS:
            full = simulate(df, scores, r["asset_class"], currency,
                            DAYTRADE_SCORE_THRESHOLD, hold, warmup, n)
            test = simulate(df, scores, r["asset_class"], currency,
                            DAYTRADE_SCORE_THRESHOLD, hold, split, n)
            fs, ts = summarize(full), summarize(test)
            if fs["n"] < MIN_DAYTRADE_TRADES:      continue
            if ts["n"] < MIN_DAYTRADE_TEST_TRADES: continue
            if fs["avg"] <= 0 or ts["avg"] <= 0:   continue

            cand = project_daytrade(r, hold)
            if cand["daytrade_predicted_net_eur"] <= 0: continue
            if pd.isna(cand["daytrade_risk_reward"]) or cand["daytrade_risk_reward"] < MIN_RR_RATIO:
                continue
            cand.update({
                "daytrade_bt_trades": fs["n"], "daytrade_bt_win_rate": fs["win_rate"],
                "daytrade_bt_avg": fs["avg"], "daytrade_bt_median": fs["median"],
                "daytrade_test_trades": ts["n"], "daytrade_test_win_rate": ts["win_rate"],
                "daytrade_test_avg": ts["avg"],
            })
            if best is None or cand["daytrade_expected_roi_pct"] > best["daytrade_expected_roi_pct"]:
                best = cand
        if best is not None:
            recs.append(best)

    recs.sort(key=lambda x: (x["daytrade_expected_roi_pct"], x["daytrade_test_avg"]),
              reverse=True)
    return recs[:N_DAYTRADE_RECOMMENDATIONS]

# =================== STOCK DAYTRADE ===================
def build_stock_daytrade_recommendations(scan_rows, enriched, day_scores_map):
    recs = []
    for r in scan_rows:
        if r["asset_class"] != "stock":  continue
        if r["daytrade_score"] < DAYTRADE_SCORE_THRESHOLD: continue
        if r["price"] <= 0: continue

        units = max(1, int(round(STOCK_DAYTRADE_NOTIONAL_EUR / r["price"])))
        notional = r["price"] * units
        if notional < STOCK_DAYTRADE_MIN_NOTIONAL: continue

        key = (r["ticker"], r["asset_class"])
        df, currency, _name = enriched.get(key, (None, None, None))
        scores = day_scores_map.get(key)
        if df is None or scores is None: continue

        n = len(df); warmup = 200
        if n - warmup < 30: continue
        split = warmup + int((n - warmup) * TRAIN_FRACTION)
        best = None
        for hold in DAYTRADE_HOLDS:
            full = simulate(df, scores, r["asset_class"], currency,
                            DAYTRADE_SCORE_THRESHOLD, hold, warmup, n,
                            target_notional=STOCK_DAYTRADE_NOTIONAL_EUR)
            train = simulate(df, scores, r["asset_class"], currency,
                             DAYTRADE_SCORE_THRESHOLD, hold, warmup, split,
                             target_notional=STOCK_DAYTRADE_NOTIONAL_EUR)
            test = simulate(df, scores, r["asset_class"], currency,
                            DAYTRADE_SCORE_THRESHOLD, hold, split, n,
                            target_notional=STOCK_DAYTRADE_NOTIONAL_EUR)
            fs, trs, ts = summarize(full), summarize(train), summarize(test)
            if fs["n"] < MIN_STOCK_DAYTRADE_TRADES: continue
            if ts["n"] < MIN_STOCK_DAYTRADE_TEST_TRADES: continue
            if fs["avg"] <= 0 or ts["avg"] <= 0 or trs["avg"] <= 0: continue

            cand = project_daytrade(r, hold, target_notional=STOCK_DAYTRADE_NOTIONAL_EUR)
            if cand["daytrade_predicted_net_eur"] <= 0: continue
            if pd.isna(cand["daytrade_risk_reward"]) or cand["daytrade_risk_reward"] < MIN_RR_RATIO:
                continue
            cand.update({
                "stock_dt_full_trades": fs["n"], "stock_dt_full_win_rate": fs["win_rate"],
                "stock_dt_full_avg": fs["avg"], "stock_dt_full_median": fs["median"],
                "stock_dt_train_trades": trs["n"], "stock_dt_train_win_rate": trs["win_rate"],
                "stock_dt_train_avg": trs["avg"],
                "stock_dt_test_trades": ts["n"], "stock_dt_test_win_rate": ts["win_rate"],
                "stock_dt_test_avg": ts["avg"],
            })
            if best is None or cand["daytrade_expected_roi_pct"] > best["daytrade_expected_roi_pct"]:
                best = cand
        if best is not None:
            recs.append(best)

    recs.sort(key=lambda x: (x["daytrade_expected_roi_pct"], x.get("stock_dt_test_avg", 0)),
              reverse=True)
    return recs[:N_STOCK_DAYTRADE_RECOMMENDATIONS]

# =================== CRYPTO DAYTRADE ===================
def build_crypto_daytrade_recommendations(scan_rows, enriched, day_scores_map):
    recs = []
    for r in scan_rows:
        if r["asset_class"] != "crypto":  continue
        if r["daytrade_score"] < CRYPTO_DAYTRADE_SCORE_THRESHOLD: continue
        if r["price"] <= 0: continue

        notional = CRYPTO_NOTIONAL_EUR
        if notional < CRYPTO_MIN_NOTIONAL: continue

        key = (r["ticker"], r["asset_class"])
        df, currency, _name = enriched.get(key, (None, None, None))
        scores = day_scores_map.get(key)
        if df is None or scores is None: continue

        n = len(df); warmup = 200
        if n - warmup < 30: continue
        split = warmup + int((n - warmup) * TRAIN_FRACTION)
        best = None
        for hold in CRYPTO_DAYTRADE_HOLDS:
            full = simulate(df, scores, "crypto", currency,
                            CRYPTO_DAYTRADE_SCORE_THRESHOLD, hold, warmup, n,
                            target_notional=CRYPTO_NOTIONAL_EUR)
            train = simulate(df, scores, "crypto", currency,
                             CRYPTO_DAYTRADE_SCORE_THRESHOLD, hold, warmup, split,
                             target_notional=CRYPTO_NOTIONAL_EUR)
            test = simulate(df, scores, "crypto", currency,
                            CRYPTO_DAYTRADE_SCORE_THRESHOLD, hold, split, n,
                            target_notional=CRYPTO_NOTIONAL_EUR)
            fs, trs, ts = summarize(full), summarize(train), summarize(test)
            if fs["n"] < MIN_CRYPTO_DT_TRADES: continue
            if ts["n"] < MIN_CRYPTO_DT_TEST_TRADES: continue
            if fs["avg"] <= 0 or ts["avg"] <= 0 or trs["avg"] <= 0: continue

            cand = project_daytrade(r, hold, target_notional=CRYPTO_NOTIONAL_EUR)
            if cand["daytrade_predicted_move_pct"] < CRYPTO_DT_MIN_PREDICTED_MOVE_PCT:
                continue
            if cand["daytrade_predicted_net_eur"] <= 0: continue
            if pd.isna(cand["daytrade_risk_reward"]) or cand["daytrade_risk_reward"] < MIN_RR_RATIO:
                continue
            cand.update({
                "crypto_dt_full_trades": fs["n"], "crypto_dt_full_win_rate": fs["win_rate"],
                "crypto_dt_full_avg": fs["avg"], "crypto_dt_full_median": fs["median"],
                "crypto_dt_train_trades": trs["n"], "crypto_dt_train_win_rate": trs["win_rate"],
                "crypto_dt_train_avg": trs["avg"],
                "crypto_dt_test_trades": ts["n"], "crypto_dt_test_win_rate": ts["win_rate"],
                "crypto_dt_test_avg": ts["avg"],
            })
            if best is None or cand["daytrade_expected_roi_pct"] > best["daytrade_expected_roi_pct"]:
                best = cand
        if best is not None:
            recs.append(best)

    recs.sort(key=lambda x: (x["daytrade_expected_roi_pct"], x.get("crypto_dt_test_avg", 0)),
              reverse=True)
    return recs[:N_CRYPTO_DAYTRADE_RECOMMENDATIONS]

# =================== PRINTERS ===================
def _drift_note(scan_close, live):
    if scan_close is None or live is None or scan_close <= 0:
        return ""
    drift = (live - scan_close) / scan_close * 100.0
    if abs(drift) < 0.05:
        return "(matches scan close)"
    return f"(scan close was {scan_close:.4f}; drift {drift:+.2f}%)"

def print_recommendations(recs, robust, weak):
    BAR = "="*135
    print("\n" + BAR)
    print(" CONCRETE TRADING RECOMMENDATIONS — ranked by expected 2-week net ROI (mixed asset classes)")
    print(BAR)

    print(f"\n  Filter applied:")
    print(f"   1. Asset class must have OOS verdict = ROBUST"
          f"{' or WEAK' if ALLOW_WEAK_CLASSES else ''}")
    print(f"   2. Current scan score must be ≥ {MIN_SCORE_FOR_REC}")
    print(f"   3. Predicted net profit after fees must be > 0")
    print(f"   4. Reward:risk ratio must be ≥ {MIN_RR_RATIO}")
    print(f"\n  Robust asset classes today: "
          f"{', '.join(sorted(robust)) if robust else '(none — no asset class survived OOS)'}")
    if weak:
        print(f"  Weak classes (excluded): {', '.join(sorted(weak))}")

    if not robust and not (ALLOW_WEAK_CLASSES and weak):
        print("\n  No asset class passed out-of-sample validation in this run.")
        print("  The honest interpretation: there is no detectable edge to trade.")
        return

    if not recs:
        print("\n  No instrument currently shows a bullish signal strong enough to meet the criteria.")
        return

    for i, r in enumerate(recs, 1):
        stars = "*" * min(5, max(1, r["score"] - 2))
        drift = _drift_note(r.get("close_at_scan"), r["price"])
        print()
        print(f"  -- #{i}  {stars:<5}  {r['name']}  ({r['ticker']} / {r['asset_class']}) " + "-"*30)
        print(f"     Direction:           LONG (BUY 1 piece)")
        print(f"     LIVE entry price:    {r['price']:>10.4f} {r['currency']}  {drift}")
        print(f"     Signal score:        {r['score']}     RSI: {r['rsi']:.1f}     "
              f"ADX: {r['adx']:.1f}     Regime: {r['regime']:+d}")
        sig_short = (r['signals'][:110] + '...') if len(r['signals']) > 110 else r['signals']
        print(f"     Active signals:      {sig_short}")
        print(f"     Predicted move:      {r['predicted_move_pct']:>+7.2f}%   "
              f"(confidence={r['confidence']:.2f})")
        print(f"     Total fees:          {r['total_fees']:>7.2f} EUR")
        print(f"     Break-even move:     {r['breakeven_pct']:>+7.2f}%")
        print(f"     >> EXPECTED NET ROI: {r['expected_roi_pct']:>+7.2f}%   "
              f"-> {r['predicted_net_eur']:>+7.2f} EUR per piece")
        print(f"     Upside (+1 vol):     {r['bull_case_net_eur']:>+7.2f} EUR     "
              f"Downside (-1 vol): {r['bear_case_net_eur']:>+7.2f} EUR")
        print(f"     Take-profit price:   {r['take_profit_price']:>10.4f} {r['currency']}")
        print(f"     Stop-loss price:     {r['stop_loss_price']:>10.4f} {r['currency']}")
        if not np.isnan(r["risk_reward"]):
            print(f"     Reward:risk ratio:   {r['risk_reward']:.2f} : 1")
        if r.get("oos_best_hold"):
            print(f"     OOS evidence:        best thr={r['oos_best_thr']}, hold={r['oos_best_hold']}d, "
                  f"test win rate {r['oos_test_winrate']:.1f}%, test avg {r['oos_test_avg']:+.2f}%")

    print("\n  " + "-"*120)
    print("  REMINDER: model projections, not guarantees. Always set the stop-loss in Revolut FIRST.")
    print("  Position sizing: ≤ 5–10% of account per trade. CFDs are leveraged; most retail CFD traders lose money.")
    print("  NOT financial advice.")

def print_stock_recommendations(recs):
    BAR = "="*135
    print("\n" + BAR)
    print(" CASH STOCK SWING RECOMMENDATIONS — 10 trading days, regular stocks only")
    print(BAR)
    if not recs:
        print("\n  No stock candidates passed the stock-specific filter today.")
        return
    for i, r in enumerate(recs, 1):
        stars = "*" * min(5, max(1, r["score"] - 2))
        drift = _drift_note(r.get("close_at_scan"), r["price"])
        print()
        print(f"  #{i} {stars:<5} {r['name']} ({r['ticker']})")
        print(f"     LIVE entry price:    {r['price']:>10.4f} {r['currency']}  {drift}")
        print(f"     Signal score:        {r['score']}     RSI: {r['rsi']:.1f}     "
              f"ADX: {r['adx']:.1f}     Regime: {r['regime']:+d}")
        sig_short = (r['signals'][:110] + '...') if len(r['signals']) > 110 else r['signals']
        print(f"     Active signals:      {sig_short}")
        print(f"     Predicted move:      {r['predicted_move_pct']:>+7.2f}%")
        print(f"     Fees:                {r['total_fees']:>7.2f} EUR")
        print(f"     Expected net ROI:    {r['expected_roi_pct']:>+7.2f}%   "
              f"-> {r['predicted_net_eur']:>+7.2f} EUR per share")
        print(f"     Take-profit price:   {r['take_profit_price']:>10.4f} {r['currency']}")
        print(f"     Stop-loss price:     {r['stop_loss_price']:>10.4f} {r['currency']}")
        if not np.isnan(r["risk_reward"]):
            print(f"     Reward:risk ratio:   {r['risk_reward']:.2f} : 1")
        print(f"     Full backtest:       {int(r['bt_trades'])} trades, "
              f"{r['bt_win_rate']:.1f}% win rate, avg {r['bt_avg']:+.2f}%")
        if r.get("test_trades", 0):
            print(f"     Recent test split:   {int(r['test_trades'])} trades, "
                  f"{r['test_win_rate']:.1f}% win rate, avg {r['test_avg']:+.2f}%")

def print_crypto_recommendations(recs):
    BAR = "="*135
    print("\n" + BAR)
    print(f" CRYPTO SWING RECOMMENDATIONS — {CRYPTO_HOLD_TRADING_DAYS}-day hold, "
          f"~€{CRYPTO_NOTIONAL_EUR:.0f} per position, Revolut fee={CRYPTO_FEE_PCT*100:.2f}%/side")
    print(BAR)
    print(f"\n  Filter applied:")
    print(f"   1. Asset class must be crypto and OOS-validated")
    print(f"   2. Current scan score ≥ {MIN_SCORE_FOR_REC}")
    print(f"   3. Predicted move ≥ {CRYPTO_MIN_PREDICTED_MOVE_PCT:.1f}% (to clear ~{2*CRYPTO_FEE_PCT*100:.2f}% round-trip fees)")
    print(f"   4. Per-ticker train/test backtest profitable in both halves; reward:risk ≥ {MIN_RR_RATIO}")

    if not recs:
        print("\n  No crypto candidates passed the filter today.")
        return

    for i, r in enumerate(recs, 1):
        stars = "*" * min(5, max(1, r["score"] - 2))
        drift = _drift_note(r.get("close_at_scan"), r["price"])
        units = r.get("crypto_units", CRYPTO_NOTIONAL_EUR / r["price"])
        print()
        print(f"  #{i} {stars:<5} {r['name']} ({r['ticker']})")
        print(f"     LIVE entry price:    {r['price']:>12.4f} {r['currency']}  {drift}")
        print(f"     Position sizing:     BUY {units:.6f} units × {r['price']:.4f} = ~€{r['notional']:.0f}")
        print(f"     Signal score:        {r['score']}     RSI: {r['rsi']:.1f}     "
              f"ADX: {r['adx']:.1f}     Regime: {r['regime']:+d}")
        sig_short = (r['signals'][:110] + '...') if len(r['signals']) > 110 else r['signals']
        print(f"     Active signals:      {sig_short}")
        print(f"     Predicted move:      {r['predicted_move_pct']:>+7.2f}%   "
              f"(confidence={r['confidence']:.2f}, 2w vol={r['vol_2w_pct']:.1f}%)")
        print(f"     Fees:                {r['total_fees']:>7.2f} EUR  "
              f"(break-even {r['breakeven_pct']:+.2f}%)")
        print(f"     >> Expected net ROI: {r['expected_roi_pct']:>+7.2f}%   "
              f"-> {r['predicted_net_eur']:>+7.2f} EUR on the position")
        print(f"     Upside (+1 vol):     {r['bull_case_net_eur']:>+7.2f} EUR     "
              f"Downside (-1 vol): {r['bear_case_net_eur']:>+7.2f} EUR")
        print(f"     Take-profit price:   {r['take_profit_price']:>12.4f} {r['currency']}")
        print(f"     Stop-loss price:     {r['stop_loss_price']:>12.4f} {r['currency']}")
        if not np.isnan(r["risk_reward"]):
            print(f"     Reward:risk ratio:   {r['risk_reward']:.2f} : 1")
        print(f"     Full backtest:       {int(r['bt_trades'])} trades, "
              f"{r['bt_win_rate']:.1f}% win rate, avg {r['bt_avg']:+.2f}%")
        if r.get("test_trades", 0):
            print(f"     Recent test split:   {int(r['test_trades'])} trades, "
                  f"{r['test_win_rate']:.1f}% win rate, avg {r['test_avg']:+.2f}%")

def print_daytrade_recommendations(recs):
    BAR = "="*135
    print("\n" + BAR)
    print(" DAYTRADE RECOMMENDATIONS (mixed, excl. crypto) — 1-3 trading days")
    print(BAR)
    if not recs:
        print("\n  No 1-3 day candidates passed the fee-aware day-trading filter today.")
        return
    for i, r in enumerate(recs, 1):
        label = "share" if r["asset_class"] == "stock" else "piece"
        drift = _drift_note(r.get("close_at_scan"), r["price"])
        print()
        print(f"  #{i} {r['name']} ({r['ticker']} / {r['asset_class']})")
        print(f"     Suggested hold:      {int(r['hold_days'])} trading day(s)")
        print(f"     LIVE entry price:    {r['price']:>10.4f} {r['currency']}  {drift}")
        print(f"     Swing/day score:     {r['score']} / {r['daytrade_score']}     "
              f"RSI: {r['rsi']:.1f}     ADX: {r['adx']:.1f}     Regime: {r['regime']:+d}")
        sig_short = (r['daytrade_signals'][:110] + '...') if len(r['daytrade_signals']) > 110 else r['daytrade_signals']
        print(f"     Active signals:      {sig_short}")
        print(f"     Predicted move:      {r['daytrade_predicted_move_pct']:>+7.2f}%")
        print(f"     Fees:                {r['daytrade_fees_eur']:>7.2f} EUR  "
              f"(break-even {r['daytrade_breakeven_pct']:+.2f}%)")
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

def print_stock_daytrade_recommendations(recs):
    BAR = "="*135
    print("\n" + BAR)
    print(f" STOCK DAYTRADE RECOMMENDATIONS — cash stocks only, ~€{STOCK_DAYTRADE_NOTIONAL_EUR:.0f} per position")
    print(BAR)
    if not recs:
        print("\n  No cash stock passed the daytrade-with-sizing filter today.")
        return
    for i, r in enumerate(recs, 1):
        units = int(r["daytrade_units"])
        drift = _drift_note(r.get("close_at_scan"), r["price"])
        print()
        print(f"  #{i} {r['name']} ({r['ticker']})")
        print(f"     Suggested hold:      {int(r['hold_days'])} trading day(s)")
        print(f"     LIVE entry price:    {r['price']:>10.4f} {r['currency']}  {drift}")
        print(f"     Position sizing:     BUY {units} shares × {r['price']:.4f} {r['currency']} "
              f"= ~{r['daytrade_notional']:.0f} {r['currency']}")
        print(f"     Swing/day score:     {r['score']} / {r['daytrade_score']}     "
              f"RSI: {r['rsi']:.1f}     ADX: {r['adx']:.1f}     Regime: {r['regime']:+d}")
        sig_short = (r['daytrade_signals'][:110] + '...') if len(r['daytrade_signals']) > 110 else r['daytrade_signals']
        print(f"     Active signals:      {sig_short}")
        print(f"     Predicted move:      {r['daytrade_predicted_move_pct']:>+7.2f}%")
        print(f"     Fees:                {r['daytrade_fees_eur']:>7.2f} EUR  "
              f"(break-even {r['daytrade_breakeven_pct']:+.2f}%)")
        print(f"     Expected net ROI:    {r['daytrade_expected_roi_pct']:>+7.2f}%   "
              f"-> {r['daytrade_predicted_net_eur']:>+7.2f} EUR on the position")
        print(f"     Take-profit price:   {r['daytrade_take_profit_price']:>10.4f} {r['currency']}")
        print(f"     Stop-loss price:     {r['daytrade_stop_loss_price']:>10.4f} {r['currency']}")
        if not np.isnan(r["daytrade_risk_reward"]):
            print(f"     Reward:risk ratio:   {r['daytrade_risk_reward']:.2f} : 1")
        print(f"     Full backtest:       {int(r['stock_dt_full_trades'])} trades, "
              f"{r['stock_dt_full_win_rate']:.1f}% win rate, avg {r['stock_dt_full_avg']:+.2f}%")
        print(f"     Train split:         {int(r['stock_dt_train_trades'])} trades, "
              f"{r['stock_dt_train_win_rate']:.1f}% win rate, avg {r['stock_dt_train_avg']:+.2f}%")
        print(f"     Test split:          {int(r['stock_dt_test_trades'])} trades, "
              f"{r['stock_dt_test_win_rate']:.1f}% win rate, avg {r['stock_dt_test_avg']:+.2f}%")

def print_crypto_daytrade_recommendations(recs):
    BAR = "="*135
    print("\n" + BAR)
    print(f" CRYPTO DAYTRADE RECOMMENDATIONS — 1-3 day hold, ~€{CRYPTO_NOTIONAL_EUR:.0f} per position")
    print(BAR)
    print(f"\n  Filter applied:")
    print(f"   1. Asset class is crypto; day-trade score ≥ {CRYPTO_DAYTRADE_SCORE_THRESHOLD}")
    print(f"   2. Predicted move ≥ {CRYPTO_DT_MIN_PREDICTED_MOVE_PCT:.1f}% (Revolut crypto fees are heavy)")
    print(f"   3. Per-ticker train/test/full splits all profitable; reward:risk ≥ {MIN_RR_RATIO}")
    if not recs:
        print("\n  No crypto coin passed the daytrade filter today.")
        return
    for i, r in enumerate(recs, 1):
        units = r["daytrade_units"]
        drift = _drift_note(r.get("close_at_scan"), r["price"])
        print()
        print(f"  #{i} {r['name']} ({r['ticker']})")
        print(f"     Suggested hold:      {int(r['hold_days'])} day(s)")
        print(f"     LIVE entry price:    {r['price']:>12.4f} {r['currency']}  {drift}")
        print(f"     Position sizing:     BUY {units:.6f} units × {r['price']:.4f} "
              f"= ~€{r['daytrade_notional']:.0f}")
        print(f"     Swing/day score:     {r['score']} / {r['daytrade_score']}     "
              f"RSI: {r['rsi']:.1f}     ADX: {r['adx']:.1f}     Regime: {r['regime']:+d}")
        sig_short = (r['daytrade_signals'][:110] + '...') if len(r['daytrade_signals']) > 110 else r['daytrade_signals']
        print(f"     Active signals:      {sig_short}")
        print(f"     Predicted move:      {r['daytrade_predicted_move_pct']:>+7.2f}%")
        print(f"     Fees:                {r['daytrade_fees_eur']:>7.2f} EUR  "
              f"(break-even {r['daytrade_breakeven_pct']:+.2f}%)")
        print(f"     Expected net ROI:    {r['daytrade_expected_roi_pct']:>+7.2f}%   "
              f"-> {r['daytrade_predicted_net_eur']:>+7.2f} EUR on the position")
        print(f"     Take-profit price:   {r['daytrade_take_profit_price']:>12.4f} {r['currency']}")
        print(f"     Stop-loss price:     {r['daytrade_stop_loss_price']:>12.4f} {r['currency']}")
        if not np.isnan(r["daytrade_risk_reward"]):
            print(f"     Reward:risk ratio:   {r['daytrade_risk_reward']:.2f} : 1")
        print(f"     Full backtest:       {int(r['crypto_dt_full_trades'])} trades, "
              f"{r['crypto_dt_full_win_rate']:.1f}% win rate, avg {r['crypto_dt_full_avg']:+.2f}%")
        print(f"     Train split:         {int(r['crypto_dt_train_trades'])} trades, "
              f"{r['crypto_dt_train_win_rate']:.1f}% win rate, avg {r['crypto_dt_train_avg']:+.2f}%")
        print(f"     Test split:          {int(r['crypto_dt_test_trades'])} trades, "
              f"{r['crypto_dt_test_win_rate']:.1f}% win rate, avg {r['crypto_dt_test_avg']:+.2f}%")

# =================== MAIN ===================
def main():
    os.makedirs(OUTDIR, exist_ok=True)
    assets = load_assets()
    print(f"Loading {len(assets)} instruments ({LOOKBACK} of history)...")
    if os.path.exists(INSTRUMENTS_CSV):
        print(f"Instrument universe loaded from {INSTRUMENTS_CSV}")

    if USE_REGIME_FILTER:
        regime_series = load_regime()
        if regime_series is not None:
            print(f"Regime filter active (benchmark: {REGIME_BENCHMARK}, "
                  f"{len(regime_series)} bars).")
        else:
            print("Regime filter could not download benchmark — proceeding without it.")
    else:
        regime_series = None

    enriched, scores_map, day_scores_map, returns = {}, {}, {}, {}
    scan_rows, all_trades, bt_summary = [], [], []

    for ticker, name, cls, cur in assets:
        df = load_and_enrich(ticker, regime_series)
        if df is None: continue
        enriched[(ticker, cls)] = (df, cur, name)
        returns[(ticker, cls)] = df["ret1"].tail(CORR_LOOKBACK_DAYS)
        scores = precompute_scores(df)
        scores_map[(ticker, cls)] = scores
        day_scores_map[(ticker, cls)] = precompute_daytrade_scores(df)

        row = current_analysis(df, ticker, name, cls, cur)
        if row is not None: scan_rows.append(project_pnl(row))

        tr = simulate(df, scores, cls, cur, SCORE_THRESHOLD, HOLD_TRADING_DAYS)
        for t in tr: t.update({"ticker": ticker, "asset_class": cls})
        all_trades.extend(tr)
        s = summarize(tr); s.update({"ticker": ticker, "name": name, "asset_class": cls})
        bt_summary.append(s)

    scan_rows.sort(key=lambda x: x["predicted_net_eur"], reverse=True)

    BAR = "="*135

    # ============== FULL CURRENT SCAN ==============
    print("\n" + BAR)
    print(f" Revolut Bullish Scanner v9 — {datetime.now():%Y-%m-%d %H:%M}")
    print(f" FULL CURRENT SCAN — all {len(scan_rows)} successfully analysed instruments")
    print(BAR)
    print(f"{'#':<3}{'Instrument':<26}{'Class':<14}{'Price':>11}{'Sc':>4}{'DSc':>5}"
          f"{'RSI':>6}{'ADX':>6}{'Rgm':>4}{'BE%':>7}{'Pred%':>7}{'Fees€':>8}{'Pred€':>9}")
    print("-"*135)
    for i, r in enumerate(scan_rows, 1):
        adx_str = f"{r['adx']:>6.1f}" if pd.notna(r['adx']) else f"{'—':>6}"
        print(f"{i:<3}{r['name'][:25]:<26}{r['asset_class']:<14}"
              f"{r['price']:>11.3f}{r['score']:>4}{r['daytrade_score']:>5}"
              f"{r['rsi']:>6.1f}{adx_str}{r['regime']:>+4d}"
              f"{r['breakeven_pct']:>7.2f}{r['predicted_move_pct']:>7.2f}"
              f"{r['total_fees']:>8.2f}{r['predicted_net_eur']:>9.2f}")

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

    # ============== PARAMETER SWEEP (TRAIN + TEST + FULL) ==============
    print("\n" + BAR)
    print(" PARAMETER SWEEP — TRAIN (first 70%) / TEST (last 30%)")
    print(BAR)
    sweep_rows = []
    for (tk, cls), (df, cur, name) in enriched.items():
        scores = scores_map[(tk, cls)]
        n = len(df); warmup = 200
        if n - warmup < 30: continue
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

    # ============== SWEEP HEATMAPS ==============
    print("\n" + BAR)
    print(" SWEEP HEATMAPS — avg %/trade for every (threshold × hold) combination")
    print(BAR)
    for cls in ASSET_CLASSES:
        print(f"\n  -- {cls.upper()} --")
        print_heatmap(sweep_df, cls, "train_avg", "TRAIN avg %/trade")
        print_heatmap(sweep_df, cls, "test_avg",  "TEST  avg %/trade")

    # ============== CONCRETE TRADING RECOMMENDATIONS ==============
    oos_lookup = {r["asset_class"]: r for r in oos_results}
    robust_set = {r["asset_class"] for r in oos_results if r.get("verdict") == "ROBUST"}
    weak_set   = {r["asset_class"] for r in oos_results if r.get("verdict") == "WEAK"}

    recs, _, _ = build_recommendations(scan_rows, oos_results, oos_lookup)
    stock_recs = build_stock_recommendations(scan_rows, enriched, scores_map,
                                             robust_set, weak_set)
    crypto_recs = build_crypto_recommendations(scan_rows, enriched, scores_map,
                                               robust_set, weak_set)
    daytrade_recs = build_daytrade_recommendations(scan_rows, enriched, day_scores_map)
    stock_daytrade_recs = build_stock_daytrade_recommendations(scan_rows, enriched, day_scores_map)
    crypto_daytrade_recs = build_crypto_daytrade_recommendations(scan_rows, enriched, day_scores_map)

    # ============== LIVE-PRICE REFRESH FOR ALL RECS ==============
    if REFRESH_LIVE_PRICES:
        print("\nRefreshing entry prices with live quotes for recommendations...")
        refresh_swing_prices(recs, STOP_LOSS_VOL_FRAC)
        refresh_swing_prices(stock_recs, STOP_LOSS_VOL_FRAC)
        refresh_swing_prices(crypto_recs, STOP_LOSS_VOL_FRAC)
        refresh_daytrade_prices(daytrade_recs, DAYTRADE_STOP_LOSS_VOL_FRAC)
        refresh_daytrade_prices(stock_daytrade_recs, DAYTRADE_STOP_LOSS_VOL_FRAC,
                                stock_notional=STOCK_DAYTRADE_NOTIONAL_EUR)
        refresh_daytrade_prices(crypto_daytrade_recs, DAYTRADE_STOP_LOSS_VOL_FRAC,
                                crypto_notional=CRYPTO_NOTIONAL_EUR)

    print_recommendations(recs, robust_set, weak_set)
    print_stock_recommendations(stock_recs)
    print_crypto_recommendations(crypto_recs)
    print_daytrade_recommendations(daytrade_recs)
    print_stock_daytrade_recommendations(stock_daytrade_recs)
    print_crypto_daytrade_recommendations(crypto_daytrade_recs)

    # ============== CSV EXPORTS ==============
    pd.DataFrame(scan_rows).to_csv(os.path.join(OUTDIR, "scan_results.csv"), index=False)
    pd.DataFrame(all_trades).to_csv(os.path.join(OUTDIR, "backtest_trades.csv"), index=False)
    pd.DataFrame(bt_summary).to_csv(os.path.join(OUTDIR, "backtest_summary.csv"), index=False)
    sweep_df.to_csv(os.path.join(OUTDIR, "sweep_results.csv"), index=False)
    pd.DataFrame(oos_results).to_csv(os.path.join(OUTDIR, "oos_verdict.csv"), index=False)
    if recs:
        pd.DataFrame(recs).to_csv(os.path.join(OUTDIR, "recommendations.csv"), index=False)
    if stock_recs:
        pd.DataFrame(stock_recs).to_csv(os.path.join(OUTDIR, "stock_recommendations.csv"), index=False)
    if crypto_recs:
        pd.DataFrame(crypto_recs).to_csv(os.path.join(OUTDIR, "crypto_recommendations.csv"), index=False)
    if daytrade_recs:
        pd.DataFrame(daytrade_recs).to_csv(os.path.join(OUTDIR, "daytrade_recommendations.csv"), index=False)
    if stock_daytrade_recs:
        pd.DataFrame(stock_daytrade_recs).to_csv(
            os.path.join(OUTDIR, "stock_daytrade_recommendations.csv"), index=False)
    if crypto_daytrade_recs:
        pd.DataFrame(crypto_daytrade_recs).to_csv(
            os.path.join(OUTDIR, "crypto_daytrade_recommendations.csv"), index=False)

    print("\n" + BAR)
    print(" CSVs written to disk:")
    print("   scan_results.csv          backtest_trades.csv          backtest_summary.csv")
    print("   sweep_results.csv         oos_verdict.csv              recommendations.csv")
    print("   stock_recommendations.csv crypto_recommendations.csv")
    print("   daytrade_recommendations.csv  stock_daytrade_recommendations.csv")
    print("   crypto_daytrade_recommendations.csv")
    print("\n" + BAR)
    print(" VERDICT LEGEND")
    print(f"   ROBUST       Test avg > {ROBUST_MIN_TEST_AVG:.2f}%/trade AND ≥ 50% of train avg")
    print(f"   WEAK         Test still > 0 but below the absolute floor")
    print("   OVERFIT      Test ≤ 0 → train win was chance/regime-luck")
    print("   INSUFFICIENT Too few test trades to judge")
    print()
    print(" Reminder: prices on recommendations were refreshed live. CFDs and crypto are risky.")
    print(" NOT financial advice.")

if __name__ == "__main__":
    main()
