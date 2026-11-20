"""Détection des courbes tracées par-dessus les bougies (moyennes mobiles…).

On cherche, pour quelques teintes vives non utilisées par les bougies, une
courbe fine qui couvre une bonne partie de la largeur du graphique. Pour
chaque colonne, l'ordonnée retenue est la médiane des pixels de cette teinte.
"""
from __future__ import annotations

import cv2
import numpy as np

from ..models import Overlay
from .candles import CandleDetector, DetectorConfig

HUES = {
    "rouge": [((0, 120, 120), (8, 255, 255)), ((172, 120, 120), (179, 255, 255))],
    "orange": [((10, 120, 120), (22, 255, 255))],
    "jaune": [((23, 120, 120), (34, 255, 255))],
    "bleue": [((95, 120, 120), (125, 255, 255))],
    "magenta": [((140, 100, 100), (170, 255, 255))],
}


def _hue_in(ranges: list, hue: int) -> bool:
    # seules les plages réellement colorées comptent (le blanc / noir couvrent toutes les teintes)
    return any(lo[0] <= hue <= hi[0] and lo[1] >= 50 for lo, hi in ranges)


def detect_overlays(image_bgr: np.ndarray, config: DetectorConfig, x_min: int, x_max: int,
                    min_coverage: float = 0.3) -> list[Overlay]:
    if x_max <= x_min:
        return []
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    used = (config.bull_ranges + config.bear_ranges) if config.mode == "color" else \
        (config.outline_ranges + config.bear_fill_ranges)
    out = []
    for name, ranges in HUES.items():
        centre = (ranges[0][0][0] + ranges[0][1][0]) // 2
        if _hue_in(used, centre):
            continue  # couleur des bougies elles-mêmes
        m = CandleDetector.mask(hsv, ranges)
        if config.margin_top:
            m[: config.margin_top] = 0
        pts = []
        for x in range(x_min, x_max + 1):
            ys = np.flatnonzero(m[:, x])
            if 0 < ys.size <= 12:  # une courbe fine, pas un bloc
                pts.append((x, float(np.median(ys))))
        if len(pts) >= min_coverage * (x_max - x_min + 1):
            # lissage léger et suppression des sauts aberrants
            ys = np.array([p[1] for p in pts])
            med = np.median(np.abs(np.diff(ys))) if len(ys) > 1 else 0
            keep = [pts[0]]
            for p in pts[1:]:
                if abs(p[1] - keep[-1][1]) <= max(25.0, 8 * med):
                    keep.append(p)
            out.append(Overlay(name, keep))
    return out
