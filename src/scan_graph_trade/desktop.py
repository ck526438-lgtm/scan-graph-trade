"""Application de bureau (Windows .exe) : fenêtre native autour de l'interface web locale.

- le moteur tourne dans le serveur local sans dépendance (``web.lite``) ;
- la fenêtre utilise pywebview (Edge WebView2 sous Windows) ; à défaut, le navigateur ;
- dans l'exécutable PyInstaller, Tesseract est embarqué dans le dossier ``tesseract/``.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Scan Graph Trade"


def _bundle_dir() -> Path | None:
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) if base else None


def configure_tesseract() -> None:
    """Utilise le Tesseract embarqué (exe) ou une installation Windows standard."""
    try:
        import pytesseract
    except ImportError:
        return
    candidates = []
    bundle = _bundle_dir()
    if bundle:
        candidates.append(bundle / "tesseract")
    for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        if os.environ.get(env):
            candidates.append(Path(os.environ[env]) / "Tesseract-OCR")
            candidates.append(Path(os.environ[env]) / "Programs" / "Tesseract-OCR")
    for d in candidates:
        exe = d / ("tesseract.exe" if os.name == "nt" else "tesseract")
        if exe.exists():
            pytesseract.pytesseract.tesseract_cmd = str(exe)
            if (d / "tessdata").is_dir():
                os.environ["TESSDATA_PREFIX"] = str(d / "tessdata")
            return


def selftest(image: str, out: str) -> int:
    """Vérifie l'exécutable sans interface : `ScanGraphTrade.exe --selftest capture.png resultat.json`."""
    import json

    from .ocr.reader import available
    from .web.service import analyze_bytes

    payload = analyze_bytes(Path(image).read_bytes(), Path(image).name)
    fc = (payload.get("analysis") or {}).get("forecast") or {}
    report = {"ocr": available(), "symbol": payload["symbol"], "timeframe": payload["timeframe"],
              "calibrated": payload["calibrated"], "candles": payload["candles"],
              "verdict": fc.get("verdict"), "score": fc.get("score")}
    Path(out).write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    return 0 if payload["candles"] > 0 and fc.get("verdict") else 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    configure_tesseract()
    if len(argv) == 3 and argv[0] == "--selftest":
        return selftest(argv[1], argv[2])
    from .web.lite import serve_background

    port = serve_background()
    url = f"http://127.0.0.1:{port}/"
    try:
        import webview
    except ImportError:
        webview = None

    if webview is not None:
        try:
            webview.settings["ALLOW_DOWNLOADS"] = True  # boutons « Exporter »
        except (AttributeError, TypeError):
            pass
        webview.create_window(APP_NAME, url, width=1380, height=900, min_size=(900, 600))
        webview.start()
        return 0

    import time
    import webbrowser

    print(f"{APP_NAME} — ouvert dans votre navigateur : {url}  (fermez cette fenêtre pour quitter)")
    webbrowser.open(url)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
