"""
Revolut Germany — Bullish Scanner v13
======================================
What's new versus v12
---------------------
Crypto analytics strengthened so day and swing trades surface more often
  • BTC-based regime overlay for crypto.  v12 used ^GSPC for every asset
    class, but crypto routinely decouples from US equities.  v13 loads
    BTC-USD daily history once, classifies the macro state (BTC > SMA50
    AND SMA50 > SMA200 → bullish; both below → bearish), and every crypto
    instrument now uses THIS regime in its scoring instead of ^GSPC.
    Stocks/CFDs/etc. continue to use the ^GSPC regime.
  • Relative strength vs BTC.  For every altcoin v13 computes vs_btc_7d
    and vs_btc_30d (excess return over BTC).  Coins outperforming BTC by
    >5% over 7 days get +1 score; underperforming by <-5% loses 1.
    >10% over 30 days adds another +1.  BTC keeps vs_btc=0.
  • Multi-timeframe alignment bonus.  When a crypto intraday recommendation
    finds that the daily swing score AND the daytrade score also fire
    bullish (≥ MTF_ALIGNMENT_THRESHOLD), the rec is tagged ALIGNED and
    the predicted move is bumped by MTF_ALIGNMENT_BOOST (default +10%)
    to reflect the higher conviction.
  • Pump / overextension filter.  Crypto recs are dropped when the recent
    5-day return exceeds CRYPTO_OVEREXTENSION_PCT (default 30%) — no point
    chasing parabolic moves where mean reversion is the higher-probability
    outcome.

Sizing reminder
  • CRYPTO_NOTIONAL_EUR = 100 (kept from v12).  Doubling from €50 to €100
    DOUBLES absolute euro P/L but does NOT change the COUNT of opportunities
    that pass filters — Revolut crypto fees are %-based, so the break-even
    % is identical at any size.  The actual rec-count increase came from
    v12's threshold + confidence changes.

What was new versus v11 (kept from v12)
---------------------------------------
Live mode (loop, refresh every 15 min, until user stops)
  • Run with LIVE_MODE=True (default) — the scan refreshes every
    LIVE_REFRESH_MIN minutes until you press Ctrl+C.  Every refresh
    re-pulls live prices, recomputes SL/TP/notional/expected ROI, and
    tags each recommendation:
       [NEW]       — appeared this refresh
       [UPDATED]   — price moved more than LIVE_UPDATE_THRESHOLD_PCT
       [TP HIT]    — live price ≥ the prior take-profit level
       [SL HIT]    — live price ≤ the prior stop-loss level
       (no tag)    — present last refresh too, price within threshold
  • Every LIVE_FULL_SCAN_HOURS the script does a full re-scan to find
    fresh signals (default 4 h).  In between, refreshes are cheap.

Market-hours awareness
  • Each recommendation now shows when its market is open and whether
    placing the order RIGHT NOW is realistic.  Headers like
    "Market: OPEN — place now" / "Market: CLOSED — opens Mon 09:30 CET".
  • Stocks/ETFs/equity CFDs gated to local exchange hours, index/commodity
    CFDs to their futures sessions, crypto is 24/7.

Colors
  • ANSI-coloured CLI output: greens for positive net/ROI, red for SL
    warnings and overbought scores, yellow for caveats (earnings,
    breakeven close, market closed), cyan for section headers, bold
    for prices and final numbers.  Set NO_COLOR=True (or env var
    NO_COLOR=1) to disable.

Crypto fixes (you reported v11 produced zero crypto recommendations)
  • CRYPTO_NOTIONAL_EUR = 100 (was 50, doubles absolute P/L).
  • Crypto-specific confidence calibration: (score-2)/6 instead of
    (score-3)/7, and predicted-move scale 0.85 instead of 0.7.  v11
    combined those two dampeners so a score-5 setup projected only
    ~1.3% — well below the 4.5% weekly floor, so everything filtered out.
    • Fee-aware min-predicted-move floors.  The crypto move filters are now
        derived from the configured round-trip fee plus a profit buffer, so
        Free-tier accounts do not surface setups that merely break even.  With
        CRYPTO_FEE_PCT = 1.99%/side the current floors are:
             weekly   5.0% → gross €5.00, net ~€1.02
             daytrade 5.0% → gross €5.00, net ~€1.02
             intraday 5.5% → gross €5.50, net ~€1.52
  • Lowered min historical-trade counts (weekly 8, daytrade 10,
    intraday 20) so coins with sparser signal history can surface.
  • Diagnostic funnel print at every crypto stage shows
       N candidates → N passed score → N passed move → N passed OOS → N passed R:R
    so you always see *why* nothing surfaced.

Slippage and CFD spreads
  • SLIPPAGE_PCT per asset class (stocks 0.05%, equity CFDs 0.10%,
    commodity CFDs 0.15%, crypto 0.30%) applied in simulate() so the
    backtest uses realistic effective entry/exit prices, not exact closes.

Earnings filter
  • Stock recs now show ⚠ if there's an upcoming earnings date within
    the hold period (data via yf.Ticker(...).calendar).  Flag, not drop.

What was new versus v10 (kept from v11)
---------------------------------------
Three horizons for stocks (matching the crypto layout)
  • Stock WEEK     — 5-day hold, cash stocks, sized to STOCK_DAYTRADE_NOTIONAL_EUR
                     (default ~€1000).  Per-ticker train/test OOS.
  • Stock DAY      — 1-3 day hold (existing).
  • Stock INTRADAY — 4-24 hour holds on HOURLY bars for the top stocks by
                     daily score.  Stocks trade ~6.5 hours/day, so the hourly
                     bar count per name is ~30× smaller than crypto; the
                     filter is correspondingly looser on min-trade counts.

Mixed WEEK track (all asset classes)
  • 5-day hold across every OOS-robust asset class, ranked by expected ROI.
    Sits between the existing 2-week swing track and the 1-3 day daytrade
    track so you can pick a clear horizon.

The three-tier picture now reads symmetrically:
                  WEEK (5d)             DAY (1-3d)            INTRADAY (4-24h)
  Mixed           build_week_recs       build_daytrade_recs   (n/a, too mixed)
  Cash stocks     build_stock_week      build_stock_daytrade  build_stock_intraday
  Crypto         build_crypto_weekly   build_crypto_daytrade build_crypto_intraday

Everything else from v10 (88-coin crypto universe, €50 crypto sizing, live-
quote refresh, R:R floor, ROBUST test-avg floor, ADX, Donchian, regime
filter, OOS-validated stock recs) is retained.

What was new versus v9 (kept from v10)
--------------------------------------
Crypto universe
  • Expanded to ~80 coins matching what Revolut DE actually offers (BTC through
    PEPE, with TON, ARB, OP, SUI, APT, IMX, AGIX, RNDR, FET, etc.).  Some
    tokens require yfinance's disambiguating numeric suffix (e.g. TON11419,
    UNI7083, SUI20947, APT21794, ARB11841, IMX10603, STX4847, APE18876,
    PEPE24478) — those forms are used here.  Any coin that fails to
    download is silently skipped, so adding or removing coins is safe.

Trade size
  • Every crypto recommendation is sized to a target of CRYPTO_NOTIONAL_EUR
     (default €100) — both swing/weekly, daytrade and intraday.  The
     default Free-tier fee model is 1.99%/side, so the move floors stay
     comfortably above the 3.98% round-trip hurdle:
         weekly   ≥ 5.0%
         daytrade ≥ 5.0%
         intraday ≥ 5.5%
    With smaller moves a €50 crypto trade can be structurally negative
    after fees — the filter is honest about that and drops such ideas.

Three crypto horizons
  • CRYPTO_WEEKLY_HOLD_DAYS = 5  → "one-week opportunities" on daily bars.
  • CRYPTO_DAYTRADE_HOLDS  = [1, 2, 3]  → 1-3 day daytrade on daily bars.
  • CRYPTO_INTRADAY_HOLDS  = [4, 8, 12, 24]  → 4-to-24-hour intraday
    on HOURLY bars (interval=1h, period=730d).  Hourly data is only pulled
    for the top MAX_CRYPTO_INTRADAY_CANDIDATES coins by daily score, so the
    extra network cost is bounded.

Everything else from v9 (rolling RangePos, ADX, Donchian, volume-gated
breakout, regime filter, calibrated confidence, R:R floor, ROBUST test-avg
floor, OOS-validated stock recs, stock daytrade with notional sizing, and
live-quote refresh for every recommendation) is retained.

Install:  pip install yfinance pandas numpy pyarrow
Run:      python revolut_scanner_v13.py
"""

import os
import sys
import time
import hashlib
import traceback
import yfinance as yf
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone, time as dtime
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

from scanner.runtime import (
    apply_global_overrides,
    collect_cli_overrides,
    filter_assets,
    load_json_config,
    merge_runtime_overrides,
    parse_cli_args,
)
from scanner.notifications import build_notification_message, send_notifications
from scanner.quality import (
    apply_symbol_overrides,
    assess_history_quality,
    load_symbol_overrides,
    summarize_quality_rows,
)
from scanner.reporting import (
    annotate_confidence_tiers,
    build_rejection_report,
    build_run_context,
    build_run_summary,
    render_html_dashboard,
    write_dataframe_export,
    write_json_export,
    write_text_export,
)
from scanner.risk import apply_portfolio_limits

# =================== USER CONFIG ===================
STOCK_FEE_OPEN_EUR     = 1.0
STOCK_FEE_CLOSE_EUR    = 1.0
EQUITY_CFD_FEE_PCT     = 0.0025
EQUITY_CFD_FEE_MIN_EUR = 0.01
CFD_BASE_RATE_USD      = 0.045
CFD_BASE_RATE_EUR      = 0.025
CFD_MARKUP             = 0.03
CRYPTO_FEE_PCT         = 0.0199  # Revolut Standard / Free tier; Premium ≈ 0.0149

# --- Slippage (applied in simulate() so backtest reflects real prices) ---
SLIPPAGE_PCT = {
    "stock":         0.0005,   # 0.05%
    "etf":           0.0005,
    "equity_cfd":    0.0010,
    "index_cfd":     0.0005,
    "commodity_cfd": 0.0015,
    "crypto":        0.0030,   # 0.30% — Revolut crypto spreads are wide
}

HOLD_TRADING_DAYS  = 10
HOLD_CALENDAR_DAYS = 14
LOOKBACK           = "3y"
UNITS_PER_TRADE    = 1

SCORE_THRESHOLD    = 5
CORR_MAX           = 0.75
CORR_LOOKBACK_DAYS = 60
OUTDIR             = "."
INSTRUMENTS_CSV    = os.path.join(os.path.dirname(__file__), "revolut_instruments.csv")
SYMBOL_OVERRIDES_JSON = os.path.join(os.path.dirname(__file__), "config", "symbol_overrides.json")
RUN_LABEL          = ""
RUNTIME_MAX_ASSETS = 0
RUNTIME_ONLY_ASSET_CLASSES = []
RUNTIME_ONLY_TICKERS = []
REJECTION_REPORT_CSV = "rejection_report.csv"
DATA_QUALITY_REPORT_CSV = "data_quality_report.csv"
PORTFOLIO_PLAN_CSV = "portfolio_plan.csv"
RUN_SUMMARY_JSON = "run_summary.json"
DASHBOARD_HTML = "dashboard.html"

# --- yfinance download cache / concurrency ---
YF_CACHE_DIR              = os.path.join(os.path.dirname(__file__), ".yf_cache")
YF_CACHE_MAX_AGE_MINUTES  = 60
YF_INCREMENTAL_DAILY      = "10d"
YF_INCREMENTAL_INTRADAY   = "10d"
YF_DOWNLOAD_TIMEOUT_SEC   = 20
YF_DOWNLOAD_MAX_WORKERS   = 8
DISABLE_YF_CACHE          = bool(os.environ.get("DISABLE_YF_CACHE"))

SWEEP_THRESHOLDS      = [3, 4, 5, 6, 7]
SWEEP_HOLDS           = [3, 5, 10, 15, 20]
MIN_TRADES_FOR_REPORT = 10

TRAIN_FRACTION      = 0.70
MIN_TEST_TRADES     = 8
ROBUST_MIN_TEST_AVG = 0.30

N_BEST_TRADES  = 15
N_WORST_TRADES = 10

# --- Recommendations (2-week swing, mixed asset classes) ---
N_RECOMMENDATIONS  = 5
MIN_SCORE_FOR_REC  = 4
ALLOW_WEAK_CLASSES = False
STOP_LOSS_VOL_FRAC = 0.5
MIN_RR_RATIO       = 1.2

# --- Cash stock swing recommendations ---
N_STOCK_RECOMMENDATIONS = 5
MIN_STOCK_BT_TRADES     = 10
STOCK_REQUIRE_OOS       = True

# --- Mixed daytrade ---
N_DAYTRADE_RECOMMENDATIONS  = 5
DAYTRADE_SCORE_THRESHOLD    = 5
DAYTRADE_HOLDS              = [1, 2, 3]
MIN_DAYTRADE_TRADES         = 20
MIN_DAYTRADE_TEST_TRADES    = 6
DAYTRADE_STOP_LOSS_VOL_FRAC = 0.6

# --- Cash stock daytrade ---
N_STOCK_DAYTRADE_RECOMMENDATIONS = 5
STOCK_DAYTRADE_NOTIONAL_EUR      = 1000.0
STOCK_DAYTRADE_MIN_NOTIONAL      = 250.0
MIN_STOCK_DAYTRADE_TRADES        = 15
MIN_STOCK_DAYTRADE_TEST_TRADES   = 5

# --- Crypto sizing (€100 base, reduced for very high-ATR coins) ---
CRYPTO_NOTIONAL_EUR = 100.0
CRYPTO_MIN_NOTIONAL = 25.0
CRYPTO_ATR_TARGET_PCT = 6.0

# --- Crypto-specific projection (less conservative than equities) ---
CRYPTO_CONFIDENCE_DIVISOR = 6.0    # (score-2)/6 instead of (score-3)/7
CRYPTO_CONFIDENCE_OFFSET  = 2.0
CRYPTO_PRED_SCALE         = 0.85   # vs 0.70 for equities
CRYPTO_ROUND_TRIP_FEE_PCT = 2 * CRYPTO_FEE_PCT * 100.0
CRYPTO_WEEKLY_EDGE_BUFFER_PCT   = 1.0
CRYPTO_DAYTRADE_EDGE_BUFFER_PCT = 1.0
CRYPTO_INTRADAY_EDGE_BUFFER_PCT = 1.5

CRYPTO_MAJOR_TICKERS = {
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "BNB-USD",
    "ADA-USD", "DOGE-USD", "AVAX-USD", "LINK-USD", "DOT-USD",
    "LTC-USD", "BCH-USD", "MATIC-USD", "TRX-USD", "TON11419-USD",
}
CRYPTO_MAJOR_OOS_BUCKET = "crypto_major"
CRYPTO_ALT_OOS_BUCKET   = "crypto_alt"

# --- Crypto WEEKLY (~5 trading-day hold) ---
N_CRYPTO_WEEKLY_RECOMMENDATIONS = 5
CRYPTO_WEEKLY_HOLD_DAYS         = 5
CRYPTO_WEEKLY_MIN_PREDICTED_PCT = round(CRYPTO_ROUND_TRIP_FEE_PCT + CRYPTO_WEEKLY_EDGE_BUFFER_PCT, 1)
MIN_CRYPTO_WEEKLY_BT_TRADES     = 8     # was 12
MIN_CRYPTO_WEEKLY_TEST_TRADES   = 4     # was 5
CRYPTO_WEEKLY_MIN_SCORE         = 3     # was 4
CRYPTO_WEEKLY_TRADE_SUGGESTIONS_CSV = "crypto_weekly_trade_suggestions.csv"
CRYPTO_WEEKLY_TRADE_SUGGESTION_COLUMNS = [
    "generated_at", "action", "ticker", "name", "asset_class", "setup", "horizon",
    "entry_price", "currency", "market_status", "market_session",
    "market_regular_hours", "market_next_open", "market_next_close", "market_note",
    "units", "notional_eur",
    "take_profit_price", "stop_loss_price", "risk_reward",
    "expected_move_pct", "expected_roi_pct", "expected_net_eur",
    "max_loss_if_sl_eur", "tp_net_eur", "breakeven_pct", "fees_eur",
    "score", "daytrade_score", "rsi", "adx", "regime", "atr_pct",
    "vs_btc_7d_pct", "vs_btc_30d_pct", "ret7_pct",
    "bt_trades", "bt_win_rate", "bt_avg", "test_trades", "test_win_rate",
    "test_avg", "live_status", "active_signals",
]

# --- Crypto DAYTRADE (1-3 day hold, daily bars) ---
N_CRYPTO_DAYTRADE_RECOMMENDATIONS = 5
CRYPTO_DAYTRADE_HOLDS             = [1, 2, 3]
CRYPTO_DAYTRADE_SCORE_THRESHOLD   = 4     # was 5
CRYPTO_DAYTRADE_MIN_PREDICTED_PCT = round(CRYPTO_ROUND_TRIP_FEE_PCT + CRYPTO_DAYTRADE_EDGE_BUFFER_PCT, 1)
MIN_CRYPTO_DT_TRADES              = 10    # was 15
MIN_CRYPTO_DT_TEST_TRADES         = 4     # was 5

# --- Crypto INTRADAY (4-24 hour hold, hourly bars) ---
N_CRYPTO_INTRADAY_RECOMMENDATIONS  = 5
CRYPTO_INTRADAY_INTERVAL           = "1h"
CRYPTO_INTRADAY_LOOKBACK           = "730d"
CRYPTO_INTRADAY_HOLDS              = [4, 8, 12, 24]
CRYPTO_INTRADAY_SCORE_THRESHOLD    = 4     # was 5
CRYPTO_INTRADAY_MIN_PREDICTED_PCT  = round(CRYPTO_ROUND_TRIP_FEE_PCT + CRYPTO_INTRADAY_EDGE_BUFFER_PCT, 1)
MIN_CRYPTO_INTRADAY_TRADES         = 20    # was 30
MIN_CRYPTO_INTRADAY_TEST_TRADES    = 6     # was 8
MAX_CRYPTO_INTRADAY_CANDIDATES     = 25

# --- Crypto diagnostic funnel (prints why recs were filtered) ---
CRYPTO_FILTER_DIAGNOSTIC = True

INTRADAY_STOP_LOSS_VOL_FRAC = 0.7

# --- Mixed WEEK (5-day hold across all robust asset classes) ---
N_WEEK_RECOMMENDATIONS = 5
WEEK_HOLD_DAYS         = 5
WEEK_MIN_SCORE         = 4

# --- Stock WEEK (cash stocks, ~€1000 sizing, 5-day hold) ---
N_STOCK_WEEK_RECOMMENDATIONS = 5
STOCK_WEEK_HOLD_DAYS         = 5
MIN_STOCK_WEEK_TRADES        = 10
MIN_STOCK_WEEK_TEST_TRADES   = 5

# --- Stock INTRADAY (4-24 hour hold on HOURLY bars) ---
N_STOCK_INTRADAY_RECOMMENDATIONS = 5
STOCK_INTRADAY_INTERVAL          = "1h"
STOCK_INTRADAY_LOOKBACK          = "730d"
STOCK_INTRADAY_HOLDS             = [4, 8, 12, 24]      # in HOURLY bars
STOCK_INTRADAY_SCORE_THRESHOLD   = 5
STOCK_INTRADAY_MIN_PREDICTED_PCT = 0.6                 # stocks ≠ crypto vol — much smaller moves OK
MIN_STOCK_INTRADAY_TRADES        = 15                  # stocks have ~30× fewer hourly bars than crypto
MIN_STOCK_INTRADAY_TEST_TRADES   = 4
MAX_STOCK_INTRADAY_CANDIDATES    = 20

TAKE_PROFIT_AT_PRED = True
USE_REGIME_FILTER   = True
REGIME_BENCHMARK    = "^GSPC"

# --- BTC-based regime overlay for crypto ---
USE_BTC_REGIME_FOR_CRYPTO = True
BTC_REGIME_TICKER         = "BTC-USD"

# --- Relative strength vs BTC (altcoins) ---
USE_BTC_RELATIVE_STRENGTH     = True
BTC_RS_7D_BULL_THRESHOLD_PCT  = 5.0    # outperforming BTC by >5% over 7d → +1
BTC_RS_7D_BEAR_THRESHOLD_PCT  = -5.0   # underperforming BTC by <-5% over 7d → -1
BTC_RS_30D_BULL_THRESHOLD_PCT = 10.0   # outperforming BTC by >10% over 30d → +1

# --- Multi-timeframe alignment ---
USE_MTF_ALIGNMENT       = True
MTF_ALIGNMENT_THRESHOLD = 5    # daily + daytrade + intraday all ≥ this → ALIGNED
MTF_ALIGNMENT_SCORE_BONUS = 2
MTF_ALIGNMENT_BOOST     = 0.10 # +10% predicted move on aligned recs

# --- Bollinger squeeze / range-expansion for crypto ---
BB_SQUEEZE_LOOKBACK      = 80
BB_SQUEEZE_RANK_MAX      = 0.20
BB_SQUEEZE_MIN_VOL_RATIO = 1.25

# --- Crypto mean-reversion bounce track ---
N_CRYPTO_MEAN_REVERSION_RECOMMENDATIONS = 5
CRYPTO_MR_HOLDS              = [1, 2, 3, 5]
CRYPTO_MR_RSI2_MAX           = 5.0
MIN_CRYPTO_MR_TRADES         = 8
MIN_CRYPTO_MR_TEST_TRADES    = 3
CRYPTO_MR_STOP_LOSS_VOL_FRAC = 0.6

