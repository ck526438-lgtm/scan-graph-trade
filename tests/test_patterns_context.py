"""Figures en chandeliers sensibles au contexte."""
from scan_graph_trade.models import Candle
from scan_graph_trade.patterns import detect_patterns


def C(i, o, h, lo, c):
    return Candle(i, i * 10, float(o), float(h), float(lo), float(c), c > o)


def _down(n=5, start=120.0, step=4.0):
    return [C(i, start - i * step, start - i * step + 1, start - (i + 1) * step - 1, start - (i + 1) * step)
            for i in range(n)]


def _up(n=5, start=80.0, step=4.0):
    return [C(i, start + i * step, start + (i + 1) * step + 1, start + i * step - 1, start + (i + 1) * step)
            for i in range(n)]


def names(candles):
    return {(p.index, p.name) for p in detect_patterns(candles)}


def test_hanging_man_after_rally():
    cs = _up()
    top = cs[-1].close
    cs.append(C(5, top, top + 0.5, top - 9, top + 2.5))  # marteau au sommet → pendu
    assert (5, "hanging_man") in names(cs)


def test_morning_star():
    cs = _down()
    lo = cs[-1].close
    cs += [C(5, lo, lo + 1, lo - 7, lo - 6), C(6, lo - 6.5, lo - 5.5, lo - 8, lo - 7),
           C(7, lo - 6, lo + 1, lo - 6.5, lo)]
    assert (7, "morning_star") in names(cs)


def test_evening_star():
    cs = _up()
    hi = cs[-1].close
    cs += [C(5, hi, hi + 7, hi - 1, hi + 6), C(6, hi + 6.5, hi + 8, hi + 5.5, hi + 7),
           C(7, hi + 6, hi + 6.5, hi - 1, hi)]
    assert (7, "evening_star") in names(cs)


def test_piercing_line():
    cs = _down()
    p = cs[-1].close
    cs += [C(5, p, p + 0.5, p - 8.5, p - 8), C(6, p - 9, p - 2, p - 9.5, p - 2.5)]
    assert (6, "piercing_line") in names(cs)
