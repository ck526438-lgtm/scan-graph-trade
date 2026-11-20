"""Annotation de la capture : zones, obliques, pivots, figures et plan de trade."""
from __future__ import annotations

import cv2
import numpy as np

from ..models import AnalysisResult

BLUE = (235, 140, 30)  # BGR — couleurs du logo (bleu / orange)
ORANGE = (30, 140, 255)
GREEN = (90, 200, 60)
RED = (60, 60, 230)
WHITE = (255, 255, 255)
GREY = (150, 150, 150)


def _text(img, txt, org, color, scale=0.45, bg=(20, 20, 20)):
    (w, h), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    x, y = int(org[0]), int(org[1])
    x = max(0, min(x, img.shape[1] - w - 4))
    y = max(h + 4, min(y, img.shape[0] - 4))
    cv2.rectangle(img, (x - 2, y - h - 4), (x + w + 2, y + 3), bg, -1)
    cv2.putText(img, txt, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)


def _ascii(s: str) -> str:
    """OpenCV n'affiche pas les accents : on les retire pour les étiquettes."""
    import unicodedata

    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def annotate(image: np.ndarray, res: AnalysisResult) -> np.ndarray:
    img = image.copy()
    ta = res.analysis
    if not ta or not res.candles:
        return img
    h, w = img.shape[:2]
    xs = [c.x for c in res.candles]
    x_of = {c.index: c.x for c in res.candles}
    right = min(w - 1, xs[-1] + 75)
    y = res.price_to_y

    # zones de support / résistance (semi-transparentes) : les plus utiles seulement
    price = ta["last_price"]
    sup = [lv for lv in ta["levels"] if lv["price"] < price]
    res_ = [lv for lv in ta["levels"] if lv["price"] >= price]
    keep = sup[-2:] + res_[:2] + [lv for lv in ta["levels"] if lv["strength"] >= 0.6]
    levels = list({round(lv["price"], 8): lv for lv in keep}.values())
    overlay = img.copy()
    for lv in levels:
        col = GREEN if lv["kind"] == "support" else RED
        y0, y1 = sorted((int(y(lv["high"])), int(y(lv["low"]))))
        cv2.rectangle(overlay, (xs[0], y0), (right, max(y1, y0 + 2)), col, -1)
    cv2.addWeighted(overlay, 0.18, img, 0.82, 0, img)
    label_x = xs[0] + 4
    for lv in levels:
        col = GREEN if lv["kind"] == "support" else RED
        yy = int(y(lv["price"]))
        cv2.line(img, (xs[0], yy), (right, yy), col, 1, cv2.LINE_AA)
        tag = "S" if lv["kind"] == "support" else "R"
        _text(img, f"{tag} {res.fmt(lv['price'])} x{lv['touches']}", (label_x, yy - 3), col, 0.38)

    # obliques
    for tl in ta["trendlines"]:
        col = GREEN if tl["kind"] == "support" else RED
        i_end = len(res.candles) - 1
        p_end = tl["p0"] + tl["slope"] * (i_end - tl["i0"])
        cv2.line(img, (x_of[tl["i0"]], int(y(tl["p0"]))), (x_of[i_end], int(y(p_end))), col, 2, cv2.LINE_AA)

    # pivots de structure (8 derniers)
    for s in ta["swings"][-8:]:
        if not s["label"]:
            continue
        xx, yy = x_of[s["index"]], int(y(s["price"]))
        dy = -8 if s["kind"] == "high" else 16
        col = GREEN if s["label"] in ("HH", "HL") else RED
        _text(img, s["label"], (xx - 8, yy + dy), col, 0.38)

    # figures chartistes
    for cp in ta["chart_patterns"]:
        pts = [(x_of.get(int(i), xs[-1]), int(y(p))) for i, p in cp["points"]]
        col = GREEN if cp["direction"] == "bullish" else RED if cp["direction"] == "bearish" else ORANGE
        if cp["name"].endswith(("triangle", "wedge", "channel")) or cp["name"] == "rectangle":
            cv2.line(img, pts[0], pts[1], col, 2, cv2.LINE_AA)
            cv2.line(img, pts[2], pts[3], col, 2, cv2.LINE_AA)
        else:
            cv2.polylines(img, [np.array(pts, np.int32)], False, col, 2, cv2.LINE_AA)
        if cp["neckline"] is not None:
            yy = int(y(cp["neckline"]))
            cv2.line(img, (pts[0][0], yy), (right, yy), col, 1, cv2.LINE_AA)
        _text(img, _ascii(cp["label"]) + (" (confirme)" if cp["confirmed"] else ""), (pts[0][0], pts[0][1] - 10), col)

    # figures en chandeliers sur les 10 dernières bougies
    n = len(res.candles)
    for p in res.patterns:
        if p.index < n - 10 or p.direction == "neutral":
            continue
        c = res.candles[p.index]
        col = GREEN if p.direction == "bullish" else RED
        yy = int(y(c.low)) + 14 if p.direction == "bullish" else int(y(c.high)) - 8
        cv2.drawMarker(img, (c.x, yy), col, cv2.MARKER_TRIANGLE_UP if p.direction == "bullish"
                       else cv2.MARKER_TRIANGLE_DOWN, 10, 2)

    # plan de trade
    fc = ta["forecast"]
    plan = fc["plan"]
    if plan:
        x0 = xs[-1] + 6
        x1 = min(w - 1, x0 + 70)
        ye, ys = int(y(plan["entry"])), int(y(plan["stop_loss"]))
        cv2.rectangle(img, (x0, min(ye, ys)), (x1, max(ye, ys)), RED, 1)
        for k, tp in enumerate(plan["take_profits"], 1):
            yt = int(y(tp))
            cv2.line(img, (xs[-1] - 60, yt), (x1, yt), GREEN, 1, cv2.LINE_AA)
            _text(img, f"TP{k} {res.fmt(tp)}", (x0, yt - 3), GREEN, 0.38)
        cv2.line(img, (xs[-1] - 60, ye), (x1, ye), BLUE, 2)
        cv2.line(img, (xs[-1] - 60, ys), (x1, ys), RED, 1, cv2.LINE_AA)
        _text(img, f"SL {res.fmt(plan['stop_loss'])}", (x0, ys + 14), RED, 0.38)

    # bandeau du verdict
    col = GREEN if fc["verdict"] == "ACHAT" else RED if fc["verdict"] == "VENTE" else ORANGE
    title = " ".join(x for x in (res.symbol, res.timeframe) if x)
    banner = f"{title}  {fc['verdict']}  score {fc['score']:+.0f}  réussite hist. {fc['confidence']:.0f}%".strip()
    _text(img, _ascii(banner), (10, 44), col, 0.6, bg=(30, 30, 30))
    _text(img, "Scan Graph Trade", (10, h - 8), GREY, 0.4)
    return img
