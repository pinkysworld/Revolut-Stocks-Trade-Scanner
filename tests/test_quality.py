from datetime import datetime

import pandas as pd

from scanner.quality import apply_symbol_overrides, assess_history_quality


ASSETS = [
    ("COMP-USD", "Compound", "crypto", "USD"),
    ("META", "Meta", "stock", "USD"),
]


OVERRIDES = {
    "COMP-USD": {"enabled": False, "reason": "unstable feed"},
    "META": {"name": "Meta Platforms", "asset_class": "stock", "currency": "USD"},
}


def test_apply_symbol_overrides_disables_and_tracks_notes():
    filtered, notes = apply_symbol_overrides(ASSETS, OVERRIDES)
    assert filtered == [("META", "Meta Platforms", "stock", "USD")]
    assert any(note["status"] == "override_disabled" for note in notes)


def test_assess_history_quality_marks_recent_complete_history_ok():
    index = pd.date_range(end=datetime.utcnow(), periods=300, freq="D")
    df = pd.DataFrame({"Close": range(300)}, index=index)
    row = assess_history_quality("BTC-USD", "crypto", df)
    assert row["status"] == "ok"
    assert row["bars"] == 300
