import pandas as pd

from scanner.reporting import (
    assign_confidence_tier,
    build_run_context,
    render_html_dashboard,
    write_dataframe_export,
)


STRONG_ROW = {
    "ticker": "BTC-USD",
    "asset_class": "crypto",
    "score": 8,
    "expected_roi_pct": 9.5,
    "risk_reward": 2.1,
    "test_avg": 1.2,
    "bt_avg": 1.5,
}


def test_assign_confidence_tier_marks_strong_non_crypto_setup_high():
    row = dict(STRONG_ROW)
    row["asset_class"] = "stock"
    out = assign_confidence_tier(row, "stock_swing")
    assert out["confidence_tier"] == "high"
    assert out["confidence_points"] >= 6


def test_write_dataframe_export_creates_snapshot_copy(tmp_path):
    run_context = build_run_context(str(tmp_path), run_label="test", snapshot_runs=True)
    path = write_dataframe_export(
        pd.DataFrame([{"ticker": "BTC-USD"}]),
        str(tmp_path),
        "sample.csv",
        snapshot_dir=run_context["snapshot_dir"],
    )
    assert path is not None
    assert (tmp_path / "sample.csv").exists()
    assert (tmp_path / "runs" / run_context["snapshot_name"] / "sample.csv").exists()


def test_render_html_dashboard_includes_disclaimer_and_console_recommendations():
    html = render_html_dashboard(
        {
            "run_id": "20260517_120000",
            "started_at": "2026-05-17T12:00:00",
            "asset_count": 2,
            "failed_count": 0,
        },
        {
            "swing": [
                {
                    "ticker": "AAPL",
                    "name": "Apple",
                    "asset_class": "stock",
                    "currency": "USD",
                    "price": 189.12,
                    "close_at_scan": "188.00",
                    "live_price_as_of": "12:03",
                    "hold_days": 10,
                    "expected_roi_pct": 5.4,
                    "predicted_net_eur": 7.8,
                    "predicted_move_pct": 8.2,
                    "take_profit_price": 198.5,
                    "stop_loss_price": 184.2,
                    "risk_reward": 1.8,
                    "score": 7,
                    "rsi": "64.5",
                    "adx": "23.7",
                    "regime": "1",
                    "signals": "Trend, breakout",
                    "market_note": "OPEN — place now",
                    "confidence_tier": "high",
                    "confidence_points": 7,
                    "portfolio_accept": True,
                    "bt_trades": 24,
                    "bt_win_rate": 58.0,
                    "bt_avg": 1.4,
                    "test_trades": 7,
                    "test_win_rate": 57.0,
                    "test_avg": 0.8,
                }
            ]
        },
        [],
        [],
        {"accepted_positions": 1, "rejected_positions": 0, "total_risk_eur": 12.0, "total_crypto_notional_eur": 0.0},
        [],
        extra_track_rows={
            "crypto_weekly_trade_suggestions": [
                {
                    "ticker": "BTC-USD",
                    "name": "Bitcoin",
                    "asset_class": "crypto",
                    "currency": "USD",
                    "entry_price": "65000.0",
                    "close_at_scan": "64000.0",
                    "hold_days": 5,
                    "action": "BUY",
                    "notional_eur": 100.0,
                    "units": 0.0015,
                    "expected_net_eur": 4.2,
                    "max_loss_if_sl_eur": -2.4,
                    "risk_reward": 1.75,
                    "market_note": "OPEN 24/7 — place now",
                }
            ]
        },
        refresh_secs=300,
    )
    assert "Educational use only" in html
    assert "content=\"300\"" in html
    assert "Trading Dashboard" in html
    assert "Mixed swing" in html
    assert "Apple" in html
    assert "LIVE entry price" in html
    assert "+0.60% vs scan" in html
    assert "as of 12:03" in html
    assert "64.5 / 23.7 / +1" in html
    assert "Signal score" in html
    assert "Active signals" in html
    assert "Full backtest" in html
    assert "Crypto trade tickets" in html
    assert "+1.56% vs scan" in html
    assert "Bitcoin" in html
