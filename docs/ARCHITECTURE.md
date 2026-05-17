# Architecture

## Main Flow

The scanner entrypoint is [revolut_scanner_v13.py](../revolut_scanner_v13.py).

The repo no longer keeps multiple tracked `revolut_scanner_v*.py` snapshots in the working tree. Historical versions should be inspected through git history; the live code path is the `v13` entrypoint plus extracted support modules in [scanner/runtime.py](../scanner/runtime.py), [scanner/reporting.py](../scanner/reporting.py), [scanner/quality.py](../scanner/quality.py), [scanner/risk.py](../scanner/risk.py), and [scanner/notifications.py](../scanner/notifications.py).

A one-shot run follows this path:

1. Load runtime overrides from CLI or JSON config.
2. Load the instrument universe from [revolut_instruments.csv](/Users/michelpicker/Downloads/revolut/revolut_instruments.csv) and apply optional symbol overrides.
3. Load benchmark regime data and the BTC crypto regime overlay.
4. Prefetch daily histories through the local parquet cache in `.yf_cache/`.
5. Enrich each instrument with indicators and generate current scan rows.
6. Run backtests and aggregate train/test out-of-sample results.
7. Build track-specific recommendation lists.
8. Annotate confidence tiers, portfolio-limit decisions, and market-hours metadata.
9. Print terminal output and export CSV, JSON, snapshot, and dashboard outputs.

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

Weekly crypto recommendations still require stronger confirmation than the class-level sweep alone:

- positive per-ticker full OOS average
- positive per-ticker test OOS average
- positive net after fees
- reward:risk above the configured floor

That means a bucket can be `OVERFIT` while an individual coin still survives if its own OOS path is strong enough.

## Cached Data

Daily and intraday yfinance downloads are cached under `.yf_cache/` to avoid repeated full downloads and speed up reruns.

## Generated Artifacts

The scanner writes CSV outputs into the repo root by default. These are intentionally ignored by git in [.gitignore](../.gitignore).

Operational outputs now also include:

- `rejection_report.csv`
- `data_quality_report.csv`
- `portfolio_plan.csv`
- `run_summary.json`
- `dashboard.html`
- `runs/<timestamp>_*` snapshot directories when snapshots are enabled
