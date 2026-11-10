import pytest
from mt5_fixtures import SERIES, mt5_chart

from scan_graph_trade.analyzer import analyze_image
from scan_graph_trade.detection import CandleDetector, auto_profile, get_profile

EXPECTED_DIRECTION = [c > o for o, _, _, c in SERIES]


@pytest.mark.parametrize("scheme", ["green_on_black", "black_on_white"])
def test_mt5_candles_and_directions(scheme):
    img = mt5_chart(scheme)
    candles = CandleDetector(get_profile(f"mt5_{scheme}")).detect(img)
    assert [c.bullish for c in candles] == EXPECTED_DIRECTION
    # OHLC reconstitué au pixel près (le contour ajoute ±1 px)
    for c, (o, h, lo, cl) in zip(candles, SERIES, strict=True):
        assert abs(c.high - h) <= 1 and abs(c.low - lo) <= 1
        assert abs(c.open - o) <= 1 and abs(c.close - cl) <= 1


@pytest.mark.parametrize("scheme", ["green_on_black", "black_on_white"])
def test_mt5_auto_profile(scheme):
    assert auto_profile(mt5_chart(scheme)).name == f"mt5_{scheme}"


def test_mt5_patterns_end_to_end():
    res = analyze_image(mt5_chart("green_on_black"), use_ocr=False)
    names = {(p.index, p.name) for p in res.patterns}
    assert res.profile == "mt5_green_on_black"
    assert (2, "hammer") in names
    assert (4, "bullish_engulfing") in names


def test_colored_profile_detected(synthetic_chart):
    assert auto_profile(synthetic_chart).name == "mt5_colored"


@pytest.mark.parametrize("scheme", ["green_on_black", "black_on_white"])
@pytest.mark.parametrize("quality", [90, 50])
def test_mt5_survives_jpeg(scheme, quality):
    import cv2

    _, buf = cv2.imencode(".jpg", mt5_chart(scheme), [cv2.IMWRITE_JPEG_QUALITY, quality])
    res = analyze_image(cv2.imdecode(buf, cv2.IMREAD_COLOR), use_ocr=False)
    assert [c.bullish for c in res.candles] == EXPECTED_DIRECTION
