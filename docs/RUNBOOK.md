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
- `PORTFOLIO_LIMITS_ENABLED`
- `PORTFOLIO_FILTER_RECOMMENDATIONS`
- `SYMBOL_OVERRIDES_JSON`
- `RUN_LABEL`

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
