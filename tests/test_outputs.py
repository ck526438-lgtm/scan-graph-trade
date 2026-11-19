"""OCR d'en-tête, rapport, annotation, CLI et API web."""
from pathlib import Path

import pytest
from chart_factory import draw_mt5, zigzag_series

from scan_graph_trade.analyzer import analyze_image
from scan_graph_trade.cli import main
from scan_graph_trade.ocr.reader import manual_axis, parse_header
from scan_graph_trade.report import annotate, render_report

SAMPLE = Path(__file__).resolve().parents[1] / "assets" / "samples" / "mt5_eurusd_m5.png"


@pytest.mark.parametrize(("text", "expected"), [
    ("ES bed EVRUSD, NS: Euro vs US Dollar", ("EURUSD", "M5")),  # lecture OCR réelle d'une capture MT5
    ("XAUUSD,H1: Gold Spot", ("XAUUSD", "H1")),
    ("GBPJPY, M15", ("GBPJPY", "M15")),
    ("rien d'utile", (None, None)),
])
def test_parse_header(text, expected):
    assert parse_header(text) == expected


def test_manual_axis():
    calib = manual_axis("100=1.1000,300=1.0900")
    assert calib(200) == pytest.approx(1.0950) and calib.decimals == 4
    with pytest.raises(ValueError):
        manual_axis("100=1.0,300=1.1")  # pente positive : impossible


def test_report_and_annotation():
    img = draw_mt5(zigzag_series([60, -30, 60, -30, 60]))
    res = analyze_image(img, use_ocr=False, symbol="EURUSD", timeframe="M5")
    txt = render_report(res)
    assert "PRONOSTIC" in txt and "PLAN DE TRADE" in txt and "EURUSD M5" in txt
    md = render_report(res, markdown=True)
    assert md.startswith("# Scan Graph Trade") and "## NIVEAUX CLÉS" in md
    out = annotate(img, res)
    assert out.shape == img.shape and (out != img).any()


def test_overlay_detected_on_real_capture():
    if not SAMPLE.exists():
        pytest.skip("capture absente")
    res = analyze_image(__import__("cv2").imread(str(SAMPLE)), use_ocr=False)
    assert [o.color for o in res.overlays] == ["rouge"]  # moyenne mobile rouge de la capture
    assert any("courbe rouge" in f["detail"] for f in res.analysis["factors"])


def test_cli_outputs(tmp_path, capsys):
    if not SAMPLE.exists():
        pytest.skip("capture absente")
    ann, rep, js = tmp_path / "a.png", tmp_path / "r.md", tmp_path / "r.json"
    assert main(["analyze", str(SAMPLE), "--no-ocr", "--annotate", str(ann), "--report", str(rep),
                 "--json", str(js)]) == 0
    assert "Verdict" in capsys.readouterr().out
    assert ann.stat().st_size > 10_000 and rep.read_text(encoding="utf-8").startswith("#")
    assert '"forecast"' in js.read_text(encoding="utf-8")


def test_web_api():
    pytest.importorskip("fastapi")
    pytest.importorskip("multipart")
    from fastapi.testclient import TestClient

    from scan_graph_trade.web import create_app

    client = TestClient(create_app())
    assert "Scan Graph" in client.get("/").text
    import cv2

    _ok, buf = cv2.imencode(".png", draw_mt5(zigzag_series([60, -30, 60, -30, 60])))
    r = client.post("/api/analyze", files={"file": ("c.png", buf.tobytes(), "image/png")},
                    data={"symbol": "eurusd"})
    assert r.status_code == 200
    d = r.json()
    assert d["symbol"] == "EURUSD" and d["analysis"]["forecast"]["verdict"] in ("ACHAT", "VENTE", "ATTENDRE")
    assert d["annotated"].startswith("data:image/png;base64,")
    assert client.post("/api/analyze", files={"file": ("x.png", b"nope", "image/png")}).status_code == 400
