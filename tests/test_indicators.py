import numpy as np
import pandas as pd

from scanner.indicators import (
    adx,
    atr,
    bollinger,
    donchian,
    ema,
    macd,
    rolling_position,
    rsi,
    sma,
)


def test_sma_matches_manual_mean():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    result = sma(s, 3)
    assert np.isnan(result.iloc[1])
    assert result.iloc[2] == 2.0
    assert result.iloc[4] == 4.0


def test_ema_first_value_equals_input():
    s = pd.Series([10, 20, 30], dtype=float)
    result = ema(s, 2)
    assert result.iloc[0] == 10.0
    assert result.iloc[-1] > result.iloc[0]


def test_rsi_is_high_for_mostly_rising_series():
    # one small dip keeps the loss term non-zero (a purely monotonic rise
    # gives RSI = NaN because there are no losses to divide by)
    vals = list(np.arange(1, 40, dtype=float))
    vals[36] -= 2.0  # dip below the prior bar, inside the trailing 14-bar window
    result = rsi(pd.Series(vals), 14)
    assert result.iloc[-1] > 90.0


def test_rsi_is_low_for_mostly_falling_series():
    vals = list(np.arange(40, 1, -1, dtype=float))
    vals[36] += 2.0  # bump above the prior bar, inside the trailing 14-bar window
    result = rsi(pd.Series(vals), 14)
    assert result.iloc[-1] < 10.0


def test_macd_returns_three_aligned_series():
    s = pd.Series(np.linspace(1, 100, 120))
    line, sig, hist = macd(s)
    assert len(line) == len(sig) == len(hist) == len(s)
    assert np.allclose((line - sig).dropna(), hist.dropna())


def test_atr_is_non_negative():
    df = pd.DataFrame({
        "High": [11, 12, 13, 14, 15],
        "Low": [9, 10, 11, 12, 13],
        "Close": [10, 11, 12, 13, 14],
    }, dtype=float)
    result = atr(df, 3)
    assert (result.dropna() >= 0).all()


def test_bollinger_band_ordering():
    s = pd.Series(np.random.RandomState(0).normal(100, 5, 100))
    lower, mid, upper = bollinger(s, 20)
    valid = mid.dropna().index
    assert (lower.loc[valid] <= mid.loc[valid]).all()
    assert (mid.loc[valid] <= upper.loc[valid]).all()


def test_rolling_position_bounds():
    close = pd.Series(np.random.RandomState(1).uniform(10, 20, 60))
    high = close + 1
    low = close - 1
    pos = rolling_position(close, high, low, 20).dropna()
    assert (pos >= 0).all() and (pos <= 1).all()


def test_adx_non_negative():
    rs = np.random.RandomState(2)
    close = pd.Series(np.cumsum(rs.normal(0, 1, 100)) + 100)
    df = pd.DataFrame({"High": close + 1, "Low": close - 1, "Close": close})
    result = adx(df, 14).dropna()
    assert (result >= 0).all()


def test_donchian_is_shifted_to_avoid_lookahead():
    high = pd.Series([1, 5, 3, 8, 2], dtype=float)
    low = pd.Series([1, 2, 1, 4, 0], dtype=float)
    dh, dl = donchian(high, low, 2)
    # value at index i only uses bars strictly before i (shift(1))
    assert dh.iloc[2] == 5.0   # max(high[0], high[1]) = max(1, 5)
    assert dl.iloc[2] == 1.0   # min(low[0], low[1]) = min(1, 2)
