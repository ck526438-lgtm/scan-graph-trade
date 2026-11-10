"""Détection des chandeliers japonais par segmentation couleur (OpenCV).

Approche : on isole les pixels « haussiers » (vert/bleu) et « baissiers »
(rouge/orange) en HSV, puis on regroupe les colonnes contiguës en bougies.
Pour chaque bougie, la mèche donne high/low et la zone la plus large donne
le corps (open/close).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from ..models import Candle

# Plages HSV (OpenCV : H 0-179). Ajustables selon la plateforme (TradingView, MT4/5…)
DEFAULT_BULL_RANGES = [((35, 60, 60), (100, 255, 255))]  # verts / bleus-verts
DEFAULT_BEAR_RANGES = [((0, 80, 80), (25, 255, 255)), ((165, 80, 80), (179, 255, 255))]  # rouges / oranges


@dataclass
class DetectorConfig:
    bull_ranges: list = field(default_factory=lambda: list(DEFAULT_BULL_RANGES))
    bear_ranges: list = field(default_factory=lambda: list(DEFAULT_BEAR_RANGES))
    min_height: int = 3  # px
    min_pixels_per_column: int = 1
    max_gap: int = 1  # colonnes vides tolérées dans une bougie


class CandleDetector:
    def __init__(self, config: DetectorConfig | None = None) -> None:
        self.config = config or DetectorConfig()

    # --- masques -------------------------------------------------------
    @staticmethod
    def _mask(hsv: np.ndarray, ranges: list) -> np.ndarray:
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for lo, hi in ranges:
            mask |= cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))
        return mask

    def _segments(self, mask: np.ndarray) -> list[tuple[int, int]]:
        cols = np.where(mask.sum(axis=0) // 255 >= self.config.min_pixels_per_column)[0]
        if cols.size == 0:
            return []
        segs, start, prev = [], cols[0], cols[0]
        for c in cols[1:]:
            if c - prev > self.config.max_gap + 1:
                segs.append((start, prev))
                start = c
            prev = c
        segs.append((start, prev))
        return segs

    def _candle_from_segment(self, mask: np.ndarray, x0: int, x1: int, bullish: bool) -> tuple | None:
        sub = mask[:, x0 : x1 + 1] > 0
        rows = np.where(sub.any(axis=1))[0]
        if rows.size == 0 or rows[-1] - rows[0] + 1 < self.config.min_height:
            return None
        top, bottom = int(rows[0]), int(rows[-1])
        widths = sub.sum(axis=1)
        body_rows = np.where(widths >= max(1, int(widths.max() * 0.6)))[0]
        body_top, body_bottom = int(body_rows[0]), int(body_rows[-1])
        x = int((x0 + x1) // 2)
        return x, top, bottom, body_top, body_bottom, bullish

    # --- API -----------------------------------------------------------
    def detect_raw(self, image_bgr: np.ndarray) -> list[tuple]:
        """Renvoie des bougies en pixels : (x, top, bottom, body_top, body_bottom, bullish)."""
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        raw = []
        for ranges, bullish in ((self.config.bull_ranges, True), (self.config.bear_ranges, False)):
            mask = self._mask(hsv, ranges)
            for x0, x1 in self._segments(mask):
                c = self._candle_from_segment(mask, x0, x1, bullish)
                if c:
                    raw.append(c)
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
            candles.append(Candle(i, x, o, high, low, c, bull))
        return candles
