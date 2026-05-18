import numpy as np
import pandas as pd

from scanner.model import FEATURES, build_features, win_probability


def _enriched_stub(n=60):
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = pd.Series(np.linspace(100, 130, n), index=idx)
    return pd.DataFrame({
        "Close": close,
        "RSI": 55.0, "RSI2": 40.0, "MACDhist": 0.5, "ADX": 25.0,
        "ATRpct": 0.02, "ret3": 0.01, "ret5": 0.02, "ret20": 0.05,
        "RangePos": 0.7, "VolRatio": 1.2, "BBWidthRank": 0.5,
        "BBWidthSlope": 0.0, "SMA20slope": 0.01,
        "SMA20": close * 0.99, "SMA50": close * 0.97, "SMA200": close * 0.9,
        "Regime": 1, "vs_btc_7d": 0.0, "vs_btc_30d": 0.0,
    }, index=idx)


def test_build_features_has_exact_feature_columns():
    feats = build_features(_enriched_stub(), "stock")
    assert list(feats.columns) == FEATURES


def test_build_features_is_crypto_flag():
    assert build_features(_enriched_stub(), "crypto")["is_crypto"].iloc[-1] == 1.0
    assert build_features(_enriched_stub(), "stock")["is_crypto"].iloc[-1] == 0.0


def test_build_features_normalizes_rsi():
    feats = build_features(_enriched_stub(), "stock")
    assert feats["rsi"].iloc[-1] == 0.55


def _toy_model():
    k = len(FEATURES)
    return {
        "features": FEATURES,
        "coef": np.zeros(k),
        "intercept": 0.0,
        "mean": np.zeros(k),
        "std": np.ones(k),
    }


def test_win_probability_zero_model_is_half():
    prob = win_probability(_toy_model(), np.zeros(len(FEATURES)))
    assert prob == 0.5


def test_win_probability_positive_logit():
    model = _toy_model()
    model["intercept"] = 2.0
    assert win_probability(model, np.zeros(len(FEATURES))) > 0.85


def test_win_probability_nan_features_returns_nan():
    feats = np.zeros(len(FEATURES))
    feats[0] = np.nan
    assert np.isnan(win_probability(_toy_model(), feats))
