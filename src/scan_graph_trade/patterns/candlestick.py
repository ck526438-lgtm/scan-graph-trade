"""Reconnaissance de figures en chandeliers japonais (règles classiques).

Les seuils sont relatifs au corps moyen des bougies récentes, ce qui rend les
règles indépendantes de l'échelle (pixels ou prix) et du zoom de la capture.

Comme un analyste, on tient compte du **contexte** : une même bougie « marteau »
s'appelle *hanging man* (pendu) au sommet d'une hausse, et les figures de
retournement ne sont retenues que si elles arrivent après un mouvement.
"""
from __future__ import annotations

import numpy as np

from ..models import Candle, PatternMatch

LOOKBACK = 20  # bougies utilisées pour la taille « normale » d'un corps
TREND_BARS = 5  # bougies utilisées pour juger le mouvement qui précède

LABELS_FR = {
    "doji": "Doji",
    "hammer": "Marteau",
    "hanging_man": "Pendu",
    "inverted_hammer": "Marteau inversé",
    "shooting_star": "Étoile filante",
    "bullish_engulfing": "Avalement haussier",
    "bearish_engulfing": "Avalement baissier",
    "bullish_harami": "Harami haussier",
    "bearish_harami": "Harami baissier",
    "piercing_line": "Ligne pénétrante",
    "dark_cloud_cover": "Couverture en nuage noir",
    "tweezer_bottom": "Creux en pince",
    "tweezer_top": "Sommet en pince",
    "morning_star": "Étoile du matin",
    "evening_star": "Étoile du soir",
    "three_white_soldiers": "Trois soldats blancs",
    "three_black_crows": "Trois corbeaux noirs",
    "bullish_marubozu": "Marubozu haussier",
    "bearish_marubozu": "Marubozu baissier",
}


def _avg_body(candles: list[Candle], i: int) -> float:
    window = candles[max(0, i - LOOKBACK) : i + 1]
    return float(np.mean([c.body for c in window])) or 1e-9


def _prior_trend(candles: list[Candle], i: int, avg: float) -> int:
    """+1 si les bougies précédant `i` montent nettement, -1 si elles baissent, 0 sinon."""
    if i < 3:
        return 0
    a = candles[max(0, i - TREND_BARS)]
    b = candles[i - 1]
    move = b.close - a.open
    if move > 1.5 * avg:
        return 1
    if move < -1.5 * avg:
        return -1
    return 0


def _mid(c: Candle) -> float:
    return (c.open + c.close) / 2


def _doji(c: Candle, avg: float) -> PatternMatch | None:
    if c.range >= 1.5 * avg and c.body <= 0.1 * c.range:
        return PatternMatch("doji", c.index, "neutral", 0.6)
    return None


def _hammer_family(c: Candle, avg: float, trend: int) -> PatternMatch | None:
    if c.body < 0.3 * avg or c.range < 1.5 * avg:
        return None
    if c.lower_wick >= 2 * c.body and c.upper_wick <= 0.3 * c.body:
        if trend > 0:
            return PatternMatch("hanging_man", c.index, "bearish", 0.55)
        return PatternMatch("hammer", c.index, "bullish", 0.7 if trend < 0 else 0.65)
    if c.upper_wick >= 2 * c.body and c.lower_wick <= 0.3 * c.body:
        if trend < 0:
            return PatternMatch("inverted_hammer", c.index, "bullish", 0.55)
        return PatternMatch("shooting_star", c.index, "bearish", 0.7 if trend > 0 else 0.65)
    return None


def _marubozu(c: Candle, avg: float) -> PatternMatch | None:
    if c.body >= 2.2 * avg and c.body >= 0.92 * c.range:
        kind = "bullish" if c.bullish else "bearish"
        return PatternMatch(f"{kind}_marubozu", c.index, kind, 0.6)
    return None


