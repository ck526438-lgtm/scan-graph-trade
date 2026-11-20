"""Structure de marché : points pivots (swings), tendance, cassures de structure.

Les pivots sont obtenus par un *zigzag* filtré par l'ATR : un sommet n'est
validé que si le prix redescend ensuite d'au moins ``k × ATR``. On obtient
ainsi la même lecture qu'un trader qui ne retient que les mouvements
significatifs, quelle que soit l'échelle de la capture.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .indicators import adx, ema, last


@dataclass(frozen=True)
class Swing:
    index: int
    price: float
    kind: str  # "high" | "low"
    label: str = ""  # HH, LH, HL, LL (structure) — vide pour le premier pivot


@dataclass(frozen=True)
class StructureBreak:
    kind: str  # "BOS" (continuation) | "CHoCH" (changement de caractère)
    direction: str  # "bullish" | "bearish"
    index: int  # bougie qui casse
    level: float  # niveau cassé


@dataclass
class TrendInfo:
    direction: str  # "haussière" | "baissière" | "range"
    strength: float  # 0-1
    structure: str  # résumé des derniers pivots, ex. "HH-HL"
    slope_atr: float  # pente de régression en ATR par bougie (fenêtre récente)
    adx: float | None
    ema_fast: float | None
    ema_slow: float | None


def zigzag(high: np.ndarray, low: np.ndarray, threshold: float) -> list[Swing]:
    """Pivots alternés haut/bas séparés d'au moins `threshold`."""
    n = len(high)
    if n < 3 or threshold <= 0:
        return []
    swings: list[Swing] = []
    trend = 0  # 1 : on cherche un sommet, -1 : un creux
    hi_i, lo_i = 0, 0
    for i in range(1, n):
        if trend >= 0 and high[i] >= high[hi_i]:
            hi_i = i
        if trend <= 0 and low[i] <= low[lo_i]:
            lo_i = i
        if trend == 0:
            if high[hi_i] - low[i] >= threshold and hi_i < i:
                swings.append(Swing(hi_i, float(high[hi_i]), "high"))
                trend, lo_i = -1, i
            elif high[i] - low[lo_i] >= threshold and lo_i < i:
                swings.append(Swing(lo_i, float(low[lo_i]), "low"))
                trend, hi_i = 1, i
        elif trend == 1 and high[hi_i] - low[i] >= threshold:
            swings.append(Swing(hi_i, float(high[hi_i]), "high"))
            trend, lo_i = -1, i
        elif trend == -1 and high[i] - low[lo_i] >= threshold:
            swings.append(Swing(lo_i, float(low[lo_i]), "low"))
            trend, hi_i = 1, i
    return label_swings(swings)


def label_swings(swings: list[Swing]) -> list[Swing]:
    out: list[Swing] = []
    prev: dict[str, float] = {}
    for s in swings:
        label = ""
        if s.kind in prev:
            if s.kind == "high":
                label = "HH" if s.price > prev["high"] else "LH"
            else:
                label = "HL" if s.price > prev["low"] else "LL"
        prev[s.kind] = s.price
        out.append(Swing(s.index, s.price, s.kind, label))
    return out


def structure_breaks(swings: list[Swing], close: np.ndarray) -> list[StructureBreak]:
    """BOS / CHoCH : clôture au-delà du dernier pivot opposé."""
    breaks: list[StructureBreak] = []
    bias = 0  # +1 haussier, -1 baissier
    last_high: Swing | None = None
    last_low: Swing | None = None
    j = 0
    broken: set[int] = set()
    for i in range(len(close)):
        while j < len(swings) and swings[j].index < i:
            s = swings[j]
            if s.kind == "high":
                last_high = s
            else:
                last_low = s
            j += 1
        if last_high and last_high.index not in broken and close[i] > last_high.price:
            kind = "BOS" if bias >= 0 else "CHoCH"
            breaks.append(StructureBreak(kind, "bullish", i, last_high.price))
            broken.add(last_high.index)
            bias = 1
        elif last_low and last_low.index not in broken and close[i] < last_low.price:
            kind = "BOS" if bias <= 0 else "CHoCH"
            breaks.append(StructureBreak(kind, "bearish", i, last_low.price))
            broken.add(last_low.index)
            bias = -1
    return breaks


def regression_slope(x: np.ndarray, window: int) -> float:
    y = x[-window:]
    if len(y) < 3:
        return 0.0
    return float(np.polyfit(np.arange(len(y)), y, 1)[0])


def trend_info(high, low, close, swings: list[Swing], atr_value: float) -> TrendInfo:
    n = len(close)
    window = max(10, min(50, n // 3))
    slope = regression_slope(close, window) / (atr_value or 1e-9)
    ef, es = last(ema(close, 20)), last(ema(close, 50))
    adx_v = last(adx(high, low, close))

    highs = [s for s in swings if s.kind == "high"][-2:]
    lows = [s for s in swings if s.kind == "low"][-2:]
    labels = [s.label for s in sorted(highs + lows, key=lambda s: s.index) if s.label]
    up = sum(lb in ("HH", "HL") for lb in labels)
    dn = sum(lb in ("LH", "LL") for lb in labels)

    score = 0.0
    if labels:
        score += (up - dn) / len(labels)  # structure : -1 … +1
    score += float(np.clip(slope * 4, -1, 1))  # pente : 0,25 ATR/bougie = forte
    if ef is not None and es is not None:
        score += 0.5 * (1 if ef > es else -1)
        score += 0.5 * (1 if close[-1] > ef else -1)
    score /= 3.0
    if adx_v is not None and adx_v < 18:
        score *= 0.6  # marché sans direction : on modère

    direction = "haussière" if score > 0.25 else "baissière" if score < -0.25 else "range"
    return TrendInfo(direction, round(min(1.0, abs(score)), 2), "-".join(labels[-4:]) or "—",
                     round(slope, 3), None if adx_v is None else round(adx_v, 1), ef, es)