# --- Overextension / pump filter for crypto ---
CRYPTO_OVEREXTENSION_DAYS = 7
CRYPTO_OVEREXTENSION_PCT  = 30.0   # drop crypto rec if ret7 >= this %

REFRESH_LIVE_PRICES  = True
LIVE_PRICE_MAX_DRIFT = 0.15

# --- Live loop (refresh recommendations every N minutes) ---
LIVE_MODE                  = True
LIVE_REFRESH_MIN           = 15        # refresh every N minutes
LIVE_FULL_SCAN_HOURS       = 4         # full re-scan every N hours, light refresh in between
LIVE_UPDATE_THRESHOLD_PCT  = 0.30      # mark [UPDATED] if price moved more than this %
MAX_LIVE_ITERATIONS        = 0         # 0 = unlimited; otherwise stop after N refreshes
PORTFOLIO_LIMITS_ENABLED   = True
PORTFOLIO_FILTER_RECOMMENDATIONS = False
PORTFOLIO_MAX_TOTAL_RISK_EUR = 120.0
PORTFOLIO_MAX_POSITIONS_TOTAL = 10
PORTFOLIO_MAX_POSITIONS_PER_TRACK = 3
PORTFOLIO_MAX_POSITIONS_PER_ASSET_CLASS = 4
PORTFOLIO_MAX_CRYPTO_NOTIONAL_EUR = 300.0
PORTFOLIO_MAX_CORRELATION = 0.85
SNAPSHOT_RUNS              = True
GENERATE_HTML_DASHBOARD    = True
NOTIFY_WEBHOOK_URL         = ""
TELEGRAM_BOT_TOKEN         = ""
TELEGRAM_CHAT_ID           = ""

# --- ANSI colors (set NO_COLOR=True or env NO_COLOR=1 to disable) ---
NO_COLOR = bool(os.environ.get("NO_COLOR"))

# --- Earnings filter (yfinance Ticker.calendar can be flaky) ---
EARNINGS_FILTER_ENABLED = True
EARNINGS_BUFFER_DAYS    = 2   # warn if earnings within (hold_days + buffer)

# =================== ASSET UNIVERSE ===================
# (ticker, display_name, asset_class, currency)
ASSETS = [
    # --- Stocks ---
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
    # --- ETFs ---
    ("VWCE.DE","Vanguard FTSE All-World","etf","EUR"),
    ("EUNL.DE","iShares Core MSCI World","etf","EUR"),
    ("CSPX.AS","iShares Core S&P 500","etf","USD"),
    ("EQQQ.DE","Invesco Nasdaq-100","etf","EUR"),
    ("EXS1.DE","iShares Core DAX","etf","EUR"),
    # --- Equity CFDs ---
    ("AAPL","Apple CFD","equity_cfd","USD"),  ("NVDA","NVIDIA CFD","equity_cfd","USD"),
    ("TSLA","Tesla CFD","equity_cfd","USD"),  ("MSFT","Microsoft CFD","equity_cfd","USD"),
    ("AMD","AMD CFD","equity_cfd","USD"),     ("META","Meta CFD","equity_cfd","USD"),
    ("SAP.DE","SAP CFD","equity_cfd","EUR"),  ("SIE.DE","Siemens CFD","equity_cfd","EUR"),
    # --- Index CFDs ---
    ("^GSPC","S&P 500 CFD","index_cfd","USD"),
    ("^NDX","Nasdaq 100 CFD","index_cfd","USD"),
    ("^GDAXI","DAX 40 CFD","index_cfd","EUR"),
    ("^FTSE","FTSE 100 CFD","index_cfd","USD"),
    ("^N225","Nikkei 225 CFD","index_cfd","USD"),
    # --- Commodity CFDs ---
    ("GC=F","Gold CFD","commodity_cfd","USD"),
    ("SI=F","Silver CFD","commodity_cfd","USD"),
    ("CL=F","WTI Crude Oil CFD","commodity_cfd","USD"),
    ("NG=F","Natural Gas CFD","commodity_cfd","USD"),
    ("HG=F","Copper CFD","commodity_cfd","USD"),
    # --- Crypto (~80 coins available on Revolut DE) ---
    ("BTC-USD","Bitcoin","crypto","USD"),         ("ETH-USD","Ethereum","crypto","USD"),
    ("BNB-USD","BNB","crypto","USD"),             ("XRP-USD","XRP","crypto","USD"),
    ("SOL-USD","Solana","crypto","USD"),          ("ADA-USD","Cardano","crypto","USD"),
    ("DOGE-USD","Dogecoin","crypto","USD"),       ("TRX-USD","TRON","crypto","USD"),
    ("DOT-USD","Polkadot","crypto","USD"),        ("MATIC-USD","Polygon","crypto","USD"),
    ("LINK-USD","Chainlink","crypto","USD"),      ("AVAX-USD","Avalanche","crypto","USD"),
    ("LTC-USD","Litecoin","crypto","USD"),        ("BCH-USD","Bitcoin Cash","crypto","USD"),
    ("ATOM-USD","Cosmos","crypto","USD"),         ("ETC-USD","Ethereum Classic","crypto","USD"),
    ("NEAR-USD","NEAR","crypto","USD"),           ("ALGO-USD","Algorand","crypto","USD"),
    ("FIL-USD","Filecoin","crypto","USD"),        ("AAVE-USD","Aave","crypto","USD"),
    ("MKR-USD","Maker","crypto","USD"),           ("ICP-USD","Internet Computer","crypto","USD"),
    ("HBAR-USD","Hedera","crypto","USD"),         ("EGLD-USD","MultiversX","crypto","USD"),
    ("XLM-USD","Stellar","crypto","USD"),         ("XTZ-USD","Tezos","crypto","USD"),
    ("VET-USD","VeChain","crypto","USD"),         ("GRT-USD","The Graph","crypto","USD"),
    ("SAND-USD","Sandbox","crypto","USD"),        ("MANA-USD","Decentraland","crypto","USD"),
    ("AXS-USD","Axie Infinity","crypto","USD"),   ("CRV-USD","Curve","crypto","USD"),
    ("COMP-USD","Compound","crypto","USD"),       ("SNX-USD","Synthetix","crypto","USD"),
    ("YFI-USD","Yearn","crypto","USD"),           ("SUSHI-USD","SushiSwap","crypto","USD"),
    ("FTM-USD","Fantom","crypto","USD"),          ("KAVA-USD","Kava","crypto","USD"),
    ("ROSE-USD","Oasis","crypto","USD"),          ("RUNE-USD","THORChain","crypto","USD"),
    ("INJ-USD","Injective","crypto","USD"),       ("RNDR-USD","Render","crypto","USD"),
    ("FET-USD","Fetch","crypto","USD"),           ("AGIX-USD","SingularityNET","crypto","USD"),
    ("BAT-USD","Basic Attention","crypto","USD"), ("CHZ-USD","Chiliz","crypto","USD"),
    ("ENJ-USD","Enjin","crypto","USD"),           ("GALA-USD","Gala","crypto","USD"),
    ("FLOW-USD","Flow","crypto","USD"),           ("ZRX-USD","0x","crypto","USD"),
    ("GMX-USD","GMX","crypto","USD"),             ("LDO-USD","Lido","crypto","USD"),
    ("XMR-USD","Monero","crypto","USD"),          ("ZEC-USD","Zcash","crypto","USD"),
    ("DASH-USD","Dash","crypto","USD"),           ("NEO-USD","NEO","crypto","USD"),
    ("QTUM-USD","Qtum","crypto","USD"),           ("WAVES-USD","Waves","crypto","USD"),
    ("ZIL-USD","Zilliqa","crypto","USD"),         ("SHIB-USD","Shiba Inu","crypto","USD"),
    ("BAL-USD","Balancer","crypto","USD"),        ("ANKR-USD","Ankr","crypto","USD"),
    ("BAND-USD","Band","crypto","USD"),           ("EOS-USD","EOS","crypto","USD"),
    ("IOTA-USD","IOTA","crypto","USD"),           ("LRC-USD","Loopring","crypto","USD"),
    ("NMR-USD","Numeraire","crypto","USD"),       ("OMG-USD","OMG Network","crypto","USD"),
    ("OXT-USD","Orchid","crypto","USD"),          ("STORJ-USD","Storj","crypto","USD"),
    ("ICX-USD","ICON","crypto","USD"),            ("ONT-USD","Ontology","crypto","USD"),
    ("DGB-USD","DigiByte","crypto","USD"),        ("IOST-USD","IOST","crypto","USD"),
    ("LSK-USD","Lisk","crypto","USD"),            ("CRO-USD","Cronos","crypto","USD"),
    # Tokens needing yfinance disambiguation suffix
    ("UNI7083-USD","Uniswap","crypto","USD"),     ("TON11419-USD","Toncoin","crypto","USD"),
    ("ARB11841-USD","Arbitrum","crypto","USD"),   ("OP-USD","Optimism","crypto","USD"),
    ("IMX10603-USD","Immutable","crypto","USD"),  ("SUI20947-USD","Sui","crypto","USD"),
    ("APT21794-USD","Aptos","crypto","USD"),      ("APE18876-USD","ApeCoin","crypto","USD"),
    ("PEPE24478-USD","Pepe","crypto","USD"),      ("STX4847-USD","Stacks","crypto","USD"),
    ("DYDX-USD","dYdX","crypto","USD"),           ("AR-USD","Arweave","crypto","USD"),
]

ASSET_CLASSES = ["stock", "etf", "equity_cfd", "index_cfd", "commodity_cfd", "crypto"]
OOS_ASSET_CLASSES = ["stock", "etf", "equity_cfd", "index_cfd", "commodity_cfd",
                     CRYPTO_MAJOR_OOS_BUCKET, CRYPTO_ALT_OOS_BUCKET]

def crypto_segment_for_ticker(ticker):
    return "major" if ticker in CRYPTO_MAJOR_TICKERS else "alt"

def oos_asset_class_for_ticker(ticker, asset_class):
    if asset_class != "crypto":
        return asset_class
    return CRYPTO_MAJOR_OOS_BUCKET if ticker in CRYPTO_MAJOR_TICKERS else CRYPTO_ALT_OOS_BUCKET

def oos_asset_class_for_row(row):
    return oos_asset_class_for_ticker(row["ticker"], row["asset_class"])

def format_oos_asset_class(asset_class):
    return asset_class.replace("_", " ")

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

    if not any(a[2] == "crypto" for a in assets):
        for a in ASSETS:
            if a[2] == "crypto":
                assets.append(a)

    return assets

# =================== COLORS ===================
class C:
    RESET = "" if NO_COLOR else "\033[0m"
    BOLD  = "" if NO_COLOR else "\033[1m"
    DIM   = "" if NO_COLOR else "\033[2m"
    RED     = "" if NO_COLOR else "\033[31m"
    GREEN   = "" if NO_COLOR else "\033[32m"
    YELLOW  = "" if NO_COLOR else "\033[33m"
    BLUE    = "" if NO_COLOR else "\033[34m"
    MAGENTA = "" if NO_COLOR else "\033[35m"
    CYAN    = "" if NO_COLOR else "\033[36m"
    WHITE   = "" if NO_COLOR else "\033[37m"
    GREY    = "" if NO_COLOR else "\033[90m"
    BG_GREEN = "" if NO_COLOR else "\033[42m"
    BG_RED   = "" if NO_COLOR else "\033[41m"
    BG_YELLOW= "" if NO_COLOR else "\033[43m"

def colorize_pct(value, threshold_pos=0.0, threshold_neg=0.0, width=7, decimals=2):
    """Color a percentage value green if > threshold_pos, red if < threshold_neg, plain otherwise."""
    s = f"{value:>+{width}.{decimals}f}%"
    if value > threshold_pos:  return f"{C.GREEN}{s}{C.RESET}"
    if value < threshold_neg:  return f"{C.RED}{s}{C.RESET}"
    return s

def colorize_money(value, currency="EUR", width=7, decimals=2):
    s = f"{value:>+{width}.{decimals}f} {currency}"
    if value > 0:  return f"{C.GREEN}{s}{C.RESET}"
    if value < 0:  return f"{C.RED}{s}{C.RESET}"
    return s

def status_badge(status):
    if status == "NEW":      return f"{C.BG_GREEN}{C.BOLD} NEW {C.RESET}"
    if status == "UPDATED":  return f"{C.BG_YELLOW}{C.BOLD} UPDATED {C.RESET}"
    if status == "TP HIT":   return f"{C.BG_GREEN}{C.BOLD} TP HIT {C.RESET}"
    if status == "SL HIT":   return f"{C.BG_RED}{C.BOLD} SL HIT {C.RESET}"
    if status == "UNCHANGED":return f"{C.DIM}[ — ]{C.RESET}"
    return ""

# =================== MARKET HOURS ===================
MARKET_FIELD_COLUMNS = [
    "market_status", "market_session", "market_regular_hours",
    "market_next_open", "market_next_close", "market_note",
]

def _tz(name):
    if ZoneInfo is None:
        return timezone.utc
    try:
        return ZoneInfo(name)
    except Exception:
        return timezone.utc

def _fmt_market_dt(value):
    if value is None:
        return ""
    return value.strftime("%a %Y-%m-%d %H:%M %Z")

def _next_weekday_at(local, target_time, start_days=0):
    candidate = (local + timedelta(days=start_days)).replace(
        hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate

def _equity_market_info(now, session, tz_name, open_time, close_time):
    tz = _tz(tz_name)
    local = now.astimezone(tz)
    regular = f"Mon-Fri {open_time:%H:%M}-{close_time:%H:%M} {tz_name}"
    if local.weekday() >= 5:
        next_open = _next_weekday_at(local, open_time, 1)
        status = "CLOSED_WEEKEND"
        note = f"CLOSED — regular hours {regular}; next open {_fmt_market_dt(next_open)}"
        return {
            "market_status": status, "market_session": session,
            "market_regular_hours": regular, "market_next_open": _fmt_market_dt(next_open),
            "market_next_close": "", "market_note": note,
        }

    open_dt = local.replace(hour=open_time.hour, minute=open_time.minute, second=0, microsecond=0)
    close_dt = local.replace(hour=close_time.hour, minute=close_time.minute, second=0, microsecond=0)
    if local < open_dt:
        note = f"CLOSED — regular hours {regular}; opens today {_fmt_market_dt(open_dt)}"
        return {
            "market_status": "PRE_MARKET", "market_session": session,
            "market_regular_hours": regular, "market_next_open": _fmt_market_dt(open_dt),
            "market_next_close": _fmt_market_dt(close_dt), "market_note": note,
        }
    if local > close_dt:
        next_open = _next_weekday_at(local, open_time, 1)
        note = f"CLOSED — regular hours {regular}; next open {_fmt_market_dt(next_open)}"
        return {
            "market_status": "AFTER_HOURS", "market_session": session,
            "market_regular_hours": regular, "market_next_open": _fmt_market_dt(next_open),
            "market_next_close": "", "market_note": note,
        }
    note = f"OPEN — regular hours {regular}; closes {_fmt_market_dt(close_dt)}"
    return {
        "market_status": "OPEN", "market_session": session,
        "market_regular_hours": regular, "market_next_open": "",
        "market_next_close": _fmt_market_dt(close_dt), "market_note": note,
    }

def _next_futures_open(local):
    open_time = dtime(18, 0)
    if local.weekday() == 6 and local.time() < open_time:
        return local.replace(hour=18, minute=0, second=0, microsecond=0)
    days_ahead = (6 - local.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return (local + timedelta(days=days_ahead)).replace(hour=18, minute=0, second=0, microsecond=0)

def _futures_market_info(now):
    tz_name = "America/New_York"
    tz = _tz(tz_name)
    local = now.astimezone(tz)
    regular = f"Sun-Fri 18:00-17:00 {tz_name} (daily 17:00-18:00 break)"
    break_start = dtime(17, 0)
    reopen = dtime(18, 0)
    weekday = local.weekday()

    if weekday == 5 or (weekday == 4 and local.time() >= break_start) or (weekday == 6 and local.time() < reopen):
        next_open = _next_futures_open(local)
        note = f"CLOSED — regular hours {regular}; next open {_fmt_market_dt(next_open)}"
        return {
            "market_status": "CLOSED_WEEKEND", "market_session": "Commodity futures",
            "market_regular_hours": regular, "market_next_open": _fmt_market_dt(next_open),
            "market_next_close": "", "market_note": note,
        }
    if break_start <= local.time() < reopen:
        next_open = local.replace(hour=18, minute=0, second=0, microsecond=0)
        note = f"CLOSED — regular hours {regular}; daily break, reopens {_fmt_market_dt(next_open)}"
        return {
            "market_status": "CLOSED_OVERNIGHT", "market_session": "Commodity futures",
            "market_regular_hours": regular, "market_next_open": _fmt_market_dt(next_open),
            "market_next_close": "", "market_note": note,
        }

    close_dt = local.replace(hour=17, minute=0, second=0, microsecond=0)
    if local.time() >= reopen:
        close_dt += timedelta(days=1)
    note = f"OPEN — regular hours {regular}; next break/close {_fmt_market_dt(close_dt)}"
    return {
        "market_status": "OPEN", "market_session": "Commodity futures",
        "market_regular_hours": regular, "market_next_open": "",
        "market_next_close": _fmt_market_dt(close_dt), "market_note": note,
    }

def market_info(asset_class, ticker, currency, now=None):
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if asset_class == "crypto":
        return {
            "market_status": "OPEN_24_7", "market_session": "Crypto spot",
            "market_regular_hours": "24/7", "market_next_open": "",
            "market_next_close": "", "market_note": "OPEN — crypto trades 24/7; place anytime",
        }
    if ticker.endswith("=F"):
        return _futures_market_info(now)
    if ticker == "^FTSE":
        return _equity_market_info(now, "London Stock Exchange", "Europe/London", dtime(8, 0), dtime(16, 30))
    if ticker == "^N225":
        return _equity_market_info(now, "Tokyo Stock Exchange", "Asia/Tokyo", dtime(9, 0), dtime(15, 0))
    if ticker == "^GDAXI" or ticker.endswith(".DE") or ticker.endswith(".F"):
        return _equity_market_info(now, "XETRA/Frankfurt", "Europe/Berlin", dtime(9, 0), dtime(17, 30))
    if ticker.endswith(".AS"):
        return _equity_market_info(now, "Euronext Amsterdam", "Europe/Amsterdam", dtime(9, 0), dtime(17, 30))
    return _equity_market_info(now, "US equities", "America/New_York", dtime(9, 30), dtime(16, 0))

def market_status(asset_class, ticker, currency, now=None):
    info = market_info(asset_class, ticker, currency, now)
    next_open = info.get("market_next_open") or None
    return info["market_status"], next_open, info["market_note"]

def market_note_colored(asset_class, ticker, currency):
    info = market_info(asset_class, ticker, currency)
    status = info["market_status"]
    note = info["market_note"]
    if status in ("OPEN", "OPEN_24_7"):
        return f"{C.GREEN}Market: {status.replace('_24_7', ' 24/7')}{C.RESET}  ({note})"
    return f"{C.YELLOW if status in ('PRE_MARKET', 'AFTER_HOURS', 'CLOSED_OVERNIGHT') else C.RED}Market: CLOSED{C.RESET}  ({note})"

def market_info_for_row(row):
    return market_info(row["asset_class"], row["ticker"], row["currency"])

def attach_market_fields(rows):
    for row in rows:
        row.update(market_info_for_row(row))
    return rows

# =================== EARNINGS ===================
def upcoming_earnings_date(ticker, within_days=14):
    """Return next earnings date within `within_days`, or None.  Best-effort —
    yfinance calendar API is unreliable and this swallows all exceptions."""
    if not EARNINGS_FILTER_ENABLED:
        return None
    try:
        t = yf.Ticker(ticker)
        cal = t.calendar
        candidates = []
        if cal is None:
            return None
        if isinstance(cal, pd.DataFrame):
            for col in cal.columns:
                v = cal[col].iloc[0] if len(cal) else None
                if isinstance(v, (pd.Timestamp, datetime)):
                    candidates.append(v.to_pydatetime() if hasattr(v, "to_pydatetime") else v)
        elif isinstance(cal, dict):
            for k, v in cal.items():
                if "earnings" not in k.lower() and "date" not in k.lower():
                    continue
                if isinstance(v, list):
                    for vi in v:
                        if isinstance(vi, (pd.Timestamp, datetime)):
                            candidates.append(vi.to_pydatetime() if hasattr(vi, "to_pydatetime") else vi)
                elif isinstance(v, (pd.Timestamp, datetime)):
                    candidates.append(v.to_pydatetime() if hasattr(v, "to_pydatetime") else v)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        future = [d for d in candidates if d.replace(tzinfo=None) >= today
                  and (d.replace(tzinfo=None) - today).days <= within_days]
        return min(future) if future else None
    except Exception:
        return None

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

# =================== YFINANCE CACHE ===================
_CACHE_WARNING_PRINTED = False

def _safe_cache_name(ticker, period, interval):
    raw = f"{ticker}|{period}|{interval}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    safe = "".join(ch if ch.isalnum() else "_" for ch in ticker)
    return os.path.join(YF_CACHE_DIR, f"{safe}_{period}_{interval}_{digest}.parquet")

def _normalize_download(df):
    if df is None or df.empty:
        return None
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    if not keep:
        return None
    df = df[keep].dropna(how="all")
    if df.empty:
        return None
    df.index = pd.to_datetime(df.index)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df

def _read_cached_history(path):
    if DISABLE_YF_CACHE or not os.path.exists(path):
        return None
    try:
        return _normalize_download(pd.read_parquet(path))
    except Exception:
        return None

def _write_cached_history(path, df):
    global _CACHE_WARNING_PRINTED
    if DISABLE_YF_CACHE or df is None or df.empty:
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        df.to_parquet(path)
    except Exception as exc:
        if not _CACHE_WARNING_PRINTED:
            print(f"{C.YELLOW}Parquet cache unavailable ({exc}); continuing without disk cache.{C.RESET}")
            _CACHE_WARNING_PRINTED = True

def _cache_is_fresh(path):
    if not os.path.exists(path):
        return False
    age_sec = time.time() - os.path.getmtime(path)
    return age_sec <= YF_CACHE_MAX_AGE_MINUTES * 60

def _raw_yf_download(ticker, period, interval="1d"):
    kwargs = {
        "tickers": ticker,
        "period": period,
        "interval": interval,
        "progress": False,
        "auto_adjust": True,
        "threads": False,
        "timeout": YF_DOWNLOAD_TIMEOUT_SEC,
    }
    try:
        return _normalize_download(yf.download(**kwargs))
    except TypeError:
        kwargs.pop("timeout", None)
        try:
            return _normalize_download(yf.download(**kwargs))
        except Exception:
            return None
    except Exception:
        return None

def download_history(ticker, period=LOOKBACK, interval="1d"):
    path = _safe_cache_name(ticker, period, interval)
    cached = _read_cached_history(path)
    if cached is not None and _cache_is_fresh(path):
        return cached.copy()

    fetch_period = period
    if cached is not None and len(cached):
        fetch_period = YF_INCREMENTAL_INTRADAY if interval != "1d" else YF_INCREMENTAL_DAILY

    fresh = _raw_yf_download(ticker, fetch_period, interval)
    if fresh is None or fresh.empty:
        return cached.copy() if cached is not None else None

    if cached is not None and len(cached):
        merged = pd.concat([cached, fresh]).sort_index()
        merged = merged[~merged.index.duplicated(keep="last")]
    else:
        merged = fresh
    _write_cached_history(path, merged)
    return merged.copy()

def prefetch_histories(tickers, period=LOOKBACK, interval="1d", label="daily"):
    unique = sorted({t for t in tickers if t})
    if not unique:
        return {}
    workers = max(1, min(YF_DOWNLOAD_MAX_WORKERS, len(unique)))
    print(f"Downloading/caching {len(unique)} unique {label} histories with {workers} worker(s)...")
    histories = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(download_history, ticker, period, interval): ticker for ticker in unique}
        for idx, future in enumerate(as_completed(future_map), 1):
            ticker = future_map[future]
            try:
                histories[ticker] = future.result()
            except Exception:
                histories[ticker] = None
            if idx % 50 == 0 or idx == len(unique):
                print(f"  {label}: {idx}/{len(unique)} histories ready")
    return histories

# =================== REGIME ===================
def load_regime():
    if not USE_REGIME_FILTER:
        return None
    df = download_history(REGIME_BENCHMARK, LOOKBACK, "1d")
    if df is None or df.empty or len(df) < 220:
        return None
    c = df["Close"]
    s50  = sma(c, 50)
    s200 = sma(c, 200)
    regime = pd.Series(0, index=c.index, dtype=int)
    regime[(c > s50) & (s50 > s200)] =  1
    regime[(c < s50) & (s50 < s200)] = -1
    return regime

def load_btc_regime():
    """Same as load_regime but on BTC-USD. Returns (regime_series, btc_close_series)
    so callers can also use BTC's close for relative-strength computations."""
    if not USE_BTC_REGIME_FOR_CRYPTO:
        return None, None
    df = download_history(BTC_REGIME_TICKER, LOOKBACK, "1d")
    if df is None or df.empty or len(df) < 220:
        return None, None
    c = df["Close"]
    s50  = sma(c, 50)
    s200 = sma(c, 200)
    regime = pd.Series(0, index=c.index, dtype=int)
    regime[(c > s50) & (c > s200)] =  1
    regime[(c < s50) & (c < s200)] = -1
    return regime, c

def add_btc_relative_strength(df, btc_close):
    """Add vs_btc_7d and vs_btc_30d columns (excess return over BTC).
    Safe for BTC itself: the computation produces 0 on a self-comparison."""
    if btc_close is None or len(df) == 0:
        df["vs_btc_7d"]  = 0.0
        df["vs_btc_30d"] = 0.0
        return df
    btc_aligned = btc_close.reindex(df.index, method="ffill")
    btc_ret7  = btc_aligned.pct_change(7)
    btc_ret30 = btc_aligned.pct_change(30)
    crypto_ret7  = df["Close"].pct_change(7)
    crypto_ret30 = df["Close"].pct_change(30)
    df["vs_btc_7d"]  = ((crypto_ret7  - btc_ret7)  * 100.0).fillna(0.0)
    df["vs_btc_30d"] = ((crypto_ret30 - btc_ret30) * 100.0).fillna(0.0)
    return df

# =================== LIVE PRICE ===================
def get_live_price(ticker, fallback):
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
             "ATR","ATRpct","BBL","BBH","BBWidth","BBWidthRank","BBWidthSlope",
             "ret3","ret5","ret20",
             "SMA20slope","HH20","DonchH","RangePos","VolRatio",
             "ADX","ADXprev","Regime"]