def _engulfing(prev: Candle, cur: Candle, avg: float, trend: int) -> PatternMatch | None:
    if prev.bullish == cur.bullish or cur.body <= prev.body or cur.body < avg:
        return None
    if prev.body < 0.3 * avg:  # la bougie englobée doit être un vrai corps
        return None
    lo, hi = min(cur.open, cur.close), max(cur.open, cur.close)
    if lo <= min(prev.open, prev.close) and hi >= max(prev.open, prev.close):
        kind = "bullish" if cur.bullish else "bearish"
        conf = 0.75 + (0.05 if (trend < 0 and cur.bullish) or (trend > 0 and not cur.bullish) else 0)
        return PatternMatch(f"{kind}_engulfing", cur.index, kind, conf)
    return None


def _harami(prev: Candle, cur: Candle, avg: float, trend: int) -> PatternMatch | None:
    if prev.body < 1.5 * avg or cur.body > 0.5 * prev.body or cur.body < 0.1 * avg:
        return None
    if prev.bullish == cur.bullish:
        return None
    lo, hi = min(prev.open, prev.close), max(prev.open, prev.close)
    if not (lo <= min(cur.open, cur.close) and max(cur.open, cur.close) <= hi):
        return None
    if not prev.bullish and trend < 0:
        return PatternMatch("bullish_harami", cur.index, "bullish", 0.55)
    if prev.bullish and trend > 0:
        return PatternMatch("bearish_harami", cur.index, "bearish", 0.55)
    return None


def _piercing_dark_cloud(prev: Candle, cur: Candle, avg: float, trend: int) -> PatternMatch | None:
    if prev.body < avg or cur.body < avg or prev.bullish == cur.bullish:
        return None
    if not prev.bullish and trend < 0 and cur.bullish:
        if cur.open <= prev.close and _mid(prev) < cur.close < prev.open:
            return PatternMatch("piercing_line", cur.index, "bullish", 0.65)
    if prev.bullish and trend > 0 and not cur.bullish:
        if cur.open >= prev.close and prev.open < cur.close < _mid(prev):
            return PatternMatch("dark_cloud_cover", cur.index, "bearish", 0.65)
    return None


def _tweezer(prev: Candle, cur: Candle, avg: float, trend: int) -> PatternMatch | None:
    tol = 0.1 * avg
    if prev.range < avg or cur.range < avg:
        return None
    if trend < 0 and not prev.bullish and cur.bullish and abs(prev.low - cur.low) <= tol:
        return PatternMatch("tweezer_bottom", cur.index, "bullish", 0.6)
    if trend > 0 and prev.bullish and not cur.bullish and abs(prev.high - cur.high) <= tol:
        return PatternMatch("tweezer_top", cur.index, "bearish", 0.6)
    return None


def _star(a: Candle, b: Candle, c: Candle, avg: float, trend: int) -> PatternMatch | None:
    if a.body < avg or c.body < 0.8 * avg or b.body > 0.5 * avg:
        return None
    if trend <= 0 and not a.bullish and c.bullish and max(b.open, b.close) <= a.close + 0.3 * avg \
            and c.close > _mid(a):
        return PatternMatch("morning_star", c.index, "bullish", 0.75)
    if trend >= 0 and a.bullish and not c.bullish and min(b.open, b.close) >= a.close - 0.3 * avg \
            and c.close < _mid(a):
        return PatternMatch("evening_star", c.index, "bearish", 0.75)
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

    def add(m: PatternMatch | None, span: int = 1) -> bool:
        # pas de doublon d'une même figure sur des bougies qui se chevauchent
        if m and m.index - last_seen.get(m.name, -10) >= span:
            out.append(m)
            last_seen[m.name] = m.index
            return True
        return False

    for i, c in enumerate(candles):
        avg = _avg_body(candles, i)
        trend = _prior_trend(candles, i, avg)
        add(_doji(c, avg) or _hammer_family(c, avg, trend) or _marubozu(c, avg))
        if i >= 1:
            p = candles[i - 1]
            add(_engulfing(p, c, avg, trend) or _piercing_dark_cloud(p, c, avg, trend)
                or _harami(p, c, avg, trend) or _tweezer(p, c, avg, trend))
        if i >= 2:
            t2 = _prior_trend(candles, i - 2, avg)
            add(_star(candles[i - 2], candles[i - 1], c, avg, t2), span=3)
            add(_three_soldiers_crows(candles[i - 2], candles[i - 1], c, avg), span=3)
    return out
