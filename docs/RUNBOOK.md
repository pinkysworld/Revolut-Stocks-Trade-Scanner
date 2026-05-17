# Runbook

## One-Shot Scan

```bash
.venv/bin/python -c "import revolut_scanner_v13 as s; s.LIVE_MODE=False; s.REFRESH_LIVE_PRICES=False; s.run_scan(iteration=0)"
```

## Compile Check

```bash
.venv/bin/python -m py_compile revolut_scanner_v13.py
```

## Common Tuning Knobs

All of these live in [revolut_scanner_v13.py](../revolut_scanner_v13.py):

- `CRYPTO_FEE_PCT`: set this to match your Revolut plan.
- `CRYPTO_NOTIONAL_EUR`: base crypto position size.
- `CRYPTO_WEEKLY_MIN_PREDICTED_PCT`
- `CRYPTO_DAYTRADE_MIN_PREDICTED_PCT`
- `CRYPTO_INTRADAY_MIN_PREDICTED_PCT`
- `MIN_RR_RATIO`
- `ALLOW_WEAK_CLASSES`
- `REFRESH_LIVE_PRICES`
- `LIVE_MODE`

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

For a fast development smoke test, shrink the asset universe in a short inline runner and point outputs to a temp directory. Repo memory already captures that pattern.
