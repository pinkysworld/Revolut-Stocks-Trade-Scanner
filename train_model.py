"""Train the swing win-probability model.

Builds a feature matrix from the whole instrument universe, labels each bar by
whether the 10-day forward return was positive, fits a logistic regression with
a chronological train/test split, and writes `model_weights.json`.

Needs scikit-learn (a dev dependency). The scanner itself only reads the JSON.

Usage:
    python train_model.py
"""
import datetime
import json

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

import revolut_scanner_v13 as rs
from scanner.model import FEATURES, build_features

HOLD = 10
TRAIN_FRACTION = 0.75


def main():
    regime = rs.load_regime()
    btc_regime, btc_close = rs.load_btc_regime()
    assets = rs.load_assets()

    frames = []
    for ticker, name, cls, currency in assets:
        df = rs.load_and_enrich(ticker, regime, btc_regime, btc_close, asset_class=cls)
        if df is None or len(df) < 300:
            continue
        feats = build_features(df, cls)
        fwd = df["Close"].shift(-HOLD) / df["Close"] - 1.0
        feats["__y"] = (fwd > 0).astype(float)
        feats["__cls"] = cls
        feats = feats[feats[FEATURES].notna().all(axis=1) & fwd.notna()]
        frames.append(feats)

    data = pd.concat(frames).sort_index()
    if len(data) < 5000:
        print(f"Only {len(data)} samples — too few to train a reliable model.")
        return

    split = int(len(data) * TRAIN_FRACTION)
    train, test = data.iloc[:split], data.iloc[split:]
    Xtr, ytr = train[FEATURES].values, train["__y"].values
    Xte, yte = test[FEATURES].values, test["__y"].values

    mean = Xtr.mean(axis=0)
    std = Xtr.std(axis=0)
    std[std == 0] = 1.0
    Ztr = (Xtr - mean) / std
    Zte = (Xte - mean) / std

    clf = LogisticRegression(max_iter=2000, C=1.0)
    clf.fit(Ztr, ytr)
    auc_tr = roc_auc_score(ytr, clf.predict_proba(Ztr)[:, 1])
    auc_te = roc_auc_score(yte, clf.predict_proba(Zte)[:, 1])
    base_rate = float(ytr.mean())

    print(f"samples: {len(data)}  (train {len(ytr)}, test {len(yte)})")
    print(f"base win rate (train): {base_rate*100:.1f}%")
    print(f"train AUC {auc_tr:.4f}   test AUC {auc_te:.4f}")
    verdict = ("USEFUL — meaningfully better than chance" if auc_te >= 0.55
               else "MARGINAL — slight edge" if auc_te >= 0.52
               else "NO EDGE — not better than chance")
    print(f"verdict: {verdict}")

    print("\nStandardized coefficients (signed feature importance):")
    for f, c in sorted(zip(FEATURES, clf.coef_[0]), key=lambda kv: -abs(kv[1])):
        print(f"  {f:<16}{c:+.4f}")

    model = {
        "features": FEATURES,
        "coef": [round(c, 6) for c in clf.coef_[0].tolist()],
        "intercept": round(float(clf.intercept_[0]), 6),
        "mean": [round(m, 8) for m in mean.tolist()],
        "std": [round(s, 8) for s in std.tolist()],
        "hold_days": HOLD,
        "trained_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "train_auc": round(float(auc_tr), 4),
        "test_auc": round(float(auc_te), 4),
        "n_train": int(len(ytr)),
        "n_test": int(len(yte)),
    }
    with open("model_weights.json", "w", encoding="utf-8") as fh:
        json.dump(model, fh, indent=1)
    print("\nWrote model_weights.json")


if __name__ == "__main__":
    main()
