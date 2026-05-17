# Revolut Scanner

A local trading scanner for the Revolut Germany instrument universe, centered around [revolut_scanner_v13.py](revolut_scanner_v13.py), which is now the only maintained scanner entrypoint in the repo.

## What It Does

- Scans stocks, ETFs, equity CFDs, index CFDs, commodity CFDs, and crypto.
- Produces swing, week, daytrade, intraday, and crypto-specific recommendation tracks.
- Uses cached yfinance downloads for faster reruns.
- Includes backtests, train/test out-of-sample verdicts, and CSV exports.
- Adds runtime JSON config, symbol override support, timestamped run snapshots, and an HTML dashboard.
- Writes rejection, data-quality, portfolio-plan, and run-summary reports for each scan.
- Keeps only the maintained scanner in the working tree; legacy version snapshots now live in git history instead of separate tracked files.
- Models Revolut Free-tier crypto fees at `1.99%` per side by default.
- Uses fee-aware crypto move floors:
  - Weekly: `5.0%`
  - Daytrade: `5.0%`
  - Intraday: `5.5%`
- Splits crypto out-of-sample diagnostics into `crypto_major` and `crypto_alt` buckets while still requiring per-ticker OOS confirmation before surfacing weekly crypto picks.

## Quick Start

Create or activate a virtual environment, then install the main dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pandas numpy yfinance pyarrow
```

Run a one-shot scan:

```bash
.venv/bin/python revolut_scanner_v13.py --one-shot --no-refresh-live-prices
```

Run with the example config layer and a smaller filtered universe:

```bash
.venv/bin/python revolut_scanner_v13.py \
  --config config/runtime_config.example.json \
  --asset-classes stock,crypto \
  --max-assets 30 \
  --one-shot
```

Compile-check the script:

```bash
.venv/bin/python -m py_compile revolut_scanner_v13.py scanner/*.py
```

Run the test suite:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

## Configuration

- Use [config/runtime_config.example.json](config/runtime_config.example.json) as the starting point for runtime overrides.
- Use [config/symbol_overrides.example.json](config/symbol_overrides.example.json) to disable or remap unstable symbols without editing the main universe file.
- CLI flags can override the config file for common controls such as `--one-shot`, `--asset-classes`, `--max-assets`, `--symbol-overrides`, `--portfolio-filter`, and notification settings.

## New Outputs

- `rejection_report.csv`: per-track acceptance or first broad rejection bucket.
- `data_quality_report.csv`: history health, stale bars, and override notes.
- `portfolio_plan.csv`: portfolio guardrail decisions and estimated per-trade risk.
- `run_summary.json`: machine-readable run metadata and output paths.
- `dashboard.html`: static report with counts, top ideas, OOS verdicts, data issues, and rejection summary.
- `runs/<timestamp>_*`: timestamped snapshot copies of every generated report when snapshots are enabled.

## Key Files

- [LICENSE](LICENSE): MIT license for the code.
- [DISCLAIMER.md](DISCLAIMER.md): trading and liability disclaimer.
- [revolut_scanner_v13.py](revolut_scanner_v13.py): main scanner logic.
- [scanner/runtime.py](scanner/runtime.py): CLI and JSON runtime config support.
- [scanner/reporting.py](scanner/reporting.py): snapshots, dashboard, confidence tiers, and report writers.
- [scanner/quality.py](scanner/quality.py): symbol overrides and data-quality diagnostics.
- [scanner/risk.py](scanner/risk.py): portfolio-aware risk limit annotations and filtering.
- [revolut_instruments.csv](revolut_instruments.csv): editable instrument universe.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): internal flow and design notes.
- [docs/RUNBOOK.md](docs/RUNBOOK.md): operating and tuning notes.
- [docs/GITHUB_SETUP.md](docs/GITHUB_SETUP.md): how to create a remote and push this repo later.
- [CHANGELOG.md](CHANGELOG.md): project history notes.

## Versioning

- The working tree keeps a single maintained scanner: [revolut_scanner_v13.py](revolut_scanner_v13.py).
- Older scanner snapshots were removed from the repo root to reduce confusion and drift.
- If you need to inspect earlier experiments, use git history instead of separate tracked `revolut_scanner_v*.py` files.

## License

This project is open sourced under the [MIT License](LICENSE).

## Disclaimer

This project is not financial advice and is provided for educational and research purposes only.

- All trading and investment decisions remain your responsibility.
- Signals, backtests, forecasts, and scanner outputs can be wrong.
- Use of this software is entirely at your own risk.
- No warranty or liability is accepted beyond the terms stated in the [LICENSE](LICENSE).

See the full [DISCLAIMER.md](DISCLAIMER.md) for the project-specific disclaimer.

## Notes

- Crypto symbols such as `COMP-USD`, `GRT-USD`, `GMX-USD`, `FTM-USD`, `RNDR-USD`, and `MATIC-USD` may intermittently fail in yfinance. The scanner already skips unusable data.
- Generated CSV outputs are ignored in git by default.
- If you later move from Revolut Free to Premium, lower `CRYPTO_FEE_PCT` in [revolut_scanner_v13.py](revolut_scanner_v13.py).
- GitHub Actions now runs a compile check and `pytest` on pushes and pull requests.
