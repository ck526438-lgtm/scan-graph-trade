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
