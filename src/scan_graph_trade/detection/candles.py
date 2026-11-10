"""Détection des chandeliers japonais (OpenCV).

Deux modes :

- ``color`` : bougies haussières et baissières de couleurs différentes
  (ex. vert / rouge). Chaque couleur est segmentée séparément en HSV.
- ``fill``  : bougies de même couleur de contour, distinguées par leur
  remplissage — c'est le cas du thème par défaut de MetaTrader 5
  (contour vert « Lime », haussière creuse noire, baissière pleine blanche).

Dans les deux cas : on supprime les lignes horizontales (ligne Bid/Ask,
grille), on regroupe les colonnes contiguës en bougies, la mèche donne
high/low et la zone la plus large donne le corps (open/close).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from ..models import Candle

# Plages HSV (OpenCV : H 0-179, S 0-255, V 0-255)
DEFAULT_BULL_RANGES = [((35, 60, 60), (100, 255, 255))]  # verts / bleus-verts
DEFAULT_BEAR_RANGES = [((0, 80, 80), (25, 255, 255)), ((165, 80, 80), (179, 255, 255))]  # rouges / oranges


@dataclass
class DetectorConfig:
    name: str = "default"
    mode: str = "color"  # "color" | "fill"
    # mode color
    bull_ranges: list = field(default_factory=lambda: list(DEFAULT_BULL_RANGES))
    bear_ranges: list = field(default_factory=lambda: list(DEFAULT_BEAR_RANGES))
    # mode fill
    outline_ranges: list = field(default_factory=list)  # contour + mèches
    bear_fill_ranges: list = field(default_factory=list)  # remplissage des baissières
    # zone utile du graphique (on ignore l'axe des prix, l'axe du temps, l'en-tête)
    margin_top: int = 0
    margin_bottom: int = 0
    margin_left: int = 0
    margin_right_fraction: float = 0.0
    close_gaps: bool = True  # referme les trous (compression JPEG, anticrénelage)
    detect_price_axis: bool = False  # repère la ligne verticale qui sépare l'axe des prix (MT5)
    # filtrage
    remove_hlines: bool = True
    min_height: int = 3  # px
    min_pixels_per_column: int = 1
    max_gap: int = 0  # colonnes vides tolérées dans une bougie


Raw = tuple[int, int, int, int, int, bool]  # x, top, bottom, body_top, body_bottom, bullish


class CandleDetector:
    def __init__(self, config: DetectorConfig | None = None) -> None:
        self.config = config or DetectorConfig()
        self._axis_x: int | None = None

    # --- masques -------------------------------------------------------
    @staticmethod
    def mask(hsv: np.ndarray, ranges: list) -> np.ndarray:
        m = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for lo, hi in ranges:
            m |= cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
        return m

    @staticmethod
    def find_price_axis(image_bgr: np.ndarray, min_coverage: float = 0.85) -> int | None:
        """Abscisse de la ligne verticale séparant le graphique de l'axe des prix (tiers droit)."""
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY).astype(np.int16)
        bg = int(np.median(gray))
        h, w = gray.shape
        coverage = (np.abs(gray - bg) > 60).sum(axis=0) / h
        cols = np.where(coverage[int(w * 0.66) :] >= min_coverage)[0]
        return int(cols[0] + int(w * 0.66)) if cols.size else None

    def _prepare(self, m: np.ndarray) -> np.ndarray:
        cfg = self.config
        h, w = m.shape
        m = m.copy()
        if cfg.close_gaps:
            m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3)))
        if self._axis_x is not None:
            m[:, self._axis_x :] = 0
        if cfg.remove_hlines and w >= 40:
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(40, w // 6), 1))
            m &= ~cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel)
        m[: cfg.margin_top, :] = 0
        if cfg.margin_bottom:
            m[h - cfg.margin_bottom :, :] = 0
        m[:, : cfg.margin_left] = 0
        right = int(w * cfg.margin_right_fraction)
        if right:
            m[:, w - right :] = 0
        return m

    def _segments(self, m: np.ndarray) -> list[tuple[int, int]]:
        cols = np.where(np.count_nonzero(m, axis=0) >= self.config.min_pixels_per_column)[0]
        if cols.size == 0:
            return []
        segs, start, prev = [], int(cols[0]), int(cols[0])
        for c in cols[1:]:
            c = int(c)
            if c - prev > self.config.max_gap + 1:
                segs.append((start, prev))
                start = c
            prev = c
        segs.append((start, prev))
        return segs

    def _geometry(self, m: np.ndarray, x0: int, x1: int):
        """Renvoie (top, bottom, body_top, body_bottom, left, right) ou None.

        Le corps est repéré par l'étendue horizontale de chaque ligne (et non le
        nombre de pixels), ce qui marche aussi pour les bougies creuses.
        """
        sub = m[:, x0 : x1 + 1] > 0
        rows = np.where(sub.any(axis=1))[0]
        if rows.size == 0 or rows[-1] - rows[0] + 1 < self.config.min_height:
            return None
        lefts = np.where(sub.any(axis=1), sub.argmax(axis=1), 0)
        rights = np.where(sub.any(axis=1), sub.shape[1] - 1 - sub[:, ::-1].argmax(axis=1), -1)
        spans = rights - lefts + 1
        body_rows = np.where(spans >= max(1, int(spans.max() * 0.6)))[0]
        btop, bbot = int(body_rows[0]), int(body_rows[-1])
        left = x0 + int(lefts[body_rows].min())
        right = x0 + int(rights[body_rows].max())
        return int(rows[0]), int(rows[-1]), btop, bbot, left, right

    # --- modes ---------------------------------------------------------
    def _detect_color(self, hsv: np.ndarray) -> list[Raw]:
        raw = []
        for ranges, bullish in ((self.config.bull_ranges, True), (self.config.bear_ranges, False)):
            m = self._prepare(self.mask(hsv, ranges))
            for x0, x1 in self._segments(m):
                g = self._geometry(m, x0, x1)
                if g:
                    top, bottom, btop, bbot, _, _ = g
                    raw.append((int((x0 + x1) // 2), top, bottom, btop, bbot, bullish))
        return raw

    def _detect_fill(self, hsv: np.ndarray) -> list[Raw]:
        outline = self._prepare(self.mask(hsv, self.config.outline_ranges))
        fill = self._prepare(self.mask(hsv, self.config.bear_fill_ranges))
        fg = outline | fill
        raw = []
        for x0, x1 in self._segments(fg):
            if not outline[:, x0 : x1 + 1].any():  # texte, étiquettes… sans contour de bougie
                continue
            g = self._geometry(fg, x0, x1)
            if not g:
                continue
            top, bottom, btop, bbot, left, right = g
            inner = fill[btop + 1 : bbot, left + 1 : right]
            bullish = True if inner.size == 0 else bool(np.count_nonzero(inner) < 0.5 * inner.size)
            raw.append((int((left + right) // 2), top, bottom, btop, bbot, bullish))
        return raw

    # --- API -----------------------------------------------------------
    def detect_raw(self, image_bgr: np.ndarray) -> list[Raw]:
        """Bougies en pixels : (x, top, bottom, body_top, body_bottom, bullish)."""
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        self._axis_x = self.find_price_axis(image_bgr) if self.config.detect_price_axis else None
        raw = self._detect_fill(hsv) if self.config.mode == "fill" else self._detect_color(hsv)
        return sorted(raw, key=lambda c: c[0])

    def detect(self, image_bgr: np.ndarray, to_price=None) -> list[Candle]:
        """Détecte les bougies. `to_price(y_pixel) -> prix` convertit si l'axe est calibré."""
        h = image_bgr.shape[0]
        conv = to_price or (lambda y: float(h - y))
        candles = []
        for i, (x, top, bottom, btop, bbot, bull) in enumerate(self.detect_raw(image_bgr)):
            high, low = float(conv(top)), float(conv(bottom))
            upper, lower = float(conv(btop)), float(conv(bbot))
            o, c = (lower, upper) if bull else (upper, lower)
            candles.append(Candle(i, int(x), o, high, low, c, bull))
        return candles
