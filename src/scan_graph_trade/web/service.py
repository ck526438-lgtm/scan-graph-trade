"""Logique commune à toutes les interfaces (FastAPI, serveur local, app bureau, app Android)."""
from __future__ import annotations

import base64
import json
import math
from importlib import resources

MAX_UPLOAD = 15 * 1024 * 1024


def page_html() -> str:
    return resources.files("scan_graph_trade.web").joinpath("index.html").read_text(encoding="utf-8")


def clean_json(o):
    """JSON strict (pas de NaN/Infinity, refusés par les navigateurs)."""
    if isinstance(o, float):
        return None if math.isnan(o) or math.isinf(o) else o
    if isinstance(o, dict):
        return {k: clean_json(v) for k, v in o.items()}
    if isinstance(o, list | tuple):
        return [clean_json(v) for v in o]
    return o


def health() -> dict:
    from .. import __version__
    from ..ocr.reader import available

    return {"status": "ok", "version": __version__, "ocr": available()}


def analyze_bytes(data: bytes, filename: str = "capture", axis: str = "", symbol: str = "",
                  timeframe: str = "", profile: str = "auto") -> dict:
    """Analyse une image envoyée par l'interface. Lève ValueError si l'entrée est invalide."""
    import cv2

    from ..analyzer import analyze_image, decode_image
    from ..ocr.reader import manual_axis
    from ..patterns.candlestick import LABELS_FR
    from ..report import DISCLAIMER, annotate, render_report

    if len(data) > MAX_UPLOAD:
        raise ValueError("Image trop lourde (15 Mo max)")
    img = decode_image(data)
    calib = manual_axis(axis) if axis.strip() else None
    res = analyze_image(img, source=filename or "capture", axis=calib, profile=profile or "auto",
                        symbol=symbol.strip().upper() or None, timeframe=timeframe.strip().upper() or None)
    ok, buf = cv2.imencode(".png", annotate(img, res))
    payload = {
        "source": res.source, "symbol": res.symbol, "timeframe": res.timeframe,
        "profile": res.profile, "candles": len(res.candles), "calibrated": res.calibrated,
        "fmt_decimals": res.price_decimals,
        "analysis": res.analysis, "report": render_report(res), "markdown": render_report(res, True),
        "patterns": [{**p.__dict__, "label": LABELS_FR.get(p.name, p.name),
                      "sens": {"bullish": "haussier", "bearish": "baissier"}.get(p.direction, "neutre")}
                     for p in res.patterns[-15:]],
        "annotated": "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode() if ok else None,
        "disclaimer": DISCLAIMER,
    }
    return json.loads(json.dumps(clean_json(payload), default=str))
