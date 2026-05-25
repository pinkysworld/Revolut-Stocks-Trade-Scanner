"""Tests for core scoring / backtest / fee logic in the scanner entrypoint."""
import numpy as np
import pandas as pd
import pytest

import revolut_scanner_v13 as scanner


# --------------------------- fees_open_close ---------------------------

def test_fees_stock_are_flat():
    assert scanner.fees_open_close("stock", 5000.0) == (
        scanner.STOCK_FEE_OPEN_EUR, scanner.STOCK_FEE_CLOSE_EUR)
    assert scanner.fees_open_close("etf", 5000.0) == (
        scanner.STOCK_FEE_OPEN_EUR, scanner.STOCK_FEE_CLOSE_EUR)


def test_fees_crypto_are_percentage_of_notional():
    of, cf = scanner.fees_open_close("crypto", 100.0)
    assert of == cf == pytest.approx(100.0 * scanner.CRYPTO_FEE_PCT)


def test_fees_equity_cfd_respects_minimum():
    of, cf = scanner.fees_open_close("equity_cfd", 1.0)  # tiny notional
    assert of == cf == scanner.EQUITY_CFD_FEE_MIN_EUR
    of2, _ = scanner.fees_open_close("equity_cfd", 10000.0)
    assert of2 == pytest.approx(10000.0 * scanner.EQUITY_CFD_FEE_PCT)


def test_fees_unknown_class_is_zero():
    assert scanner.fees_open_close("index_cfd", 1000.0) == (0.0, 0.0)


# ------------------------------ verdict --------------------------------

def test_verdict_insufficient_when_too_few_test_trades():
    assert scanner.verdict(1.0, scanner.MIN_TEST_TRADES - 1, 1.0) == "INSUFFICIENT"


def test_verdict_insufficient_when_test_avg_nan():
    assert scanner.verdict(1.0, 20, float("nan")) == "INSUFFICIENT"


def test_verdict_overfit_when_test_avg_non_positive():
    assert scanner.verdict(2.0, 20, 0.0) == "OVERFIT"
    assert scanner.verdict(2.0, 20, -0.5) == "OVERFIT"


def test_verdict_weak_when_below_robust_floor():
    assert scanner.verdict(2.0, 20, scanner.ROBUST_MIN_TEST_AVG / 2) == "WEAK"


def test_verdict_robust_when_test_holds_up_against_train():
    assert scanner.verdict(1.0, 20, 0.8) == "ROBUST"


def test_verdict_weak_when_test_decays_versus_train():
    assert scanner.verdict(10.0, 20, 1.0) == "WEAK"


# ----------------------------- _oos_gate_ok ----------------------------

def _summ(n, avg):
    return {"n": n, "avg": avg}


def test_oos_gate_accepts_healthy_track():
    assert scanner._oos_gate_ok(_summ(50, 1.0), _summ(35, 1.2), _summ(15, 0.8),
                                min_full=10, min_test=8)


def test_oos_gate_rejects_too_few_full_trades():
    assert not scanner._oos_gate_ok(_summ(5, 1.0), _summ(3, 1.0), _summ(2, 1.0),
                                    min_full=10, min_test=8)


def test_oos_gate_rejects_non_positive_test_avg():
    assert not scanner._oos_gate_ok(_summ(50, 1.0), _summ(35, 1.0), _summ(15, -0.1),
                                    min_full=10, min_test=8)


def test_oos_gate_rejects_negative_train_when_required():
    args = (_summ(50, 1.0), _summ(35, -0.5), _summ(15, 0.8))
    assert not scanner._oos_gate_ok(*args, min_full=10, min_test=8, require_train=True)
    assert scanner._oos_gate_ok(*args, min_full=10, min_test=8, require_train=False)


# --------------------- calibration & CFD leverage ----------------------

def test_calibrated_expected_move_blends_full_and_test():
    # 0.4*full + 0.6*test
    assert scanner.calibrated_expected_move(2.0, 1.0) == pytest.approx(0.4 * 2.0 + 0.6 * 1.0)


def test_calibrated_expected_move_falls_back_to_available():
    assert scanner.calibrated_expected_move(None, 1.5) == 1.5
    assert scanner.calibrated_expected_move(3.0, float("nan")) == 3.0
    assert scanner.calibrated_expected_move(None, None) == 0.0