DAYTRADE_CRIT_COLS = ["Close","Open","High","Low","EMA8","EMA21","RSI",
                      "RSI2","MACDhist","ATR","ATRpct","ret1","ret2",
                      "ret3","RangePos","VolRatio","ADX","Regime"]

INTRADAY_CRIT_COLS = ["Close","Open","High","Low","EMA8","EMA21","SMA20","SMA50",
                      "RSI","RSI2","MACD","MACDsig","MACDhist","ATR","ATRpct",
                      "BBL","BBH","BBWidth","BBWidthRank","BBWidthSlope",
                      "ret1","ret3","RangePos","VolRatio","ADX",
                      "ADXprev","Regime"]

def compute_score(last, prev, asset_class=None):
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
    if asset_class == "crypto":
        squeezed = (prev["BBWidthRank"] <= BB_SQUEEZE_RANK_MAX
                    and prev["BBWidthSlope"] < 0)
        if squeezed and last["Close"] > last["BBH"] and last["VolRatio"] >= BB_SQUEEZE_MIN_VOL_RATIO:
            score += 2; sig.append("bb_squeeze_range_expansion")
        elif squeezed and last["Close"] < last["BBL"] and last["VolRatio"] >= BB_SQUEEZE_MIN_VOL_RATIO:
            score -= 2; sig.append("bb_squeeze_downside_break")
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
    # Crypto-specific: relative strength vs BTC (signals named differently
    # so users can see the difference in the output's "Active signals" line)
    if asset_class == "crypto" and USE_BTC_RELATIVE_STRENGTH:
        rs7  = last.get("vs_btc_7d", 0.0)
        rs30 = last.get("vs_btc_30d", 0.0)
        if pd.notna(rs7):
            if rs7 > BTC_RS_7D_BULL_THRESHOLD_PCT:
                score += 1; sig.append(f"outperforming_btc_7d(+{rs7:.1f}%)")
            elif rs7 < BTC_RS_7D_BEAR_THRESHOLD_PCT:
                score -= 1; sig.append(f"underperforming_btc_7d({rs7:.1f}%)")
        if pd.notna(rs30) and rs30 > BTC_RS_30D_BULL_THRESHOLD_PCT:
            score += 1; sig.append(f"outperforming_btc_30d(+{rs30:.1f}%)")
    return score, sig

def precompute_scores(df, asset_class=None):
    out = np.full(len(df), np.nan)
    extra_cols = ["vs_btc_7d", "vs_btc_30d"] if asset_class == "crypto" else []
    cols = CRIT_COLS + [c for c in extra_cols if c in df.columns]
    rows = df[cols].to_dict("records")
    for i in range(1, len(df)):
        last, prev = rows[i], rows[i-1]
        if any(pd.isna(last[c]) or pd.isna(prev[c]) for c in CRIT_COLS):
            continue
        s, _ = compute_score(pd.Series(last), pd.Series(prev), asset_class=asset_class)
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

# -------- Intraday scoring (designed for HOURLY bars) --------
def compute_intraday_score(last, prev):
    """Hourly-bar scoring. SMA20 here = 20 hours (~24h), SMA50 = ~2 days.
    Trend signals use those shorter windows; macro regime still daily."""
    sig, score = [], 0
    if last["Close"] > last["EMA8"] > last["EMA21"]:      score += 2; sig.append("hourly_ema_aligned")
    if prev["EMA8"] <= prev["EMA21"] and last["EMA8"] > last["EMA21"]:
        score += 2; sig.append("fresh_ema_cross_h")
    if last["Close"] > last["SMA20"] > last["SMA50"]:     score += 1; sig.append("above_short_sma_stack")
    if last["MACDhist"] > 0 and last["MACDhist"] > prev["MACDhist"]:
        score += 1; sig.append("macd_hist_rising_h")
    if prev["MACD"] < prev["MACDsig"] and last["MACD"] > last["MACDsig"]:
        score += 2; sig.append("hourly_macd_cross")
    if 40 <= last["RSI"] <= 70:                           score += 1; sig.append("rsi_zone_h")
    if last["RSI2"] < 10 and last["Close"] > prev["Close"]:
        score += 2; sig.append("rsi2_bounce_h")
    if 0.001 < last["ret1"] < 0.025:                      score += 1; sig.append("hourly_momentum")
    if 0.003 < last["ret3"] < 0.05:                       score += 1; sig.append("3h_momentum")
    if last["Close"] > last["BBH"]:                       score += 1; sig.append("h_bb_breakout")
    squeezed = (prev["BBWidthRank"] <= BB_SQUEEZE_RANK_MAX
                and prev["BBWidthSlope"] < 0)
    if squeezed and last["Close"] > last["BBH"] and last["VolRatio"] >= BB_SQUEEZE_MIN_VOL_RATIO:
        score += 2; sig.append("h_bb_squeeze_expansion")
    if last["RangePos"] >= 0.80:                          score += 1; sig.append("near_20h_high")
    if last["VolRatio"] >= 1.30:                          score += 1; sig.append("hourly_vol_expansion")
    if last["ATRpct"] < 0.003:                            score -= 1; sig.append("too_quiet_h")
    if last["ATRpct"] > 0.04:                             score -= 1; sig.append("too_choppy_h")
    if last["RSI"] > 82 or last["ret1"] > 0.05:           score -= 2; sig.append("h_overextended")
    if last["ADX"] > 25 and last["ADX"] > last["ADXprev"]:
        score += 1; sig.append("hourly_adx_rising")
    elif last["ADX"] < 15:
        score -= 1; sig.append("hourly_adx_chop")
    if last["Regime"] == 1:                                score += 1; sig.append("daily_macro_bull")
    elif last["Regime"] == -1:                             score -= 1; sig.append("daily_macro_bear")
    return score, sig

def precompute_intraday_scores(df):
    out = np.full(len(df), np.nan)
    rows = df[INTRADAY_CRIT_COLS].to_dict("records")
    for i in range(1, len(df)):
        last, prev = rows[i], rows[i-1]
        if any(pd.isna(last[c]) or pd.isna(prev[c]) for c in INTRADAY_CRIT_COLS):
            continue
        s, _ = compute_intraday_score(last, prev)
        out[i] = s
    return pd.Series(out, index=df.index)

# =================== DATA LOAD ===================
def add_bollinger_squeeze_features(df):
    width = (df["BBH"] - df["BBL"]) / df["BBM"].replace(0, np.nan)
    df["BBWidth"] = width.replace([np.inf, -np.inf], np.nan)
    df["BBWidthRank"] = df["BBWidth"].rolling(BB_SQUEEZE_LOOKBACK).rank(pct=True)
    df["BBWidthSlope"] = df["BBWidth"] / df["BBWidth"].shift(5) - 1
    return df

def load_and_enrich(ticker, regime_series=None, btc_regime_series=None,
                    btc_close=None, asset_class=None, raw_df=None):
    df = raw_df.copy() if raw_df is not None else download_history(ticker, LOOKBACK, "1d")
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
    df = add_bollinger_squeeze_features(df)
    df["ret5"] = c.pct_change(5)
    df["ret7"] = c.pct_change(CRYPTO_OVEREXTENSION_DAYS)
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
    # Regime: crypto uses BTC's regime if available, everything else uses ^GSPC
    chosen_regime = btc_regime_series if (asset_class == "crypto"
                                          and USE_BTC_REGIME_FOR_CRYPTO
                                          and btc_regime_series is not None) else regime_series
    if chosen_regime is not None:
        df["Regime"] = chosen_regime.reindex(df.index, method="ffill").fillna(0).astype(int)
    else:
        df["Regime"] = 0
    # Relative strength vs BTC: only meaningful for crypto
    if asset_class == "crypto" and USE_BTC_RELATIVE_STRENGTH:
        df = add_btc_relative_strength(df, btc_close)
    else:
        df["vs_btc_7d"]  = 0.0
        df["vs_btc_30d"] = 0.0
    return df

def load_and_enrich_intraday(ticker, regime_series=None, raw_df=None):
    """Hourly enrichment for intraday recommendations."""
    df = raw_df.copy() if raw_df is not None else download_history(
        ticker, CRYPTO_INTRADAY_LOOKBACK, CRYPTO_INTRADAY_INTERVAL)
    if df is None or df.empty or len(df) < 300:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    c = df["Close"]
    df["EMA8"], df["EMA21"] = ema(c, 8), ema(c, 21)
    df["SMA20"], df["SMA50"] = sma(c, 20), sma(c, 50)
    df["RSI"] = rsi(c)
    df["RSI2"] = rsi(c, 2)
    m, ms, mh = macd(c)
    df["MACD"], df["MACDsig"], df["MACDhist"] = m, ms, mh
    df["ATR"] = atr(df)
    df["ATRpct"] = df["ATR"] / c
    bbl, _, bbh = bollinger(c, 20)
    bbm = sma(c, 20)
    df["BBL"], df["BBM"], df["BBH"] = bbl, bbm, bbh
    df = add_bollinger_squeeze_features(df)
    df["ret1"] = c.pct_change(1)
    df["ret3"] = c.pct_change(3)
    df["RangePos"] = rolling_position(c, df["High"], df["Low"], n=20)
    df["ADX"] = adx(df, 14)
    df["ADXprev"] = df["ADX"].shift(1)
    if "Volume" in df.columns:
        vol20 = df["Volume"].replace(0, np.nan).rolling(20).mean()
        df["VolRatio"] = (df["Volume"] / vol20).replace([np.inf, -np.inf], np.nan).fillna(1.0)
    else:
        df["VolRatio"] = 1.0
    # Daily regime → hourly via date-based ffill (avoids tz alignment headaches)
    if regime_series is not None:
        try:
            regime_dated = pd.Series(regime_series.values,
                                     index=pd.to_datetime(regime_series.index).date)
            keys = pd.DatetimeIndex(df.index).date
            df["Regime"] = regime_dated.reindex(keys).fillna(0).astype(int).values
        except Exception:
            df["Regime"] = 0
    else:
        df["Regime"] = 0
    return df

# =================== CURRENT SCAN ===================
def calibrated_confidence(score, asset_class=None):
    if asset_class == "crypto":
        return float(np.clip((score - CRYPTO_CONFIDENCE_OFFSET) / CRYPTO_CONFIDENCE_DIVISOR, 0.0, 1.0))
    return float(np.clip((score - 3) / 7.0, 0.0, 1.0))

def pred_scale_for(asset_class):
    return CRYPTO_PRED_SCALE if asset_class == "crypto" else 0.7

def crypto_notional_for_atr(atr_pct):
    if atr_pct is None or pd.isna(atr_pct) or atr_pct <= 0:
        return CRYPTO_NOTIONAL_EUR
    scale = min(1.0, CRYPTO_ATR_TARGET_PCT / max(float(atr_pct), 0.01))
    return float(np.clip(CRYPTO_NOTIONAL_EUR * scale, CRYPTO_MIN_NOTIONAL, CRYPTO_NOTIONAL_EUR))

def crypto_notional_for_row(row, atr_key="atr_pct"):
    return crypto_notional_for_atr(row.get(atr_key, np.nan))

def crypto_is_overextended(row):
    return row.get("ret7_pct", 0.0) >= CRYPTO_OVEREXTENSION_PCT

def current_crypto_mean_reversion_signal(last):
    return (pd.notna(last.get("RSI2"))
            and pd.notna(last.get("SMA50"))
            and last["RSI2"] < CRYPTO_MR_RSI2_MAX
            and last["Close"] > last["Open"]
            and last["Close"] > last["SMA50"])

def current_analysis(df, ticker, name, asset_class, currency):
    last, prev = df.iloc[-1], df.iloc[-2]
    if last[CRIT_COLS].isna().any() or prev[CRIT_COLS].isna().any():
        return None
    score, sig = compute_score(last, prev, asset_class=asset_class)
    day_score, day_sig = compute_daytrade_score(last, prev)
    atr_pct = float(last["ATR"] / last["Close"])
    vol_2w = atr_pct * np.sqrt(HOLD_TRADING_DAYS) * 100.0
    confidence = calibrated_confidence(score, asset_class)
    pred_move = confidence * vol_2w * pred_scale_for(asset_class)
    crypto_segment = crypto_segment_for_ticker(ticker) if asset_class == "crypto" else ""
    return {"ticker": ticker, "name": name, "asset_class": asset_class,
            "currency": currency, "price": float(last["Close"]),
            "score": int(score), "rsi": float(last["RSI"]),
            "adx": float(last["ADX"]) if pd.notna(last["ADX"]) else np.nan,
            "regime": int(last["Regime"]),
            "daytrade_score": int(day_score),
            "crypto_segment": crypto_segment,
            "atr_pct": atr_pct * 100.0,
            "ret7_pct": float(last.get("ret7", 0.0) * 100.0) if pd.notna(last.get("ret7", np.nan)) else 0.0,
            "vs_btc_7d_pct": float(last.get("vs_btc_7d", 0.0)) if pd.notna(last.get("vs_btc_7d", np.nan)) else 0.0,
            "vs_btc_30d_pct": float(last.get("vs_btc_30d", 0.0)) if pd.notna(last.get("vs_btc_30d", np.nan)) else 0.0,
            "mean_reversion_signal": bool(asset_class == "crypto" and current_crypto_mean_reversion_signal(last)),
            "range_pos": float(last["RangePos"]),
            "vol_ratio": float(last["VolRatio"]),
            "vol_2w_pct": vol_2w,
            "predicted_move_pct": pred_move,
            "confidence": confidence,
            "signals": ", ".join(sig),
            "daytrade_signals": ", ".join(day_sig)}

def current_intraday_analysis(df, ticker, name, asset_class, currency):
    last, prev = df.iloc[-1], df.iloc[-2]
    if last[INTRADAY_CRIT_COLS].isna().any() or prev[INTRADAY_CRIT_COLS].isna().any():
        return None
    intraday_score, sig = compute_intraday_score(last, prev)
    atr_pct = float(last["ATR"] / last["Close"])
    crypto_segment = crypto_segment_for_ticker(ticker) if asset_class == "crypto" else ""
    return {"ticker": ticker, "name": name, "asset_class": asset_class,
            "currency": currency, "price": float(last["Close"]),
            "intraday_score": int(intraday_score),
            "crypto_segment": crypto_segment,
            "intraday_rsi": float(last["RSI"]),
            "intraday_adx": float(last["ADX"]) if pd.notna(last["ADX"]) else np.nan,
            "regime": int(last["Regime"]),
            "intraday_atr_pct": atr_pct * 100.0,
            "intraday_range_pos": float(last["RangePos"]),
            "intraday_vol_ratio": float(last["VolRatio"]),
            "intraday_signals": ", ".join(sig)}

def project_pnl(row, units=UNITS_PER_TRADE):
    if row["asset_class"] == "crypto":
        notional = crypto_notional_for_row(row)
        units = notional / row["price"]
    else:
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
    if row["asset_class"] == "crypto":
        row["crypto_notional"] = notional
        row["crypto_units"] = units
    return row

