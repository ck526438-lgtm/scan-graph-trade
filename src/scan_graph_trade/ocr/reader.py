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


# --- moteur OCR externe (ex. Google ML Kit dans l'application Android) -----
# fonction image_bgr -> [{"text", "x", "y", "w", "h"}] (mots, en pixels de l'image)
_word_provider = None
_cache: tuple[int, list[dict]] | None = None


def set_word_provider(fn) -> None:
    """Branche un OCR externe à la place de Tesseract (None pour revenir à Tesseract)."""
    global _word_provider, _cache
    _word_provider, _cache = fn, None


def _words(image: np.ndarray) -> list[dict]:
    global _cache
    key = hash((image.shape, image[:: max(1, image.shape[0] // 64), :: max(1, image.shape[1] // 64)].tobytes()))
    if _cache is None or _cache[0] != key:
        try:
            words = list(_word_provider(image) or [])
        except Exception:  # noqa: BLE001 — un OCR défaillant ne doit pas bloquer l'analyse
            words = []
        _cache = (key, words)
    return _cache[1]


def _lines(words: list[dict]) -> list[str]:
    rows: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (w["y"] + w["h"] / 2, w["x"])):
        cy = w["y"] + w["h"] / 2
        if rows and abs(cy - (rows[-1][0]["y"] + rows[-1][0]["h"] / 2)) <= max(4, w["h"] / 2):
            rows[-1].append(w)
        else:
            rows.append([w])
    return [" ".join(w["text"] for w in sorted(r, key=lambda w: w["x"])) for r in rows]


def available() -> bool:
    if _word_provider is not None:
        return True
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


_LABEL = re.compile(r"[A-Za-z]{3,}|\d[\d.,:]{2,}")
_tess_cache: tuple[int, list[dict]] | None = None


def _tesseract_words(image: np.ndarray) -> list[dict]:
    global _tess_cache
    key = hash((image.shape, image[:: max(1, image.shape[0] // 64), :: max(1, image.shape[1] // 64)].tobytes()))
    if _tess_cache is not None and _tess_cache[0] == key:
        return _tess_cache[1]
    words: list[dict] = []
    try:
        d = pytesseract.image_to_data(_prep(image, 2), output_type=pytesseract.Output.DICT, config="--psm 11")
        for t, x, y, w, h, conf in zip(d["text"], d["left"], d["top"], d["width"], d["height"], d["conf"],
                                       strict=False):
            if t.strip() and float(conf) >= 70:
                words.append({"text": t.strip(), "x": x / 2, "y": y / 2, "w": w / 2, "h": h / 2})
    except Exception:  # noqa: BLE001
        words = []
    _tess_cache = (key, words)
    return words


def text_boxes(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Boîtes (x, y, w, h) du texte de la capture (en-tête, graduations, heures, étiquettes).

    Elles sont effacées avant de chercher les bougies : sinon un texte de la même
    couleur qu'une bougie (en-tête blanc de MT5, heures noires sur fond blanc…)
    se colle aux bougies voisines ou est pris pour une bougie.
    """
    if not available():
        return []
    words = _words(image) if _word_provider is not None else _tesseract_words(image)
    h, w = image.shape[:2]
    out = []
    for wd in words:
        if not _LABEL.search(str(wd["text"])) or wd["w"] > 0.4 * w or wd["h"] > 0.06 * h:
            continue
        out.append((int(wd["x"]), int(wd["y"]), int(np.ceil(wd["w"])), int(np.ceil(wd["h"]))))
    return out


def extract_text(image: np.ndarray, lang: str = "eng") -> list[str]:
    """Extrait les lignes de texte (symbole, timeframe, valeurs d'indicateurs…)."""
    if _word_provider is not None:
        return _lines(_words(image))
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
    strip_h = max(18, min(30, h // 20))
    if _word_provider is not None:
        top = [wd for wd in _words(image) if wd["y"] < strip_h and wd["x"] < min(w, 500)]
        txt = " ".join(_lines(top))
        sym, tf = parse_header(txt)
        return sym, tf, txt
    strip = image[0:strip_h, 0 : min(w, 500)]
    # plusieurs lectures (agrandissement / mode de page) : les versions de Tesseract diffèrent
    best: tuple[str | None, str | None, str] = (None, None, "")
    for scale, psm in ((4, 7), (3, 7), (2, 7), (4, 6), (3, 11)):
        txt = pytesseract.image_to_string(_prep(strip, scale), config=f"--psm {psm}").strip()
        sym, tf = parse_header(txt)
        if (sym is not None) + (tf is not None) > (best[0] is not None) + (best[1] is not None):
            best = (sym, tf, txt)
        if sym and tf:
            break
    return best


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
    if _word_provider is not None:
        return _calibrate_from_words([wd for wd in _words(image) if wd["x"] >= x0 - 2])
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


def _parse_price(text: str) -> tuple[float, int] | None:
    t = text.strip().replace(" ", "").lstrip("-_").rstrip(".,")
    if not _NUMBER.match(t):
        return None
    t = t.replace(",", ".")
    return float(t), (len(t.split(".")[1]) if "." in t else 0)


def _calibrate_from_words(words: list[dict]) -> AxisCalibration | None:
    points, decs = [], []
    for wd in words:
        parsed = _parse_price(wd["text"])
        if parsed:
            points.append((wd["y"] + wd["h"] / 2, parsed[0]))
            decs.append(parsed[1])
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
