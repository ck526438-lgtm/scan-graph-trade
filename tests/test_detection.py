from scan_graph_trade.detection import CandleDetector


def test_detects_two_candles(synthetic_chart):
    candles = CandleDetector().detect(synthetic_chart)
    assert len(candles) == 2
    bear, bull = candles
    assert not bear.bullish and bull.bullish
    assert bull.high > bull.close > bull.open > bull.low
    assert bear.open > bear.close
