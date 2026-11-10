import csv
import json

from scan_graph_trade.analyzer import analyze_image
from scan_graph_trade.export import export_csv, export_json
from scan_graph_trade.ocr.reader import fit_axis


def test_exports(synthetic_chart, tmp_path):
    res = analyze_image(synthetic_chart, use_ocr=False)
    data = json.loads(export_json(res, tmp_path / "r.json").read_text())
    assert len(data["candles"]) == 2
    rows = list(csv.DictReader(export_csv(res, tmp_path / "r.csv").open()))
    assert "bullish_engulfing" in rows[1]["patterns"]


def test_fit_axis():
    calib = fit_axis([(0, 1.1000), (100, 1.0900), (200, 1.0800)])
    assert calib is not None and abs(calib(50) - 1.0950) < 1e-9
    assert fit_axis([(0, 1.0)]) is None
