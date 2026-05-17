# Changelog

## 2026-05-17

- Removed legacy `revolut_scanner_v*.py` snapshots from the working tree and standardized the repo on [revolut_scanner_v13.py](revolut_scanner_v13.py) as the only maintained entrypoint.
- Updated README, architecture notes, and runbook instructions to reflect the single-entrypoint layout, extracted support modules, and current reporting outputs.

## 2026-05-16

- Switched the crypto fee model to Revolut Free-tier pricing (`1.99%` per side).
- Made crypto minimum predicted-move floors fee-aware so setups still leave a profit buffer after fees.
- Replaced the blunt weekly crypto class gate with per-ticker OOS enforcement, while keeping risk/reward and net-after-fee filters intact.
- Split crypto out-of-sample reporting into `crypto_major` and `crypto_alt` buckets.
- Added market-status fields and notes to recommendation outputs and CSVs.
- Added local project documentation and git-repo scaffolding.