# =================== SIMULATION ===================
def simulate(df, scores, asset_class, currency, threshold, hold,
             start_idx=200, end_idx=None, target_notional=None,
             charge_overnight=True, apply_slippage=True):
    """Backtest at a given threshold/hold.  When target_notional is set, position
    sizes scale to that euro target; for crypto units are fractional.  Set
    charge_overnight=False for intraday hourly bars.

    Slippage (SLIPPAGE_PCT per asset class) is applied to entry and exit when
    apply_slippage=True (default): you pay slightly more on entry and receive
    slightly less on exit, modelling spread + market impact."""
    if end_idx is None: end_idx = len(df)
    closes = df["Close"].values
    scores_arr = scores.values
    dates = df.index
    trades = []
    last_exit = start_idx - 1
    cal_days = max(1, int(round(hold * 1.4))) if charge_overnight else 0
    slip = SLIPPAGE_PCT.get(asset_class, 0.0) if apply_slippage else 0.0
    for i in range(start_idx, end_idx - hold):
        if i <= last_exit: continue
        s = scores_arr[i]
        if not np.isfinite(s) or s < threshold: continue
        entry_raw = closes[i]; exit_raw = closes[i + hold]
        if not (np.isfinite(entry_raw) and np.isfinite(exit_raw) and entry_raw > 0): continue
        # Effective long-side prices: buy higher, sell lower
        entry = entry_raw * (1 + slip)
        exit_ = exit_raw * (1 - slip)
        if target_notional and asset_class in ("stock", "etf"):
            units = max(1, int(round(target_notional / entry)))
        elif target_notional and asset_class == "crypto":
            units = target_notional / entry
        else:
            units = UNITS_PER_TRADE
        notional = entry * units
        of, cf  = fees_open_close(asset_class, notional)
        ov      = overnight_cost(asset_class, notional, currency, cal_days) if charge_overnight else 0.0
        fees    = of + cf + ov
        net     = (exit_ - entry) * units - fees
        try:
            entry_label = dates[i].strftime("%Y-%m-%d %H:%M")
            exit_label  = dates[i+hold].strftime("%Y-%m-%d %H:%M")
        except Exception:
            entry_label = str(dates[i]); exit_label = str(dates[i+hold])
        trades.append({"entry_date": entry_label, "exit_date": exit_label,
                       "score": int(s), "entry": entry, "exit": exit_,
                       "units": units, "notional": notional,
                       "fees_eur": fees, "net_pl_eur": net,
                       "ret_pct": net / notional * 100.0})
        last_exit = i + hold
    return trades

def summarize(trades):
    if not trades:
        return {"n":0, "win_rate":np.nan, "avg":np.nan, "median":np.nan,
        "total":0.0, "best":np.nan, "worst":np.nan,
        "sharpe":np.nan, "max_drawdown_pct":np.nan,
        "profit_factor":np.nan}
    r = np.array([t["ret_pct"] for t in trades])
    pnl = np.array([t["net_pl_eur"] for t in trades])
    std = float(r.std(ddof=1)) if len(r) > 1 else np.nan
    sharpe = float((r.mean() / std) * np.sqrt(len(r))) if std and np.isfinite(std) and std > 0 else np.nan
    equity = np.cumsum(r)
    peaks = np.maximum.accumulate(equity)
    max_drawdown = float((equity - peaks).min()) if len(equity) else np.nan
    gross_profit = float(pnl[pnl > 0].sum()) if len(pnl) else 0.0
    gross_loss = float(-pnl[pnl < 0].sum()) if len(pnl) else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (np.inf if gross_profit > 0 else np.nan)
    return {"n": len(trades),
            "win_rate": float((r > 0).mean() * 100),
            "avg": float(r.mean()), "median": float(np.median(r)),
            "total": float(sum(t["net_pl_eur"] for t in trades)),
        "best": float(r.max()), "worst": float(r.min()),
        "sharpe": sharpe,
        "max_drawdown_pct": max_drawdown,
        "profit_factor": float(profit_factor)}

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
def refresh_swing_prices(recs, sl_vol_frac=STOP_LOSS_VOL_FRAC,
                         crypto_notional=None, stock_notional=None):
    for r in recs:
        scan_close = r["price"]
        live = get_live_price(r["ticker"], scan_close)
        r["close_at_scan"] = scan_close
        r["price"] = live
        cls = r["asset_class"]
        if cls == "crypto" and crypto_notional:
            notional = r.get("crypto_notional", r.get("notional", crypto_notional))
            units = notional / live
        elif cls in ("stock", "etf") and stock_notional:
            units = max(1, int(round(stock_notional / live)))
            notional = live * units
        else:
            units = UNITS_PER_TRADE
            notional = live * units
        of, cf = fees_open_close(cls, notional)
        cal_days = r.get("hold_calendar_days",
                         max(1, int(round(r.get("hold_days", HOLD_TRADING_DAYS) * 1.4))))
        ov = overnight_cost(cls, notional, r["currency"], cal_days)
        fees = of + cf + ov
        gross = notional * r["predicted_move_pct"] / 100.0
        bull_g = notional * r["vol_2w_pct"] / 100.0
        r["notional"] = notional
        if cls == "crypto":
            r["crypto_units"] = units
        if cls in ("stock", "etf") and stock_notional:
            r["stock_week_units"] = units
            r["stock_week_notional"] = notional
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
    for r in recs:
        scan_close = r["price"]
        live = get_live_price(r["ticker"], scan_close)
        r["close_at_scan"] = scan_close
        r["price"] = live
        cls = r["asset_class"]
        if stock_notional and cls in ("stock", "etf"):
            units = max(1, int(round(stock_notional / live)))
        elif crypto_notional and cls == "crypto":
            notional_target = r.get("crypto_notional", r.get("daytrade_notional", crypto_notional))
            units = notional_target / live
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

def refresh_intraday_prices(recs, sl_vol_frac=INTRADAY_STOP_LOSS_VOL_FRAC,
                            crypto_notional=None):
    for r in recs:
        scan_close = r["price"]
        live = get_live_price(r["ticker"], scan_close)
        r["close_at_scan"] = scan_close
        r["price"] = live
        cls = r["asset_class"]
        if cls == "crypto" and crypto_notional:
            notional = r.get("crypto_notional", r.get("intraday_notional", crypto_notional))
            units = notional / live
        else:
            units = UNITS_PER_TRADE
            notional = live * units
        of, cf = fees_open_close(cls, notional)
        fees = of + cf  # no overnight for intraday
        gross = notional * r["intraday_predicted_move_pct"] / 100.0
        r["intraday_units"] = units
        r["intraday_notional"] = notional
        r["intraday_fees_eur"] = fees
        r["intraday_breakeven_pct"] = fees / notional * 100 if notional > 0 else np.nan
        r["intraday_predicted_net_eur"] = gross - fees
        r["intraday_expected_roi_pct"] = (gross - fees) / notional * 100 if notional > 0 else np.nan
        sl, tp, rr = trade_levels(live, r["intraday_vol_pct"],
                                  r["intraday_predicted_move_pct"], sl_vol_frac)
        r["intraday_stop_loss_price"] = sl
        r["intraday_take_profit_price"] = tp
        r["intraday_risk_reward"] = rr
    return recs

# =================== SWING RECOMMENDATIONS (mixed asset classes) ===================
def build_recommendations(scan_rows, oos_results, oos_lookup):
    robust = {r["asset_class"] for r in oos_results if r.get("verdict") == "ROBUST"}
    weak   = {r["asset_class"] for r in oos_results if r.get("verdict") == "WEAK"}
    accept = robust | (weak if ALLOW_WEAK_CLASSES else set())

    recs = []
    for r in scan_rows:
        if r["asset_class"] not in accept: continue
        if r["asset_class"] == "crypto":   continue  # crypto has dedicated tracks
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
        # Earnings warning (best-effort, swallows errors)
        earn = upcoming_earnings_date(r["ticker"], within_days=HOLD_TRADING_DAYS + EARNINGS_BUFFER_DAYS)
        earn_warn = earn.strftime("%Y-%m-%d") if earn else None
        recs.append({
            **r,
            "expected_roi_pct": roi_pct,
            "stop_loss_price": sl_price,
            "take_profit_price": tp_price,
            "risk_reward": rr,
            "bt_trades": full["n"], "bt_win_rate": full["win_rate"],
            "bt_avg": full["avg"], "bt_total": full["total"],
            "test_trades": test["n"], "test_win_rate": test["win_rate"], "test_avg": test["avg"],
            "earnings_warning": earn_warn,
        })
    recs.sort(key=lambda x: (x["expected_roi_pct"], x["bt_avg"]), reverse=True)
    return recs[:N_STOCK_RECOMMENDATIONS]

