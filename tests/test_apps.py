"""Applications .exe / .apk : serveur local, OCR externe (ML Kit), auto-test de l'exécutable."""
import json
import urllib.error
import urllib.request
import uuid

import chart_factory
import cv2
import pytest
from chart_factory import draw_mt5, zigzag_series

from scan_graph_trade.analyzer import analyze_image
from scan_graph_trade.desktop import main as desktop_main
from scan_graph_trade.ocr import reader
from scan_graph_trade.web.lite import parse_multipart, serve_background


def _multipart(fields: dict, file: tuple[str, bytes]) -> tuple[str, bytes]:
    b = uuid.uuid4().hex
    out = b""
    for k, v in fields.items():
        out += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    out += (f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{file[0]}"\r\n'
            "Content-Type: image/png\r\n\r\n").encode() + file[1] + f"\r\n--{b}--\r\n".encode()
    return f"multipart/form-data; boundary={b}", out


def test_parse_multipart():
    ctype, body = _multipart({"symbol": "xauusd", "axis": ""}, ("capture é.png", b"\x89PNG\r\n--data"))
    fields, files = parse_multipart(ctype, body)
    assert fields == {"symbol": "xauusd", "axis": ""}
    assert files["file"] == ("capture é.png", b"\x89PNG\r\n--data")


@pytest.fixture(scope="module")
def server():
    return f"http://127.0.0.1:{serve_background()}"


def test_lite_server(server):
    assert "Scan Graph" in urllib.request.urlopen(server + "/").read().decode()
    assert json.loads(urllib.request.urlopen(server + "/api/health").read())["status"] == "ok"
    _, png = cv2.imencode(".png", draw_mt5(zigzag_series([60, -30, 60, -30, 60])))
    ctype, body = _multipart({"symbol": "eurusd"}, ("c.png", png.tobytes()))
    req = urllib.request.Request(server + "/api/analyze", data=body, headers={"Content-Type": ctype})
    d = json.loads(urllib.request.urlopen(req).read())
    assert d["symbol"] == "EURUSD" and d["analysis"]["forecast"]["verdict"] in ("ACHAT", "VENTE", "ATTENDRE")


def test_lite_server_errors(server):
    ctype, body = _multipart({}, ("x.png", b"pas une image"))
    req = urllib.request.Request(server + "/api/analyze", data=body, headers={"Content-Type": ctype})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 400
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(server + "/nope")
    assert e.value.code == 404


def test_external_ocr_provider():
    """Simule ML Kit (appli Android) : les mots lus suffisent à calibrer l'axe et lire l'en-tête."""
    series = zigzag_series([60, -30, 60, -30, 60])
    img = draw_mt5(series, header="XAUUSD,H4")
    words = [dict(w) for w in chart_factory.LAST_LABELS]
    calls = []
    reader.set_word_provider(lambda im: calls.append(1) or words)
    try:
        res = analyze_image(img)
    finally:
        reader.set_word_provider(None)
    assert res.calibrated and (res.symbol, res.timeframe) == ("XAUUSD", "H4")
    assert abs(res.candles[-1].close - series[-1][3]) < 0.0002
    assert len(calls) == 1  # un seul passage OCR par capture (cache)


def test_external_ocr_failure_is_harmless():
    reader.set_word_provider(lambda im: 1 / 0)
    try:
        res = analyze_image(draw_mt5(zigzag_series([60, -30, 60])))
    finally:
        reader.set_word_provider(None)
    assert not res.calibrated and res.candles


def test_desktop_selftest(tmp_path):
    img = tmp_path / "c.png"
    cv2.imwrite(str(img), draw_mt5(zigzag_series([60, -30, 60, -30, 60])))
    out = tmp_path / "r.json"
    assert desktop_main(["--selftest", str(img), str(out)]) == 0
    r = json.loads(out.read_text(encoding="utf-8"))
    assert r["candles"] > 20 and r["verdict"]
