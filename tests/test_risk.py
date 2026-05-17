import pandas as pd

from scanner.risk import apply_portfolio_limits


TRACK_ROWS = {
    "swing": [
        {
            "ticker": "AAA",
            "asset_class": "stock",
            "price": 100.0,
            "stop_loss_price": 95.0,
            "notional": 1000.0,
            "expected_roi_pct": 7.0,
        },
        {
            "ticker": "BBB",
            "asset_class": "stock",
            "price": 50.0,
            "stop_loss_price": 47.5,
            "notional": 900.0,
            "expected_roi_pct": 6.5,
        },
    ]
}


RETURNS = {
    ("AAA", "stock"): pd.Series([0.01, 0.02, -0.01, 0.03, 0.01] * 6),
    ("BBB", "stock"): pd.Series([0.01, 0.02, -0.01, 0.03, 0.01] * 6),
}


def test_apply_portfolio_limits_rejects_correlated_position_when_filtering():
    filtered, plan, summary = apply_portfolio_limits(
        TRACK_ROWS,
        RETURNS,
        {
            "enabled": True,
            "filter_recommendations": True,
            "max_correlation": 0.8,
            "max_positions_total": 5,
        },
    )
    assert len(filtered["swing"]) == 1
    assert summary["rejected_positions"] == 1
    assert any(str(row["portfolio_reason"]).startswith("correlated_with") for row in plan if not row["portfolio_accept"])