# =================== CRYPTO — WEEKLY (5-day hold, daily bars) ===================
def build_crypto_weekly_recommendations(scan_rows, enriched, scores_map,
                                        robust_classes, weak_classes):
    diag = {"start": 0, "asset_class_gate": False, "score": 0, "predicted_move": 0,
            "oos_missing": 0, "oos_full_trades": 0, "oos_full_avg": 0,
            "oos_test_trades": 0, "oos_test_avg": 0, "rr": 0, "passed": 0}
    diag["start"] = sum(1 for r in scan_rows if r["asset_class"] == "crypto")

    accepted_groups = robust_classes | (weak_classes if ALLOW_WEAK_CLASSES else set())
    crypto_groups = {CRYPTO_MAJOR_OOS_BUCKET, CRYPTO_ALT_OOS_BUCKET}
    if not (crypto_groups & accepted_groups):
        if CRYPTO_FILTER_DIAGNOSTIC:
            print(f"{C.YELLOW}[CRYPTO WEEKLY DIAGNOSTIC]{C.RESET} crypto asset class did NOT pass OOS verdict "
                  f"— continuing with per-ticker OOS only.")
    else:
        diag["asset_class_gate"] = True

    recs = []
    for r in scan_rows:
        if r["asset_class"] != "crypto": continue
        if r["score"] < CRYPTO_WEEKLY_MIN_SCORE: continue
        diag["score"] += 1
        if r["price"] <= 0: continue
        # Pump filter: don't chase coins already up 30%+ in seven days.
        if crypto_is_overextended(r):
            continue

        # Crypto-specific projection at the WEEKLY horizon
        scaled_vol = r["vol_2w_pct"] * np.sqrt(CRYPTO_WEEKLY_HOLD_DAYS / HOLD_TRADING_DAYS)
        scaled_pred = r["confidence"] * scaled_vol * pred_scale_for("crypto")
        if scaled_pred < CRYPTO_WEEKLY_MIN_PREDICTED_PCT: continue
        diag["predicted_move"] += 1

        key = (r["ticker"], r["asset_class"])
        df = enriched.get(key, (None,))[0]
        scores = scores_map.get(key)
        if df is None or scores is None:
            diag["oos_missing"] += 1
            continue

        notional = crypto_notional_for_row(r)
        oos = run_per_ticker_oos(df, scores, "crypto", r["currency"],
                                 SCORE_THRESHOLD, CRYPTO_WEEKLY_HOLD_DAYS,
                                 target_notional=notional)
        if oos is None:
            diag["oos_missing"] += 1
            continue
        full, train, test = oos
        if full["n"] < MIN_CRYPTO_WEEKLY_BT_TRADES: continue
        diag["oos_full_trades"] += 1
        if full["avg"] is None or full["avg"] <= 0: continue
        diag["oos_full_avg"] += 1
        if test["n"] < MIN_CRYPTO_WEEKLY_TEST_TRADES: continue
        diag["oos_test_trades"] += 1
        if test["avg"] is None or test["avg"] <= 0: continue
        diag["oos_test_avg"] += 1

        units = notional / r["price"]
        of, cf = fees_open_close("crypto", notional)
        fees = of + cf
        gross = notional * scaled_pred / 100.0
        bull_g = notional * scaled_vol / 100.0
        predicted_net_eur = gross - fees
        if predicted_net_eur <= 0: continue
        breakeven_pct = fees / notional * 100

        sl_price, tp_price, rr = trade_levels(
            r["price"], scaled_vol, scaled_pred, STOP_LOSS_VOL_FRAC)
        if pd.isna(rr) or rr < MIN_RR_RATIO:
            continue
        diag["rr"] += 1
        diag["passed"] += 1

        recs.append({
            **r,
            "oos_bucket": oos_asset_class_for_row(r),
            "hold_days": CRYPTO_WEEKLY_HOLD_DAYS,
            "vol_2w_pct": scaled_vol,            # repurposed: hold-period vol
            "predicted_move_pct": scaled_pred,
            "crypto_units": units,
            "crypto_notional": notional,
            "notional": notional,
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
    if CRYPTO_FILTER_DIAGNOSTIC:
        print(f"{C.CYAN}[CRYPTO WEEKLY FUNNEL]{C.RESET} "
              f"{diag['start']} candidates → {diag['score']} passed score≥{CRYPTO_WEEKLY_MIN_SCORE}"
              f" → {diag['predicted_move']} passed move≥{CRYPTO_WEEKLY_MIN_PREDICTED_PCT}%"
              f" → {diag['oos_full_avg']} OOS-profitable full"
              f" → {diag['oos_test_avg']} OOS-profitable test"
              f" → {diag['rr']} passed R:R≥{MIN_RR_RATIO}"
              f" → {C.BOLD}{diag['passed']} surfaced{C.RESET}")
    return recs[:N_CRYPTO_WEEKLY_RECOMMENDATIONS]

def build_crypto_weekly_trade_suggestions(recs):
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    suggestions = []
    for r in recs:
        units = r.get("crypto_units", r.get("notional", CRYPTO_NOTIONAL_EUR) / r["price"])
        fees = r.get("total_fees", 0.0)
        max_loss_if_sl = -((r["price"] - r["stop_loss_price"]) * units + fees)
        tp_net = (r["take_profit_price"] - r["price"]) * units - fees
        market = market_info_for_row(r)
        suggestions.append({
            "generated_at": generated_at,
            "action": "BUY",
            "ticker": r["ticker"],
            "name": r["name"],
            "asset_class": r["asset_class"],
            "setup": "crypto_weekly_trend",
            "horizon": f"{int(r.get('hold_days', CRYPTO_WEEKLY_HOLD_DAYS))}d",
            "entry_price": r["price"],
            "currency": r["currency"],
            **market,
            "units": units,
            "notional_eur": r.get("notional", r.get("crypto_notional", np.nan)),
            "take_profit_price": r["take_profit_price"],
            "stop_loss_price": r["stop_loss_price"],
            "risk_reward": r.get("risk_reward", np.nan),
            "expected_move_pct": r.get("predicted_move_pct", np.nan),
            "expected_roi_pct": r.get("expected_roi_pct", np.nan),
            "expected_net_eur": r.get("predicted_net_eur", np.nan),
            "max_loss_if_sl_eur": max_loss_if_sl,
            "tp_net_eur": tp_net,
            "breakeven_pct": r.get("breakeven_pct", np.nan),
            "fees_eur": fees,
            "score": r.get("score", np.nan),
            "daytrade_score": r.get("daytrade_score", np.nan),
            "rsi": r.get("rsi", np.nan),
            "adx": r.get("adx", np.nan),
            "regime": r.get("regime", np.nan),
            "atr_pct": r.get("atr_pct", np.nan),
            "vs_btc_7d_pct": r.get("vs_btc_7d_pct", 0.0),
            "vs_btc_30d_pct": r.get("vs_btc_30d_pct", 0.0),
            "ret7_pct": r.get("ret7_pct", 0.0),
            "bt_trades": r.get("bt_trades", np.nan),
            "bt_win_rate": r.get("bt_win_rate", np.nan),
            "bt_avg": r.get("bt_avg", np.nan),
            "test_trades": r.get("test_trades", np.nan),
            "test_win_rate": r.get("test_win_rate", np.nan),
            "test_avg": r.get("test_avg", np.nan),
            "live_status": r.get("live_status", ""),
            "active_signals": r.get("signals", ""),
        })
    return suggestions

# =================== MIXED DAYTRADE (excl. crypto) ===================
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
    confidence = calibrated_confidence(row["daytrade_score"], cls)
    scaled_vol = row["vol_2w_pct"] * np.sqrt(hold_days / HOLD_TRADING_DAYS)
    predicted_move_pct = confidence * scaled_vol * pred_scale_for(cls)
    gross = notional * predicted_move_pct / 100.0
    sl_price, tp_price, rr = trade_levels(
        row["price"], scaled_vol, predicted_move_pct, DAYTRADE_STOP_LOSS_VOL_FRAC)
    out = {
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
    if cls == "crypto":
        out["crypto_notional"] = notional
    return out

def build_daytrade_recommendations(scan_rows, enriched, day_scores_map):
    scan_lookup = {
        (r["ticker"], r["asset_class"]): r
        for r in scan_rows
        if r["daytrade_score"] >= DAYTRADE_SCORE_THRESHOLD and r["notional"] > 0
    }
    recs = []
    for key, r in scan_lookup.items():
        if r["asset_class"] == "crypto": continue
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

# =================== CRYPTO DAYTRADE (1-3 day, daily bars) ===================
def build_crypto_daytrade_recommendations(scan_rows, enriched, day_scores_map):
    diag = {"start": 0, "score": 0, "oos": 0, "move": 0, "rr": 0, "passed": 0}
    diag["start"] = sum(1 for r in scan_rows if r["asset_class"] == "crypto")
    recs = []
    for r in scan_rows:
        if r["asset_class"] != "crypto": continue
        if r["daytrade_score"] < CRYPTO_DAYTRADE_SCORE_THRESHOLD: continue
        diag["score"] += 1
        if r["price"] <= 0: continue
        # Pump filter: don't chase coins already up 30%+ in seven days.
        if crypto_is_overextended(r):
            continue

        notional = crypto_notional_for_row(r)
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
                            target_notional=notional)
            train = simulate(df, scores, "crypto", currency,
                             CRYPTO_DAYTRADE_SCORE_THRESHOLD, hold, warmup, split,
                             target_notional=notional)
            test = simulate(df, scores, "crypto", currency,
                            CRYPTO_DAYTRADE_SCORE_THRESHOLD, hold, split, n,
                            target_notional=notional)
            fs, trs, ts = summarize(full), summarize(train), summarize(test)
            if fs["n"] < MIN_CRYPTO_DT_TRADES: continue
            if ts["n"] < MIN_CRYPTO_DT_TEST_TRADES: continue
            if fs["avg"] <= 0 or ts["avg"] <= 0 or trs["avg"] <= 0: continue

            diag["oos"] += 1
            cand = project_daytrade(r, hold, target_notional=notional)
            if cand["daytrade_predicted_move_pct"] < CRYPTO_DAYTRADE_MIN_PREDICTED_PCT:
                continue
            diag["move"] += 1
            if cand["daytrade_predicted_net_eur"] <= 0: continue
            if pd.isna(cand["daytrade_risk_reward"]) or cand["daytrade_risk_reward"] < MIN_RR_RATIO:
                continue
            diag["rr"] += 1
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
            diag["passed"] += 1

    recs.sort(key=lambda x: (x["daytrade_expected_roi_pct"], x.get("crypto_dt_test_avg", 0)),
              reverse=True)
    if CRYPTO_FILTER_DIAGNOSTIC:
        print(f"{C.CYAN}[CRYPTO DAYTRADE FUNNEL]{C.RESET} "
              f"{diag['start']} candidates → {diag['score']} passed dt-score≥{CRYPTO_DAYTRADE_SCORE_THRESHOLD}"
              f" → {diag['oos']} passed OOS"
              f" → {diag['move']} passed move≥{CRYPTO_DAYTRADE_MIN_PREDICTED_PCT}%"
              f" → {diag['rr']} passed R:R"
              f" → {C.BOLD}{diag['passed']} surfaced{C.RESET}")
    return recs[:N_CRYPTO_DAYTRADE_RECOMMENDATIONS]

# =================== CRYPTO MEAN REVERSION (oversold bounce) ===================
def precompute_crypto_mean_reversion_scores(df):
    signal = ((df["RSI2"] < CRYPTO_MR_RSI2_MAX)
              & (df["Close"] > df["Open"])
              & (df["Close"] > df["SMA50"]))
    return signal.astype(float).where(signal.notna(), np.nan)

def build_crypto_mean_reversion_recommendations(scan_rows, enriched):
    diag = {"start": 0, "signal": 0, "oos": 0, "passed": 0}
    diag["start"] = sum(1 for r in scan_rows if r["asset_class"] == "crypto")
    recs = []
    for r in scan_rows:
        if r["asset_class"] != "crypto": continue
        if not r.get("mean_reversion_signal", False): continue
        if crypto_is_overextended(r): continue
        diag["signal"] += 1

        key = (r["ticker"], r["asset_class"])
        df, currency, _name = enriched.get(key, (None, None, None))
        if df is None: continue
        scores = precompute_crypto_mean_reversion_scores(df)
        if not np.isfinite(scores.iloc[-1]) or scores.iloc[-1] < 1: continue

        n = len(df); warmup = 200
        if n - warmup < 30: continue
        split = warmup + int((n - warmup) * TRAIN_FRACTION)
        notional = crypto_notional_for_row(r)

        best = None
        for hold in CRYPTO_MR_HOLDS:
            full = simulate(df, scores, "crypto", currency, 1, hold, warmup, n,
                            target_notional=notional)
            train = simulate(df, scores, "crypto", currency, 1, hold, warmup, split,
                             target_notional=notional)
            test = simulate(df, scores, "crypto", currency, 1, hold, split, n,
                            target_notional=notional)
            fs, trs, ts = summarize(full), summarize(train), summarize(test)
            if fs["n"] < MIN_CRYPTO_MR_TRADES: continue
            if ts["n"] < MIN_CRYPTO_MR_TEST_TRADES: continue
            if fs["avg"] <= 0 or ts["avg"] <= 0 or trs["avg"] <= 0: continue
            diag["oos"] += 1

            expected_roi_pct = min(fs["avg"], ts["avg"])
            fees_pct = 2 * CRYPTO_FEE_PCT * 100.0
            predicted_move_pct = max(expected_roi_pct + fees_pct, fees_pct + 0.01)
            vol_pct = r["atr_pct"] * np.sqrt(hold)
            gross = notional * predicted_move_pct / 100.0
            of, cf = fees_open_close("crypto", notional)
            fees = of + cf
            predicted_net_eur = gross - fees
            if predicted_net_eur <= 0: continue

            sl, tp, rr = trade_levels(r["price"], vol_pct, predicted_move_pct,
                                      CRYPTO_MR_STOP_LOSS_VOL_FRAC)
            if pd.isna(rr) or rr < MIN_RR_RATIO: continue

            units = notional / r["price"]
            cand = {
                **r,
                "setup": "crypto_mean_reversion",
                "hold_days": hold,
                "crypto_units": units,
                "crypto_notional": notional,
                "notional": notional,
                "vol_2w_pct": vol_pct,
                "predicted_move_pct": predicted_move_pct,
                "open_fee": of,
                "close_fee": cf,
                "overnight": 0.0,
                "total_fees": fees,
                "breakeven_pct": fees / notional * 100,
                "predicted_net_eur": predicted_net_eur,
                "expected_roi_pct": predicted_net_eur / notional * 100,
                "stop_loss_price": sl,
                "take_profit_price": tp,
                "risk_reward": rr,
                "mr_full_trades": fs["n"], "mr_full_win_rate": fs["win_rate"],
                "mr_full_avg": fs["avg"], "mr_full_median": fs["median"],
                "mr_train_trades": trs["n"], "mr_train_avg": trs["avg"],
                "mr_test_trades": ts["n"], "mr_test_win_rate": ts["win_rate"],
                "mr_test_avg": ts["avg"],
            }
            if best is None or cand["expected_roi_pct"] > best["expected_roi_pct"]:
                best = cand
        if best is not None:
            recs.append(best)
            diag["passed"] += 1

    recs.sort(key=lambda x: (x["expected_roi_pct"], x.get("mr_test_avg", 0)), reverse=True)
    if CRYPTO_FILTER_DIAGNOSTIC:
        print(f"{C.CYAN}[CRYPTO MEAN-REVERSION FUNNEL]{C.RESET} "
              f"{diag['start']} candidates → {diag['signal']} live RSI2<{CRYPTO_MR_RSI2_MAX:g} bounce signals"
              f" → {diag['oos']} passed OOS"
              f" → {C.BOLD}{diag['passed']} surfaced{C.RESET}")
    return recs[:N_CRYPTO_MEAN_REVERSION_RECOMMENDATIONS]

# =================== CRYPTO INTRADAY (hourly bars) ===================
def build_crypto_intraday_recommendations(crypto_candidates, regime_series, hourly_histories=None):
    """For each crypto candidate, pull hourly bars, score on those bars,
    OOS-validate at each hold horizon in CRYPTO_INTRADAY_HOLDS hours, and
    emit a recommendation if any horizon passes."""
    diag = {"start": len(crypto_candidates), "hourly_data": 0, "score": 0,
            "oos": 0, "move": 0, "rr": 0, "passed": 0}
    recs = []
    hourly_histories = hourly_histories or {}
    for r in crypto_candidates:
        ticker = r["ticker"]
        if crypto_is_overextended(r):
            continue
        df = load_and_enrich_intraday(ticker, regime_series, raw_df=hourly_histories.get(ticker))
        if df is None: continue
        diag["hourly_data"] += 1
        scores = precompute_intraday_scores(df)

        n = len(df); warmup = 200
        if n - warmup < 100: continue
        split = warmup + int((n - warmup) * TRAIN_FRACTION)

        # Current intraday analysis (latest hourly bar)
        current = current_intraday_analysis(df, ticker, r["name"], "crypto", r["currency"])
        if current is None: continue
        raw_intraday_score = current["intraday_score"]
        mtf_aligned = (USE_MTF_ALIGNMENT
                       and r["score"] >= MTF_ALIGNMENT_THRESHOLD
                       and r["daytrade_score"] >= MTF_ALIGNMENT_THRESHOLD
                       and raw_intraday_score >= MTF_ALIGNMENT_THRESHOLD)
        if mtf_aligned:
            current["intraday_score"] += MTF_ALIGNMENT_SCORE_BONUS
            current["intraday_signals"] = (current["intraday_signals"] + ", " if current["intraday_signals"] else "") \
                + f"mtf_alignment_bonus(+{MTF_ALIGNMENT_SCORE_BONUS})"
        if current["intraday_score"] < CRYPTO_INTRADAY_SCORE_THRESHOLD: continue
        diag["score"] += 1

        notional = crypto_notional_for_atr(current["intraday_atr_pct"])
        best = None
        for hold_h in CRYPTO_INTRADAY_HOLDS:
            full = simulate(df, scores, "crypto", r["currency"],
                            CRYPTO_INTRADAY_SCORE_THRESHOLD, hold_h, warmup, n,
                            target_notional=notional,
                            charge_overnight=False)
            train = simulate(df, scores, "crypto", r["currency"],
                             CRYPTO_INTRADAY_SCORE_THRESHOLD, hold_h, warmup, split,
                             target_notional=notional,
                             charge_overnight=False)
            test = simulate(df, scores, "crypto", r["currency"],
                            CRYPTO_INTRADAY_SCORE_THRESHOLD, hold_h, split, n,
                            target_notional=notional,
                            charge_overnight=False)
            fs, trs, ts = summarize(full), summarize(train), summarize(test)
            if fs["n"] < MIN_CRYPTO_INTRADAY_TRADES: continue
            if ts["n"] < MIN_CRYPTO_INTRADAY_TEST_TRADES: continue
            if fs["avg"] <= 0 or ts["avg"] <= 0 or trs["avg"] <= 0: continue

            diag["oos"] += 1
            # Project a candidate at this hold horizon
            confidence = calibrated_confidence(current["intraday_score"], "crypto")
            atr_pct = current["intraday_atr_pct"] / 100.0
            scaled_vol_pct = atr_pct * np.sqrt(hold_h) * 100.0
            predicted_move_pct = confidence * scaled_vol_pct * pred_scale_for("crypto")
            if mtf_aligned:
                predicted_move_pct *= (1.0 + MTF_ALIGNMENT_BOOST)
            if predicted_move_pct < CRYPTO_INTRADAY_MIN_PREDICTED_PCT: continue
            diag["move"] += 1

            units = notional / current["price"]
            of, cf = fees_open_close("crypto", notional)
            fees = of + cf  # no overnight on intraday
            gross = notional * predicted_move_pct / 100.0
            predicted_net_eur = gross - fees
            if predicted_net_eur <= 0: continue

            sl, tp, rr = trade_levels(current["price"], scaled_vol_pct,
                                      predicted_move_pct,
                                      INTRADAY_STOP_LOSS_VOL_FRAC)
            if pd.isna(rr) or rr < MIN_RR_RATIO: continue
            diag["rr"] += 1

            cand = {
                **current,
                "score": r["score"],            # carry over daily swing score for context
                "mtf_aligned": mtf_aligned,
                "vs_btc_7d_pct": r.get("vs_btc_7d_pct", 0.0),
                "vs_btc_30d_pct": r.get("vs_btc_30d_pct", 0.0),
                "ret7_pct": r.get("ret7_pct", 0.0),
                "rsi": current["intraday_rsi"],
                "adx": current["intraday_adx"],
                "regime": current["regime"],
                "daytrade_score": r["daytrade_score"],
                "hold_hours": hold_h,
                "crypto_notional": notional,
                "intraday_units": units,
                "intraday_notional": notional,
                "intraday_vol_pct": scaled_vol_pct,
                "intraday_predicted_move_pct": predicted_move_pct,
                "intraday_fees_eur": fees,
                "intraday_breakeven_pct": fees / notional * 100,
                "intraday_predicted_net_eur": predicted_net_eur,
                "intraday_expected_roi_pct": predicted_net_eur / notional * 100,
                "intraday_stop_loss_price": sl,
                "intraday_take_profit_price": tp,
                "intraday_risk_reward": rr,
                "intraday_bt_trades": fs["n"], "intraday_bt_win_rate": fs["win_rate"],
                "intraday_bt_avg": fs["avg"], "intraday_bt_median": fs["median"],
                "intraday_train_trades": trs["n"], "intraday_train_avg": trs["avg"],
                "intraday_test_trades": ts["n"], "intraday_test_win_rate": ts["win_rate"],
                "intraday_test_avg": ts["avg"],
            }
            if best is None or cand["intraday_expected_roi_pct"] > best["intraday_expected_roi_pct"]:
                best = cand
        if best is not None:
            recs.append(best)
            diag["passed"] += 1

    recs.sort(key=lambda x: (x["intraday_expected_roi_pct"], x.get("intraday_test_avg", 0)),
              reverse=True)
    if CRYPTO_FILTER_DIAGNOSTIC:
        print(f"{C.CYAN}[CRYPTO INTRADAY FUNNEL]{C.RESET} "
              f"{diag['start']} candidates → {diag['hourly_data']} had hourly data"
              f" → {diag['score']} passed intra-score≥{CRYPTO_INTRADAY_SCORE_THRESHOLD}"
              f" → {diag['oos']} passed OOS"
              f" → {diag['move']} passed move≥{CRYPTO_INTRADAY_MIN_PREDICTED_PCT}%"
              f" → {C.BOLD}{diag['passed']} surfaced{C.RESET}")
    return recs[:N_CRYPTO_INTRADAY_RECOMMENDATIONS]

# =================== MIXED WEEK (5-day hold, all asset classes) ===================
def build_week_recommendations(scan_rows, enriched, scores_map, oos_results, oos_lookup):
    """5-day-hold recommendations across every OOS-robust asset class.
    Crypto has its own dedicated weekly track and is excluded here."""
    robust = {r["asset_class"] for r in oos_results if r.get("verdict") == "ROBUST"}
    weak   = {r["asset_class"] for r in oos_results if r.get("verdict") == "WEAK"}
    accept = robust | (weak if ALLOW_WEAK_CLASSES else set())

    recs = []
    for r in scan_rows:
        if r["asset_class"] not in accept: continue
        if r["asset_class"] == "crypto":   continue
        if r["score"] < WEEK_MIN_SCORE:    continue
        if r["price"] <= 0:                continue

        # Re-scale move and vol from the 2-week baseline to the 1-week horizon
        scaled_vol = r["vol_2w_pct"] * np.sqrt(WEEK_HOLD_DAYS / HOLD_TRADING_DAYS)
        scaled_pred = r["confidence"] * scaled_vol * 0.7

        key = (r["ticker"], r["asset_class"])
        df = enriched.get(key, (None,))[0]
        scores = scores_map.get(key)
        if df is None or scores is None: continue

        # Per-ticker OOS at the 5-day horizon
        oos_ticker = run_per_ticker_oos(df, scores, r["asset_class"], r["currency"],
                                        SCORE_THRESHOLD, WEEK_HOLD_DAYS)
        if oos_ticker is None: continue
        full, train, test = oos_ticker
        if full["n"] < MIN_TRADES_FOR_REPORT: continue
        if full["avg"] is None or full["avg"] <= 0: continue
        if test["n"] < MIN_TEST_TRADES: continue
        if test["avg"] is None or test["avg"] <= 0: continue

        # Project P/L at the 5-day horizon
        units = UNITS_PER_TRADE
        notional = r["price"] * units
        of, cf = fees_open_close(r["asset_class"], notional)
        cal_days = max(1, int(round(WEEK_HOLD_DAYS * 1.4)))
        ov = overnight_cost(r["asset_class"], notional, r["currency"], cal_days)
        fees = of + cf + ov
        gross = notional * scaled_pred / 100.0
        predicted_net = gross - fees
        if predicted_net <= 0: continue

        sl, tp, rr = trade_levels(r["price"], scaled_vol, scaled_pred, STOP_LOSS_VOL_FRAC)
        if pd.isna(rr) or rr < MIN_RR_RATIO: continue

        recs.append({
            **r,
            "hold_days": WEEK_HOLD_DAYS,
            "vol_2w_pct": scaled_vol,
            "predicted_move_pct": scaled_pred,
            "notional": notional,
            "open_fee": of, "close_fee": cf, "overnight": ov,
            "total_fees": fees,
            "breakeven_pct": fees / notional * 100 if notional > 0 else np.nan,
            "predicted_net_eur": predicted_net,
            "bull_case_net_eur": notional * scaled_vol / 100 - fees,
            "bear_case_net_eur": -notional * scaled_vol / 100 - fees,
            "expected_roi_pct": predicted_net / notional * 100,
            "stop_loss_price": sl,
            "take_profit_price": tp,
            "risk_reward": rr,
            "week_bt_trades": full["n"], "week_bt_win_rate": full["win_rate"],
            "week_bt_avg": full["avg"],
            "week_test_trades": test["n"], "week_test_win_rate": test["win_rate"],
            "week_test_avg": test["avg"],
            "oos_class_thr": oos_lookup.get(r["asset_class"], {}).get("thr"),
        })
    recs.sort(key=lambda x: x["expected_roi_pct"], reverse=True)
    return recs[:N_WEEK_RECOMMENDATIONS]

# =================== STOCK WEEK (cash stocks, 5-day hold, sized) ===================
def build_stock_week_recommendations(scan_rows, enriched, scores_map, robust_classes, weak_classes):
    """5-day cash-stock recs sized at STOCK_DAYTRADE_NOTIONAL_EUR (~€1000),
    so fixed 1+1 EUR fees stay <0.3% of notional."""
    if "stock" not in (robust_classes | (weak_classes if ALLOW_WEAK_CLASSES else set())):
        return []

    recs = []
    for r in scan_rows:
        if r["asset_class"] != "stock":    continue
        if r["score"] < WEEK_MIN_SCORE:    continue
        if r["price"] <= 0:                continue

        units = max(1, int(round(STOCK_DAYTRADE_NOTIONAL_EUR / r["price"])))
        notional = r["price"] * units
        if notional < STOCK_DAYTRADE_MIN_NOTIONAL: continue

        key = (r["ticker"], r["asset_class"])
        df = enriched.get(key, (None,))[0]
        scores = scores_map.get(key)
        if df is None or scores is None: continue

        oos = run_per_ticker_oos(df, scores, "stock", r["currency"],
                                 SCORE_THRESHOLD, STOCK_WEEK_HOLD_DAYS,
                                 target_notional=STOCK_DAYTRADE_NOTIONAL_EUR)
        if oos is None: continue
        full, train, test = oos
        if full["n"] < MIN_STOCK_WEEK_TRADES: continue
        if full["avg"] is None or full["avg"] <= 0: continue
        if test["n"] < MIN_STOCK_WEEK_TEST_TRADES: continue
        if test["avg"] is None or test["avg"] <= 0: continue
        if train["avg"] is None or train["avg"] <= 0: continue

        scaled_vol = r["vol_2w_pct"] * np.sqrt(STOCK_WEEK_HOLD_DAYS / HOLD_TRADING_DAYS)
        scaled_pred = r["confidence"] * scaled_vol * 0.7
        gross = notional * scaled_pred / 100.0
        of, cf = fees_open_close("stock", notional)
        fees = of + cf  # no overnight on cash stocks
        predicted_net = gross - fees
        if predicted_net <= 0: continue

        sl, tp, rr = trade_levels(r["price"], scaled_vol, scaled_pred, STOP_LOSS_VOL_FRAC)
        if pd.isna(rr) or rr < MIN_RR_RATIO: continue

        recs.append({
            **r,
            "hold_days": STOCK_WEEK_HOLD_DAYS,
            "vol_2w_pct": scaled_vol,
            "predicted_move_pct": scaled_pred,
            "stock_week_units": units,
            "stock_week_notional": notional,
            "notional": notional,
            "total_fees": fees,
            "breakeven_pct": fees / notional * 100,
            "predicted_net_eur": predicted_net,
            "expected_roi_pct": predicted_net / notional * 100,
            "stop_loss_price": sl,
            "take_profit_price": tp,
            "risk_reward": rr,
            "sw_full_trades": full["n"], "sw_full_win_rate": full["win_rate"],
            "sw_full_avg": full["avg"],
            "sw_train_trades": train["n"], "sw_train_avg": train["avg"],
            "sw_test_trades": test["n"], "sw_test_win_rate": test["win_rate"],
            "sw_test_avg": test["avg"],
        })
    recs.sort(key=lambda x: (x["expected_roi_pct"], x["sw_test_avg"]), reverse=True)
    return recs[:N_STOCK_WEEK_RECOMMENDATIONS]

# =================== STOCK INTRADAY (4-24 hour hold on HOURLY bars) ===================
def load_and_enrich_intraday_stock(ticker, regime_series=None, raw_df=None):
    """Hourly enrichment for stocks. Same fields as crypto intraday."""
    df = raw_df.copy() if raw_df is not None else download_history(
        ticker, STOCK_INTRADAY_LOOKBACK, STOCK_INTRADAY_INTERVAL)
    if df is None or df.empty or len(df) < 200:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    c = df["Close"]
    df["EMA8"], df["EMA21"] = ema(c, 8), ema(c, 21)
    df["SMA20"], df["SMA50"] = sma(c, 20), sma(c, 50)
    df["RSI"] = rsi(c)
    df["RSI2"] = rsi(c, 2)
    m, ms, mh = macd(c)
    df["MACD"], df["MACDsig"], df["MACDhist"] = m, ms, mh
    df["ATR"] = atr(df)
    df["ATRpct"] = df["ATR"] / c
    bbl, _, bbh = bollinger(c, 20)
    bbm = sma(c, 20)
    df["BBL"], df["BBM"], df["BBH"] = bbl, bbm, bbh
    df = add_bollinger_squeeze_features(df)
    df["ret1"] = c.pct_change(1)
    df["ret3"] = c.pct_change(3)
    df["RangePos"] = rolling_position(c, df["High"], df["Low"], n=20)
    df["ADX"] = adx(df, 14)
    df["ADXprev"] = df["ADX"].shift(1)
    if "Volume" in df.columns:
        vol20 = df["Volume"].replace(0, np.nan).rolling(20).mean()
        df["VolRatio"] = (df["Volume"] / vol20).replace([np.inf, -np.inf], np.nan).fillna(1.0)
    else:
        df["VolRatio"] = 1.0
    if regime_series is not None:
        try:
            regime_dated = pd.Series(regime_series.values,
                                     index=pd.to_datetime(regime_series.index).date)
            keys = pd.DatetimeIndex(df.index).date
            df["Regime"] = regime_dated.reindex(keys).fillna(0).astype(int).values
        except Exception:
            df["Regime"] = 0
    else:
        df["Regime"] = 0
    return df

def build_stock_intraday_recommendations(stock_candidates, regime_series, hourly_histories=None):
    """Hourly-bar intraday for top stocks. Sized at STOCK_DAYTRADE_NOTIONAL_EUR."""
    recs = []
    hourly_histories = hourly_histories or {}
    for r in stock_candidates:
        ticker = r["ticker"]
        df = load_and_enrich_intraday_stock(ticker, regime_series, raw_df=hourly_histories.get(ticker))
        if df is None: continue
        scores = precompute_intraday_scores(df)

        n = len(df); warmup = 100  # smaller warmup — fewer hourly bars per stock
        if n - warmup < 50: continue
        split = warmup + int((n - warmup) * TRAIN_FRACTION)

        current = current_intraday_analysis(df, ticker, r["name"], "stock", r["currency"])
        if current is None: continue
        if current["intraday_score"] < STOCK_INTRADAY_SCORE_THRESHOLD: continue

        units = max(1, int(round(STOCK_DAYTRADE_NOTIONAL_EUR / current["price"])))
        notional = current["price"] * units
        if notional < STOCK_DAYTRADE_MIN_NOTIONAL: continue

        best = None
        for hold_h in STOCK_INTRADAY_HOLDS:
            full = simulate(df, scores, "stock", r["currency"],
                            STOCK_INTRADAY_SCORE_THRESHOLD, hold_h, warmup, n,
                            target_notional=STOCK_DAYTRADE_NOTIONAL_EUR,
                            charge_overnight=False)
            train = simulate(df, scores, "stock", r["currency"],
                             STOCK_INTRADAY_SCORE_THRESHOLD, hold_h, warmup, split,
                             target_notional=STOCK_DAYTRADE_NOTIONAL_EUR,
                             charge_overnight=False)
            test = simulate(df, scores, "stock", r["currency"],
                            STOCK_INTRADAY_SCORE_THRESHOLD, hold_h, split, n,
                            target_notional=STOCK_DAYTRADE_NOTIONAL_EUR,
                            charge_overnight=False)
            fs, trs, ts = summarize(full), summarize(train), summarize(test)
            if fs["n"] < MIN_STOCK_INTRADAY_TRADES: continue
            if ts["n"] < MIN_STOCK_INTRADAY_TEST_TRADES: continue
            if fs["avg"] <= 0 or ts["avg"] <= 0 or trs["avg"] <= 0: continue

            confidence = calibrated_confidence(current["intraday_score"])
            atr_pct = current["intraday_atr_pct"] / 100.0
            scaled_vol_pct = atr_pct * np.sqrt(hold_h) * 100.0
            predicted_move_pct = confidence * scaled_vol_pct * 0.7
            if predicted_move_pct < STOCK_INTRADAY_MIN_PREDICTED_PCT: continue

            of, cf = fees_open_close("stock", notional)
            fees = of + cf  # no overnight on intraday
            gross = notional * predicted_move_pct / 100.0
            predicted_net_eur = gross - fees
            if predicted_net_eur <= 0: continue

            sl, tp, rr = trade_levels(current["price"], scaled_vol_pct,
                                      predicted_move_pct,
                                      INTRADAY_STOP_LOSS_VOL_FRAC)
            if pd.isna(rr) or rr < MIN_RR_RATIO: continue

            cand = {
                **current,
                "score": r["score"],
                "rsi": current["intraday_rsi"],
                "adx": current["intraday_adx"],
                "regime": current["regime"],
                "daytrade_score": r["daytrade_score"],
                "hold_hours": hold_h,
                "intraday_units": units,
                "intraday_notional": notional,
                "intraday_vol_pct": scaled_vol_pct,
                "intraday_predicted_move_pct": predicted_move_pct,
                "intraday_fees_eur": fees,
                "intraday_breakeven_pct": fees / notional * 100,
                "intraday_predicted_net_eur": predicted_net_eur,
                "intraday_expected_roi_pct": predicted_net_eur / notional * 100,
                "intraday_stop_loss_price": sl,
                "intraday_take_profit_price": tp,
                "intraday_risk_reward": rr,
                "intraday_bt_trades": fs["n"], "intraday_bt_win_rate": fs["win_rate"],
                "intraday_bt_avg": fs["avg"], "intraday_bt_median": fs["median"],
                "intraday_train_trades": trs["n"], "intraday_train_avg": trs["avg"],
                "intraday_test_trades": ts["n"], "intraday_test_win_rate": ts["win_rate"],
                "intraday_test_avg": ts["avg"],
            }
            if best is None or cand["intraday_expected_roi_pct"] > best["intraday_expected_roi_pct"]:
                best = cand
        if best is not None:
            recs.append(best)

    recs.sort(key=lambda x: (x["intraday_expected_roi_pct"], x.get("intraday_test_avg", 0)),
              reverse=True)
    return recs[:N_STOCK_INTRADAY_RECOMMENDATIONS]

# =================== PRINTERS ===================
def _drift_note(scan_close, live):
    if scan_close is None or live is None or scan_close <= 0:
        return ""
    drift = (live - scan_close) / scan_close * 100.0
    if abs(drift) < 0.05:
        return f"{C.DIM}(matches scan close){C.RESET}"
    arrow = f"{C.GREEN}↑{C.RESET}" if drift > 0 else f"{C.RED}↓{C.RESET}"
    return f"{C.DIM}(scan close was {scan_close:.4f}; drift {arrow} {drift:+.2f}%){C.RESET}"

def _market_line(asset_class, ticker, currency):
    return market_note_colored(asset_class, ticker, currency)

def _print_market_line(r):
    print(f"     {_market_line(r['asset_class'], r['ticker'], r['currency'])}")

def _market_short_label(r):
    status = r.get("market_status") or market_info_for_row(r)["market_status"]
    if status == "OPEN_24_7":
        return "24/7"
    if status == "OPEN":
        return "OPEN"
    return "CLOSED"

def _status_tag(r):
    """Render the [NEW]/[UPDATED]/[TP HIT]/[SL HIT] live-mode tag."""
    tag = r.get("live_status", "")
    return status_badge(tag) + " " if tag else ""

def _earnings_warning(r):
    e = r.get("earnings_warning")
    if not e: return ""
    return f"\n     {C.YELLOW}⚠ Earnings within hold period:{C.RESET} {e}"

def _header(text):
    return f"{C.BOLD}{C.CYAN}{text}{C.RESET}"

def print_recommendations(recs, robust, weak):
    BAR = "="*135
    robust_display = sorted(cls for cls in robust if not cls.startswith("crypto_"))
    weak_display = sorted(cls for cls in weak if not cls.startswith("crypto_"))
    print("\n" + BAR)
    print(_header(" CONCRETE TRADING RECOMMENDATIONS — 2-week net ROI (mixed asset classes, excl. crypto)"))
    print(BAR)
    print(f"\n  Filter applied:")
    print(f"   1. Asset class must have OOS verdict = ROBUST"
          f"{' or WEAK' if ALLOW_WEAK_CLASSES else ''}")
    print(f"   2. Current scan score must be ≥ {MIN_SCORE_FOR_REC}")
    print(f"   3. Predicted net profit after fees must be > 0; reward:risk ≥ {MIN_RR_RATIO}")
    print(f"\n  Robust asset classes today: "
          f"{', '.join(robust_display) if robust_display else '(none)'}")
    if weak_display:
        print(f"  Weak classes (excluded): {', '.join(weak_display)}")
    if not recs:
        print("\n  No instrument currently shows a bullish signal strong enough to meet the criteria.")
        return
    for i, r in enumerate(recs, 1):
        stars = "*" * min(5, max(1, r["score"] - 2))
        drift = _drift_note(r.get("close_at_scan"), r["price"])
        tag = _status_tag(r)
        print()
        print(f"  -- #{i}  {stars:<5}  {tag}{C.BOLD}{r['name']}{C.RESET}  ({r['ticker']} / {r['asset_class']}) " + "-"*20)
        _print_market_line(r)
        print(f"     Direction:           LONG (BUY 1 piece)")
        print(f"     LIVE entry price:    {C.BOLD}{r['price']:>10.4f} {r['currency']}{C.RESET}  {drift}")
        print(f"     Signal score:        {r['score']}     RSI: {r['rsi']:.1f}     "
              f"ADX: {r['adx']:.1f}     Regime: {r['regime']:+d}")
        sig_short = (r['signals'][:110] + '...') if len(r['signals']) > 110 else r['signals']
        print(f"     Active signals:      {sig_short}")
        print(f"     Predicted move:      {colorize_pct(r['predicted_move_pct'])}")
        print(f"     Total fees:          {r['total_fees']:>7.2f} EUR  (break-even {colorize_pct(r['breakeven_pct'])})")
        print(f"     {C.BOLD}>> EXPECTED NET ROI: {colorize_pct(r['expected_roi_pct'])}  ->  "
              f"{colorize_money(r['predicted_net_eur'])} per piece{C.RESET}")
        print(f"     Take-profit price:   {C.GREEN}{r['take_profit_price']:>10.4f}{C.RESET} {r['currency']}")
        print(f"     Stop-loss price:     {C.RED}{r['stop_loss_price']:>10.4f}{C.RESET} {r['currency']}")
        if not np.isnan(r["risk_reward"]):
            rr_color = C.GREEN if r['risk_reward'] >= 1.5 else (C.YELLOW if r['risk_reward'] >= 1.0 else C.RED)
            print(f"     Reward:risk ratio:   {rr_color}{r['risk_reward']:.2f} : 1{C.RESET}")
        print(_earnings_warning(r), end="")

def print_stock_recommendations(recs):
    BAR = "="*135
    print("\n" + BAR)
    print(" CASH STOCK SWING RECOMMENDATIONS — 10 trading days, regular stocks only")
    print(BAR)
    if not recs:
        print("\n  No stock candidates passed the stock-specific filter today.")
        return
    for i, r in enumerate(recs, 1):
        drift = _drift_note(r.get("close_at_scan"), r["price"])
        print()
        print(f"  #{i} {r['name']} ({r['ticker']})")
        _print_market_line(r)
        print(f"     LIVE entry price:    {r['price']:>10.4f} {r['currency']}  {drift}")
        print(f"     Signal score:        {r['score']}     RSI: {r['rsi']:.1f}     "
              f"ADX: {r['adx']:.1f}     Regime: {r['regime']:+d}")
        print(f"     Predicted move:      {r['predicted_move_pct']:>+7.2f}%")
        print(f"     Expected net ROI:    {r['expected_roi_pct']:>+7.2f}%  -> {r['predicted_net_eur']:>+7.2f} EUR per share")
        print(f"     Take-profit price:   {r['take_profit_price']:>10.4f} {r['currency']}")
        print(f"     Stop-loss price:     {r['stop_loss_price']:>10.4f} {r['currency']}")
        print(f"     Full backtest:       {int(r['bt_trades'])} trades, {r['bt_win_rate']:.1f}% win rate, avg {r['bt_avg']:+.2f}%")
        if r.get("test_trades", 0):
            print(f"     Recent test split:   {int(r['test_trades'])} trades, {r['test_win_rate']:.1f}% win rate, avg {r['test_avg']:+.2f}%")

def print_crypto_weekly_recommendations(recs):
    BAR = "="*135
    print("\n" + BAR)
    print(f" CRYPTO WEEKLY RECOMMENDATIONS — {CRYPTO_WEEKLY_HOLD_DAYS}-day hold, "
        f"base €{CRYPTO_NOTIONAL_EUR:.0f} ATR-adjusted sizing, fee={CRYPTO_FEE_PCT*100:.2f}%/side")
    print(BAR)
    print(f"\n  Predicted move must clear {CRYPTO_WEEKLY_MIN_PREDICTED_PCT:.1f}% "
        f"(round-trip fee is {2*CRYPTO_FEE_PCT*100:.2f}% of position notional)")
    if not recs:
        print("\n  No crypto candidates passed the weekly filter today.")
        return
    for i, r in enumerate(recs, 1):
        drift = _drift_note(r.get("close_at_scan"), r["price"])
        units = r.get("crypto_units", CRYPTO_NOTIONAL_EUR / r["price"])
        print()
        print(f"  #{i} {r['name']} ({r['ticker']})")
        _print_market_line(r)
        print(f"     LIVE entry price:    {r['price']:>14.6f} {r['currency']}  {drift}")
        print(f"     Position sizing:     BUY {units:.8f} units = ~€{r['notional']:.2f}")
        print(f"     Hold:                {int(r['hold_days'])} days")
        print(f"     Signal score:        {r['score']}     RSI: {r['rsi']:.1f}     "
              f"ADX: {r['adx']:.1f}     Regime: {r['regime']:+d}")
        print(f"     BTC relative:        7d {r.get('vs_btc_7d_pct', 0.0):+.2f}%     "
              f"30d {r.get('vs_btc_30d_pct', 0.0):+.2f}%     7d return {r.get('ret7_pct', 0.0):+.2f}%")
        sig_short = (r['signals'][:110] + '...') if len(r['signals']) > 110 else r['signals']
        print(f"     Active signals:      {sig_short}")
        print(f"     Predicted move:      {r['predicted_move_pct']:>+7.2f}%   "
              f"(confidence={r['confidence']:.2f}, {r['hold_days']}d vol={r['vol_2w_pct']:.1f}%)")
        print(f"     Fees:                {r['total_fees']:>7.2f} EUR  (break-even {r['breakeven_pct']:+.2f}%)")
        print(f"     >> Expected net ROI: {r['expected_roi_pct']:>+7.2f}%   "
              f"-> {r['predicted_net_eur']:>+7.2f} EUR on €{r['notional']:.0f}")
        print(f"     Upside (+1 vol):     {r['bull_case_net_eur']:>+7.2f} EUR     "
              f"Downside (-1 vol): {r['bear_case_net_eur']:>+7.2f} EUR")
        print(f"     Take-profit price:   {r['take_profit_price']:>14.6f} {r['currency']}")
        print(f"     Stop-loss price:     {r['stop_loss_price']:>14.6f} {r['currency']}")
        print(f"     Reward:risk ratio:   {r['risk_reward']:.2f} : 1")
        print(f"     Full backtest:       {int(r['bt_trades'])} trades, {r['bt_win_rate']:.1f}% win rate, avg {r['bt_avg']:+.2f}%")
        print(f"     Recent test split:   {int(r['test_trades'])} trades, {r['test_win_rate']:.1f}% win rate, avg {r['test_avg']:+.2f}%")

def print_crypto_weekly_trade_suggestions(suggestions):
    BAR = "="*135
    print("\n" + BAR)
    print(f" CRYPTO WEEKLY TRADE SUGGESTIONS — actionable {CRYPTO_WEEKLY_HOLD_DAYS}-day BUY/TP/SL rows")
    print(BAR)
    if not suggestions:
        print("\n  No crypto weekly trade suggestions generated today.")
        return
    print(f"{'#':<4}{'Action':<7}{'Coin':<18}{'Mkt':>8}{'Entry':>14}{'Size€':>9}{'Units':>14}"
          f"{'TP':>14}{'SL':>14}{'Exp€':>10}{'Risk€':>10}{'R:R':>7}")
    print("-"*135)
    for i, r in enumerate(suggestions, 1):
        print(f"{i:<4}{r['action']:<7}{r['name'][:17]:<18}"
              f"{_market_short_label(r):>8}{r['entry_price']:>14.6f}{r['notional_eur']:>9.2f}{r['units']:>14.8f}"
              f"{r['take_profit_price']:>14.6f}{r['stop_loss_price']:>14.6f}"
              f"{r['expected_net_eur']:>+10.2f}{r['max_loss_if_sl_eur']:>+10.2f}"
              f"{r['risk_reward']:>7.2f}")
    print("\n  Market details:")
    for r in suggestions:
        print(f"   - {r['ticker']}: {r['market_note']}")
    print(f"\n  Saved to {CRYPTO_WEEKLY_TRADE_SUGGESTIONS_CSV}")

def print_daytrade_recommendations(recs):
    BAR = "="*135
    print("\n" + BAR)
    print(" DAYTRADE RECOMMENDATIONS (mixed, excl. crypto) — 1-3 trading days")
    print(BAR)
    if not recs:
        print("\n  No 1-3 day candidates passed the fee-aware filter today.")
        return
    for i, r in enumerate(recs, 1):
        label = "share" if r["asset_class"] == "stock" else "piece"
        drift = _drift_note(r.get("close_at_scan"), r["price"])
        print()
        print(f"  #{i} {r['name']} ({r['ticker']} / {r['asset_class']})")
        _print_market_line(r)
        print(f"     Suggested hold:      {int(r['hold_days'])} trading day(s)")
        print(f"     LIVE entry price:    {r['price']:>10.4f} {r['currency']}  {drift}")
        print(f"     Swing/day score:     {r['score']} / {r['daytrade_score']}     "
              f"RSI: {r['rsi']:.1f}     ADX: {r['adx']:.1f}")
        print(f"     Predicted move:      {r['daytrade_predicted_move_pct']:>+7.2f}%")
        print(f"     Fees:                {r['daytrade_fees_eur']:>7.2f} EUR  (break-even {r['daytrade_breakeven_pct']:+.2f}%)")
        print(f"     Expected net ROI:    {r['daytrade_expected_roi_pct']:>+7.2f}%   -> {r['daytrade_predicted_net_eur']:>+7.2f} EUR per {label}")
        print(f"     Take-profit price:   {r['daytrade_take_profit_price']:>10.4f} {r['currency']}")
        print(f"     Stop-loss price:     {r['daytrade_stop_loss_price']:>10.4f} {r['currency']}")
        if not np.isnan(r["daytrade_risk_reward"]):
            print(f"     Reward:risk ratio:   {r['daytrade_risk_reward']:.2f} : 1")
        print(f"     Full backtest:       {int(r['daytrade_bt_trades'])} trades, {r['daytrade_bt_win_rate']:.1f}% win rate, avg {r['daytrade_bt_avg']:+.2f}%")
        print(f"     Recent test split:   {int(r['daytrade_test_trades'])} trades, {r['daytrade_test_win_rate']:.1f}% win rate, avg {r['daytrade_test_avg']:+.2f}%")

def print_stock_daytrade_recommendations(recs):
    BAR = "="*135
    print("\n" + BAR)
    print(f" STOCK DAYTRADE RECOMMENDATIONS — cash stocks only, ~€{STOCK_DAYTRADE_NOTIONAL_EUR:.0f} per position")
    print(BAR)
    if not recs:
        print("\n  No cash stock passed the daytrade filter today.")
        return
    for i, r in enumerate(recs, 1):
        units = int(r["daytrade_units"])
        drift = _drift_note(r.get("close_at_scan"), r["price"])
        print()
        print(f"  #{i} {r['name']} ({r['ticker']})")
        _print_market_line(r)
        print(f"     Suggested hold:      {int(r['hold_days'])} trading day(s)")
        print(f"     LIVE entry price:    {r['price']:>10.4f} {r['currency']}  {drift}")
        print(f"     Position sizing:     BUY {units} shares = ~{r['daytrade_notional']:.0f} {r['currency']}")
        print(f"     Swing/day score:     {r['score']} / {r['daytrade_score']}     "
              f"RSI: {r['rsi']:.1f}     ADX: {r['adx']:.1f}")
        print(f"     Predicted move:      {r['daytrade_predicted_move_pct']:>+7.2f}%")
        print(f"     Expected net ROI:    {r['daytrade_expected_roi_pct']:>+7.2f}%   -> {r['daytrade_predicted_net_eur']:>+7.2f} EUR")
        print(f"     Take-profit price:   {r['daytrade_take_profit_price']:>10.4f} {r['currency']}")
        print(f"     Stop-loss price:     {r['daytrade_stop_loss_price']:>10.4f} {r['currency']}")
        if not np.isnan(r["daytrade_risk_reward"]):
            print(f"     Reward:risk ratio:   {r['daytrade_risk_reward']:.2f} : 1")
        print(f"     Full backtest:       {int(r['stock_dt_full_trades'])} trades, {r['stock_dt_full_win_rate']:.1f}% win rate, avg {r['stock_dt_full_avg']:+.2f}%")
        print(f"     Test split:          {int(r['stock_dt_test_trades'])} trades, {r['stock_dt_test_win_rate']:.1f}% win rate, avg {r['stock_dt_test_avg']:+.2f}%")

def print_crypto_daytrade_recommendations(recs):
    BAR = "="*135
    print("\n" + BAR)
    print(f" CRYPTO DAYTRADE RECOMMENDATIONS — 1-3 day hold, base €{CRYPTO_NOTIONAL_EUR:.0f} ATR-adjusted sizing")
    print(BAR)
    print(f"\n  Predicted move must clear {CRYPTO_DAYTRADE_MIN_PREDICTED_PCT:.1f}% "
          f"(round-trip fee is {2*CRYPTO_FEE_PCT*100:.2f}% of position notional)")
    if not recs:
        print("\n  No crypto coin passed the daytrade filter today.")
        return
    for i, r in enumerate(recs, 1):
        units = r["daytrade_units"]
        drift = _drift_note(r.get("close_at_scan"), r["price"])
        print()
        print(f"  #{i} {r['name']} ({r['ticker']})")
        _print_market_line(r)
        print(f"     Suggested hold:      {int(r['hold_days'])} day(s)")
        print(f"     LIVE entry price:    {r['price']:>14.6f} {r['currency']}  {drift}")
        print(f"     Position sizing:     BUY {units:.8f} units = ~€{r['daytrade_notional']:.2f}")
        print(f"     Swing/day score:     {r['score']} / {r['daytrade_score']}     "
              f"RSI: {r['rsi']:.1f}     ADX: {r['adx']:.1f}")
        print(f"     BTC relative:        7d {r.get('vs_btc_7d_pct', 0.0):+.2f}%     "
              f"30d {r.get('vs_btc_30d_pct', 0.0):+.2f}%     7d return {r.get('ret7_pct', 0.0):+.2f}%")
        sig_short = (r['daytrade_signals'][:110] + '...') if len(r['daytrade_signals']) > 110 else r['daytrade_signals']
        print(f"     Active signals:      {sig_short}")
        print(f"     Predicted move:      {r['daytrade_predicted_move_pct']:>+7.2f}%")
        print(f"     Fees:                {r['daytrade_fees_eur']:>7.2f} EUR  (break-even {r['daytrade_breakeven_pct']:+.2f}%)")
        print(f"     >> Expected net ROI: {r['daytrade_expected_roi_pct']:>+7.2f}%   "
              f"-> {r['daytrade_predicted_net_eur']:>+7.2f} EUR on €{r['daytrade_notional']:.0f}")
        print(f"     Take-profit price:   {r['daytrade_take_profit_price']:>14.6f} {r['currency']}")
        print(f"     Stop-loss price:     {r['daytrade_stop_loss_price']:>14.6f} {r['currency']}")
        print(f"     Reward:risk ratio:   {r['daytrade_risk_reward']:.2f} : 1")
        print(f"     Full backtest:       {int(r['crypto_dt_full_trades'])} trades, {r['crypto_dt_full_win_rate']:.1f}% win rate, avg {r['crypto_dt_full_avg']:+.2f}%")
        print(f"     Test split:          {int(r['crypto_dt_test_trades'])} trades, {r['crypto_dt_test_win_rate']:.1f}% win rate, avg {r['crypto_dt_test_avg']:+.2f}%")

def print_crypto_mean_reversion_recommendations(recs):
    BAR = "="*135
    print("\n" + BAR)
    print(f" CRYPTO MEAN-REVERSION BOUNCES — RSI2<{CRYPTO_MR_RSI2_MAX:g}, green close, above SMA50")
    print(BAR)
    print(f"\n  Separate oversold-bounce track. Position size starts at €{CRYPTO_NOTIONAL_EUR:.0f} "
          f"and scales down when daily ATR% is above {CRYPTO_ATR_TARGET_PCT:.1f}%.")
    if not recs:
        print("\n  No crypto coin currently meets the mean-reversion bounce filter.")
        return
    for i, r in enumerate(recs, 1):
        units = r["crypto_units"]
        drift = _drift_note(r.get("close_at_scan"), r["price"])
        print()
        print(f"  #{i} {r['name']} ({r['ticker']})")
        _print_market_line(r)
        print(f"     LIVE entry price:    {r['price']:>14.6f} {r['currency']}  {drift}")
        print(f"     Position sizing:     BUY {units:.8f} units = ~€{r['notional']:.2f}")
        print(f"     Hold:                {int(r['hold_days'])} day(s)")
        print(f"     Bounce setup:        RSI2<{CRYPTO_MR_RSI2_MAX:g}, green close, close>SMA50")
        print(f"     RSI: {r['rsi']:.1f}     ATR: {r['atr_pct']:.2f}%     7d return: {r['ret7_pct']:+.2f}%")
        print(f"     BTC relative:        7d {r.get('vs_btc_7d_pct', 0.0):+.2f}%     30d {r.get('vs_btc_30d_pct', 0.0):+.2f}%")
        print(f"     Predicted move:      {r['predicted_move_pct']:>+7.2f}%")
        print(f"     Fees:                {r['total_fees']:>7.2f} EUR  (break-even {r['breakeven_pct']:+.2f}%)")
        print(f"     >> Expected net ROI: {r['expected_roi_pct']:>+7.2f}%   "
              f"-> {r['predicted_net_eur']:>+7.2f} EUR")
        print(f"     Take-profit price:   {r['take_profit_price']:>14.6f} {r['currency']}")
        print(f"     Stop-loss price:     {r['stop_loss_price']:>14.6f} {r['currency']}")
        print(f"     Reward:risk ratio:   {r['risk_reward']:.2f} : 1")
        print(f"     MR backtest:         {int(r['mr_full_trades'])} trades, {r['mr_full_win_rate']:.1f}% win rate, avg {r['mr_full_avg']:+.2f}%")
        print(f"     MR test split:       {int(r['mr_test_trades'])} trades, {r['mr_test_win_rate']:.1f}% win rate, avg {r['mr_test_avg']:+.2f}%")

def print_crypto_intraday_recommendations(recs):
    BAR = "="*135
    print("\n" + BAR)
    print(f" CRYPTO INTRADAY RECOMMENDATIONS — {CRYPTO_INTRADAY_HOLDS} hour holds, "
            f"base €{CRYPTO_NOTIONAL_EUR:.0f} ATR-adjusted sizing, hourly bars")
    print(BAR)
    print(f"\n  Predicted move must clear {CRYPTO_INTRADAY_MIN_PREDICTED_PCT:.1f}% "
          f"after Revolut fees ({2*CRYPTO_FEE_PCT*100:.2f}% round-trip).  Hourly bars from "
          f"yfinance go back ~{CRYPTO_INTRADAY_LOOKBACK} for backtesting.")
    if not recs:
        print("\n  No crypto coin currently meets the intraday filter on hourly bars.")
        print("  This is the strictest of the three crypto tracks — intraday moves rarely")
        print("  exceed the 3% Revolut round-trip fee after spread and fees.  Try larger size or")
        print("  wait for higher-volatility windows.")
        return
    for i, r in enumerate(recs, 1):
        units = r["intraday_units"]
        drift = _drift_note(r.get("close_at_scan"), r["price"])
        aligned_tag = ""
        if r.get("mtf_aligned"):
            aligned_tag = f" {C.BG_GREEN}{C.BOLD} ALIGNED {C.RESET}"
        print()
        print(f"  #{i} {C.BOLD}{r['name']}{C.RESET} ({r['ticker']}){aligned_tag}")
        _print_market_line(r)
        print(f"     Suggested hold:      {int(r['hold_hours'])} hour(s)")
        print(f"     LIVE entry price:    {C.BOLD}{r['price']:>14.6f} {r['currency']}{C.RESET}  {drift}")
        print(f"     Position sizing:     BUY {units:.8f} units = ~€{r['intraday_notional']:.2f}")
        print(f"     Daily score:         {r['score']}  Daytrade score: {r['daytrade_score']}  "
              f"Intraday score: {r['intraday_score']}"
              + (f"  {C.GREEN}(all 3 ≥ {MTF_ALIGNMENT_THRESHOLD}){C.RESET}" if r.get("mtf_aligned") else ""))
        print(f"     Hourly RSI: {r['rsi']:.1f}     Hourly ADX: {r['adx']:.1f}     "
              f"Daily regime: {r['regime']:+d}")
        print(f"     BTC relative:        7d {r.get('vs_btc_7d_pct', 0.0):+.2f}%     "
              f"30d {r.get('vs_btc_30d_pct', 0.0):+.2f}%     7d return {r.get('ret7_pct', 0.0):+.2f}%")
        sig_short = (r['intraday_signals'][:110] + '...') if len(r['intraday_signals']) > 110 else r['intraday_signals']
        print(f"     Hourly signals:      {sig_short}")
        print(f"     Hourly vol ({r['hold_hours']}h): {r['intraday_vol_pct']:>+6.2f}%")
        print(f"     Predicted move:      {r['intraday_predicted_move_pct']:>+7.2f}%")
        print(f"     Fees:                {r['intraday_fees_eur']:>7.2f} EUR  (break-even {r['intraday_breakeven_pct']:+.2f}%)")
        print(f"     >> Expected net ROI: {r['intraday_expected_roi_pct']:>+7.2f}%   "
              f"-> {r['intraday_predicted_net_eur']:>+7.2f} EUR on €{r['intraday_notional']:.0f}")
        print(f"     Take-profit price:   {r['intraday_take_profit_price']:>14.6f} {r['currency']}")
        print(f"     Stop-loss price:     {r['intraday_stop_loss_price']:>14.6f} {r['currency']}")
        print(f"     Reward:risk ratio:   {r['intraday_risk_reward']:.2f} : 1")
        print(f"     Hourly backtest:     {int(r['intraday_bt_trades'])} trades, {r['intraday_bt_win_rate']:.1f}% win rate, avg {r['intraday_bt_avg']:+.2f}%")
        print(f"     Hourly test split:   {int(r['intraday_test_trades'])} trades, {r['intraday_test_win_rate']:.1f}% win rate, avg {r['intraday_test_avg']:+.2f}%")

def print_week_recommendations(recs):
    BAR = "="*135
    print("\n" + BAR)
    print(f" MIXED WEEK RECOMMENDATIONS — {WEEK_HOLD_DAYS}-day hold, all OOS-robust asset classes (excl. crypto)")
    print(BAR)
    if not recs:
        print("\n  No instrument passed the 5-day-hold filter today.")
        return
    for i, r in enumerate(recs, 1):
        drift = _drift_note(r.get("close_at_scan"), r["price"])
        print()
        print(f"  #{i} {r['name']} ({r['ticker']} / {r['asset_class']})")
        _print_market_line(r)
        print(f"     Hold:                {int(r['hold_days'])} days")
        print(f"     LIVE entry price:    {r['price']:>10.4f} {r['currency']}  {drift}")
        print(f"     Signal score:        {r['score']}     RSI: {r['rsi']:.1f}     "
              f"ADX: {r['adx']:.1f}     Regime: {r['regime']:+d}")
        sig_short = (r['signals'][:110] + '...') if len(r['signals']) > 110 else r['signals']
        print(f"     Active signals:      {sig_short}")
        print(f"     Predicted move:      {r['predicted_move_pct']:>+7.2f}%   "
              f"({int(r['hold_days'])}-day vol={r['vol_2w_pct']:.1f}%)")
        print(f"     Fees:                {r['total_fees']:>7.2f} EUR  (break-even {r['breakeven_pct']:+.2f}%)")
        print(f"     >> Expected net ROI: {r['expected_roi_pct']:>+7.2f}%  -> {r['predicted_net_eur']:>+7.2f} EUR per piece")
        print(f"     Take-profit price:   {r['take_profit_price']:>10.4f} {r['currency']}")
        print(f"     Stop-loss price:     {r['stop_loss_price']:>10.4f} {r['currency']}")
        print(f"     Reward:risk ratio:   {r['risk_reward']:.2f} : 1")
        print(f"     5-day full backtest: {int(r['week_bt_trades'])} trades, {r['week_bt_win_rate']:.1f}% win rate, avg {r['week_bt_avg']:+.2f}%")
        print(f"     5-day test split:    {int(r['week_test_trades'])} trades, {r['week_test_win_rate']:.1f}% win rate, avg {r['week_test_avg']:+.2f}%")

def print_stock_week_recommendations(recs):
    BAR = "="*135
    print("\n" + BAR)
    print(f" STOCK WEEK RECOMMENDATIONS — cash stocks, {STOCK_WEEK_HOLD_DAYS}-day hold, ~€{STOCK_DAYTRADE_NOTIONAL_EUR:.0f} per position")
    print(BAR)
    if not recs:
        print("\n  No cash stock passed the 5-day filter today.")
        return
    for i, r in enumerate(recs, 1):
        units = int(r["stock_week_units"])
        drift = _drift_note(r.get("close_at_scan"), r["price"])
        print()
        print(f"  #{i} {r['name']} ({r['ticker']})")
        _print_market_line(r)
        print(f"     LIVE entry price:    {r['price']:>10.4f} {r['currency']}  {drift}")
        print(f"     Position sizing:     BUY {units} shares = ~{r['stock_week_notional']:.0f} {r['currency']}")
        print(f"     Hold:                {int(r['hold_days'])} days")
        print(f"     Signal score:        {r['score']}     RSI: {r['rsi']:.1f}     "
              f"ADX: {r['adx']:.1f}     Regime: {r['regime']:+d}")
        sig_short = (r['signals'][:110] + '...') if len(r['signals']) > 110 else r['signals']
        print(f"     Active signals:      {sig_short}")
        print(f"     Predicted move:      {r['predicted_move_pct']:>+7.2f}%")
        print(f"     Fees:                {r['total_fees']:>7.2f} EUR  (break-even {r['breakeven_pct']:+.2f}%)")
        print(f"     >> Expected net ROI: {r['expected_roi_pct']:>+7.2f}%   "
              f"-> {r['predicted_net_eur']:>+7.2f} EUR on the position")
        print(f"     Take-profit price:   {r['take_profit_price']:>10.4f} {r['currency']}")
        print(f"     Stop-loss price:     {r['stop_loss_price']:>10.4f} {r['currency']}")
        print(f"     Reward:risk ratio:   {r['risk_reward']:.2f} : 1")
        print(f"     5-day backtest:      {int(r['sw_full_trades'])} trades, {r['sw_full_win_rate']:.1f}% win rate, avg {r['sw_full_avg']:+.2f}%")
        print(f"     Train split:         {int(r['sw_train_trades'])} trades, avg {r['sw_train_avg']:+.2f}%")
        print(f"     Test split:          {int(r['sw_test_trades'])} trades, {r['sw_test_win_rate']:.1f}% win rate, avg {r['sw_test_avg']:+.2f}%")

def print_stock_intraday_recommendations(recs):
    BAR = "="*135
    print("\n" + BAR)
    print(f" STOCK INTRADAY RECOMMENDATIONS — cash stocks, hourly bars, "
          f"~€{STOCK_DAYTRADE_NOTIONAL_EUR:.0f} per position")
    print(BAR)
    print(f"\n  Holds: {STOCK_INTRADAY_HOLDS} hours.  Stock hourly bars are sparse (~6.5/day for US),")
    print(f"  so filters use a looser min-trade count.  Predicted move floor: {STOCK_INTRADAY_MIN_PREDICTED_PCT:.2f}%.")
    if not recs:
        print("\n  No cash stock currently meets the intraday filter on hourly bars.")
        return
    for i, r in enumerate(recs, 1):
        units = int(r["intraday_units"])
        drift = _drift_note(r.get("close_at_scan"), r["price"])
        print()
        print(f"  #{i} {r['name']} ({r['ticker']})")
        _print_market_line(r)
        print(f"     Suggested hold:      {int(r['hold_hours'])} hour(s)")
        print(f"     LIVE entry price:    {r['price']:>10.4f} {r['currency']}  {drift}")
        print(f"     Position sizing:     BUY {units} shares = ~{r['intraday_notional']:.0f} {r['currency']}")
        print(f"     Daily score:         {r['score']}  Daytrade score: {r['daytrade_score']}  "
              f"Intraday score: {r['intraday_score']}")
        print(f"     Hourly RSI: {r['rsi']:.1f}     Hourly ADX: {r['adx']:.1f}     "
              f"Daily regime: {r['regime']:+d}")
        sig_short = (r['intraday_signals'][:110] + '...') if len(r['intraday_signals']) > 110 else r['intraday_signals']
        print(f"     Hourly signals:      {sig_short}")
        print(f"     Hourly vol ({r['hold_hours']}h): {r['intraday_vol_pct']:>+6.2f}%")
        print(f"     Predicted move:      {r['intraday_predicted_move_pct']:>+7.2f}%")
        print(f"     Fees:                {r['intraday_fees_eur']:>7.2f} EUR  (break-even {r['intraday_breakeven_pct']:+.2f}%)")
        print(f"     >> Expected net ROI: {r['intraday_expected_roi_pct']:>+7.2f}%   "
              f"-> {r['intraday_predicted_net_eur']:>+7.2f} EUR")
        print(f"     Take-profit price:   {r['intraday_take_profit_price']:>10.4f} {r['currency']}")
        print(f"     Stop-loss price:     {r['intraday_stop_loss_price']:>10.4f} {r['currency']}")
        print(f"     Reward:risk ratio:   {r['intraday_risk_reward']:.2f} : 1")
        print(f"     Hourly backtest:     {int(r['intraday_bt_trades'])} trades, {r['intraday_bt_win_rate']:.1f}% win rate, avg {r['intraday_bt_avg']:+.2f}%")
        print(f"     Hourly test split:   {int(r['intraday_test_trades'])} trades, {r['intraday_test_win_rate']:.1f}% win rate, avg {r['intraday_test_avg']:+.2f}%")

# =================== LIVE-MODE STATE ===================
_LIVE_PRIOR = {}  # key=(track, ticker) → previous price (for [UPDATED]/[TP HIT]/[SL HIT] detection)

def _tag_recs_live(track_key_prefix, recs, price_key="price",
                   sl_key="stop_loss_price", tp_key="take_profit_price"):
    """Tag each rec with NEW/UPDATED/TP HIT/SL HIT vs the prior live iteration."""
    for r in recs:
        key = (track_key_prefix, r["ticker"])
        prior = _LIVE_PRIOR.get(key)
        prior_sl = _LIVE_PRIOR.get((track_key_prefix + "_sl", r["ticker"]))
        prior_tp = _LIVE_PRIOR.get((track_key_prefix + "_tp", r["ticker"]))
        live = r.get(price_key, 0)
        if prior is None:
            r["live_status"] = "NEW"
        elif prior_tp is not None and live >= prior_tp:
            r["live_status"] = "TP HIT"
        elif prior_sl is not None and live <= prior_sl:
            r["live_status"] = "SL HIT"
        elif prior > 0 and abs(live - prior) / prior * 100 >= LIVE_UPDATE_THRESHOLD_PCT:
            r["live_status"] = "UPDATED"
        else:
            r["live_status"] = "UNCHANGED"
        _LIVE_PRIOR[key] = live
        if r.get(sl_key) is not None: _LIVE_PRIOR[(track_key_prefix + "_sl", r["ticker"])] = r[sl_key]
        if r.get(tp_key) is not None: _LIVE_PRIOR[(track_key_prefix + "_tp", r["ticker"])] = r[tp_key]

# =================== MAIN ===================
def run_scan(iteration=0):
    """Run one full scan cycle. Called once at startup, then optionally
    every LIVE_FULL_SCAN_HOURS hours in live mode."""
    os.makedirs(OUTDIR, exist_ok=True)
    run_context = build_run_context(OUTDIR, RUN_LABEL, iteration=iteration,
                                    snapshot_runs=SNAPSHOT_RUNS)
    assets = load_assets()
    symbol_overrides = load_symbol_overrides(SYMBOL_OVERRIDES_JSON)
    assets, quality_rows = apply_symbol_overrides(assets, symbol_overrides)
    assets = filter_assets(
        assets,
        only_asset_classes=RUNTIME_ONLY_ASSET_CLASSES,
        only_tickers=RUNTIME_ONLY_TICKERS,
        max_assets=RUNTIME_MAX_ASSETS,
    )
    asset_count = len(assets)
    crypto_count = sum(1 for a in assets if a[2] == "crypto")
    print(f"Loading {len(assets)} instruments ({crypto_count} crypto, {LOOKBACK} of daily history)...")
    if os.path.exists(INSTRUMENTS_CSV):
        print(f"Instrument universe loaded from {INSTRUMENTS_CSV}")
    if symbol_overrides:
        print(f"Symbol overrides loaded from {SYMBOL_OVERRIDES_JSON} ({len(symbol_overrides)} entries).")
    if run_context["snapshot_dir"]:
        print(f"Snapshot run directory: {run_context['snapshot_dir']}")

    if USE_REGIME_FILTER:
        regime_series = load_regime()
        if regime_series is not None:
            print(f"Regime filter active (benchmark: {REGIME_BENCHMARK}).")
        else:
            print("Regime filter could not download benchmark — proceeding without it.")
    else:
        regime_series = None

    # BTC regime + close — used by every crypto instrument
    btc_regime_series, btc_close = (None, None)
    if USE_BTC_REGIME_FOR_CRYPTO:
        btc_regime_series, btc_close = load_btc_regime()
        if btc_regime_series is not None:
            print(f"{C.CYAN}BTC regime overlay active{C.RESET} (benchmark: {BTC_REGIME_TICKER}, "
                  f"{len(btc_regime_series)} bars) — used for crypto only.")
        else:
            print("BTC regime could not be downloaded — crypto will fall back to ^GSPC regime.")

    daily_histories = prefetch_histories(
        [ticker for ticker, _name, _cls, _cur in assets], LOOKBACK, "1d", "daily")

    enriched, scores_map, day_scores_map, returns = {}, {}, {}, {}
    scan_rows, all_trades, bt_summary = [], [], []
    output_files = {}

    def _remember_output(key, path):
        if path:
            output_files[key] = path

    failed = []
    for ticker, name, cls, cur in assets:
        df = load_and_enrich(ticker, regime_series, btc_regime_series, btc_close,
                             asset_class=cls, raw_df=daily_histories.get(ticker))
        if df is None:
            failed.append(f"{ticker}/{cls}")
            quality_rows.append(
                assess_history_quality(ticker, cls, None, name=name, currency=cur,
                                       error="No usable history returned")
            )
            continue
        quality_rows.append(
            assess_history_quality(ticker, cls, df, name=name, currency=cur)
        )
        enriched[(ticker, cls)] = (df, cur, name)
        returns[(ticker, cls)] = df["ret1"].tail(CORR_LOOKBACK_DAYS)
        scores = precompute_scores(df, asset_class=cls)
        scores_map[(ticker, cls)] = scores
        day_scores_map[(ticker, cls)] = precompute_daytrade_scores(df)

        row = current_analysis(df, ticker, name, cls, cur)
        if row is not None: scan_rows.append(project_pnl(row))

        tr = simulate(df, scores, cls, cur, SCORE_THRESHOLD, HOLD_TRADING_DAYS)
        for t in tr: t.update({"ticker": ticker, "asset_class": cls})
        all_trades.extend(tr)
        s = summarize(tr); s.update({"ticker": ticker, "name": name, "asset_class": cls})
        bt_summary.append(s)

    if failed:
        print(f"  ({len(failed)} tickers had no usable data and were skipped: "
              f"{', '.join(failed[:8])}{'...' if len(failed) > 8 else ''})")

    scan_rows.sort(key=lambda x: x["predicted_net_eur"], reverse=True)
    BAR = "="*135

    # ============== FULL CURRENT SCAN ==============
    print("\n" + BAR)
    print(f" Revolut Bullish Scanner v10 — {datetime.now():%Y-%m-%d %H:%M}")
    print(f" FULL CURRENT SCAN — all {len(scan_rows)} successfully analysed instruments")
    print(BAR)
    print(f"{'#':<4}{'Instrument':<26}{'Class':<14}{'Price':>12}{'Sc':>4}{'DSc':>5}"
          f"{'RSI':>6}{'ADX':>6}{'Rgm':>4}{'BE%':>7}{'Pred%':>7}")
    print("-"*135)
    for i, r in enumerate(scan_rows, 1):
        adx_str = f"{r['adx']:>6.1f}" if pd.notna(r['adx']) else f"{'—':>6}"
        print(f"{i:<4}{r['name'][:25]:<26}{r['asset_class']:<14}"
              f"{r['price']:>12.4f}{r['score']:>4}{r['daytrade_score']:>5}"
              f"{r['rsi']:>6.1f}{adx_str}{r['regime']:>+4d}"
              f"{r['breakeven_pct']:>7.2f}{r['predicted_move_pct']:>7.2f}")

    # ============== PARAMETER SWEEP + OOS VERDICT ==============
    print("\n" + BAR); print(" PARAMETER SWEEP — TRAIN (70%) / TEST (30%)"); print(BAR)
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
                    "oos_asset_class": oos_asset_class_for_ticker(tk, cls),
                    "threshold": thr, "hold_days": hold,
                    "train_n": ts["n"], "train_win": ts["win_rate"],
                    "train_avg": ts["avg"], "train_total": ts["total"],
                    "test_n": vs["n"], "test_win": vs["win_rate"],
                    "test_avg": vs["avg"], "test_total": vs["total"],
                    "full_n": fs["n"], "full_win": fs["win_rate"],
                    "full_avg": fs["avg"], "full_total": fs["total"],
                })
    sweep_df = pd.DataFrame(sweep_rows)

    print("\n  OOS VERDICT — best train params vs. unseen test data")
    print("  " + "-"*120)
    print(f"  {'Asset class':<16}{'Thr':>4}{'Hold':>5}  |"
          f"{'Tr N':>5}{'Tr Win%':>9}{'Tr Avg%':>9}  |"
          f"{'Te N':>5}{'Te Win%':>9}{'Te Avg%':>9}  {'Verdict':<14}")
    print("  " + "-"*120)
    oos_results = []
    for cls in OOS_ASSET_CLASSES:
        sub = sweep_df[sweep_df["oos_asset_class"] == cls]
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
        oos_results.append({"asset_class": cls, **best, "verdict": v})
        vw_str = f"{best['vw']:>9.1f}" if not np.isnan(best['vw']) else f"{'—':>9}"
        va_str = f"{best['va']:>+9.2f}" if not np.isnan(best['va']) else f"{'—':>9}"
        print(f"  {format_oos_asset_class(cls):<16}{best['thr']:>4}{best['hold']:>5}  |"
              f"{best['tn']:>5}{best['tw']:>9.1f}{best['ta']:>+9.2f}  |"
              f"{best['vn']:>5}{vw_str}{va_str}  {v:<14}")

    # ============== BUILD ALL RECOMMENDATIONS ==============
    oos_lookup = {r["asset_class"]: r for r in oos_results}
    robust_set = {r["asset_class"] for r in oos_results if r.get("verdict") == "ROBUST"}
    weak_set   = {r["asset_class"] for r in oos_results if r.get("verdict") == "WEAK"}

    recs, _, _      = build_recommendations(scan_rows, oos_results, oos_lookup)
    stock_recs      = build_stock_recommendations(scan_rows, enriched, scores_map, robust_set, weak_set)
    crypto_weekly   = build_crypto_weekly_recommendations(scan_rows, enriched, scores_map, robust_set, weak_set)
    week_recs       = build_week_recommendations(scan_rows, enriched, scores_map, oos_results, oos_lookup)
    stock_week_recs = build_stock_week_recommendations(scan_rows, enriched, scores_map, robust_set, weak_set)
    daytrade_recs   = build_daytrade_recommendations(scan_rows, enriched, day_scores_map)
    stock_dt_recs   = build_stock_daytrade_recommendations(scan_rows, enriched, day_scores_map)
    crypto_dt_recs  = build_crypto_daytrade_recommendations(scan_rows, enriched, day_scores_map)
    crypto_mr_recs  = build_crypto_mean_reversion_recommendations(scan_rows, enriched)

    # --- Crypto intraday: pull hourly bars for top-N crypto candidates ---
    crypto_candidates = sorted(
        [r for r in scan_rows if r["asset_class"] == "crypto"],
        key=lambda r: r["score"] + r["daytrade_score"] * 0.5,
        reverse=True
    )[:MAX_CRYPTO_INTRADAY_CANDIDATES]
    print(f"\nPulling hourly bars for top {len(crypto_candidates)} crypto candidates "
          f"({CRYPTO_INTRADAY_INTERVAL} interval, {CRYPTO_INTRADAY_LOOKBACK} back)...")
    crypto_hourly_histories = prefetch_histories(
        [r["ticker"] for r in crypto_candidates], CRYPTO_INTRADAY_LOOKBACK,
        CRYPTO_INTRADAY_INTERVAL, "crypto hourly")
    crypto_intraday_recs = build_crypto_intraday_recommendations(
        crypto_candidates, regime_series, crypto_hourly_histories)

    # --- Stock intraday: pull hourly bars for top-N stock candidates ---
    stock_candidates = sorted(
        [r for r in scan_rows if r["asset_class"] == "stock"],
        key=lambda r: r["score"] + r["daytrade_score"] * 0.5,
        reverse=True
    )[:MAX_STOCK_INTRADAY_CANDIDATES]
    print(f"Pulling hourly bars for top {len(stock_candidates)} stock candidates "
          f"({STOCK_INTRADAY_INTERVAL} interval, {STOCK_INTRADAY_LOOKBACK} back)...")
    stock_hourly_histories = prefetch_histories(
        [r["ticker"] for r in stock_candidates], STOCK_INTRADAY_LOOKBACK,
        STOCK_INTRADAY_INTERVAL, "stock hourly")
    stock_intraday_recs = build_stock_intraday_recommendations(
        stock_candidates, regime_series, stock_hourly_histories)

    # ============== LIVE-PRICE REFRESH ==============
    if REFRESH_LIVE_PRICES:
        print("Refreshing entry prices with live quotes...")
        refresh_swing_prices(recs, STOP_LOSS_VOL_FRAC)
        refresh_swing_prices(stock_recs, STOP_LOSS_VOL_FRAC)
        refresh_swing_prices(crypto_weekly, STOP_LOSS_VOL_FRAC, crypto_notional=CRYPTO_NOTIONAL_EUR)
        refresh_swing_prices(week_recs, STOP_LOSS_VOL_FRAC)
        refresh_swing_prices(stock_week_recs, STOP_LOSS_VOL_FRAC,
                             stock_notional=STOCK_DAYTRADE_NOTIONAL_EUR)
        refresh_daytrade_prices(daytrade_recs, DAYTRADE_STOP_LOSS_VOL_FRAC)
        refresh_daytrade_prices(stock_dt_recs, DAYTRADE_STOP_LOSS_VOL_FRAC,
                                stock_notional=STOCK_DAYTRADE_NOTIONAL_EUR)
        refresh_daytrade_prices(crypto_dt_recs, DAYTRADE_STOP_LOSS_VOL_FRAC,
                                crypto_notional=CRYPTO_NOTIONAL_EUR)
        refresh_swing_prices(crypto_mr_recs, CRYPTO_MR_STOP_LOSS_VOL_FRAC,
                     crypto_notional=CRYPTO_NOTIONAL_EUR)
        refresh_intraday_prices(crypto_intraday_recs, INTRADAY_STOP_LOSS_VOL_FRAC,
                                crypto_notional=CRYPTO_NOTIONAL_EUR)
        refresh_intraday_prices(stock_intraday_recs, INTRADAY_STOP_LOSS_VOL_FRAC)

    track_rows = {
        "swing": recs,
        "week": week_recs,
        "stock_swing": stock_recs,
        "stock_week": stock_week_recs,
        "crypto_weekly": crypto_weekly,
        "daytrade": daytrade_recs,
        "stock_daytrade": stock_dt_recs,
        "crypto_daytrade": crypto_dt_recs,
        "crypto_mean_reversion": crypto_mr_recs,
        "stock_intraday": stock_intraday_recs,
        "crypto_intraday": crypto_intraday_recs,
    }
    track_rows = annotate_confidence_tiers(track_rows)
    track_rows, portfolio_plan_rows, risk_summary = apply_portfolio_limits(
        track_rows,
        returns,
        {
            "enabled": PORTFOLIO_LIMITS_ENABLED,
            "filter_recommendations": PORTFOLIO_FILTER_RECOMMENDATIONS,
            "max_total_risk_eur": PORTFOLIO_MAX_TOTAL_RISK_EUR,
            "max_positions_total": PORTFOLIO_MAX_POSITIONS_TOTAL,
            "max_positions_per_track": PORTFOLIO_MAX_POSITIONS_PER_TRACK,
            "max_positions_per_asset_class": PORTFOLIO_MAX_POSITIONS_PER_ASSET_CLASS,
            "max_crypto_notional_eur": PORTFOLIO_MAX_CRYPTO_NOTIONAL_EUR,
            "max_correlation": PORTFOLIO_MAX_CORRELATION,
        },
    )
    recs = track_rows["swing"]
    week_recs = track_rows["week"]
    stock_recs = track_rows["stock_swing"]
    stock_week_recs = track_rows["stock_week"]
    crypto_weekly = track_rows["crypto_weekly"]
    daytrade_recs = track_rows["daytrade"]
    stock_dt_recs = track_rows["stock_daytrade"]
    crypto_dt_recs = track_rows["crypto_daytrade"]
    crypto_mr_recs = track_rows["crypto_mean_reversion"]
    stock_intraday_recs = track_rows["stock_intraday"]
    crypto_intraday_recs = track_rows["crypto_intraday"]

    rejection_rows = build_rejection_report(
        scan_rows,
        track_rows,
        robust_set=robust_set,
        weak_set=weak_set,
        allow_weak_classes=ALLOW_WEAK_CLASSES,
        portfolio_plan_rows=portfolio_plan_rows,
        config={
            "MIN_SCORE_FOR_REC": MIN_SCORE_FOR_REC,
            "DAYTRADE_SCORE_THRESHOLD": DAYTRADE_SCORE_THRESHOLD,
            "CRYPTO_WEEKLY_MIN_SCORE": CRYPTO_WEEKLY_MIN_SCORE,
            "CRYPTO_WEEKLY_MIN_PREDICTED_PCT": CRYPTO_WEEKLY_MIN_PREDICTED_PCT,
            "CRYPTO_MR_RSI2_MAX": CRYPTO_MR_RSI2_MAX,
            "STOCK_INTRADAY_SCORE_THRESHOLD": STOCK_INTRADAY_SCORE_THRESHOLD,
            "CRYPTO_INTRADAY_SCORE_THRESHOLD": CRYPTO_INTRADAY_SCORE_THRESHOLD,
        },
    )
    quality_summary = summarize_quality_rows(quality_rows)

    # ============== PRINT ALL TRACKS ==============
    # ----- Live-mode status tagging (NEW/UPDATED/TP HIT/SL HIT vs prior iter) -----
    if LIVE_MODE:
        _tag_recs_live("swing",        recs)
        _tag_recs_live("week",         week_recs)
        _tag_recs_live("stock",        stock_recs)
        _tag_recs_live("stock_week",   stock_week_recs)
        _tag_recs_live("crypto_week",  crypto_weekly)
        _tag_recs_live("daytrade",     daytrade_recs,
                       sl_key="daytrade_stop_loss_price", tp_key="daytrade_take_profit_price")
        _tag_recs_live("stock_dt",     stock_dt_recs,
                       sl_key="daytrade_stop_loss_price", tp_key="daytrade_take_profit_price")
        _tag_recs_live("crypto_dt",    crypto_dt_recs,
                       sl_key="daytrade_stop_loss_price", tp_key="daytrade_take_profit_price")
        _tag_recs_live("crypto_mr",    crypto_mr_recs)
        _tag_recs_live("stock_intra",  stock_intraday_recs,
                       sl_key="intraday_stop_loss_price", tp_key="intraday_take_profit_price")
        _tag_recs_live("crypto_intra", crypto_intraday_recs,
                       sl_key="intraday_stop_loss_price", tp_key="intraday_take_profit_price")

    for rows in (recs, week_recs, stock_recs, stock_week_recs,
                 crypto_weekly, daytrade_recs, stock_dt_recs, crypto_dt_recs,
                 crypto_mr_recs, stock_intraday_recs, crypto_intraday_recs):
        attach_market_fields(rows)

    crypto_weekly_trade_suggestions = build_crypto_weekly_trade_suggestions(crypto_weekly)
    attach_market_fields(crypto_weekly_trade_suggestions)

    print_recommendations(recs, robust_set, weak_set)
    print_week_recommendations(week_recs)
    print_stock_recommendations(stock_recs)
    print_stock_week_recommendations(stock_week_recs)
    print_crypto_weekly_trade_suggestions(crypto_weekly_trade_suggestions)
    print_crypto_weekly_recommendations(crypto_weekly)
    print_daytrade_recommendations(daytrade_recs)
    print_stock_daytrade_recommendations(stock_dt_recs)
    print_crypto_daytrade_recommendations(crypto_dt_recs)
    print_crypto_mean_reversion_recommendations(crypto_mr_recs)
    print_stock_intraday_recommendations(stock_intraday_recs)
    print_crypto_intraday_recommendations(crypto_intraday_recs)

    # ============== CSV EXPORTS ==============
    snapshot_dir = run_context["snapshot_dir"]
    _remember_output("scan_results", write_dataframe_export(
        pd.DataFrame(scan_rows), OUTDIR, "scan_results.csv", snapshot_dir=snapshot_dir))
    _remember_output("backtest_trades", write_dataframe_export(
        pd.DataFrame(all_trades), OUTDIR, "backtest_trades.csv", snapshot_dir=snapshot_dir))
    _remember_output("backtest_summary", write_dataframe_export(
        pd.DataFrame(bt_summary), OUTDIR, "backtest_summary.csv", snapshot_dir=snapshot_dir))
    _remember_output("sweep_results", write_dataframe_export(
        sweep_df, OUTDIR, "sweep_results.csv", snapshot_dir=snapshot_dir))
    _remember_output("oos_verdict", write_dataframe_export(
        pd.DataFrame(oos_results), OUTDIR, "oos_verdict.csv", snapshot_dir=snapshot_dir))
    _remember_output("recommendations", write_dataframe_export(
        pd.DataFrame(recs), OUTDIR, "recommendations.csv", snapshot_dir=snapshot_dir,
        allow_empty=False))
    _remember_output("week_recommendations", write_dataframe_export(
        pd.DataFrame(week_recs), OUTDIR, "week_recommendations.csv", snapshot_dir=snapshot_dir,
        allow_empty=False))
    _remember_output("stock_recommendations", write_dataframe_export(
        pd.DataFrame(stock_recs), OUTDIR, "stock_recommendations.csv", snapshot_dir=snapshot_dir,
        allow_empty=False))
    _remember_output("stock_week_recommendations", write_dataframe_export(
        pd.DataFrame(stock_week_recs), OUTDIR, "stock_week_recommendations.csv", snapshot_dir=snapshot_dir,
        allow_empty=False))
    _remember_output("crypto_weekly_recommendations", write_dataframe_export(
        pd.DataFrame(crypto_weekly), OUTDIR, "crypto_weekly_recommendations.csv", snapshot_dir=snapshot_dir,
        allow_empty=False))
    _remember_output("crypto_weekly_trade_suggestions", write_dataframe_export(
        pd.DataFrame(crypto_weekly_trade_suggestions, columns=CRYPTO_WEEKLY_TRADE_SUGGESTION_COLUMNS),
        OUTDIR, CRYPTO_WEEKLY_TRADE_SUGGESTIONS_CSV, snapshot_dir=snapshot_dir))
    _remember_output("daytrade_recommendations", write_dataframe_export(
        pd.DataFrame(daytrade_recs), OUTDIR, "daytrade_recommendations.csv", snapshot_dir=snapshot_dir,
        allow_empty=False))
    _remember_output("stock_daytrade_recommendations", write_dataframe_export(
        pd.DataFrame(stock_dt_recs), OUTDIR, "stock_daytrade_recommendations.csv", snapshot_dir=snapshot_dir,
        allow_empty=False))
    _remember_output("crypto_daytrade_recommendations", write_dataframe_export(
        pd.DataFrame(crypto_dt_recs), OUTDIR, "crypto_daytrade_recommendations.csv", snapshot_dir=snapshot_dir,
        allow_empty=False))
    _remember_output("crypto_mean_reversion_recommendations", write_dataframe_export(
        pd.DataFrame(crypto_mr_recs), OUTDIR, "crypto_mean_reversion_recommendations.csv", snapshot_dir=snapshot_dir,
        allow_empty=False))
    _remember_output("stock_intraday_recommendations", write_dataframe_export(
        pd.DataFrame(stock_intraday_recs), OUTDIR, "stock_intraday_recommendations.csv", snapshot_dir=snapshot_dir,
        allow_empty=False))
    _remember_output("crypto_intraday_recommendations", write_dataframe_export(
        pd.DataFrame(crypto_intraday_recs), OUTDIR, "crypto_intraday_recommendations.csv", snapshot_dir=snapshot_dir,
        allow_empty=False))
    _remember_output("rejection_report", write_dataframe_export(
        pd.DataFrame(rejection_rows), OUTDIR, REJECTION_REPORT_CSV, snapshot_dir=snapshot_dir))
    _remember_output("data_quality_report", write_dataframe_export(
        pd.DataFrame(quality_rows), OUTDIR, DATA_QUALITY_REPORT_CSV, snapshot_dir=snapshot_dir))
    _remember_output("portfolio_plan", write_dataframe_export(
        pd.DataFrame(portfolio_plan_rows), OUTDIR, PORTFOLIO_PLAN_CSV, snapshot_dir=snapshot_dir))

    run_summary = build_run_summary(
        run_context,
        track_rows,
        quality_summary,
        risk_summary,
        rejection_rows,
        output_files,
        asset_count=asset_count,
        failed_count=len(failed),
    )
    if GENERATE_HTML_DASHBOARD:
        dashboard_html = render_html_dashboard(
            run_summary,
            track_rows,
            quality_rows,
            rejection_rows,
            risk_summary,
            oos_results,
        )
        _remember_output("dashboard", write_text_export(
            dashboard_html, OUTDIR, DASHBOARD_HTML, snapshot_dir=snapshot_dir))

    run_summary = build_run_summary(
        run_context,
        track_rows,
        quality_summary,
        risk_summary,
        rejection_rows,
        output_files,
        asset_count=asset_count,
        failed_count=len(failed),
    )
    _remember_output("run_summary", write_json_export(
        run_summary, OUTDIR, RUN_SUMMARY_JSON, snapshot_dir=snapshot_dir))

    notification_results = send_notifications(
        build_notification_message(run_summary),
        webhook_url=NOTIFY_WEBHOOK_URL,
        telegram_token=TELEGRAM_BOT_TOKEN,
        telegram_chat_id=TELEGRAM_CHAT_ID,
    )

    print("\n" + BAR)
    print(" CSVs written to disk (one per recommendation track):")
    print("   --- core data ---")
    print("   scan_results.csv  backtest_trades.csv  backtest_summary.csv  sweep_results.csv  oos_verdict.csv")
    print("   --- WEEK (5-day) ---")
    print("   week_recommendations.csv  stock_week_recommendations.csv  crypto_weekly_recommendations.csv")
    print(f"   {CRYPTO_WEEKLY_TRADE_SUGGESTIONS_CSV}")
    print("   --- DAY (1-3 day) ---")
    print("   daytrade_recommendations.csv  stock_daytrade_recommendations.csv  crypto_daytrade_recommendations.csv")
    print("   --- OPS / REPORTING ---")
    print(f"   {REJECTION_REPORT_CSV}  {DATA_QUALITY_REPORT_CSV}  {PORTFOLIO_PLAN_CSV}  {RUN_SUMMARY_JSON}")
    if GENERATE_HTML_DASHBOARD:
        print(f"   {DASHBOARD_HTML}")
    if run_context["snapshot_dir"]:
        print(f"   Snapshot copy: {run_context['snapshot_dir']}")
    if notification_results:
        delivered = ", ".join(
            f"{row['channel']}={'ok' if row['ok'] else 'failed'}"
            for row in notification_results
        )
        print(f"   Notifications: {delivered}")
    print("   crypto_mean_reversion_recommendations.csv")
    print("   --- INTRADAY (hours, hourly bars) ---")
    print("   stock_intraday_recommendations.csv  crypto_intraday_recommendations.csv")
    print("   --- 2-week swing ---")
    print("   recommendations.csv  stock_recommendations.csv")
    print()
    print(" Reminder: crypto recommendations use a €{:.0f} base size and scale down when ATR% is high.".format(CRYPTO_NOTIONAL_EUR))
    print(f" Revolut Free crypto fees are configured at {CRYPTO_FEE_PCT*100:.2f}%/side; lower CRYPTO_FEE_PCT only if you have Premium.")
    print(" Crypto trades 24/7 — set Revolut price alerts for SL/TP because there's no overnight gap protection.")
    print(" Stock intraday: hourly bars only exist during exchange hours, so 24h hold ≈ next-day open.")
    print(" NOT financial advice.")

