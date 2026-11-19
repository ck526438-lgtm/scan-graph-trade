"""Figures chartistes construites sur les pivots : double sommet/creux,
tête-épaules (et inversée), triangles, biseaux, canaux, lignes de tendance.

Chaque figure est « en formation » ou « confirmée » (clôture au-delà de la
ligne de cou / de la borne). Les objectifs suivent la règle classique :
hauteur de la figure reportée depuis le point de cassure.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np

from .structure import Swing


@dataclass(frozen=True)
class ChartPattern:
    name: str  # identifiant (ex. "double_top")
    label: str  # libellé français
    direction: str  # "bullish" | "bearish" | "neutral"
    start: int
    end: int
    confirmed: bool
    confidence: float
    neckline: float | None = None  # niveau de déclenchement
    target: float | None = None  # objectif théorique
    points: tuple = ()  # ((index, prix), ...) pour l'annotation


@dataclass(frozen=True)
class TrendLine:
    kind: str  # "support" | "résistance"
    i0: int
    p0: float
    i1: int
    p1: float
    touches: int
    slope: float  # prix par bougie

    def at(self, i: int) -> float:
        return self.p0 + self.slope * (i - self.i0)


@dataclass
class _Ctx:
    swings: list[Swing]
    close: np.ndarray
    atr: float
    highs: list[Swing] = field(init=False)
    lows: list[Swing] = field(init=False)

    def __post_init__(self) -> None:
        self.highs = [s for s in self.swings if s.kind == "high"]
        self.lows = [s for s in self.swings if s.kind == "low"]


def _between(swings: list[Swing], a: int, b: int, kind: str) -> list[Swing]:
    return [s for s in swings if a < s.index < b and s.kind == kind]


def _crossed(close: np.ndarray, start: int, level: float, below: bool) -> bool:
    seg = close[start + 1 :]
    return bool(seg.size and ((seg < level).any() if below else (seg > level).any()))


def _double(ctx: _Ctx) -> list[ChartPattern]:
    out = []
    tol = 0.5 * ctx.atr
    for kind, opp, name, label, direction in (
        ("high", "low", "double_top", "Double sommet", "bearish"),
        ("low", "high", "double_bottom", "Double creux", "bullish"),
    ):
        pts = ctx.highs if kind == "high" else ctx.lows
        recent = pts[-4:]
        for a, b in itertools.pairwise(recent):
            if abs(a.price - b.price) > tol:
                continue
            mid = _between(ctx.swings, a.index, b.index, opp)
            if not mid:
                continue
            m = min(mid, key=lambda s: s.price) if kind == "high" else max(mid, key=lambda s: s.price)
            height = abs((a.price + b.price) / 2 - m.price)
            if height < 1.5 * ctx.atr:
                continue
            bearish = direction == "bearish"
            confirmed = _crossed(ctx.close, b.index, m.price, below=bearish)
            target = m.price - height if bearish else m.price + height
            conf = 0.55 + (0.2 if confirmed else 0) + 0.1 * (1 - abs(a.price - b.price) / tol)
            out.append(ChartPattern(name, label, direction, a.index, b.index, confirmed, round(min(conf, 0.9), 2),
                                    m.price, target, ((a.index, a.price), (m.index, m.price), (b.index, b.price))))
    return out


def _head_shoulders(ctx: _Ctx) -> list[ChartPattern]:
    out = []
    for kind, opp, name, label, direction in (
        ("high", "low", "head_shoulders", "Tête-épaules", "bearish"),
        ("low", "high", "inverse_head_shoulders", "Tête-épaules inversée", "bullish"),
    ):
        pts = ctx.highs if kind == "high" else ctx.lows
        sign = 1 if kind == "high" else -1
        recent = pts[-5:]
        for ls, hd, rs in zip(recent, recent[1:], recent[2:], strict=False):
            higher = (hd.price - max(ls.price, rs.price)) if sign > 0 else (min(ls.price, rs.price) - hd.price)
            if higher < 0.8 * ctx.atr or abs(ls.price - rs.price) > 1.2 * ctx.atr:
                continue
            t1 = _between(ctx.swings, ls.index, hd.index, opp)
            t2 = _between(ctx.swings, hd.index, rs.index, opp)
            if not t1 or not t2:
                continue
            n1, n2 = t1[-1], t2[0]
            slope = (n2.price - n1.price) / max(1, n2.index - n1.index)
            neck_now = n2.price + slope * (len(ctx.close) - 1 - n2.index)
            height = abs(hd.price - (n1.price + slope * (hd.index - n1.index)))
            bearish = direction == "bearish"
            seg = ctx.close[rs.index + 1 :]
            neck_seg = n2.price + slope * (np.arange(rs.index + 1, len(ctx.close)) - n2.index)
            confirmed = bool(seg.size and ((seg < neck_seg).any() if bearish else (seg > neck_seg).any()))
            target = neck_now - height if bearish else neck_now + height
            out.append(ChartPattern(name, label, direction, ls.index, rs.index, confirmed,
                                    0.8 if confirmed else 0.6, neck_now, target,
                                    ((ls.index, ls.price), (n1.index, n1.price), (hd.index, hd.price),
                                     (n2.index, n2.price), (rs.index, rs.price))))
    return out


def _fit(points: list[Swing]) -> tuple[float, float]:
    xs = np.array([p.index for p in points], float)
    ys = np.array([p.price for p in points], float)
    a, b = np.polyfit(xs, ys, 1)
    return float(a), float(b)


def _converging(ctx: _Ctx) -> list[ChartPattern]:
    """Triangles, biseaux et canaux sur les 3 derniers sommets et 3 derniers creux."""
    hs, ls = ctx.highs[-3:], ctx.lows[-3:]
    if len(hs) < 2 or len(ls) < 2 or len(hs) + len(ls) < 5:
        return []
    start = min(hs[0].index, ls[0].index)
    end = max(hs[-1].index, ls[-1].index)
    span = max(1, end - start)
    ah, bh = _fit(hs)
    al, bl = _fit(ls)
    # pentes exprimées en ATR sur toute la durée de la figure
    sh, sl = ah * span / ctx.atr, al * span / ctx.atr
    flat = 0.8
    width_start = (ah * start + bh) - (al * start + bl)
    width_end = (ah * end + bh) - (al * end + bl)
    if width_start <= 0 or width_end <= 0:
        return []
    converging = width_end < 0.75 * width_start
    parallel = abs(width_end - width_start) < 0.25 * width_start

    name = label = None
    direction = "neutral"
    if converging:
        if abs(sh) < flat and sl > flat:
            name, label, direction = "ascending_triangle", "Triangle ascendant", "bullish"
        elif sh < -flat and abs(sl) < flat:
            name, label, direction = "descending_triangle", "Triangle descendant", "bearish"
        elif sh < -flat and sl > flat:
            name, label = "symmetrical_triangle", "Triangle symétrique"
        elif sh > flat and sl > flat:
            name, label, direction = "rising_wedge", "Biseau ascendant", "bearish"
        elif sh < -flat and sl < -flat:
            name, label, direction = "falling_wedge", "Biseau descendant", "bullish"
    elif parallel:
        if sh > flat and sl > flat:
            name, label, direction = "rising_channel", "Canal haussier", "bullish"
        elif sh < -flat and sl < -flat:
            name, label, direction = "falling_channel", "Canal baissier", "bearish"
        elif abs(sh) < flat and abs(sl) < flat:
            name, label = "rectangle", "Rectangle (range)"
    if not name:
        return []

    n = len(ctx.close) - 1
    upper, lower = ah * n + bh, al * n + bl
    c = ctx.close[-1]
    height = width_start
    confirmed = False
    if c > upper:
        confirmed, direction = True, "bullish"
        target, trigger = upper + height, upper
        label += " — cassure haussière"
    elif c < lower:
        confirmed, direction = True, "bearish"
        target, trigger = lower - height, lower
        label += " — cassure baissière"
    else:
        trigger = upper if direction == "bullish" else lower if direction == "bearish" else None
        target = None if trigger is None else (trigger + height if direction == "bullish" else trigger - height)
    pts = ((start, ah * start + bh), (n, upper), (start, al * start + bl), (n, lower))
    return [ChartPattern(name, label, direction, start, n, confirmed, 0.75 if confirmed else 0.55,
                         trigger, target, pts)]


def trend_lines(swings: list[Swing], close: np.ndarray, atr: float) -> list[TrendLine]:
    """Ligne de support (creux montants) et de résistance (sommets descendants) les plus récentes."""
    out = []
    n = len(close)
    for kind, pts, want in (("support", [s for s in swings if s.kind == "low"], 1),
                            ("résistance", [s for s in swings if s.kind == "high"], -1)):
        best = None
        recent = pts[-5:]
        for i in range(len(recent)):
            for j in range(i + 1, len(recent)):
                a, b = recent[i], recent[j]
                slope = (b.price - a.price) / max(1, b.index - a.index)
                if want * slope <= 0:
                    continue
                line = TrendLine(kind, a.index, a.price, b.index, b.price, 0, slope)
                # la ligne ne doit pas être traversée franchement par les clôtures
                seg = np.arange(a.index, n)
                vals = line.at(seg)
                viol = (close[a.index:] < vals - 0.3 * atr) if want > 0 else (close[a.index:] > vals + 0.3 * atr)
                if viol[: b.index - a.index + 1].any():
                    continue
                touches = sum(abs(p.price - line.at(p.index)) < 0.4 * atr for p in pts if p.index >= a.index)
                broken = bool(viol[b.index - a.index + 1 :].any())
                if broken:
                    continue
                score = touches * 10 + b.index
                if best is None or score > best[0]:
                    best = (score, TrendLine(kind, a.index, a.price, b.index, b.price, touches, slope))
        if best:
            out.append(best[1])
    return out


def detect_chart_patterns(swings: list[Swing], close: np.ndarray, atr: float) -> list[ChartPattern]:
    if atr <= 0 or len(swings) < 3:
        return []
    ctx = _Ctx(swings, close, atr)
    found = _double(ctx) + _head_shoulders(ctx) + _converging(ctx)
    # on garde les figures récentes (terminées dans le dernier tiers du graphique)
    horizon = len(close) - max(15, len(close) // 3)
    found = [p for p in found if p.end >= horizon]
    # une seule occurrence par type : la plus récente
    best: dict[str, ChartPattern] = {}
    for p in found:
        if p.name not in best or p.end > best[p.name].end:
            best[p.name] = p
    return sorted(best.values(), key=lambda p: p.end)
