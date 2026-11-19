"""Interface web : `sgt serve` puis http://127.0.0.1:8000 (glisser-déposer une capture).

Dépendances : ``pip install "scan-graph-trade[web]"`` (FastAPI, Uvicorn, python-multipart).
"""
# pas de `from __future__ import annotations` : FastAPI doit résoudre UploadFile (import local)

import base64
import json
import math
from importlib import resources


def _clean(o):
    """JSON strict (pas de NaN/Infinity, refusés par les navigateurs)."""
    if isinstance(o, float):
        return None if math.isnan(o) or math.isinf(o) else o
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list | tuple):
        return [_clean(v) for v in o]
    return o


def create_app():
    try:
        from fastapi import FastAPI, File, Form, HTTPException, UploadFile
        from fastapi.responses import HTMLResponse, JSONResponse
    except ImportError as e:  # pragma: no cover
        raise SystemExit('Interface web : installez les dépendances avec  pip install "scan-graph-trade[web]"') from e

    import cv2

    from .. import __version__
    from ..analyzer import analyze_image, decode_image
    from ..ocr.reader import manual_axis
    from ..patterns.candlestick import LABELS_FR
    from ..report import DISCLAIMER, annotate, render_report

    app = FastAPI(title="Scan Graph Trade", version=__version__)
    page = resources.files(__package__).joinpath("index.html").read_text(encoding="utf-8")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return page

    @app.get("/api/health")
    def health() -> dict:
        from ..ocr.reader import available

        return {"status": "ok", "version": __version__, "ocr": available()}

    @app.post("/api/analyze")
    async def analyze(file: UploadFile = File(...), axis: str = Form(""), symbol: str = Form(""),
                      timeframe: str = Form(""), profile: str = Form("auto")):
        data = await file.read()
        if len(data) > 15 * 1024 * 1024:
            raise HTTPException(413, "Image trop lourde (15 Mo max)")
        try:
            img = decode_image(data)
            calib = manual_axis(axis) if axis.strip() else None
            res = analyze_image(img, source=file.filename or "capture", axis=calib, profile=profile,
                                symbol=symbol.strip().upper() or None,
                                timeframe=timeframe.strip().upper() or None)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
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
        return JSONResponse(json.loads(json.dumps(_clean(payload), default=str)))

    return app


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    try:
        import uvicorn
    except ImportError as e:  # pragma: no cover
        raise SystemExit('Interface web : installez les dépendances avec  pip install "scan-graph-trade[web]"') from e
    print(f"Scan Graph Trade — interface web sur http://{host}:{port}")
    uvicorn.run(create_app(), host=host, port=port, log_level="warning")
