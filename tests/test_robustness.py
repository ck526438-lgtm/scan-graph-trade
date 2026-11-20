"""Robustesse de la lecture sur des captures dégradées (JPEG, téléphone, partage réduit)."""
import cv2
import numpy as np
import pytest
from chart_factory import draw_mt5, random_walk, zigzag_series

from scan_graph_trade.analysis.engine import PROB_SPREAD
from scan_graph_trade.analyzer import analyze_image
from scan_graph_trade.detection import CandleDetector, auto_profile


def _jpeg(img, q):
    return cv2.imdecode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])[1], cv2.IMREAD_COLOR)


def _phone(img):  # capture haute densité (agrandie) puis compressée
    return _jpeg(cv2.resize(img, None, fx=2.4, fy=2.4, interpolation=cv2.INTER_LINEAR), 80)


def _shared(img):  # capture réduite et recompressée (partage par messagerie)
    return _jpeg(cv2.resize(img, None, fx=0.7, fy=0.7, interpolation=cv2.INTER_AREA), 70)


@pytest.mark.parametrize("scheme", ["green_on_black", "black_on_white", "colored"])
@pytest.mark.parametrize("n", [60, 120, 200])
@pytest.mark.parametrize("degrade", [lambda i: i, lambda i: _jpeg(i, 60), _phone],
                         ids=["nette", "jpeg", "telephone"])
def test_candle_count_on_degraded_captures(scheme, n, degrade):
    series = random_walk(n, seed=10 * n, drift=-0.05)
    res = analyze_image(degrade(draw_mt5(series, width=1000, height=560, scheme=scheme)),
                        use_ocr=False, technical=False)
    assert abs(len(res.candles) - n) <= 2


@pytest.mark.parametrize("scheme", ["black_on_white", "colored"])
def test_shared_capture_moderate_zoom(scheme):
    series = random_walk(60, seed=600, drift=-0.05)
    res = analyze_image(_shared(draw_mt5(series, width=1000, height=560, scheme=scheme)),
                        use_ocr=False, technical=False)
    assert abs(len(res.candles) - 60) <= 1


def test_header_text_does_not_swallow_first_candles():
    """L'en-tête blanc de MT5 ne doit pas se coller aux premières bougies (thème vert sur noir)."""
    series = random_walk(60, seed=600)
    res = analyze_image(draw_mt5(series, width=1000, height=560), use_ocr=False, technical=False)
    assert len(res.candles) == 60
    assert res.candles[1].x - res.candles[0].x == pytest.approx(14, abs=1)


def test_bull_bear_colour_survives_jpeg():
    series = random_walk(120, seed=1200)
    res = analyze_image(_jpeg(draw_mt5(series, width=1000, height=560), 60), use_ocr=False, technical=False)
    true = [c > o for o, _, _, c in series]
    ok = np.mean([cd.bullish == t for cd, t in zip(res.candles, true, strict=False)])
    assert ok > 0.93


def test_pitch_is_measured():
    img = draw_mt5(random_walk(120, seed=3), width=1000, height=560)
    det = CandleDetector(auto_profile(img))
    det.detect(img)
    assert det.pitch == pytest.approx(7.0, abs=0.05)


def test_forecast_numbers_are_calibrated():
    res = analyze_image(draw_mt5(zigzag_series([60, -30, 60, -30, 60, -30, 60])), use_ocr=False)
    fc = res.analysis["forecast"]
    assert abs(fc["probability_up"] - 50) <= PROB_SPREAD
    assert 40 <= fc["confidence"] <= 60  # réussite historique mesurée, pas une formule à 90 %
    assert "historiques" in fc["reliability"]["note"]
