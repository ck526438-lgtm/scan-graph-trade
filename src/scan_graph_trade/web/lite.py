"""Serveur web local sans dépendance (bibliothèque standard uniquement).

C'est lui qui tourne à l'intérieur des applications Windows (.exe) et Android
(.apk) : il sert la même page et la même API que la version FastAPI.
"""
from __future__ import annotations

import json
import threading
from email.parser import BytesParser
from email.policy import HTTP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .service import MAX_UPLOAD, analyze_bytes, health, page_html


def parse_multipart(content_type: str, body: bytes) -> tuple[dict[str, str], dict[str, tuple[str, bytes]]]:
    """Décode un formulaire multipart/form-data → (champs texte, fichiers {nom: (filename, octets)})."""
    msg = BytesParser(policy=HTTP).parsebytes(
        b"Content-Type: " + content_type.encode("latin-1") + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
    )
    fields: dict[str, str] = {}
    files: dict[str, tuple[str, bytes]] = {}
    if not msg.is_multipart():
        return fields, files
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        data = part.get_payload(decode=True) or b""
        filename = part.get_filename()
        if filename is not None:
            files[name] = (filename, data)
        else:
            fields[name] = data.decode(part.get_content_charset() or "utf-8", "replace")
    return fields, files


class Handler(BaseHTTPRequestHandler):
    server_version = "ScanGraphTrade"
    page: str = ""

    def log_message(self, *args) -> None:  # silencieux
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._send(200, self.page.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/health":
            self._json(200, health())
        else:
            self._json(404, {"detail": "Introuvable"})

    def do_POST(self) -> None:
        if self.path.split("?")[0] != "/api/analyze":
            self._json(404, {"detail": "Introuvable"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_UPLOAD + 1024 * 1024:
            self._json(413, {"detail": "Image trop lourde (15 Mo max)"})
            return
        body = self.rfile.read(length)
        fields, files = parse_multipart(self.headers.get("Content-Type", ""), body)
        if "file" not in files:
            self._json(400, {"detail": "Aucune image reçue"})
            return
        filename, data = files["file"]
        try:
            payload = analyze_bytes(data, filename, fields.get("axis", ""), fields.get("symbol", ""),
                                    fields.get("timeframe", ""), fields.get("profile", "auto"))
        except ValueError as e:
            self._json(400, {"detail": str(e)})
            return
        except Exception as e:  # noqa: BLE001 — l'appli ne doit jamais planter sur une capture
            self._json(500, {"detail": f"Erreur d'analyse : {e}"})
            return
        self._json(200, payload)


def make_server(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    Handler.page = page_html()
    return ThreadingHTTPServer((host, port), Handler)


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    make_server(host, port).serve_forever()


def serve_background(port: int = 0, host: str = "127.0.0.1") -> int:
    """Démarre le serveur dans un thread et renvoie le port (utilisé par les applis .exe / .apk)."""
    srv = make_server(host, port)
    threading.Thread(target=srv.serve_forever, daemon=True, name="sgt-server").start()
    return srv.server_address[1]