def main(argv=None):
    """Live-mode wrapper: run scan in a loop, refreshing every LIVE_REFRESH_MIN
    minutes until the user presses Ctrl+C. Set LIVE_MODE=False for a one-shot run."""
    args = parse_cli_args(argv)
    file_config = load_json_config(args.config)
    cli_overrides = collect_cli_overrides(args)
    overrides = merge_runtime_overrides(file_config, cli_overrides)
    apply_global_overrides(globals(), overrides)

    if not LIVE_MODE:
        run_scan(iteration=0)
        return

    print(f"\n{C.BOLD}{C.CYAN}LIVE MODE ON — refresh every {LIVE_REFRESH_MIN} min. "
          f"Ctrl+C to stop.{C.RESET}\n")
    iteration = 0
    try:
        while True:
            iteration += 1
            started = datetime.now()
            print(f"\n{C.BOLD}{C.MAGENTA}" + "#"*135 + f"{C.RESET}")
            print(f"{C.BOLD}{C.MAGENTA}# REFRESH #{iteration} — {started:%Y-%m-%d %H:%M:%S}{C.RESET}")
            print(f"{C.BOLD}{C.MAGENTA}" + "#"*135 + f"{C.RESET}")
            try:
                run_scan(iteration=iteration)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"{C.RED}Scan iteration {iteration} failed: {e}{C.RESET}")
                traceback.print_exc()

            if MAX_LIVE_ITERATIONS and iteration >= MAX_LIVE_ITERATIONS:
                print(f"\n{C.YELLOW}Reached MAX_LIVE_ITERATIONS ({MAX_LIVE_ITERATIONS}). Exiting.{C.RESET}")
                break

            next_refresh = started + timedelta(minutes=LIVE_REFRESH_MIN)
            now = datetime.now()
            sleep_sec = max(0, int((next_refresh - now).total_seconds()))
            print(f"\n{C.DIM}Next refresh at {next_refresh:%H:%M:%S} "
                  f"(~{sleep_sec//60} min {sleep_sec%60} s). Ctrl+C to stop.{C.RESET}")
            try:
                time.sleep(sleep_sec)
            except KeyboardInterrupt:
                raise
    except KeyboardInterrupt:
        print(f"\n\n{C.YELLOW}Stopped by user after {iteration} iteration(s). Goodbye.{C.RESET}")

if __name__ == "__main__":
    main()
