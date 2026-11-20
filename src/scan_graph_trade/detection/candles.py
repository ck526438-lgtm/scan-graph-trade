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

import itertools
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
    fill_margin_top: int = 0  # bande haute ignorée pour le remplissage seulement (mode fill)
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
        self.exclude: list[tuple[int, int, int, int]] = []  # zones de texte (x, y, w, h) à ignorer
        self.pitch: float | None = None  # pas mesuré entre deux bougies (px), après detect()

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
        for x, y, bw, bh in self.exclude:  # texte lu par l'OCR : en-tête, étiquettes, axe du temps
            m[max(0, y - 2) : y + bh + 2, max(0, x - 2) : x + bw + 2] = 0
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

    def _segments(self, m: np.ndarray, pitch: float | None = None,
                  cut_mask: np.ndarray | None = None) -> list[tuple[int, int]]:
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
        if pitch:
            segs = self._grid_segments(m, m if cut_mask is None else cut_mask, pitch)
        return segs

    # --- bougies collées ---------------------------------------------------
    @staticmethod
    def _pitch_from_segments(segs: list[tuple[int, int]]) -> tuple[float | None, float]:
        """Pas de la grille sur laquelle tombent les bords des segments (bougies seules ou collées).

        Les bords gauches (et droits) de tous les segments sont alignés sur une
        grille de pas P, même quand plusieurs bougies sont soudées : on cherche
        le plus grand P qui aligne presque tous les bords. Renvoie (P, score 0-1).
        """
        if len(segs) < 6:
            return None, 0.0
        lefts = np.array([s[0] for s in segs], dtype=float)
        rights = np.array([s[1] for s in segs], dtype=float)
        span = rights[-1] - lefts[0]
        hi = min(80.0, span / 5)
        if hi <= 3:
            return None, 0.0
        cands = np.arange(3.0, hi, 0.05)

        def score(edges: np.ndarray) -> np.ndarray:
            ph = (edges[None, :] % cands[:, None]) / cands[:, None]  # phase 0-1
            bins = np.floor(ph * 40).astype(int) % 40
            hist = np.zeros((len(cands), 40))
            np.add.at(hist, (np.repeat(np.arange(len(cands)), len(edges)), bins.ravel()), 1)
            win = sum(np.roll(hist, k, axis=1) for k in (-2, -1, 0, 1, 2))  # ±0,06 P
            return win.max(axis=1) / len(edges)

        sc = (score(lefts) + score(rights)) / 2
        best = float(sc.max())
        if best < 0.6:
            return None, best
        i = int(np.where(sc >= 0.92 * best)[0].max())  # le plus grand pas (pas une sous-harmonique)
        p = float(cands[i])
        # affinage : régression des bords sur leur rang dans la grille
        for edges in (lefts,):
            j = np.round((edges - edges[0]) / p)
            ok = np.abs((edges - edges[0]) / p - j) < 0.15
            if ok.sum() >= 4 and np.ptp(j[ok]) > 0:
                p = float(np.polyfit(j[ok], edges[ok], 1)[0])
        return p, float(sc[i])

    def estimate_pitch(self, m: np.ndarray) -> tuple[float | None, np.ndarray]:
        """Écart horizontal (px) entre deux bougies consécutives (None si incertain).

        MT5 dessine toutes les bougies avec le même pas. On le mesure sur les
        bougies bien séparées ; il sert ensuite à redécouper les blocs de bougies
        que le flou JPEG ou un redimensionnement a soudées. Si le flou a comblé
        les espaces, on « amincit » d'abord le masque horizontalement (érosion),
        ce qui rouvre les séparations. Renvoie aussi le masque utilisé pour
        trouver les points de coupe.
        """
        best: tuple[float, float | None, np.ndarray] = (0.0, None, m)
        for k in (1, 3, 5):
            mm = m if k == 1 else cv2.erode(m, cv2.getStructuringElement(cv2.MORPH_RECT, (k, 1)))
            segs = self._segments(mm)
            p, sc = self._pitch_from_segments(segs)
            # plus il y a de segments bien alignés, plus la mesure est sûre
            q = sc * min(1.0, len(segs) / 30)
            if p is not None and q > best[0] + 0.02:
                best = (q, p, mm)
        return best[1], best[2]

    @staticmethod
    def _grid_segments(m: np.ndarray, cut_mask: np.ndarray, pitch: float) -> list[tuple[int, int]]:
        """Redécoupe la zone des bougies sur la grille de pas `pitch`.

        Gère les deux défauts des captures dégradées : bougies soudées (une seule
        tache pour plusieurs bougies) et bougies creuses coupées en deux morceaux.
        Chaque séparation est recalée sur la colonne la plus vide autour de sa
        position théorique.
        """
        prof = np.count_nonzero(m, axis=0)
        nz = np.where(prof > 0)[0]
        if nz.size == 0:
            return []
        cprof = np.count_nonzero(cut_mask, axis=0).astype(float) + 0.01 * prof
        # phase de la grille : centres des segments isolés du masque de coupe
        cols = np.where(np.count_nonzero(cut_mask, axis=0) > 0)[0]
        centers = []
        if cols.size:
            start = prev = int(cols[0])
            for c in [*list(cols[1:]), None]:
                if c is None or c - prev > 1:
                    if prev - start + 1 < pitch:
                        centers.append((start + prev) / 2)
                    if c is not None:
                        start = int(c)
                if c is not None:
                    prev = int(c)
        if centers:
            ang = 2 * np.pi * np.array(centers) / pitch
            phase = float(np.angle(np.mean(np.exp(1j * ang))) / (2 * np.pi) * pitch) % pitch
        else:
            phase = float(nz[0]) % pitch
        first, last_col = int(nz[0]), int(nz[-1])
        j0 = int(np.floor((first - phase) / pitch)) - 1
        j1 = int(np.ceil((last_col - phase) / pitch)) + 1
        cuts = []
        for j in range(j0, j1 + 1):
            b = phase + (j + 0.5) * pitch  # séparation théorique entre deux bougies
            lo, hi = int(np.floor(b - pitch / 4)), int(np.ceil(b + pitch / 4))
            lo, hi = max(lo, 0), min(hi, m.shape[1] - 1)
            if hi < lo:
                continue
            cut = lo + int(np.argmin(cprof[lo : hi + 1]))
            if cuts and cut <= cuts[-1]:
                continue
            cuts.append(cut)
        out = []
        for c0, c1 in itertools.pairwise(cuts):
            x0, x1 = c0 + 1, c1 - 1
            if x1 < x0:
                continue
            sub = np.where(prof[x0 : x1 + 1] > 0)[0]
            if sub.size:
                out.append((x0 + int(sub[0]), x0 + int(sub[-1])))
        return out

    def _geometry(self, m: np.ndarray, x0: int, x1: int, extent: np.ndarray | None = None):
        """Renvoie (top, bottom, body_top, body_bottom, left, right) ou None.

        Le corps est repéré par l'étendue horizontale de chaque ligne (et non le
        nombre de pixels), ce qui marche aussi pour les bougies creuses.
        `extent` (optionnel) est le masque utilisé pour les extrémités des mèches.
        """
        sub = m[:, x0 : x1 + 1] > 0
        ext = sub if extent is None else extent[:, x0 : x1 + 1] > 0
        rows = np.where(ext.any(axis=1))[0]
        if rows.size == 0 or rows[-1] - rows[0] + 1 < self.config.min_height:
            return None
        lefts = np.where(sub.any(axis=1), sub.argmax(axis=1), 0)
        rights = np.where(sub.any(axis=1), sub.shape[1] - 1 - sub[:, ::-1].argmax(axis=1), -1)
        spans = rights - lefts + 1
        widest = int(spans.max())
        # au moins 2 px dès que la bougie est plus large que sa mèche (bougies de 3 px en dézoom)
        threshold = 1 if widest <= 1 else max(2, int(np.ceil(widest * 0.6)))
        body_rows = np.where(spans >= threshold)[0]
        btop, bbot = int(body_rows[0]), int(body_rows[-1])
        left = x0 + int(lefts[body_rows].min())
        right = x0 + int(rights[body_rows].max())
        return int(rows[0]), int(rows[-1]), btop, bbot, left, right

    @staticmethod
    def _remove_unframed(fill: np.ndarray, outline: np.ndarray) -> np.ndarray:
        """Garde seulement les zones de remplissage entourées par un contour de bougie.

        Écarte le texte de l'en-tête, les étiquettes et objets de même couleur
        qui, sinon, se collent aux bougies situées en dessous.
        """
        if not fill.any() or fill is outline:
            return fill
        near = cv2.dilate(outline, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
        n, lab = cv2.connectedComponents((fill > 0).astype(np.uint8), connectivity=8)
        if n <= 1:
            return fill
        touching = np.unique(lab[(near > 0) & (lab > 0)])
        keep = np.zeros(n, dtype=bool)
        keep[touching] = True
        return np.where(keep[lab], fill, 0).astype(fill.dtype)

    # --- modes ---------------------------------------------------------
    def _detect_color(self, hsv: np.ndarray) -> list[Raw]:
        raw = []
        masks = [(self._prepare(self.mask(hsv, ranges)), bullish)
                 for ranges, bullish in ((self.config.bull_ranges, True), (self.config.bear_ranges, False))]
        pitch, cut = self.estimate_pitch(masks[0][0] | masks[1][0])
        self.pitch = pitch
        for m, bullish in masks:
            for x0, x1 in self._segments(m, pitch, cut & m if pitch else None):
                g = self._geometry(m, x0, x1)
                if g:
                    top, bottom, btop, bbot, _, _ = g
                    raw.append((int((x0 + x1) // 2), top, bottom, btop, bbot, bullish))
        return raw

    @staticmethod
    def _is_hollow(hsv, fill, btop, bbot, left, right, bg_v: float) -> bool:
        """Corps creux (haussière MT5) ou plein (baissière) ?

        On regarde la luminosité de la colonne centrale du corps, comparée au fond :
        un corps creux a la couleur du fond. Plus robuste que la couleur exacte du
        remplissage, que la compression JPEG teinte (blanc → verdâtre).
        """
        if bbot - btop < 2 or right - left < 2:  # corps trop fin : pas d'intérieur visible
            inner = fill[btop : bbot + 1, left : right + 1]
            return True if inner.size == 0 else bool(np.count_nonzero(inner) < 0.5 * inner.size)
        cx = (left + right) / 2
        half = max(0, int((right - left) / 6))
        x0, x1 = round(cx) - half, round(cx) + half + 1
        pad = max(1, (bbot - btop) // 6)
        y0, y1 = btop + pad, bbot - pad + 1
        if y1 <= y0:
            y0, y1 = btop + 1, bbot
        core = hsv[y0:y1, x0:x1, 2].astype(float)
        if core.size == 0:
            return True
        return bool(abs(float(np.median(core)) - bg_v) < 0.45 * 255)

    def _detect_fill(self, hsv: np.ndarray) -> list[Raw]:
        bg_v = float(np.median(hsv[..., 2]))
        outline = self._prepare(self.mask(hsv, self.config.outline_ranges))
        fill = self._prepare(self.mask(hsv, self.config.bear_fill_ranges))
        if self.config.fill_margin_top:  # en-tête (texte de même couleur que le remplissage)
            fill[: max(self.config.fill_margin_top, int(0.035 * fill.shape[0])), :] = 0
        fill = self._remove_unframed(fill, outline)
        fg = outline | fill
        raw = []
        pitch, cut = self.estimate_pitch(outline)
        self.pitch = pitch
        for x0, x1 in self._segments(fg, pitch, cut if pitch else None):
            if not outline[:, x0 : x1 + 1].any():  # texte, étiquettes… sans contour de bougie
                continue
            g = self._geometry(fg, x0, x1, extent=outline)
            if not g:
                continue
            top, bottom, btop, bbot, left, right = g
            btop, bbot = max(btop, top), min(bbot, bottom)
            bullish = self._is_hollow(hsv, fill, btop, bbot, left, right, bg_v)
            raw.append((int((left + right) // 2), top, bottom, btop, bbot, bullish))
        return raw

    # --- API -----------------------------------------------------------
    def detect_raw(self, image_bgr: np.ndarray) -> list[Raw]:
        """Bougies en pixels : (x, top, bottom, body_top, body_bottom, bullish)."""
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        self._axis_x = self.find_price_axis(image_bgr) if self.config.detect_price_axis else None
        raw = self._detect_fill(hsv) if self.config.mode == "fill" else self._detect_color(hsv)
        return sorted(raw, key=lambda c: c[0])

    def detect(self, image_bgr: np.ndarray, to_price=None,
               text_boxes: list[tuple[int, int, int, int]] | None = None) -> list[Candle]:
        """Détecte les bougies. `to_price(y_pixel) -> prix` convertit si l'axe est calibré.

        `text_boxes` : boîtes (x, y, w, h) des mots lus par l'OCR, effacées avant la détection.
        """
        h = image_bgr.shape[0]
        self.exclude = [b for b in (text_boxes or []) if b[3] < 0.08 * h]
        conv = to_price or (lambda y: float(h - y))
        candles = []
        for i, (x, top, bottom, btop, bbot, bull) in enumerate(self.detect_raw(image_bgr)):
            high, low = float(conv(top)), float(conv(bottom))
            upper, lower = float(conv(btop)), float(conv(bbot))
            o, c = (lower, upper) if bull else (upper, lower)
            candles.append(Candle(i, int(x), o, high, low, c, bull))
        return candles
