import pandas as pd

from scanner import journal


def _price_df(dates, highs, lows, closes):
    idx = pd.to_datetime(dates)
    return pd.DataFrame({"High": highs, "Low": lows, "Close": closes}, index=idx)


def _rec(ticker="AAPL", price=100.0, tp=110.0, sl=95.0, hold=5):
    return {
        "ticker": ticker, "name": ticker, "asset_class": "stock", "currency": "USD",
        "price": price, "take_profit_price": tp, "stop_loss_price": sl, "hold_days": hold,
        "predicted_move_pct": 5.0, "expected_roi_pct": 4.0, "win_probability": 0.6,
        "score": 6, "risk_reward": 1.5,
    }


def test_append_logs_and_dedups(tmp_path):
    path = str(tmp_path / "journal.csv")
    now = pd.Timestamp("2026-01-05").to_pydatetime()
    n1 = journal.append_recommendations(path, {"swing": [_rec()]}, now=now)
    n2 = journal.append_recommendations(path, {"swing": [_rec()]}, now=now)  # same day
    assert n1 == 1
    assert n2 == 0  # deduped
    rows = journal.load_journal(path)
    assert len(rows) == 1
    assert rows[0]["ticker"] == "AAPL" and rows[0]["status"] == "open"


def test_append_skips_when_no_levels(tmp_path):
    path = str(tmp_path / "journal.csv")
    bad = _rec()
    bad["take_profit_price"] = None
    n = journal.append_recommendations(path, {"swing": [bad]}, now=pd.Timestamp("2026-01-05").to_pydatetime())
    assert n == 0


def test_score_take_profit(tmp_path):
    path = str(tmp_path / "journal.csv")
    now = pd.Timestamp("2026-01-05").to_pydatetime()
    journal.append_recommendations(path, {"swing": [_rec(tp=110, sl=95, hold=5)]}, now=now)
    # day 2 high reaches 111 -> TP hit at 110
    df = _price_df(["2026-01-06", "2026-01-07"], [105, 111], [99, 104], [104, 109])
    rows = journal.score_open_entries(path, lambda t: df, now=now)
    r = rows[0]
    assert r["status"] == "closed" and r["outcome"] == "TP"
    assert float(r["exit_price"]) == 110.0
    assert float(r["realized_pct"]) == 10.0


def test_score_stop_loss_wins_ties(tmp_path):
    path = str(tmp_path / "journal.csv")
    now = pd.Timestamp("2026-01-05").to_pydatetime()
    journal.append_recommendations(path, {"swing": [_rec(tp=110, sl=95, hold=5)]}, now=now)
    # a bar that touches both 110 and 95 -> SL assumed first (conservative)
    df = _price_df(["2026-01-06"], [112], [94], [100])
    rows = journal.score_open_entries(path, lambda t: df, now=now)
    assert rows[0]["outcome"] == "SL"
    assert float(rows[0]["realized_pct"]) == -5.0


def test_score_time_exit(tmp_path):
    path = str(tmp_path / "journal.csv")
    now = pd.Timestamp("2026-01-05").to_pydatetime()
    journal.append_recommendations(path, {"swing": [_rec(tp=200, sl=1, hold=3)]}, now=now)
    df = _price_df(["2026-01-06", "2026-01-07", "2026-01-08"],
                   [101, 102, 103], [99, 100, 101], [100, 101, 102])
    rows = journal.score_open_entries(path, lambda t: df, now=now)
    assert rows[0]["outcome"] == "TIME"
    assert float(rows[0]["exit_price"]) == 102.0


def test_score_stays_open_without_enough_bars(tmp_path):
    path = str(tmp_path / "journal.csv")
    now = pd.Timestamp("2026-01-05").to_pydatetime()
    journal.append_recommendations(path, {"swing": [_rec(tp=200, sl=1, hold=5)]}, now=now)
    df = _price_df(["2026-01-06"], [101], [99], [100])  # only 1 bar, hold 5
    rows = journal.score_open_entries(path, lambda t: df, now=now)
    assert rows[0]["status"] == "open"


def test_summarize(tmp_path):
    rows = [
        {"status": "closed", "track": "swing", "outcome": "TP", "realized_pct": "10"},
        {"status": "closed", "track": "swing", "outcome": "SL", "realized_pct": "-5"},
        {"status": "open", "track": "swing"},
    ]
    s = journal.summarize_journal(rows)
    assert s["closed"] == 2 and s["open"] == 1
    assert s["overall"]["win_rate"] == 50.0
    assert s["overall"]["avg_realized"] == 2.5
    assert s["per_track"]["swing"]["n"] == 2
