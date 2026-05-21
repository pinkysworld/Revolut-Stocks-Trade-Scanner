# Changelog

## 2026-05-21

- Added volatility-targeted position sizing (`attach_risk_sizing`,
  `RISK_PER_TRADE`): each recommendation shows a suggested size so that hitting
  the stop-loss costs roughly a fixed risk budget. Because the stop is
  ATR-derived, volatile names are sized smaller — equal risk per position rather
  than equal notional. CFD sizes show the leveraged margin; advisory only.
- Documented the survivorship bias prominently: backtests/OOS use only
  instruments that exist today, so historical win rates and averages are
  optimistically biased. Now stated in the run footer and the README.
- Fixed CI: bare `pytest` could not import the package; added
  `pyproject.toml` with `pythonpath = ["."]`.

## 2026-05-19 (performance journal)

- Added a live performance journal ([scanner/journal.py](scanner/journal.py)) that
  closes the loop on the scanner: every surfaced recommendation is logged to
  `journal.csv` (deduped per track/ticker/day), then scored against the actual
  price path that followed — take-profit hit, stop-loss hit, or timed out at the
  hold horizon (stop assumed first on ambiguous bars). Each scan prints a running
  track record (win rate, average realized return, TP/SL/time counts, per track).
- Added `journal_report.py` for a detailed review of realized outcomes and recent
  closed trades, and unit tests covering logging dedup and TP/SL/TIME scoring.

## 2026-05-19

- Investigated two prediction-improvement ideas with measurement before
  integration. Earnings surprise (`analyze_earnings.py`, `scanner/fundamentals.py`):
  no post-earnings drift in this large-cap universe (beat vs miss spread
  −0.03%) — not integrated as a predictor. Longer horizon: forward tests
  showed trend signals and a cross-sectional ranker have genuine edge at a
  ~40-day horizon (logistic ranker AUC 0.61, top-5 lift +3.3%) versus none at
  10 days.
- Added a position-trade track (`build_position_recommendations`): ~40-day
  hold, all OOS-robust classes excluding crypto, momentum-ranked, with looser
  OOS minimum-trade gates suited to the longer horizon. New
  `position_recommendations.csv` output.

## 2026-05-18 (scoring & regime)

- Cleaned up `compute_score` using the per-signal attribution: removed the
  signals with negative forward-return lift (`fresh_golden_cross`,
  `rsi_oversold_reversal`, `rsi_healthy`, `macd_bullish_cross`,
  `macd_hist_rising`), dropped the backwards `rsi_overbought` penalty, and
  removed the BTC relative-strength block (it chased pumps; cross-sectional
  strength is now handled by the regime-gated momentum factor). Score
  thresholds lowered to match the smaller score range.
- Added a VIX volatility-regime overlay: a bullish benchmark regime is
  downgraded to neutral when the VIX is elevated and forced bearish when it is
  high — drawdowns and momentum reversals cluster in high-VIX windows.
- Recommendations now show a "Win probability" — the empirical held-out OOS
  backtest win rate (a measured frequency, not a model output).
- Re-fitted the score thresholds against data (`calibrate_thresholds.py`):
  `SCORE_THRESHOLD` 5, `MIN_SCORE_FOR_REC`/`WEEK_MIN_SCORE` 4, and
  `CRYPTO_WEEKLY_MIN_SCORE` 7 (crypto forward-return lift only turns positive
  at score ≥ 7). The calibration also confirmed the score barely discriminates
  for equities at any threshold — the OOS gate and momentum tilt are what
  carry recommendation quality there.

## 2026-05-18 (later)

- Added a regime-gated cross-sectional momentum tilt. `prototype_ranker.py`
  forward-testing showed an ML ranker has no edge but naive cross-sectional
  momentum does (top-5 momentum names beat the median by ~+2.4%/10 days).
  Recommendations are now ranked by `rank_score` — a blend of the calibrated
  ROI percentile and the asset's momentum rank within its peer class
  (`MOMENTUM_TILT_WEIGHT`). The momentum component is neutralised when the
  asset's macro regime is bearish, since momentum reverses in downtrends.
- Cards show a "Momentum rank" line; the tilt is flagged as off in bearish regimes.

## 2026-05-18

