"""Générateur de captures synthétiques au format MetaTrader 5."""
import cv2
import numpy as np

SCHEMES = {
    # fond, contour/mèche, remplissage haussier, remplissage baissier, texte, grille (BGR)
    "green_on_black": dict(bg=(0, 0, 0), outline=(0, 255, 0), bull=(0, 0, 0), bear=(255, 255, 255),
                           text=(255, 255, 255), grid=(153, 136, 119)),
    "black_on_white": dict(bg=(255, 255, 255), outline=(0, 0, 0), bull=(255, 255, 255), bear=(0, 0, 0),
                           text=(0, 0, 0), grid=(192, 192, 192)),
}

# (open, high, low, close) en pixels « prix » (plus grand = plus haut)
SERIES = [
    (200, 248, 185, 240), (240, 250, 225, 230), (210, 222, 160, 220),   # haussière, baissière, marteau
    (228, 232, 200, 205), (200, 260, 195, 250),                         # baissière, avalement haussier
]


def mt5_chart(scheme: str, width: int = 640, height: int = 420):
    s = SCHEMES[scheme]
    img = np.full((height, width, 3), s["bg"], np.uint8)
    # grille pointillée
    for y in range(40, height - 30, 60):
        for x in range(0, width - 60, 4):
            img[y, x] = s["grid"]
    # en-tête + axe des prix + axe du temps
    cv2.putText(img, "EURUSD,M5", (6, 13), cv2.FONT_HERSHEY_SIMPLEX, 0.4, s["text"], 1)
    cv2.line(img, (width - 58, 0), (width - 58, height), s["text"], 1)
    for y in range(40, height - 30, 60):
        cv2.putText(img, f"1.08{y:02d}", (width - 52, y + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, s["text"], 1)
    cv2.putText(img, "10 Nov 12:50", (40, height - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.35, s["text"], 1)
    # ligne Bid sur toute la largeur
    cv2.line(img, (0, 160), (width - 58, 160), s["grid"], 1)

    def y(p):
        return height - p

    for i, (o, h, lo, c) in enumerate(SERIES):
        x = 80 + i * 40
        cv2.line(img, (x, y(h)), (x, y(lo)), s["outline"], 1)
        top, bot = y(max(o, c)), y(min(o, c))
        fill = s["bull"] if c > o else s["bear"]
        cv2.rectangle(img, (x - 4, top), (x + 4, bot), fill, -1)
        cv2.rectangle(img, (x - 4, top), (x + 4, bot), s["outline"], 1)
    return img
