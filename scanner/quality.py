from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import pandas as pd


DEFAULT_STALE_DAYS = {
    "crypto": 2,
    "stock": 5,
    "etf": 5,
    "equity_cfd": 5,
    "index_cfd": 5,
    "commodity_cfd": 5,
}


def load_symbol_overrides(path: str | None) -> Dict[str, Dict[str, Any]]:
    if not path:
        return {}
    override_path = Path(path)
    if not override_path.exists():
        return {}
    with override_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Symbol overrides must be a JSON object keyed by ticker")
    out: Dict[str, Dict[str, Any]] = {}
    for ticker, payload in data.items():
        if not isinstance(payload, dict):
            continue
        clean_ticker = str(ticker).strip()
        if clean_ticker:
            out[clean_ticker] = payload
    return out


def apply_symbol_overrides(
    assets: Sequence[tuple[str, str, str, str]],
    overrides: Mapping[str, Mapping[str, Any]],
) -> tuple[List[tuple[str, str, str, str]], List[Dict[str, Any]]]:
    filtered: List[tuple[str, str, str, str]] = []
    notes: List[Dict[str, Any]] = []
    seen = set()

    for ticker, name, asset_class, currency in assets:
        payload = dict(overrides.get(ticker, {}))
        if payload.get("enabled") is False:
            notes.append({
                "ticker": ticker,
                "asset_class": asset_class,
                "status": "override_disabled",
                "bars": 0,
                "stale_days": None,
                "missing_close_pct": None,
                "note": payload.get("reason", "Disabled in symbol overrides"),
                "last_bar": None,
                "name": name,
                "currency": currency,
            })
            continue

        updated = (
            str(payload.get("ticker", ticker)).strip() or ticker,
            str(payload.get("name", name)).strip() or name,
            str(payload.get("asset_class", asset_class)).strip() or asset_class,
            str(payload.get("currency", currency)).strip().upper() or currency,
        )
        if updated in seen:
            continue
        seen.add(updated)
        filtered.append(updated)

        if updated != (ticker, name, asset_class, currency):
            notes.append({
                "ticker": updated[0],
                "asset_class": updated[2],
                "status": "override_remapped",
                "bars": None,
                "stale_days": None,
                "missing_close_pct": None,
                "note": payload.get("reason", f"Remapped from {ticker}/{asset_class}"),
                "last_bar": None,
                "name": updated[1],
                "currency": updated[3],
            })
    return filtered, notes


def _normalize_timestamp(value: Any) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    stamp = pd.Timestamp(value)
    if pd.isna(stamp):
        return None
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert("UTC").tz_localize(None)
    return stamp.to_pydatetime()


def assess_history_quality(
    ticker: str,
    asset_class: str,
    df: pd.DataFrame | None,
    *,
    name: str = "",
    currency: str = "",
    error: str | None = None,
    stale_days_map: Mapping[str, int] | None = None,
) -> Dict[str, Any]:
    stale_days_map = stale_days_map or DEFAULT_STALE_DAYS
    row: Dict[str, Any] = {
        "ticker": ticker,
        "asset_class": asset_class,
        "status": "ok",
        "bars": 0,
        "stale_days": None,
        "missing_close_pct": None,
        "note": error or "",
        "last_bar": None,
        "name": name,
        "currency": currency,
    }
    if df is None or df.empty:
        row["status"] = "missing"
        row["note"] = error or "No usable history returned"
        return row

    row["bars"] = int(len(df))
    last_bar = _normalize_timestamp(df.index.max())
    row["last_bar"] = last_bar.isoformat(sep=" ") if last_bar else None
    close_series = df.get("Close")
    if close_series is not None and len(close_series) > 0:
        row["missing_close_pct"] = float(close_series.isna().mean() * 100.0)

    if last_bar is not None:
        age_days = max(0, (datetime.utcnow() - last_bar).days)
        row["stale_days"] = age_days
        if age_days > int(stale_days_map.get(asset_class, 5)):
            row["status"] = "stale"
            row["note"] = row["note"] or f"Last bar is {age_days} day(s) old"

    if row["bars"] < 260 and row["status"] == "ok":
        row["status"] = "short_history"
        row["note"] = row["note"] or "History shorter than ~1 trading year"

    if row["missing_close_pct"] is not None and row["missing_close_pct"] > 1.0 and row["status"] == "ok":
        row["status"] = "warning"
        row["note"] = row["note"] or "Close series has >1% missing values"

    return row


def summarize_quality_rows(rows: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    rows_list = list(rows)
    counts = Counter(str(row.get("status", "unknown")) for row in rows_list)
    issues = [row for row in rows_list if row.get("status") not in ("ok",)]
    return {
        "total": len(rows_list),
        "ok": counts.get("ok", 0),
        "status_counts": dict(counts),
        "issue_count": len(issues),
        "issues": issues[:20],
    }