- Added `analyze_signals.py` — per-signal attribution showing each scoring
  signal's realized forward-return lift. Found several signals are noise or
  negative-lift (`macd_bullish_cross`, `macro_bullish`, the BTC relative-
  strength signals), and that `rsi_overbought` is wrongly penalised.
- Added an optional ML win-probability model: `scanner/model.py` (numpy-only
  inference), `train_model.py` (scikit-learn training). The model is gated on
  held-out test AUC — the current model scored 0.49 (no edge), so the scanner
  auto-disables it rather than display a misleading number.
- Added optional `isin` / `wkn` columns to the instrument universe; recommendations
  now show WKN/ISIN (best-effort ISIN auto-resolution via yfinance, cached) so
  assets are easier to locate inside Revolut.

## 2026-05-17 (maintainability pass)

- Fixed a regression in the daytrade path: `_score_adx` reads `ADXprev`, but `DAYTRADE_CRIT_COLS` did not list it, so `compute_daytrade_score` raised `KeyError: 'ADXprev'`.
- Extracted the pure technical indicators (`sma`, `ema`, `rsi`, `macd`, `atr`, `bollinger`, `rolling_position`, `adx`, `donchian`) into [scanner/indicators.py](scanner/indicators.py) so they can be unit-tested in isolation.
- Added bounded retries with exponential backoff to yfinance downloads (`YF_DOWNLOAD_RETRIES`, `YF_DOWNLOAD_BACKOFF_SEC`) so transient network/rate-limit failures no longer make scans flaky.
- Extracted shared track-builder helpers (`_enriched_df_and_scores`, `_oos_gate_ok`) to remove duplicated lookup and per-ticker OOS gating logic across the `build_*` recommendation tracks.
- Pinned dependency version ranges in `requirements.txt` / `requirements-dev.txt` so an unattended yfinance/pandas upgrade cannot silently change data shape.
- Added unit tests for indicators, scoring, backtest simulation, fee math, OOS verdict logic, and the new helpers.
- Reworked the console output: boxed section headers, consistent recommendation "cards" with score stars and a market-status badge, aligned label/value rows, a standout EXPECTED NET ROI line, and color applied to ROI, predicted move, fees, win rates, backtest averages, and reward:risk across every recommendation track.
- Recalibrated the predicted-move forecast: paper-trade forward tests showed the volatility-based projection overstated realized returns 2.5x-14x (ATR measures dispersion, not direction). The headline expected move/ROI is now anchored to realized backtest averages (`recalibrate_recs`); ATR volatility is retained only for TP/SL sizing.
- Added a CFD leverage model (`CFD_LEVERAGE`, ESMA retail caps: equity 5:1, index 20:1, commodity 10:1). CFD recommendations now post margin = notional / leverage, express expected ROI on that margin, and show a leverage badge plus a margin line on the card. Overnight financing remains charged on full notional.
- Added `paper_trade.py`, a forward-testing harness that replays each track's entry rule over held-out history to measure detection edge and predicted-move calibration.

## 2026-05-17

- Added live-state persistence to `live_state.json`, parallel live price refreshes, TP/SL instant alerts, and live price timestamps in the dashboard.
- Added price drift versus scan price to recommendation cards and refreshed the HTML dashboard into a denser operational scanner view.
- Added enriched indicator parquet caching under `.yf_cache/enriched/` and sweep/backtest JSON caching under `.yf_cache/sweep/`.
- Replaced the single train/test OOS split with rolling 3-fold walk-forward OOS aggregation.
- Extracted shared ADX and regime scoring helpers and added a console rejection reason summary at the end of each scan.
- Removed legacy `revolut_scanner_v*.py` snapshots from the working tree and standardized the repo on [revolut_scanner_v13.py](revolut_scanner_v13.py) as the only maintained entrypoint.
- Updated README, architecture notes, and runbook instructions to reflect the single-entrypoint layout, extracted support modules, and current reporting outputs.

## 2026-05-16

- Switched the crypto fee model to Revolut Free-tier pricing (`1.99%` per side).
- Made crypto minimum predicted-move floors fee-aware so setups still leave a profit buffer after fees.
- Replaced the blunt weekly crypto class gate with per-ticker OOS enforcement, while keeping risk/reward and net-after-fee filters intact.
- Split crypto out-of-sample reporting into `crypto_major` and `crypto_alt` buckets.
- Added market-status fields and notes to recommendation outputs and CSVs.
- Added local project documentation and git-repo scaffolding.
