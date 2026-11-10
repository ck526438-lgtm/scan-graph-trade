"""OCR (Tesseract) : lecture du texte et calibration de l'axe des prix.

Tesseract doit être installé sur le système (voir README). Si pytesseract
ou le binaire est absent, les fonctions dégradent proprement.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None

_NUMBER = re.compile(r"^-?\d{1,7}(?:[.,]\d{1,6})?$")


@dataclass(frozen=True)
class AxisCalibration:
    slope: float
    intercept: float

    def __call__(self, y: float) -> float:
        return self.slope * y + self.intercept


def _available() -> bool:
    if pytesseract is None:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except (pytesseract.TesseractNotFoundError, OSError, RuntimeError):
        return False


def extract_text(image: np.ndarray, lang: str = "eng") -> list[str]:
    """Extrait les lignes de texte (symbole, timeframe, valeurs d'indicateurs…)."""
    if not _available():
        return []
    txt = pytesseract.image_to_string(image, lang=lang)
    return [line.strip() for line in txt.splitlines() if line.strip()]


def fit_axis(points: list[tuple[float, float]]) -> AxisCalibration | None:
    """Régression linéaire prix = a*y + b à partir de paires (y_pixel, prix)."""
    if len(points) < 2:
        return None
    ys, prices = np.array(points, dtype=float).T
    if np.ptp(ys) == 0:
        return None
    a, b = np.polyfit(ys, prices, 1)
    if a >= 0:  # le prix doit diminuer quand y augmente
        return None
    return AxisCalibration(float(a), float(b))


def calibrate_price_axis(image: np.ndarray, axis_fraction: float = 0.12) -> AxisCalibration | None:
    """Lit les graduations de l'axe des prix (bande droite de l'image)."""
    if not _available():
        return None
    w = image.shape[1]
    band = image[:, int(w * (1 - axis_fraction)) :]
    data = pytesseract.image_to_data(band, config="--psm 11", output_type=pytesseract.Output.DICT)
    points = []
    for text, top, height in zip(data["text"], data["top"], data["height"], strict=False):
        t = text.strip().replace(" ", "")
        if _NUMBER.match(t):
            points.append((top + height / 2, float(t.replace(",", "."))))
    return fit_axis(points)
