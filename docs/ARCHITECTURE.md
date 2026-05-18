# Architecture

## Main Flow

The scanner entrypoint is [revolut_scanner_v13.py](../revolut_scanner_v13.py).

The repo no longer keeps multiple tracked `revolut_scanner_v*.py` snapshots in the working tree. Historical versions should be inspected through git history; the live code path is the `v13` entrypoint plus extracted support modules in [scanner/runtime.py](../scanner/runtime.py), [scanner/reporting.py](../scanner/reporting.py), [scanner/quality.py](../scanner/quality.py), [scanner/risk.py](../scanner/risk.py), [scanner/indicators.py](../scanner/indicators.py), and [scanner/notifications.py](../scanner/notifications.py).

[scanner/indicators.py](../scanner/indicators.py) holds the pure technical-indicator functions (moving averages, RSI, MACD, ATR, Bollinger bands, ADX, Donchian channels). They depend only on pandas/numpy and are unit-tested in [tests/test_indicators.py](../tests/test_indicators.py).

A one-shot run follows this path:

1. Load runtime overrides from CLI or JSON config.
2. Load the instrument universe from [revolut_instruments.csv](../revolut_instruments.csv) and apply optional symbol overrides.
3. Load benchmark regime data and the BTC crypto regime overlay.
4. Prefetch daily histories through the local parquet cache in `.yf_cache/`.
5. Enrich each instrument with indicators, reusing `.yf_cache/enriched/` when the latest bar has not changed.
6. Run backtests and cached sweep work, then aggregate 3-fold walk-forward out-of-sample results.
7. Build track-specific recommendation lists.
8. Annotate confidence tiers, portfolio-limit decisions, market-hours metadata, and live TP/SL status.
9. Print terminal output, including the rejection reason summary, and export CSV, JSON, snapshot, and dashboard outputs.

## Recommendation Tracks

- Mixed swing: 2-week horizon, excludes crypto.
- Mixed week: 5-day horizon, excludes crypto.
- Stock swing, stock week, stock daytrade, stock intraday.
- Crypto weekly, crypto daytrade, crypto mean-reversion, crypto intraday.
- Crypto weekly trade suggestions as a compact execution-oriented output.

## Crypto Design Notes

### Fee Model

The current default is Revolut Free-tier pricing:

- `CRYPTO_FEE_PCT = 0.0199`
- Round-trip fee: `3.98%`

The crypto move floors are derived from round-trip fees plus a buffer, so the headline thresholds themselves still imply a positive edge after fees.

### OOS Segmentation

Crypto is reported in two OOS buckets:

- `crypto_major`
- `crypto_alt`

This keeps the diagnostic sweep from mixing BTC/ETH-style behavior with long-tail altcoins.

The scanner now uses rolling 3-fold walk-forward windows for OOS aggregation instead of a single fixed train/test split. This gives the sweep a more useful view across recent regimes while still keeping train/test separation.

Weekly crypto recommendations still require stronger confirmation than the class-level sweep alone:

- positive per-ticker full OOS average
- positive per-ticker test OOS average
- positive net after fees
- reward:risk above the configured floor

That means a bucket can be `OVERFIT` while an individual coin still survives if its own OOS path is strong enough.

## Cached Data

Daily and intraday yfinance downloads are cached under `.yf_cache/` to avoid repeated full downloads and speed up reruns.

Additional derived caches are stored alongside the raw data:

- `.yf_cache/enriched/`: indicator-enriched DataFrames keyed by ticker, asset class, and last bar date.
- `.yf_cache/sweep/`: per-ticker sweep/backtest JSON rows keyed by the latest bar date and walk-forward setting.

These derived caches are runtime artifacts. They can be deleted safely when a fully fresh scan is needed.

## Live Tracking And Notifications

Live price refreshes are batched with a thread pool before per-recommendation TP/SL tagging. Each refreshed recommendation stores `live_price_as_of` for dashboard display.

Prior live status is saved in `live_state.json`. New TP HIT and SL HIT transitions are queued during tagging and flushed through the existing Telegram/webhook notification layer.

## Dashboard Rendering

[scanner/reporting.py](../scanner/reporting.py) renders `dashboard.html` as a compact operational scanner dashboard. The page includes summary stats, track coverage, top ideas, guardrails, data quality, rejection counts, OOS verdicts, and recommendation cards.

In live mode, the dashboard receives a meta refresh interval and recommendation cards show price drift versus scan price plus the live price timestamp.

## Generated Artifacts

The scanner writes CSV outputs into the repo root by default. These are intentionally ignored by git in [.gitignore](../.gitignore).

Operational outputs now also include:

- `rejection_report.csv`
- `data_quality_report.csv`
- `portfolio_plan.csv`
- `run_summary.json`
- `dashboard.html`
- `live_state.json`
- `runs/<timestamp>_*` snapshot directories when snapshots are enabled
