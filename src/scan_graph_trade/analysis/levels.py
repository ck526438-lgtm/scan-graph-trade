"""Supports / résistances : regroupement des pivots en zones de prix."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .structure import Swing


@dataclass(frozen=True)
class Level:
    price: float  # centre de la zone
    low: float
    high: float
    touches: int
    last_index: int
    kind: str  # "support" | "résistance" (par rapport au prix actuel)
    strength: float  # 0-1


def find_levels(swings: list[Swing], current: float, atr_value: float, n_candles: int,
                tolerance: float = 0.6, max_levels: int = 8) -> list[Level]:
    """Zones = pivots distants de moins de `tolerance × ATR`. Force = contacts + récence."""
    if not swings or atr_value <= 0:
        return []
    tol = tolerance * atr_value
    clusters: list[list[Swing]] = []
    for s in sorted(swings, key=lambda s: s.price):
        # distance au centre de la zone (et non au dernier pivot) : évite les zones « élastiques »
        if clusters and s.price - np.mean([x.price for x in clusters[-1]]) <= tol:
            clusters[-1].append(s)
        else:
            clusters.append([s])

    levels = []
    for cl in clusters:
        prices = [s.price for s in cl]
        center = sum(prices) / len(prices)
        last_i = max(s.index for s in cl)
        recency = last_i / max(1, n_candles - 1)
        strength = min(1.0, 0.1 + 0.1 * min(len(cl), 6) + 0.3 * recency)
        half = max(tol / 2, float(np.std(prices)))
        levels.append(Level(center, center - half, center + half, len(cl), last_i,
                            "support" if center < current else "résistance", round(strength, 2)))
    # les zones les plus proches du prix d'abord (ce sont elles qui comptent pour le trade),
    # puis les plus fortes jusqu'à `max_levels`
    below = sorted([lv for lv in levels if lv.price < current], key=lambda lv: current - lv.price)[:3]
    above = sorted([lv for lv in levels if lv.price >= current], key=lambda lv: lv.price - current)[:3]
    chosen = {id(lv): lv for lv in below + above}
    for lv in sorted(levels, key=lambda lv: -lv.strength):
        if len(chosen) >= max_levels:
            break
        chosen.setdefault(id(lv), lv)
    return sorted(chosen.values(), key=lambda lv: lv.price)


def nearest(levels: list[Level], current: float, kind: str) -> Level | None:
    if kind == "support":
        cands = [lv for lv in levels if lv.price < current]
        return max(cands, key=lambda lv: lv.price) if cands else None
    cands = [lv for lv in levels if lv.price > current]
    return min(cands, key=lambda lv: lv.price) if cands else None
