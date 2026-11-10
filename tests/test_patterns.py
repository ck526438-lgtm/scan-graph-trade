from scan_graph_trade.detection import CandleDetector
from scan_graph_trade.models import Candle
from scan_graph_trade.patterns import detect_patterns


def test_bullish_engulfing_on_synthetic_chart(synthetic_chart):
    names = {p.name for p in detect_patterns(CandleDetector().detect(synthetic_chart))}
    assert "bullish_engulfing" in names


def test_doji():
    c = Candle(0, 0, open=10.0, high=12.0, low=8.0, close=10.1, bullish=True)
    assert detect_patterns([c])[0].name == "doji"


def test_hammer():
    c = Candle(0, 0, open=10.0, high=10.6, low=7.0, close=10.5, bullish=True)
    assert detect_patterns([c])[0].name == "hammer"
