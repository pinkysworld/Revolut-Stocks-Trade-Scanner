# Architecture

## Main Flow

The scanner entrypoint is [revolut_scanner_v13.py](../revolut_scanner_v13.py).

A one-shot run follows this path:

1. Load the instrument universe from [revolut_instruments.csv](/Users/michelpicker/Downloads/revolut/revolut_instruments.csv).
2. Load benchmark regime data and the BTC crypto regime overlay.
3. Prefetch daily histories through the local parquet cache in `.yf_cache/`.
4. Enrich each instrument with indicators and generate current scan rows.
5. Run backtests and aggregate train/test out-of-sample results.
6. Build track-specific recommendation lists.
7. Attach market-hours metadata.
8. Print terminal output and export CSVs.

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
