from types import SimpleNamespace

from scanner.runtime import collect_cli_overrides, filter_assets, merge_runtime_overrides


ASSETS = [
    ("BTC-USD", "Bitcoin", "crypto", "USD"),
    ("AAPL", "Apple", "stock", "USD"),
    ("SPY", "SPDR S&P 500", "etf", "USD"),
]


def test_filter_assets_respects_class_ticker_and_limit():
    filtered = filter_assets(
        ASSETS,
        only_asset_classes=["stock", "crypto"],
        only_tickers=["BTC-USD", "AAPL"],
        max_assets=1,
    )
    assert filtered == [("BTC-USD", "Bitcoin", "crypto", "USD")]


def test_merge_runtime_overrides_prefers_later_values():
    merged = merge_runtime_overrides({"OUTDIR": "one", "LIVE_MODE": True}, {"OUTDIR": "two"})
    assert merged["OUTDIR"] == "two"
    assert merged["LIVE_MODE"] is True


def test_collect_cli_overrides_includes_new_runtime_toggles():
    args = SimpleNamespace(
        outdir="/tmp/out",
        lookback="1y",
        symbol_overrides="config/custom.json",
        run_label="nightly",
        notify_webhook_url="",
        telegram_token="",
        telegram_chat_id="",
        live_mode=False,
        one_shot=False,
        refresh_live_prices=False,
        snapshot_runs=True,
        generate_dashboard=True,
        portfolio_limits=True,
        portfolio_filter=False,
        max_assets=25,
        asset_classes="",
        tickers="",
    )
    overrides = collect_cli_overrides(args)
    assert overrides["OUTDIR"] == "/tmp/out"
    assert overrides["SYMBOL_OVERRIDES_JSON"] == "config/custom.json"
    assert overrides["PORTFOLIO_LIMITS_ENABLED"] is True
    assert overrides["PORTFOLIO_FILTER_RECOMMENDATIONS"] is False
    assert overrides["RUNTIME_MAX_ASSETS"] == 25