def test_cfd_leverage_values():
    assert scanner.cfd_leverage("equity_cfd") == 5.0
    assert scanner.cfd_leverage("index_cfd") == 20.0
    assert scanner.cfd_leverage("commodity_cfd") == 10.0
    assert scanner.cfd_leverage("stock") == 1.0
    assert scanner.cfd_leverage("crypto") == 1.0


def test_margin_required_is_notional_over_leverage():
    assert scanner.margin_required("equity_cfd", 5000.0) == pytest.approx(1000.0)
    assert scanner.margin_required("index_cfd", 20000.0) == pytest.approx(1000.0)
    assert scanner.margin_required("stock", 1000.0) == pytest.approx(1000.0)


def test_recalibrate_recs_anchors_roi_to_backtest_and_margin():
    recs = [
        {"asset_class": "stock", "notional": 1000.0,
         "bt_avg": 2.0, "test_avg": 1.0},
        {"asset_class": "equity_cfd", "notional": 5000.0,
         "bt_avg": 2.0, "test_avg": 1.0},
    ]
    scanner.recalibrate_recs(recs, move_key="predicted_move_pct",
                             net_key="predicted_net_eur", roi_key="expected_roi_pct",
                             notional_key="notional",
                             full_avg_key="bt_avg", test_avg_key="test_avg")
    exp_move = 0.4 * 2.0 + 0.6 * 1.0  # = 1.4%
    stock, cfd = recs
    # stock: ROI on full notional == the calibrated move
    assert stock["predicted_move_pct"] == pytest.approx(exp_move)
    assert stock["expected_roi_pct"] == pytest.approx(exp_move)
    assert stock["margin_eur"] == pytest.approx(1000.0)
    # CFD: same move, but ROI on margin is leveraged 5x
    assert cfd["predicted_move_pct"] == pytest.approx(exp_move)
    assert cfd["expected_roi_pct"] == pytest.approx(exp_move * 5.0)
    assert cfd["margin_eur"] == pytest.approx(1000.0)


# ------------------------ momentum factor ------------------------------

def test_momentum_rank_is_cross_sectional_percentile():
    rows = [{"asset_class": "stock", "regime": 1, "mom_raw": m}
            for m in (0.01, 0.05, 0.02, 0.09, 0.04, 0.07)]
    scanner.attach_momentum_factor(rows)
    ranks = sorted(r["momentum_rank"] for r in rows)
    assert ranks[0] == 0.0 and ranks[-1] == 1.0
    # the highest 20-day return gets rank 1.0
    top = max(rows, key=lambda r: r["mom_raw"])
    assert top["momentum_rank"] == 1.0


def test_momentum_gated_neutralised_in_bearish_regime():
    rows = [{"asset_class": "stock", "regime": 1, "mom_raw": m}
            for m in (0.01, 0.05, 0.02, 0.09, 0.04, 0.07)]
    rows[3]["regime"] = -1  # the top-momentum name, but bearish regime
    scanner.attach_momentum_factor(rows)
    assert rows[3]["momentum_rank"] == 1.0      # raw rank still computed
    assert rows[3]["momentum_gated"] == 0.5     # but neutralised for ranking


def test_momentum_small_group_defaults_to_neutral():
    rows = [{"asset_class": "etf", "regime": 1, "mom_raw": 0.03},
            {"asset_class": "etf", "regime": 1, "mom_raw": 0.05}]
    scanner.attach_momentum_factor(rows)  # <5 names -> no cross-section
    assert all(r["momentum_rank"] == 0.5 for r in rows)


# --------------------------- cache freshness ---------------------------

def test_daily_cache_reused_for_the_day(tmp_path):
    import os, time
    p = tmp_path / "h.parquet"
    p.write_text("x")
    two_hours_ago = time.time() - 2 * 3600
    os.utime(p, (two_hours_ago, two_hours_ago))
    # daily data 2h old is still fresh (reused for the day); intraday is not
    assert scanner._cache_is_fresh(str(p), "1d") is True
    assert scanner._cache_is_fresh(str(p), "1h") is False


def test_daily_cache_expires_after_a_day(tmp_path):
    import os, time
    p = tmp_path / "h.parquet"
    p.write_text("x")
    thirteen_hours_ago = time.time() - 13 * 3600
    os.utime(p, (thirteen_hours_ago, thirteen_hours_ago))
    assert scanner._cache_is_fresh(str(p), "1d") is False


