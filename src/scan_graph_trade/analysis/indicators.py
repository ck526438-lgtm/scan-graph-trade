"""Indicateurs techniques recalculés à partir des bougies extraites de la capture.

Toutes les fonctions prennent/rendent des ``numpy.ndarray`` de même longueur
que la série ; les premières valeurs (période de chauffe) valent ``nan``.
"""
from __future__ import annotations

import numpy as np

from ..models import Candle


def ohlc(candles: list[Candle]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    a = np.array([(c.open, c.high, c.low, c.close) for c in candles], dtype=float).reshape(-1, 4)
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]


def sma(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if len(x) >= n > 0:
        c = np.cumsum(np.insert(x, 0, 0.0))
        out[n - 1 :] = (c[n:] - c[:-n]) / n
    return out


def ema(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if len(x) < n or n <= 0:
        return out
    k = 2.0 / (n + 1)
    out[n - 1] = x[:n].mean()
    for i in range(n, len(x)):
        out[i] = x[i] * k + out[i - 1] * (1 - k)
    return out


def _wilder(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if len(x) < n:
        return out
    out[n - 1] = x[:n].mean()
    for i in range(n, len(x)):
        out[i] = (out[i - 1] * (n - 1) + x[i]) / n
    return out


def rsi(close: np.ndarray, n: int = 14) -> np.ndarray:
    out = np.full(len(close), np.nan)
    if len(close) <= n:
        return out
    d = np.diff(close)
    up, dn = _wilder(np.clip(d, 0, None), n), _wilder(np.clip(-d, 0, None), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = up / dn
        r = np.where(dn == 0, 100.0, 100 - 100 / (1 + rs))
    out[1:] = r
    return out


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    prev = np.concatenate([[close[0]], close[:-1]]) if len(close) else close
    return np.maximum.reduce([high - low, np.abs(high - prev), np.abs(low - prev)])


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14) -> np.ndarray:
    tr = true_range(high, low, close)
    if len(tr) < n:  # série courte : moyenne simple pour avoir quand même une échelle
        return np.full(len(tr), tr.mean() if len(tr) else np.nan)
    return _wilder(tr, n)


def macd(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    line = ema(close, fast) - ema(close, slow)
    sig = np.full(len(close), np.nan)
    valid = ~np.isnan(line)
    if valid.sum() >= signal:
        sig[valid] = ema(line[valid], signal)
    return line, sig, line - sig


def bollinger(close: np.ndarray, n: int = 20, k: float = 2.0):
    mid = sma(close, n)
    std = np.full(len(close), np.nan)
    for i in range(n - 1, len(close)):
        std[i] = close[i - n + 1 : i + 1].std()
    return mid - k * std, mid, mid + k * std


def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14) -> np.ndarray:
    """Force de la tendance (0-100). > 25 : tendance établie, < 20 : marché sans direction."""
    out = np.full(len(close), np.nan)
    if len(close) < 2 * n + 1:
        return out
    up, dn = np.diff(high), -np.diff(low)
    plus = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = true_range(high, low, close)[1:]
    atr_ = _wilder(tr, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi = 100 * _wilder(plus, n) / atr_
        mdi = 100 * _wilder(minus, n) / atr_
        dx = 100 * np.abs(pdi - mdi) / (pdi + mdi)
    dx = np.nan_to_num(dx, nan=0.0)
    valid = dx[n - 1 :]
    out[n:] = _wilder(valid, n)
    return out


def last(x: np.ndarray) -> float | None:
    """Dernière valeur définie de la série (ou None)."""
    v = x[~np.isnan(x)] if len(x) else x
    return float(v[-1]) if len(v) else None
