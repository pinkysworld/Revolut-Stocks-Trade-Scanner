# Changelog

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