# --------------------------- risk-based sizing -------------------------

def test_risk_sizing_equal_risk_for_cash_equity():
    rows = [{"asset_class": "stock", "currency": "USD", "price": 100.0,
             "stop_loss_price": 95.0}]
    scanner.attach_risk_sizing(rows, risk_per_trade=20.0)
    r = rows[0]
    assert r["risk_units"] == 4.0          # 20 / (100-95)
    assert r["risk_notional"] == 400.0
    assert r["risk_margin"] == 400.0       # leverage 1
    assert r["risk_max_loss"] == 20.0


def test_risk_sizing_cfd_margin_is_leveraged():
    rows = [{"asset_class": "equity_cfd", "currency": "USD", "price": 100.0,
             "stop_loss_price": 95.0}]
    scanner.attach_risk_sizing(rows, risk_per_trade=20.0)
    r = rows[0]
    assert r["risk_units"] == 4.0
    assert r["risk_margin"] == pytest.approx(80.0)   # 400 / 5x
    assert r["risk_max_loss"] == 20.0


def test_risk_sizing_crypto_is_fractional():
    rows = [{"asset_class": "crypto", "currency": "USD", "price": 100.0,
             "stop_loss_price": 90.0}]
    scanner.attach_risk_sizing(rows, risk_per_trade=20.0)
    r = rows[0]
    assert r["risk_units"] == pytest.approx(2.0)      # 20 / 10, fractional
    assert r["risk_max_loss"] == pytest.approx(20.0)


def test_risk_sizing_uses_track_specific_stop_key():
    rows = [{"asset_class": "stock", "currency": "USD", "price": 50.0,
             "daytrade_stop_loss_price": 48.0}]
    scanner.attach_risk_sizing(rows, risk_per_trade=10.0)
    assert rows[0]["risk_units"] == 5.0   # 10 / (50-48)


def test_risk_sizing_is_fractional_not_floored():
    # high-priced instrument: units stay fractional so the risk target is exact
    rows = [{"asset_class": "index_cfd", "currency": "USD", "price": 30000.0,
             "stop_loss_price": 29250.0}]  # 750 risk per unit
    scanner.attach_risk_sizing(rows, risk_per_trade=20.0)
    r = rows[0]
    assert r["risk_units"] == pytest.approx(20.0 / 750.0)
    assert r["risk_max_loss"] == pytest.approx(20.0)   # hits the budget, not floored to 1


def test_risk_sizing_skips_invalid():
    rows = [{"asset_class": "stock", "currency": "USD", "price": 100.0,
             "stop_loss_price": 105.0}]  # stop above entry
    scanner.attach_risk_sizing(rows, risk_per_trade=20.0)
    assert "risk_units" not in rows[0]


def test_risk_sizing_reads_global_at_call_time(monkeypatch):
    # a runtime-config override of RISK_PER_TRADE must take effect (default-arg
    # binding used to freeze it at import)
    monkeypatch.setattr(scanner, "RISK_PER_TRADE", 50.0)
    rows = [{"asset_class": "stock", "currency": "USD", "price": 100.0,
             "stop_loss_price": 95.0}]
    scanner.attach_risk_sizing(rows)  # no explicit budget -> uses the global
    assert rows[0]["risk_max_loss"] == pytest.approx(50.0)
    assert rows[0]["risk_units"] == pytest.approx(10.0)  # 50 / 5


# ------------------------------ simulate -------------------------------

def _rising_frame(n=260, step=1.0):
    idx = pd.date_range("2022-01-01", periods=n, freq="D")
    close = pd.Series(np.arange(100.0, 100.0 + n * step, step)[:n], index=idx)
    return pd.DataFrame({"Close": close}, index=idx)


def test_simulate_generates_profitable_trades_on_uptrend():
    df = _rising_frame()
    scores = pd.Series(6.0, index=df.index)
    trades = scanner.simulate(df, scores, "stock", "EUR", threshold=5, hold=5,
                              apply_slippage=False)
    assert len(trades) > 0
    assert all(t["net_pl_eur"] > 0 for t in trades)
    assert all(t["exit"] > t["entry"] for t in trades)


