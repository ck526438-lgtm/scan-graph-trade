"""Interface web : `sgt serve` puis http://127.0.0.1:8000 (glisser-déposer une capture).

Deux serveurs au choix, même page et même API :

- FastAPI (``pip install "scan-graph-trade[web]"``) : documentation automatique sur /docs ;
- serveur local sans dépendance (``web.lite``) : utilisé par les applications .exe et .apk.
"""
# pas de `from __future__ import annotations` : FastAPI doit résoudre UploadFile (import local)

from .service import analyze_bytes, clean_json, health, page_html

__all__ = ["analyze_bytes", "clean_json", "create_app", "health", "page_html", "run"]


def create_app():
    try:
        from fastapi import FastAPI, File, Form, HTTPException, UploadFile
        from fastapi.responses import HTMLResponse, JSONResponse
    except ImportError as e:  # pragma: no cover
        raise SystemExit('Interface web : installez les dépendances avec  pip install "scan-graph-trade[web]"') from e

    from .. import __version__

    app = FastAPI(title="Scan Graph Trade", version=__version__)
    page = page_html()

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return page

    @app.get("/api/health")
    def api_health() -> dict:
        return health()

    @app.post("/api/analyze")
    async def analyze(file: UploadFile = File(...), axis: str = Form(""), symbol: str = Form(""),
                      timeframe: str = Form(""), profile: str = Form("auto")):
        data = await file.read()
        try:
            payload = analyze_bytes(data, file.filename or "capture", axis, symbol, timeframe, profile)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        return JSONResponse(payload)

    return app


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    """FastAPI si installé, sinon le serveur local sans dépendance."""
    try:
        import uvicorn

        app = create_app()
    except (ImportError, SystemExit):
        from .lite import serve

        print(f"Scan Graph Trade — interface web (serveur local) sur http://{host}:{port}")
        serve(host, port)
        return
    print(f"Scan Graph Trade — interface web sur http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")
