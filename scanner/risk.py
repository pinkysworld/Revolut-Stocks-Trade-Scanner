from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Mapping, MutableMapping, Sequence, Tuple

import pandas as pd


def _first_positive(row: Mapping[str, Any], keys: Sequence[str]) -> float:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if numeric > 0:
            return numeric
    return 0.0


def resolve_notional(row: Mapping[str, Any]) -> float:
    return _first_positive(
        row,
        [
            "notional",
            "crypto_notional",
            "daytrade_notional",
            "intraday_notional",
            "stock_week_notional",
            "notional_eur",
        ],
    )


def resolve_expected_net_eur(row: Mapping[str, Any]) -> float:
    for key in (
        "predicted_net_eur",
        "daytrade_predicted_net_eur",
        "intraday_predicted_net_eur",
        "expected_net_eur",
    ):
        value = row.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    notional = resolve_notional(row)
    roi = resolve_expected_roi_pct(row)
    if notional > 0 and roi:
        return notional * roi / 100.0
    return 0.0


def resolve_expected_roi_pct(row: Mapping[str, Any]) -> float:
    for key in (
        "expected_roi_pct",
        "daytrade_expected_roi_pct",
        "intraday_expected_roi_pct",
    ):
        value = row.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def resolve_stop_loss_price(row: Mapping[str, Any]) -> float:
    return _first_positive(
        row,
        ["stop_loss_price", "daytrade_stop_loss_price", "intraday_stop_loss_price"],
    )


def estimate_risk_eur(row: Mapping[str, Any]) -> float:
    notional = resolve_notional(row)
    if notional <= 0:
        return 0.0
    try:
        price = float(row.get("price") or 0.0)
    except (TypeError, ValueError):
        price = 0.0
    stop_loss = resolve_stop_loss_price(row)
    if price <= 0 or stop_loss <= 0:
        return 0.0
    return max(0.0, abs(price - stop_loss) / price * notional)


def _correlation_with_accepted(
    row: Mapping[str, Any],
    accepted: Sequence[Mapping[str, Any]],
    returns_lookup: Mapping[Tuple[str, str], pd.Series],
    max_correlation: float,
    min_overlap: int = 20,
) -> tuple[bool, str | None, float | None]:
    ticker = str(row.get("ticker", ""))
    asset_class = str(row.get("asset_class", ""))
    series = returns_lookup.get((ticker, asset_class))
    if series is None or series.empty or not accepted or max_correlation <= 0:
        return False, None, None

    for other in accepted:
        other_series = returns_lookup.get((str(other.get("ticker", "")), str(other.get("asset_class", ""))))
        if other_series is None or other_series.empty:
            continue
        joined = pd.concat([series, other_series], axis=1).dropna()
        if len(joined) < min_overlap:
            continue
        corr = float(joined.iloc[:, 0].corr(joined.iloc[:, 1]))
        if corr >= max_correlation:
            return True, str(other.get("ticker", "")), corr
    return False, None, None


def apply_portfolio_limits(
    track_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    returns_lookup: Mapping[Tuple[str, str], pd.Series],
    config: Mapping[str, Any],
) -> tuple[Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]], Dict[str, Any]]:
    enabled = bool(config.get("enabled", True))
    filter_recommendations = bool(config.get("filter_recommendations", False))
    max_total_risk_eur = float(config.get("max_total_risk_eur", 0.0) or 0.0)
    max_positions_total = int(config.get("max_positions_total", 0) or 0)
    max_positions_per_track = int(config.get("max_positions_per_track", 0) or 0)
    max_positions_per_asset_class = int(config.get("max_positions_per_asset_class", 0) or 0)
    max_crypto_notional_eur = float(config.get("max_crypto_notional_eur", 0.0) or 0.0)
    max_correlation = float(config.get("max_correlation", 0.0) or 0.0)

    accepted_rows: List[Dict[str, Any]] = []
    track_counts: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    total_risk_eur = 0.0
    total_crypto_notional = 0.0
    filtered_tracks: Dict[str, List[Dict[str, Any]]] = {}
    plan_rows: List[Dict[str, Any]] = []

    for track_name, rows in track_rows.items():
        out_rows: List[Dict[str, Any]] = []
        for rank, row in enumerate(rows, 1):
            work = dict(row)
            risk_eur = estimate_risk_eur(work)
            notional = resolve_notional(work)
            expected_net = resolve_expected_net_eur(work)
            reasons: List[str] = []

            if enabled:
                if max_positions_total and len(accepted_rows) >= max_positions_total:
                    reasons.append("max_positions_total")
                if max_positions_per_track and track_counts[track_name] >= max_positions_per_track:
                    reasons.append("max_positions_per_track")
                asset_class = str(work.get("asset_class", ""))
                if max_positions_per_asset_class and class_counts[asset_class] >= max_positions_per_asset_class:
                    reasons.append("max_positions_per_asset_class")
                if max_total_risk_eur and (total_risk_eur + risk_eur) > max_total_risk_eur:
                    reasons.append("max_total_risk_eur")
                if asset_class == "crypto" and max_crypto_notional_eur and (total_crypto_notional + notional) > max_crypto_notional_eur:
                    reasons.append("max_crypto_notional_eur")
                correlated, against, corr = _correlation_with_accepted(
                    work,
                    accepted_rows,
                    returns_lookup,
                    max_correlation,
                )
                if correlated:
                    reasons.append(f"correlated_with:{against}:{corr:.2f}")

            accepted = not reasons
            work["portfolio_accept"] = accepted
            work["portfolio_reason"] = "ok" if accepted else reasons[0]
            work["portfolio_risk_eur"] = risk_eur
            work["portfolio_expected_net_eur"] = expected_net
            work["portfolio_rank"] = rank
            work["portfolio_track"] = track_name

            if accepted:
                accepted_rows.append(work)
                track_counts[track_name] += 1
                class_counts[str(work.get("asset_class", ""))] += 1
                total_risk_eur += risk_eur
                if work.get("asset_class") == "crypto":
                    total_crypto_notional += notional

            if accepted or not filter_recommendations:
                out_rows.append(work)

            plan_rows.append({
                "track": track_name,
                "ticker": work.get("ticker"),
                "asset_class": work.get("asset_class"),
                "portfolio_accept": accepted,
                "portfolio_reason": work["portfolio_reason"],
                "portfolio_rank": rank,
                "portfolio_risk_eur": risk_eur,
                "portfolio_expected_net_eur": expected_net,
                "notional": notional,
                "expected_roi_pct": resolve_expected_roi_pct(work),
            })
        filtered_tracks[track_name] = out_rows

    summary = {
        "enabled": enabled,
        "filter_recommendations": filter_recommendations,
        "accepted_positions": len(accepted_rows),
        "accepted_by_track": dict(track_counts),
        "accepted_by_asset_class": dict(class_counts),
        "total_risk_eur": round(total_risk_eur, 2),
        "total_crypto_notional_eur": round(total_crypto_notional, 2),
        "rejected_positions": sum(1 for row in plan_rows if not row["portfolio_accept"]),
    }
    return filtered_tracks, plan_rows, summary
