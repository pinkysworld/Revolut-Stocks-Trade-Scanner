import pandas as pd

from scanner.reporting import assign_confidence_tier, build_run_context, write_dataframe_export


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
