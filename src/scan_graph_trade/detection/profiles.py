"""Profils de couleurs par plateforme, avec détection automatique.

MetaTrader 5 propose trois schémas (clic droit > Propriétés > Couleurs) :

- « Green On Black » (défaut) : fond noir, contour/mèches Lime, haussière
  creuse (noire), baissière pleine (blanche)            → ``mt5_green_on_black``
- « Black On White » : fond blanc, contour noir, haussière blanche,
  baissière noire                                       → ``mt5_black_on_white``
- Couleurs personnalisées vert / rouge (très courant)   → ``mt5_colored``
"""
from __future__ import annotations

import cv2
import numpy as np

from .candles import DEFAULT_BEAR_RANGES, DEFAULT_BULL_RANGES, CandleDetector, DetectorConfig

LIME = [((40, 70, 70), (80, 255, 255))]
WHITE = [((0, 0, 190), (179, 60, 255))]
BLACK = [((0, 0, 0), (179, 255, 60))]

# Zone utile MT5 : en-tête (symbole, timeframe), axe du temps, axe des prix à droite
_MT5_MARGINS = dict(margin_top=18, margin_bottom=20, margin_right_fraction=0.07, detect_price_axis=True)


def _profiles() -> dict[str, DetectorConfig]:
    return {
        "default": DetectorConfig(),
        "mt5_green_on_black": DetectorConfig(
            name="mt5_green_on_black", mode="fill", outline_ranges=LIME, bear_fill_ranges=WHITE,
            # l'en-tête est blanc (sans contour vert) : pas besoin de marge haute,
            # ce qui évite de tronquer les plus hautes mèches
            **{**_MT5_MARGINS, "margin_top": 0},
        ),
        "mt5_black_on_white": DetectorConfig(
            name="mt5_black_on_white", mode="fill", outline_ranges=BLACK, bear_fill_ranges=BLACK,
            **_MT5_MARGINS,
        ),
        "mt5_colored": DetectorConfig(
            name="mt5_colored", mode="color",
            bull_ranges=list(DEFAULT_BULL_RANGES), bear_ranges=list(DEFAULT_BEAR_RANGES),
            **_MT5_MARGINS,
        ),
    }


PROFILE_NAMES = ["auto", *_profiles().keys()]


def get_profile(name: str) -> DetectorConfig:
    try:
        return _profiles()[name]
    except KeyError:
        raise ValueError(f"Profil inconnu : {name!r}. Choix : {', '.join(PROFILE_NAMES)}") from None


def auto_profile(image_bgr: np.ndarray) -> DetectorConfig:
    """Devine le schéma MT5 à partir des couleurs dominantes de la capture."""
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    n_red = np.count_nonzero(CandleDetector.mask(hsv, DEFAULT_BEAR_RANGES))
    n_lime = np.count_nonzero(CandleDetector.mask(hsv, LIME))
    n_green = np.count_nonzero(CandleDetector.mask(hsv, DEFAULT_BULL_RANGES))
    dark_bg = float(np.median(hsv[..., 2])) < 100

    if n_red > 0.15 * (n_green + 1):  # deux couleurs distinctes → mode couleur
        return get_profile("mt5_colored")
    if dark_bg and n_lime > 0:
        return get_profile("mt5_green_on_black")
    if not dark_bg and n_green == 0:
        return get_profile("mt5_black_on_white")
    return get_profile("default")
