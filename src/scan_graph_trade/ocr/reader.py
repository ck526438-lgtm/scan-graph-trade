"""OCR (Tesseract) : lecture du texte, de l'en-tête et calibration de l'axe des prix.

Tesseract doit être installé sur le système (voir README). Si pytesseract
ou le binaire est absent, les fonctions dégradent proprement.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

import cv2
import numpy as np

try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None

_NUMBER = re.compile(r"^-?\d{1,7}(?:[.,]\d{1,6})?$")

KNOWN_SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD", "EURGBP", "EURJPY",
    "GBPJPY", "EURCHF", "EURAUD", "EURCAD", "AUDJPY", "CADJPY", "CHFJPY", "GBPCHF", "GBPAUD",
    "AUDCAD", "AUDNZD", "NZDJPY", "XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD", "US30", "NAS100",
    "US100", "SPX500", "US500", "GER40", "DE40", "UK100", "USOIL", "UKOIL", "XTIUSD", "XBRUSD",
    "USDXOF", "EURXOF",
]
TIMEFRAMES = ["M1", "M2", "M3", "M4", "M5", "M6", "M10", "M12", "M15", "M20", "M30",
              "H1", "H2", "H3", "H4", "H6", "H8", "H12", "D1", "W1", "MN1"]
_TF_FIX = str.maketrans({"N": "M", "S": "5", "O": "0", "I": "1", "L": "1", "Z": "2", "B": "8"})


@dataclass(frozen=True)
class AxisCalibration:
    slope: float
    intercept: float
    decimals: int = 5

    def __call__(self, y: float) -> float:
        return self.slope * y + self.intercept


def available() -> bool:
    if pytesseract is None:
        return False
    try:
        pytesseract.get_tesseract_version()
        return True
    except (pytesseract.TesseractNotFoundError, OSError, RuntimeError):
        return False


_available = available  # compatibilité


def _prep(img: np.ndarray, scale: int = 3) -> np.ndarray:
    """Gris, agrandi, texte sombre sur fond clair : ce que Tesseract lit le mieux."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    g = cv2.resize(g, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    if np.median(g) < 128:
        g = 255 - g
    return g


def extract_text(image: np.ndarray, lang: str = "eng") -> list[str]:
    """Extrait les lignes de texte (symbole, timeframe, valeurs d'indicateurs…)."""
    if not available():
        return []
    txt = pytesseract.image_to_string(image, lang=lang)
    return [line.strip() for line in txt.splitlines() if line.strip()]


def parse_header(text: str) -> tuple[str | None, str | None]:
    """Symbole et unité de temps depuis un texte d'en-tête OCR (tolère les erreurs de lecture)."""
    up = text.upper()
    symbol = None
    tokens = re.findall(r"[A-Z0-9]{4,7}", up)
    for t in tokens:
        if t in KNOWN_SYMBOLS:
            symbol = t
            break
    if symbol is None:
        for t in tokens:
            m = difflib.get_close_matches(t, KNOWN_SYMBOLS, n=1, cutoff=0.8)
            if m:
                symbol = m[0]
                break
    tf = None
    for cand in re.findall(r"[,\s]\s*([A-Z0-9]{1,3})\b", up):
        fixed = cand[0].translate({ord("N"): "M"}) + cand[1:].translate(_TF_FIX) if cand else cand
        if fixed in TIMEFRAMES:
            tf = fixed
            break
        if fixed == "MN":
            tf = "MN1"
            break
    return symbol, tf


def read_header(image: np.ndarray) -> tuple[str | None, str | None, str]:
    """Lit l'en-tête (coin haut-gauche) : MT5 affiche « EURUSD, M5: Euro vs US Dollar »."""
    if not available():
        return None, None, ""
    h, w = image.shape[:2]
    strip = image[0 : max(18, min(30, h // 20)), 0 : min(w, 500)]
    txt = pytesseract.image_to_string(_prep(strip, 4), config="--psm 7")
    sym, tf = parse_header(txt)
    return sym, tf, txt.strip()


def fit_axis(points: list[tuple[float, float]], decimals: int = 5) -> AxisCalibration | None:
    """Régression linéaire robuste prix = a*y + b à partir de paires (y_pixel, prix)."""
    if len(points) < 2:
        return None
    pts = np.array(points, dtype=float)
    for _ in range(3):  # on écarte les lectures aberrantes de l'OCR
        ys, prices = pts.T
        if len(pts) < 2 or np.ptp(ys) == 0:
            return None
        a, b = np.polyfit(ys, prices, 1)
        res = np.abs(prices - (a * ys + b))
        mad = np.median(res)
        keep = res <= max(3 * mad, 1e-12) if len(pts) > 3 else np.ones(len(pts), bool)
        if keep.all():
            break
        pts = pts[keep]
    if a >= 0:  # le prix doit diminuer quand y augmente
        return None
    return AxisCalibration(float(a), float(b), decimals)


def calibrate_price_axis(image: np.ndarray, axis_fraction: float = 0.12,
                         axis_x: int | None = None) -> AxisCalibration | None:
    """Lit les graduations de l'axe des prix (bande droite de l'image)."""
    if not available():
        return None
    w = image.shape[1]
    x0 = axis_x + 1 if axis_x is not None else int(w * (1 - axis_fraction))
    band = image[:, x0:]
    if band.shape[1] < 8:
        return None
    scale = 3
    data = pytesseract.image_to_data(_prep(band, scale), output_type=pytesseract.Output.DICT,
                                     config="--psm 11 -c tessedit_char_whitelist=0123456789.,-")
    points, decs = [], []
    for text, top, height, conf in zip(data["text"], data["top"], data["height"], data["conf"], strict=False):
        # les petits traits de graduation sont souvent lus comme un « - » en tête
        t = text.strip().replace(" ", "").lstrip("-_").rstrip(".,")
        if _NUMBER.match(t) and float(conf) > 30:
            t = t.replace(",", ".")
            points.append(((top + height / 2) / scale, float(t)))
            decs.append(len(t.split(".")[1]) if "." in t else 0)
    decimals = max(set(decs), key=decs.count) if decs else 5
    return fit_axis(points, decimals)


def manual_axis(spec: str) -> AxisCalibration:
    """Calibration manuelle : "y1=prix1,y2=prix2" (ex. "16=1.16540,684=1.15210")."""
    pts = []
    decs = []
    for part in spec.split(","):
        y, p = part.split("=")
        pts.append((float(y), float(p)))
        decs.append(len(p.split(".")[1]) if "." in p else 0)
    calib = fit_axis(pts, max(decs))
    if calib is None:
        raise ValueError("Calibration invalide : il faut 2 points, le prix le plus haut avec le plus petit y.")
    return calib