def test_simulate_skips_when_scores_below_threshold():
    df = _rising_frame()
    scores = pd.Series(2.0, index=df.index)
    trades = scanner.simulate(df, scores, "stock", "EUR", threshold=5, hold=5)
    assert trades == []


def test_simulate_trades_do_not_overlap():
    df = _rising_frame()
    scores = pd.Series(6.0, index=df.index)
    trades = scanner.simulate(df, scores, "stock", "EUR", threshold=5, hold=5,
                              apply_slippage=False)
    dates = [t["entry_date"] for t in trades]
    assert len(dates) == len(set(dates))


def test_simulate_slippage_reduces_net():
    df = _rising_frame()
    scores = pd.Series(6.0, index=df.index)
    no_slip = scanner.simulate(df, scores, "crypto", "USD", threshold=5, hold=5,
                               apply_slippage=False)
    with_slip = scanner.simulate(df, scores, "crypto", "USD", threshold=5, hold=5,
                                 apply_slippage=True)
    assert sum(t["net_pl_eur"] for t in with_slip) < sum(t["net_pl_eur"] for t in no_slip)


# ------------------------------ summarize ------------------------------

def test_summarize_empty_trades():
    out = scanner.summarize([])
    assert out["n"] == 0
    assert np.isnan(out["avg"])


def test_summarize_winrate_and_totals():
    trades = [
        {"ret_pct": 2.0, "net_pl_eur": 20.0},
        {"ret_pct": -1.0, "net_pl_eur": -10.0},
        {"ret_pct": 3.0, "net_pl_eur": 30.0},
        {"ret_pct": 1.0, "net_pl_eur": 10.0},
    ]
    out = scanner.summarize(trades)
    assert out["n"] == 4
    assert out["win_rate"] == pytest.approx(75.0)
    assert out["total"] == pytest.approx(50.0)
    assert out["profit_factor"] == pytest.approx(60.0 / 10.0)


# ----------------------------- compute_score ---------------------------

def _neutral_bar():
    """A bar where no scoring signal fires -> score 0."""
    return {
        "Close": 100.0, "Open": 100.0, "High": 101.0, "Low": 99.0,
        "SMA20": 101.0, "SMA50": 102.0, "SMA200": 103.0,
        "EMA8": 100.0, "EMA21": 101.0,
        "RSI": 70.0, "MACD": -1.0, "MACDsig": 0.0, "MACDhist": -1.0,
        "ATR": 1.0, "ATRpct": 0.05,
        "BBL": 95.0, "BBH": 105.0, "BBWidth": 10.0,
        "BBWidthRank": 0.5, "BBWidthSlope": 0.0,
        "ret3": 0.0, "ret5": 0.0, "ret20": 0.0,
        "SMA20slope": -1.0, "HH20": 110.0, "DonchH": 110.0,
        "RangePos": 0.5, "VolRatio": 1.0,
        "ADX": 20.0, "ADXprev": 20.0, "Regime": 0,
    }


def test_compute_score_neutral_bar_is_zero():
    bar = _neutral_bar()
    score, signals = scanner.compute_score(bar, dict(bar))
    assert score == 0
    assert signals == []


def test_compute_score_rewards_price_above_moving_averages():
    bar = _neutral_bar()
    bar["Close"] = 104.0  # now above SMA20/50/200
    score, signals = scanner.compute_score(bar, _neutral_bar())
    assert score == 3
    assert {"above_SMA20", "above_SMA50", "above_SMA200"}.issubset(set(signals))


def test_compute_score_no_longer_penalizes_overbought_rsi():
    # Attribution showed overbought RSI precedes positive returns (momentum
    # continuation), so the old -1 penalty was removed.
    bar = _neutral_bar()
    bar["RSI"] = 80.0
    score, signals = scanner.compute_score(bar, _neutral_bar())
    assert score == 0
    assert "rsi_overbought" not in signals


def test_compute_score_volume_breakout_bonus():
    bar = _neutral_bar()
    bar["Close"] = 111.0       # above HH20 (110)
    bar["VolRatio"] = 1.4      # >= 1.30 volume confirmation
    score, signals = scanner.compute_score(bar, _neutral_bar())
    assert "20d_breakout_on_volume" in signals
    assert "volume_confirmation" in signals
