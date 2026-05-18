"""Prototype: cross-sectional ranking model.

Tests the hypothesis from the analysis discussion — that predicting *relative*
performance is more learnable than absolute direction.

Instead of "will this asset rise?" (train_model.py, test AUC 0.49) it asks
"will this asset beat the cross-sectional median over the next 10 days?" and
adds cross-sectional rank features (where each asset sits within the universe
that day). It trains both a logistic regression and a gradient-boosted model,
then reports the metric that actually matters: do the model's top-K picks
outperform the median out-of-sample?

This is a prototype — standalone, not wired into the scanner. If it shows real
edge, the next step is to integrate it; if not, that is strong evidence the
universe is not predictable at this horizon.

Usage:
    python prototype_ranker.py [hold_days] [top_k]
"""
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

import revolut_scanner_v13 as rs
from scanner.model import FEATURES, build_features

HOLD = int(sys.argv[1]) if len(sys.argv) > 1 else 10
TOPK = int(sys.argv[2]) if len(sys.argv) > 2 else 5
MIN_NAMES = 20          # dates need this many assets for a real cross-section
# existing features whose cross-sectional rank we add as new features
RANK_COLS = ["ret20", "ret5", "rsi", "adx", "range_pos", "d_sma200", "macd_hist"]


def build_panel():
    regime = rs.load_regime()
    btc_regime, btc_close = rs.load_btc_regime()
    frames = []
    for ticker, name, cls, currency in rs.load_assets():
        df = rs.load_and_enrich(ticker, regime, btc_regime, btc_close, asset_class=cls)
        if df is None or len(df) < 300:
            continue
        feats = build_features(df, cls).copy()
        fwd = df["Close"].shift(-HOLD) / df["Close"] - 1.0
        feats["fwd"] = fwd
        feats["ticker"] = ticker
        feats["date"] = feats.index
        feats = feats[feats[FEATURES].notna().all(axis=1) & fwd.notna()]
        frames.append(feats)
    panel = pd.concat(frames, ignore_index=True)
    counts = panel.groupby("date")["ticker"].transform("count")
    return panel[counts >= MIN_NAMES].copy()


def topk_lift(test, score_col):
    """Mean (top-K forward return − that date's median) across test dates."""
    lifts, hit = [], []
    for _, g in test.groupby("date"):
        if len(g) < TOPK * 2:
            continue
        med = g["fwd"].median()
        top = g.nlargest(TOPK, score_col)
        lifts.append(top["fwd"].mean() - med)
        hit.append((top["fwd"] > med).mean())
    return np.mean(lifts) * 100, np.mean(hit) * 100, len(lifts)


def main():
    print(f"CROSS-SECTIONAL RANKER PROTOTYPE — {HOLD}-day horizon, top-{TOPK}")
    print("=" * 78)
    panel = build_panel()

    cs_features = []
    for col in RANK_COLS:
        rcol = f"cs_rank_{col}"
        panel[rcol] = panel.groupby("date")[col].rank(pct=True)
        cs_features.append(rcol)

    median_fwd = panel.groupby("date")["fwd"].transform("median")
    panel["y"] = (panel["fwd"] > median_fwd).astype(float)

    model_features = FEATURES + cs_features
    panel = panel.dropna(subset=model_features + ["y"])

    dates = np.sort(panel["date"].unique())
    cut = dates[int(len(dates) * 0.75)]
    train = panel[panel["date"] < cut]
    test = panel[panel["date"] >= cut].copy()
    print(f"panel rows: {len(panel)}   dates: {len(dates)}   "
          f"train {len(train)} / test {len(test)}")
    print(f"label = beat cross-sectional median  (base rate {panel['y'].mean()*100:.1f}%)")

    Xtr, ytr = train[model_features].values, train["y"].values
    Xte, yte = test[model_features].values, test["y"].values
    mean, std = Xtr.mean(0), Xtr.std(0)
    std[std == 0] = 1.0
    Ztr, Zte = (Xtr - mean) / std, (Xte - mean) / std

    lr = LogisticRegression(max_iter=2000).fit(Ztr, ytr)
    gb = HistGradientBoostingClassifier(max_iter=250, max_depth=4).fit(Xtr, ytr)
    test["score_lr"] = lr.predict_proba(Zte)[:, 1]
    test["score_gb"] = gb.predict_proba(Xte)[:, 1]
    auc_lr = roc_auc_score(yte, test["score_lr"])
    auc_gb = roc_auc_score(yte, test["score_gb"])

    print("\nOut-of-sample test AUC:")
    print(f"  logistic regression : {auc_lr:.4f}")
    print(f"  gradient boosting   : {auc_gb:.4f}")
    print(f"  (absolute-direction model from train_model.py was 0.49)")

    print(f"\nTop-{TOPK} lift — mean (top-{TOPK} fwd return − date median), test dates:")
    for label, col in [("logistic", "score_lr"), ("gradient boosting", "score_gb"),
                        ("naive momentum (ret20)", "cs_rank_ret20")]:
        lift, hit, ndays = topk_lift(test, col)
        print(f"  {label:<26}{lift:>+7.3f}%   beats-median rate {hit:>5.1f}%   ({ndays} dates)")

    print("\nGradient-boosting feature importance (permutation, top 12):")
    from sklearn.inspection import permutation_importance
    imp = permutation_importance(gb, Xte, yte, n_repeats=4, random_state=0,
                                 scoring="roc_auc")
    for idx in np.argsort(imp.importances_mean)[::-1][:12]:
        print(f"  {model_features[idx]:<18}{imp.importances_mean[idx]:+.4f}")

    best_auc = max(auc_lr, auc_gb)
    if best_auc >= 0.55:
        verdict = "EDGE — relative ranking is learnable; worth integrating"
    elif best_auc >= 0.52:
        verdict = "MARGINAL — small edge; integrate cautiously"
    else:
        verdict = "NO EDGE — universe not predictable at this horizon"
    print(f"\nVERDICT: {verdict}")


if __name__ == "__main__":
    main()
