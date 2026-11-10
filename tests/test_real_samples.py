"""Tests de non-régression sur de vraies captures MT5 (assets/samples/)."""
from pathlib import Path

import pytest

from scan_graph_trade.analyzer import analyze_file

SAMPLES = Path(__file__).resolve().parents[1] / "assets" / "samples"
EURUSD = SAMPLES / "mt5_eurusd_m5.png"


@pytest.mark.skipif(not EURUSD.exists(), reason="capture d'exemple absente")
def test_mt5_eurusd_m5_capture():
    res = analyze_file(EURUSD, use_ocr=False)
    assert res.profile == "mt5_green_on_black"
    assert 320 <= len(res.candles) <= 345  # ~332 bougies visibles
    bears = sum(not c.bullish for c in res.candles)
    assert 0.3 < bears / len(res.candles) < 0.5
    # la plus haute mèche (sommet du graphique) n'est pas tronquée par l'en-tête
    assert max(c.high for c in res.candles) >= res.candles[0].high and min(
        c.x for c in res.candles if c.high == max(k.high for k in res.candles)
    ) > 1300
    # aucune bougie dans la zone transparente à droite du graphique
    assert max(c.x for c in res.candles) < 1505
    assert len(res.patterns) < 0.3 * len(res.candles)
