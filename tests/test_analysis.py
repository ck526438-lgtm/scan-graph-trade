"""Tests du moteur d'analyse experte : indicateurs, structure, figures, pronostic."""
import itertools

import numpy as np
import pytest
from chart_factory import draw_mt5, zigzag_series

from scan_graph_trade.analysis.chart_patterns import detect_chart_patterns
from scan_graph_trade.analysis.indicators import atr, ema, rsi, sma
from scan_graph_trade.analysis.levels import find_levels, nearest
from scan_graph_trade.analysis.structure import Swing, label_swings, structure_breaks, zigzag
from scan_graph_trade.analyzer import analyze_image
from scan_graph_trade.ocr.reader import available
from scan_graph_trade.patterns.candlestick import LABELS_FR


# --- indicateurs ---------------------------------------------------------
def test_indicators_basics():
    x = np.arange(1, 31, dtype=float)
    assert sma(x, 5)[4] == 3.0 and np.isnan(sma(x, 5)[3])
    e = ema(x, 10)
    assert np.isnan(e[8]) and e[-1] < x[-1]
    assert rsi(x)[-1] == 100.0
    assert rsi(x[::-1])[-1] < 1
    a = atr(x + 1, x - 1, x, 14)
    assert a[-1] == pytest.approx(2.0, rel=0.05)


# --- structure -------------------------------------------------------------
def _series(points, bars=6):
    """Série OHLC linéaire passant par `points` (prix)."""
    closes = []
    for p0, p1 in itertools.pairwise(points):
        closes += list(np.linspace(p0, p1, bars, endpoint=False))
    closes.append(points[-1])
    c = np.array(closes)
    return c + 0.2, c - 0.2, c


def test_zigzag_and_labels():
    h, lo, _c = _series([10, 20, 15, 25, 18, 30])
    sw = zigzag(h, lo, threshold=3)
    kinds = [s.kind for s in sw]
    assert kinds[:4] == ["low", "high", "low", "high"]
    assert [s.label for s in sw if s.label] == ["HL", "HH", "HL"][: len([s for s in sw if s.label])]


def test_structure_break_choch():
    sw = label_swings([Swing(0, 20, "high"), Swing(5, 10, "low"), Swing(10, 16, "high")])
    close = np.array([15] * 6 + [12] * 5 + [9, 14, 17])  # casse le creux (BOS baissier) puis 16 (CHoCH)
    br = structure_breaks(sw, close)
    assert [(b.kind, b.direction) for b in br] == [("BOS", "bearish"), ("CHoCH", "bullish")]


def test_levels_cluster_and_nearest():
    sw = [Swing(1, 100.0, "low"), Swing(5, 100.3, "low"), Swing(9, 110.0, "high"), Swing(12, 110.2, "high")]
    lv = find_levels(sw, current=105, atr_value=1.0, n_candles=15)
    assert len(lv) == 2
    assert nearest(lv, 105, "support").touches == 2
    assert nearest(lv, 105, "résistance").price == pytest.approx(110.1)


# --- figures chartistes ----------------------------------------------------
def test_double_top_confirmed():
    sw = label_swings([Swing(0, 90, "low"), Swing(10, 110, "high"), Swing(20, 100, "low"),
                       Swing(30, 110.2, "high")])
    close = np.concatenate([np.linspace(90, 110, 30), np.linspace(110, 97, 10)])
    found = {p.name: p for p in detect_chart_patterns(sw, close, atr=2.0)}
    dt = found["double_top"]
    assert dt.direction == "bearish" and dt.confirmed
    assert dt.neckline == 100 and dt.target == pytest.approx(100 - 10.1)


def test_head_and_shoulders():
    sw = label_swings([Swing(0, 90, "low"), Swing(8, 105, "high"), Swing(14, 98, "low"), Swing(20, 112, "high"),
                       Swing(26, 98, "low"), Swing(32, 105, "high")])
    close = np.concatenate([np.linspace(90, 105, 33), np.linspace(105, 99, 5)])
    names = {p.name for p in detect_chart_patterns(sw, close, atr=2.0)}
    assert "head_shoulders" in names


# --- pronostic de bout en bout -------------------------------------------
@pytest.mark.parametrize(("legs", "verdict"), [
    ([60, -30, 60, -30, 60, -30, 60], "ACHAT"),
    ([-60, 30, -60, 30, -60, 30, -50], "VENTE"),
])
def test_forecast_follows_trend(legs, verdict):
    res = analyze_image(draw_mt5(zigzag_series(legs)), use_ocr=False)
    fc = res.analysis["forecast"]
    assert fc["verdict"] == verdict
    plan = fc["plan"]
    sign = 1 if verdict == "ACHAT" else -1
    assert sign * (plan["entry"] - plan["stop_loss"]) > 0  # stop du bon côté
    assert all(sign * (tp - plan["entry"]) > 0 for tp in plan["take_profits"])
    assert all(rr >= 1.0 for rr in plan["risk_reward"])
    assert (fc["probability_up"] > 50) == (verdict == "ACHAT")
    assert res.analysis["trend"]["direction"] == ("haussière" if verdict == "ACHAT" else "baissière")


def test_flat_market_waits():
    res = analyze_image(draw_mt5(zigzag_series([20, -20] * 5, seed=7)), use_ocr=False)
    assert res.analysis["forecast"]["verdict"] == "ATTENDRE"
    assert res.analysis["forecast"]["plan"] is None


@pytest.mark.skipif(not available(), reason="Tesseract absent")
def test_real_prices_with_ocr():
    series = zigzag_series([60, -30, 60, -30, 60])
    res = analyze_image(draw_mt5(series, header="EURUSD,M15"))
    assert res.calibrated and res.symbol == "EURUSD" and res.timeframe == "M15"
    # dernière clôture reconstituée à moins d'un pip
    assert abs(res.candles[-1].close - series[-1][3]) < 0.0001
    assert res.fmt(res.candles[-1].close).startswith("1.1")


def test_all_patterns_have_french_label():
    from scan_graph_trade.patterns import candlestick

    names = {n for n in dir(candlestick)}
    assert "detect_patterns" in names
    for key, label in LABELS_FR.items():
        assert key and label
