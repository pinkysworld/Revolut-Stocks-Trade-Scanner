"""Logistic-regression win-probability model for swing recommendations.

Predicts P(positive 10-day forward return) from indicator features. Training
lives in `train_model.py` (which needs scikit-learn); inference here needs only
numpy/pandas, so the scanner itself stays dependency-light. The trained model
is stored as plain JSON (`model_weights.json`) — standardisation stats plus
logistic coefficients — so there is no pickle/version coupling.

The feature builder is shared by training and inference so the two can never
drift apart.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

MODEL_PATH = os.path.join(os.path.dirname(__file__), os.pardir, "model_weights.json")

FEATURES = [
    "rsi", "rsi2", "macd_hist", "adx", "atr_pct",
    "ret3", "ret5", "ret20", "range_pos", "vol_ratio",
    "bb_width_rank", "bb_width_slope", "sma20_slope",
    "d_sma20", "d_sma50", "d_sma200", "regime",
    "is_crypto", "vs_btc_7d", "vs_btc_30d",
]


def build_features(df: pd.DataFrame, asset_class: str | None = None) -> pd.DataFrame:
    """Build the model feature matrix from an enriched daily DataFrame.

    Returns a DataFrame aligned to df.index with exactly the FEATURES columns.
    Rows with missing indicators stay as NaN; callers drop or skip them.
    """
    close = df["Close"]
    out = pd.DataFrame(index=df.index)
    out["rsi"] = df["RSI"] / 100.0
    out["rsi2"] = df["RSI2"] / 100.0
    out["macd_hist"] = df["MACDhist"] / close.replace(0, np.nan)
    out["adx"] = df["ADX"] / 100.0
    out["atr_pct"] = df["ATRpct"]
    out["ret3"] = df["ret3"]
    out["ret5"] = df["ret5"]
    out["ret20"] = df["ret20"]
    out["range_pos"] = df["RangePos"]
    out["vol_ratio"] = df["VolRatio"].clip(0, 5)
    out["bb_width_rank"] = df["BBWidthRank"]
    out["bb_width_slope"] = df["BBWidthSlope"]
    out["sma20_slope"] = df["SMA20slope"]
    out["d_sma20"] = close / df["SMA20"] - 1.0
    out["d_sma50"] = close / df["SMA50"] - 1.0
    out["d_sma200"] = close / df["SMA200"] - 1.0
    out["regime"] = df["Regime"].astype(float)
    out["is_crypto"] = 1.0 if asset_class == "crypto" else 0.0
    vs7 = df["vs_btc_7d"] if "vs_btc_7d" in df.columns else 0.0
    vs30 = df["vs_btc_30d"] if "vs_btc_30d" in df.columns else 0.0
    out["vs_btc_7d"] = (vs7 / 100.0) if hasattr(vs7, "__len__") else vs7
    out["vs_btc_30d"] = (vs30 / 100.0) if hasattr(vs30, "__len__") else vs30
    return out[FEATURES].replace([np.inf, -np.inf], np.nan)


def load_model(path: str = MODEL_PATH):
    """Load the JSON model. Returns None if absent or incompatible (the scanner
    then simply omits the ML probability — it is an optional enhancement)."""
    try:
        with open(path, encoding="utf-8") as fh:
            m = json.load(fh)
    except Exception:
        return None
    if m.get("features") != FEATURES:
        return None
    m["coef"] = np.asarray(m["coef"], dtype=float)
    m["mean"] = np.asarray(m["mean"], dtype=float)
    m["std"] = np.asarray(m["std"], dtype=float)
    return m


def win_probability(model, feature_row) -> float:
    """P(positive forward return) for one feature row. NaN if features missing."""
    x = np.asarray(feature_row, dtype=float)
    if x.shape != model["coef"].shape or not np.all(np.isfinite(x)):
        return float("nan")
    z = (x - model["mean"]) / model["std"]
    logit = float(np.dot(z, model["coef"]) + model["intercept"])
    return 1.0 / (1.0 + np.exp(-logit))
