"""Pont Android ↔ moteur Python : OCR ML Kit + démarrage du serveur local."""
import json

_port = None


def _mlkit_words(image_bgr):
    import cv2
    from java import jclass

    ok, buf = cv2.imencode(".png", image_bgr)
    if not ok:
        return []
    return json.loads(str(jclass("com.ck526438.scangraphtrade.OcrHelper").recognize(buf.tobytes())))


def start() -> int:
    global _port
    if _port is None:
        from scan_graph_trade.ocr.reader import set_word_provider
        from scan_graph_trade.web.lite import serve_background

        set_word_provider(_mlkit_words)
        _port = serve_background()
    return _port


def selftest(path: str) -> str:
    """Analyse une capture et renvoie un résumé JSON (utilisé par le test automatique sur émulateur)."""
    from scan_graph_trade.ocr.reader import _words
    from scan_graph_trade.web.service import analyze_bytes

    start()
    with open(path, "rb") as f:
        data = f.read()
    d = analyze_bytes(data, path.rsplit("/", 1)[-1])
    fc = (d.get("analysis") or {}).get("forecast") or {}
    import cv2
    import numpy as np

    words = _words(cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR))
    return json.dumps({"symbol": d["symbol"], "timeframe": d["timeframe"], "calibrated": d["calibrated"],
                       "candles": d["candles"], "verdict": fc.get("verdict"), "score": fc.get("score"),
                       "ocr_words": len(words)}, ensure_ascii=False)
