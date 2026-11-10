"""Reconnaissance de figures en chandeliers japonais (règles classiques).

Les seuils sont relatifs au corps moyen des bougies récentes, ce qui rend les
règles indépendantes de l'échelle (pixels ou prix) et du zoom de la capture.
"""
from __future__ import annotations

import numpy as np

from ..models import Candle, PatternMatch

LOOKBACK = 20  # bougies utilisées pour la taille « normale » d'un corps


def _avg_body(candles: list[Candle], i: int) -> float:
    window = candles[max(0, i - LOOKBACK) : i + 1]
    return float(np.mean([c.body for c in window])) or 1e-9


def _doji(c: Candle, avg: float) -> PatternMatch | None:
    if c.range >= avg and c.body <= 0.1 * c.range:
        return PatternMatch("doji", c.index, "neutral", 0.6)
    return None


def _hammer_family(c: Candle, avg: float) -> PatternMatch | None:
    if c.body < 0.3 * avg or c.range < 1.5 * avg:
        return None
    if c.lower_wick >= 2 * c.body and c.upper_wick <= 0.3 * c.body:
        return PatternMatch("hammer", c.index, "bullish", 0.65)
    if c.upper_wick >= 2 * c.body and c.lower_wick <= 0.3 * c.body:
        return PatternMatch("shooting_star", c.index, "bearish", 0.65)
    return None


def _engulfing(prev: Candle, cur: Candle, avg: float) -> PatternMatch | None:
    if prev.bullish == cur.bullish or cur.body <= prev.body or cur.body < avg:
        return None
    if prev.body < 0.3 * avg:  # la bougie englobée doit être un vrai corps
        return None
    lo, hi = min(cur.open, cur.close), max(cur.open, cur.close)
    if lo <= min(prev.open, prev.close) and hi >= max(prev.open, prev.close):
        kind = "bullish" if cur.bullish else "bearish"
        return PatternMatch(f"{kind}_engulfing", cur.index, kind, 0.75)
    return None


def _strong(c: Candle, avg: float) -> bool:
    return c.body >= 0.8 * avg and c.body >= 0.5 * c.range


def _three_soldiers_crows(a: Candle, b: Candle, c: Candle, avg: float) -> PatternMatch | None:
    if not all(_strong(x, avg) for x in (a, b, c)):
        return None
    if a.bullish and b.bullish and c.bullish and a.close < b.close < c.close:
        # chaque bougie ouvre dans le corps de la précédente
        if a.open <= b.open <= a.close and b.open <= c.open <= b.close:
            return PatternMatch("three_white_soldiers", c.index, "bullish", 0.7)
    if not (a.bullish or b.bullish or c.bullish) and a.close > b.close > c.close:
        if a.close <= b.open <= a.open and b.close <= c.open <= b.open:
            return PatternMatch("three_black_crows", c.index, "bearish", 0.7)
    return None


def detect_patterns(candles: list[Candle]) -> list[PatternMatch]:
    out: list[PatternMatch] = []
    last_seen: dict[str, int] = {}

    def add(m: PatternMatch | None, span: int = 1) -> None:
        # pas de doublon d'une même figure sur des bougies qui se chevauchent
        if m and m.index - last_seen.get(m.name, -10) >= span:
            out.append(m)
            last_seen[m.name] = m.index

    for i, c in enumerate(candles):
        avg = _avg_body(candles, i)
        add(_doji(c, avg) or _hammer_family(c, avg))
        if i >= 1:
            add(_engulfing(candles[i - 1], c, avg))
        if i >= 2:
            add(_three_soldiers_crows(candles[i - 2], candles[i - 1], c, avg), span=3)
    return out
