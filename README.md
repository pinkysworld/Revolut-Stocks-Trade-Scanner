# Revolut Scanner

A local trading scanner for the Revolut Germany instrument universe, centered around [revolut_scanner_v13.py](revolut_scanner_v13.py).

## What It Does

- Scans stocks, ETFs, equity CFDs, index CFDs, commodity CFDs, and crypto.
- Produces swing, week, daytrade, intraday, and crypto-specific recommendation tracks.
- Uses cached yfinance downloads for faster reruns.
- Includes backtests, train/test out-of-sample verdicts, and CSV exports.
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
.venv/bin/python -c "import revolut_scanner_v13 as s; s.LIVE_MODE=False; s.REFRESH_LIVE_PRICES=False; s.run_scan(iteration=0)"
```

Compile-check the script:

```bash
.venv/bin/python -m py_compile revolut_scanner_v13.py
```

## Key Files

- [LICENSE](LICENSE): MIT license for the code.
- [DISCLAIMER.md](DISCLAIMER.md): trading and liability disclaimer.
- [revolut_scanner_v13.py](revolut_scanner_v13.py): main scanner logic.
- [revolut_instruments.csv](revolut_instruments.csv): editable instrument universe.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): internal flow and design notes.
- [docs/RUNBOOK.md](docs/RUNBOOK.md): operating and tuning notes.
- [docs/GITHUB_SETUP.md](docs/GITHUB_SETUP.md): how to create a remote and push this repo later.
- [CHANGELOG.md](CHANGELOG.md): project history notes.

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
