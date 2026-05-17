# Runbook

## One-Shot Scan

```bash
.venv/bin/python revolut_scanner_v13.py --one-shot --no-refresh-live-prices
```

To run with the JSON config layer:

```bash
.venv/bin/python revolut_scanner_v13.py --config config/runtime_config.example.json --one-shot
```

## Compile Check

```bash
.venv/bin/python -m py_compile revolut_scanner_v13.py scanner/*.py
```

## Test Suite

```bash
.venv/bin/python -m pytest -q
```

## Live Dashboard Mode

When `LIVE_MODE` is enabled, the scanner refreshes recommendation prices, writes `dashboard.html`, and injects an HTML auto-refresh interval based on `LIVE_REFRESH_MIN`.

Live recommendation cards show price drift versus the scan price and an `as of HH:MM` freshness timestamp. TP/SL status is persisted to `live_state.json`, so restarting the scanner does not lose prior TP HIT or SL HIT state.

If Telegram or webhook settings are configured, new TP HIT and SL HIT transitions are sent immediately after live tagging.

## Common Tuning Knobs

The scanner runtime is split between [revolut_scanner_v13.py](../revolut_scanner_v13.py) and the extracted support modules under [scanner/runtime.py](../scanner/runtime.py), [scanner/reporting.py](../scanner/reporting.py), [scanner/quality.py](../scanner/quality.py), and [scanner/risk.py](../scanner/risk.py).

Common knobs include:

- `CRYPTO_FEE_PCT`: set this to match your Revolut plan.
- `CRYPTO_NOTIONAL_EUR`: base crypto position size.
- `CRYPTO_WEEKLY_MIN_PREDICTED_PCT`
- `CRYPTO_DAYTRADE_MIN_PREDICTED_PCT`
- `CRYPTO_INTRADAY_MIN_PREDICTED_PCT`
- `MIN_RR_RATIO`
- `ALLOW_WEAK_CLASSES`
- `REFRESH_LIVE_PRICES`
- `LIVE_MODE`
- `LIVE_REFRESH_MIN`
- `PORTFOLIO_LIMITS_ENABLED`
- `PORTFOLIO_FILTER_RECOMMENDATIONS`
- `SYMBOL_OVERRIDES_JSON`
- `RUN_LABEL`

## Cache Hygiene

Runtime caches live under `.yf_cache/`:

- raw yfinance parquet downloads
- enriched indicator parquet files under `.yf_cache/enriched/`
- sweep/backtest JSON files under `.yf_cache/sweep/`

The enriched and sweep caches are keyed to the latest bar date, so ordinary reruns should reuse work while new market data naturally invalidates stale entries. Delete `.yf_cache/` if you want a fully cold scan.

## Current Crypto Assumptions

For a Free-tier account, the scanner currently uses:

- `1.99%` fee per side
- `5.0%` weekly minimum predicted move
- `5.0%` crypto daytrade minimum predicted move
- `5.5%` crypto intraday minimum predicted move

These are intentionally conservative enough that a surfaced trade should still have room after fees.

## Known Data Quality Issues

Some yfinance symbols can fail intermittently or appear delisted in recent periods. Recent failures seen in this workspace include:

- `COMP-USD`
- `GRT-USD`
- `GMX-USD`
- `FTM-USD`
- `RNDR-USD`
- `MATIC-USD`

The scanner already skips instruments with unusable data.

## Smoke-Test Pattern

For a fast development smoke test, shrink the asset universe in a short inline runner and point outputs to a temp directory. The current validation pattern also checks that `dashboard.html`, `run_summary.json`, `rejection_report.csv`, `data_quality_report.csv`, and `portfolio_plan.csv` are written.

For dashboard changes, render a small sample through `scanner.reporting.render_html_dashboard()` and inspect it in a browser. Keep the top of the page compact enough that top ideas appear quickly on both desktop and mobile widths.
