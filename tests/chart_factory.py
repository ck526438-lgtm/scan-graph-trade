"""Fabrique de captures MT5 réalistes à partir d'une série OHLC connue (avec axe des prix lisible)."""
import cv2
import numpy as np


def random_walk(n=120, drift=0.0, vol=1.0, seed=0, start=1.1000, unit=0.0001):
    rng = np.random.default_rng(seed)
    out, price = [], start
    for _ in range(n):
        o = price
        c = o + (drift + rng.normal(0, vol)) * unit * 10
        hi = max(o, c) + abs(rng.normal(0, vol)) * unit * 4
        lo = min(o, c) - abs(rng.normal(0, vol)) * unit * 4
        out.append((o, hi, lo, c))
        price = c
    return out


def zigzag_series(legs, bars_per_leg=12, start=1.1000, unit=0.0001, seed=1):
    """Série qui suit des jambes successives (en pips), ex. [+60, -30, +60, -30]."""
    rng = np.random.default_rng(seed)
    out, price = [], start
    for leg in legs:
        step = leg * unit / bars_per_leg
        for _ in range(bars_per_leg):
            o = price
            c = o + step + rng.normal(0, abs(step) * 0.3)
            hi = max(o, c) + abs(rng.normal(0, abs(step) * 0.3))
            lo = min(o, c) - abs(rng.normal(0, abs(step) * 0.3))
            out.append((o, hi, lo, c))
            price = c
    return out


LAST_LABELS: list[dict] = []  # positions des graduations du dernier graphique dessiné (OCR simulé)


def draw_mt5(series, width=900, height=500, header="EURUSD,M5", decimals=4, scheme="green_on_black"):
    bg, outline, bull, bear, text = {
        "green_on_black": ((0, 0, 0), (0, 255, 0), (0, 0, 0), (255, 255, 255), (255, 255, 255)),
        "black_on_white": ((255, 255, 255), (0, 0, 0), (255, 255, 255), (0, 0, 0), (0, 0, 0)),
        # couleurs perso vert / rouge (très courant, notamment sur MT5 mobile) : contour = couleur du corps
        "colored": ((18, 18, 18), None, (80, 175, 76), (54, 67, 244), (200, 200, 200)),
    }[scheme]
    img = np.full((height, width, 3), bg, np.uint8)
    axis_x = width - 70
    lo = min(s[2] for s in series)
    hi = max(s[1] for s in series)
    pad = (hi - lo) * 0.08
    top_p, bot_p = hi + pad, lo - pad
    y0, y1 = 25, height - 25

    def y(p):
        return round(y0 + (top_p - p) / (top_p - bot_p) * (y1 - y0))

    cv2.putText(img, header, (6, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, text, 1, cv2.LINE_AA)
    cv2.line(img, (axis_x, 0), (axis_x, height), text, 1)
    step = 10 ** -decimals * 10
    while (top_p - bot_p) / step > 10:
        step *= 2
    p = np.ceil(bot_p / step) * step
    LAST_LABELS.clear()
    LAST_LABELS.append({"text": header.replace(",", ", "), "x": 6, "y": 4, "w": 90, "h": 12})
    while p < top_p:
        yy = y(p)
        cv2.line(img, (axis_x, yy), (axis_x + 4, yy), text, 1)
        LAST_LABELS.append({"text": f"{p:.{decimals}f}", "x": axis_x + 7, "y": yy - 5, "w": 50, "h": 10})
        cv2.putText(img, f"{p:.{decimals}f}", (axis_x + 7, yy + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, text, 1,
                    cv2.LINE_AA)
        p += step

    spacing = max(4, (axis_x - 30) // (len(series) + 1))
    half = max(1, spacing // 2 - 1)
    for i, (o, h, lw, c) in enumerate(series):
        x = 15 + i * spacing
        body = bull if c > o else bear
        edge = outline if outline is not None else body
        cv2.line(img, (x, y(h)), (x, y(lw)), edge, 1)
        t, b = y(max(o, c)), y(min(o, c))
        cv2.rectangle(img, (x - half, t), (x + half, max(b, t + 1)), body, -1)
        cv2.rectangle(img, (x - half, t), (x + half, max(b, t + 1)), edge, 1)
    return img
