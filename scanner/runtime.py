from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence


def _csv_list(value: str | None) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Revolut trade scanner")
    parser.add_argument("--config", help="Path to a JSON runtime config file")
    parser.add_argument("--outdir", help="Output directory override")
    parser.add_argument("--lookback", help="History lookback override, e.g. 3y")
    parser.add_argument("--symbol-overrides", help="Path to a JSON symbol override file")
    parser.add_argument("--asset-classes", help="Comma-separated asset classes to keep")
    parser.add_argument("--tickers", help="Comma-separated ticker allowlist")
    parser.add_argument("--max-assets", type=int, help="Maximum number of assets to scan after filtering")
    parser.add_argument("--run-label", help="Optional run label for snapshots and reports")
    parser.add_argument("--one-shot", action="store_true", help="Run one scan and exit")
    parser.add_argument("--live-mode", dest="live_mode", action="store_true", help="Force live mode on")
    parser.add_argument("--no-live-mode", dest="live_mode", action="store_false", help="Force live mode off")
    parser.add_argument("--refresh-live-prices", dest="refresh_live_prices", action="store_true",
                        help="Refresh live prices before output")
    parser.add_argument("--no-refresh-live-prices", dest="refresh_live_prices", action="store_false",
                        help="Skip live price refresh")
    parser.add_argument("--notify-webhook-url", help="Optional webhook URL for summary notifications")
    parser.add_argument("--telegram-token", help="Optional Telegram bot token")
    parser.add_argument("--telegram-chat-id", help="Optional Telegram chat id")
    parser.add_argument("--snapshot-runs", dest="snapshot_runs", action="store_true",
                        help="Write timestamped run snapshots")
    parser.add_argument("--no-snapshot-runs", dest="snapshot_runs", action="store_false",
                        help="Disable timestamped run snapshots")
    parser.add_argument("--generate-dashboard", dest="generate_dashboard", action="store_true",
                        help="Generate an HTML dashboard")
    parser.add_argument("--no-generate-dashboard", dest="generate_dashboard", action="store_false",
                        help="Disable HTML dashboard generation")
    parser.add_argument("--portfolio-limits", dest="portfolio_limits", action="store_true",
                        help="Enable portfolio limit annotations")
    parser.add_argument("--no-portfolio-limits", dest="portfolio_limits", action="store_false",
                        help="Disable portfolio limit annotations")
    parser.add_argument("--portfolio-filter", dest="portfolio_filter", action="store_true",
                        help="Filter recommendations through the portfolio limit plan")
    parser.add_argument("--no-portfolio-filter", dest="portfolio_filter", action="store_false",
                        help="Keep recommendations but still annotate them with portfolio checks")
    parser.set_defaults(live_mode=None, refresh_live_prices=None,
                        snapshot_runs=None, generate_dashboard=None,
                        portfolio_limits=None, portfolio_filter=None)
    return parser


def parse_cli_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_arg_parser().parse_args(argv)


def load_json_config(path: str | None) -> Dict[str, Any]:
    if not path:
        return {}
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Runtime config must be a JSON object")
    return data


def collect_cli_overrides(args: argparse.Namespace) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}
    mapping = {
        "outdir": "OUTDIR",
        "lookback": "LOOKBACK",
        "symbol_overrides": "SYMBOL_OVERRIDES_JSON",
        "run_label": "RUN_LABEL",
        "notify_webhook_url": "NOTIFY_WEBHOOK_URL",
        "telegram_token": "TELEGRAM_BOT_TOKEN",
        "telegram_chat_id": "TELEGRAM_CHAT_ID",
    }
    for arg_name, target_name in mapping.items():
        value = getattr(args, arg_name, None)
        if value not in (None, ""):
            overrides[target_name] = value

    if args.live_mode is not None:
        overrides["LIVE_MODE"] = bool(args.live_mode)
    if args.one_shot:
        overrides["LIVE_MODE"] = False
    if args.refresh_live_prices is not None:
        overrides["REFRESH_LIVE_PRICES"] = bool(args.refresh_live_prices)
    if args.snapshot_runs is not None:
        overrides["SNAPSHOT_RUNS"] = bool(args.snapshot_runs)
    if args.generate_dashboard is not None:
        overrides["GENERATE_HTML_DASHBOARD"] = bool(args.generate_dashboard)
    if args.portfolio_limits is not None:
        overrides["PORTFOLIO_LIMITS_ENABLED"] = bool(args.portfolio_limits)
    if args.portfolio_filter is not None:
        overrides["PORTFOLIO_FILTER_RECOMMENDATIONS"] = bool(args.portfolio_filter)
    if args.max_assets is not None:
        overrides["RUNTIME_MAX_ASSETS"] = int(args.max_assets)

    asset_classes = _csv_list(getattr(args, "asset_classes", None))
    if asset_classes:
        overrides["RUNTIME_ONLY_ASSET_CLASSES"] = asset_classes
    tickers = _csv_list(getattr(args, "tickers", None))
    if tickers:
        overrides["RUNTIME_ONLY_TICKERS"] = tickers
    return overrides


def merge_runtime_overrides(*configs: Mapping[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for config in configs:
        if not config:
            continue
        for key, value in config.items():
            if value is not None:
                merged[key] = value
    return merged


def apply_global_overrides(namespace: Dict[str, Any], overrides: Mapping[str, Any]) -> None:
    for key, value in overrides.items():
        namespace[key] = value


def filter_assets(
    assets: Sequence[tuple[str, str, str, str]],
    only_asset_classes: Iterable[str] | None = None,
    only_tickers: Iterable[str] | None = None,
    max_assets: int | None = None,
) -> List[tuple[str, str, str, str]]:
    filtered = list(assets)
    classes = {item.strip() for item in (only_asset_classes or []) if item and item.strip()}
    tickers = {item.strip() for item in (only_tickers or []) if item and item.strip()}
    if classes:
        filtered = [asset for asset in filtered if asset[2] in classes]
    if tickers:
        filtered = [asset for asset in filtered if asset[0] in tickers]
    if max_assets and max_assets > 0:
        filtered = filtered[:max_assets]
    return filtered
