"""Reconnaissance de figures en chandeliers japonais (règles classiques)."""
from __future__ import annotations

from ..models import Candle, PatternMatch


def _doji(c: Candle) -> PatternMatch | None:
    if c.range > 0 and c.body <= 0.1 * c.range:
        return PatternMatch("doji", c.index, "neutral", 0.6)
    return None


def _hammer_family(c: Candle) -> PatternMatch | None:
    if c.range == 0 or c.body == 0:
        return None
    if c.lower_wick >= 2 * c.body and c.upper_wick <= 0.3 * c.body:
        return PatternMatch("hammer", c.index, "bullish", 0.65)
    if c.upper_wick >= 2 * c.body and c.lower_wick <= 0.3 * c.body:
        return PatternMatch("shooting_star", c.index, "bearish", 0.65)
    return None


def _engulfing(prev: Candle, cur: Candle) -> PatternMatch | None:
    if prev.bullish == cur.bullish or cur.body <= prev.body:
        return None
    lo, hi = min(cur.open, cur.close), max(cur.open, cur.close)
    if lo <= min(prev.open, prev.close) and hi >= max(prev.open, prev.close):
        kind = "bullish" if cur.bullish else "bearish"
        return PatternMatch(f"{kind}_engulfing", cur.index, kind, 0.75)
    return None


def _three_soldiers_crows(a: Candle, b: Candle, c: Candle) -> PatternMatch | None:
    if a.bullish and b.bullish and c.bullish and a.close < b.close < c.close:
        return PatternMatch("three_white_soldiers", c.index, "bullish", 0.7)
    if not (a.bullish or b.bullish or c.bullish) and a.close > b.close > c.close:
        return PatternMatch("three_black_crows", c.index, "bearish", 0.7)
    return None


def detect_patterns(candles: list[Candle]) -> list[PatternMatch]:
    out: list[PatternMatch] = []
    for i, c in enumerate(candles):
        for rule in (_doji, _hammer_family):
            m = rule(c)
            if m:
                out.append(m)
                break
        if i >= 1 and (m := _engulfing(candles[i - 1], c)):
            out.append(m)
        if i >= 2 and (m := _three_soldiers_crows(candles[i - 2], candles[i - 1], c)):
            out.append(m)
    return out
