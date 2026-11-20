"""Banc d'essai de la précision de Scan Graph Trade.

Deux mesures, reproductibles :

1. ``detection`` — précision de la lecture de la capture (image → OHLC) :
   on dessine des graphiques MT5 dont on connaît les vraies bougies, on les
   dégrade (compression JPEG, redimensionnement façon capture de téléphone,
   schémas de couleurs, zoom) et on compare ce que le moteur relit.

2. ``forecast`` — qualité du pronostic sur de vraies données de marché :
   on fait glisser une « capture » de N bougies sur l'historique, on demande
   le pronostic, puis on regarde ce qui s'est réellement passé ensuite
   (objectif 1 touché avant le stop ? le prix est-il allé dans le bon sens ?).

Usage :
    python tools/benchmark.py detection
    python tools/benchmark.py forecast data/*.csv  [--window 150 --step 5 --horizon 48]

Les CSV doivent contenir des colonnes open, high, low, close (n'importe quel
séparateur ; les colonnes de date sont ignorées).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from scan_graph_trade.analysis import analyze_technicals  # noqa: E402
from scan_graph_trade.models import AnalysisResult, Candle  # noqa: E402
from scan_graph_trade.patterns import detect_patterns  # noqa: E402


# --------------------------------------------------------------------------- données
def load_ohlc(path: str | Path) -> np.ndarray:
    """Lit un CSV d'historique et renvoie un tableau (n, 4) open/high/low/close."""
    rows = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        parts = [p.strip() for p in line.replace("\t", ",").replace(";", ",").split(",")]
        nums = []
        for p in parts:
            try:
                nums.append(float(p))
            except ValueError:
                nums.append(None)
        # premier quadruplet cohérent o/h/l/c
        for i in range(len(nums) - 3):
            q = nums[i : i + 4]
            if None in q:
                continue
            o, h, lo, c = q
            if h >= max(o, c) and lo <= min(o, c) and h > 0 and lo > 0:
                rows.append(q)
                break
    return np.array(rows, dtype=float)


def make_result(ohlc: np.ndarray, decimals: int = 5) -> AnalysisResult:
    candles = [Candle(i, 10 + 6 * i, float(o), float(h), float(lo), float(c), bool(c >= o))
               for i, (o, h, lo, c) in enumerate(ohlc)]
    return AnalysisResult(source="bench", candles=candles, patterns=detect_patterns(candles),
                          calibrated=True, price_decimals=decimals, axis=(-1.0, 0.0))


# --------------------------------------------------------------------------- pronostic
def simulate(plan: dict, future: np.ndarray) -> tuple[float, str]:
    """R obtenu sur l'objectif 1 (stop prioritaire si les deux sont touchés dans la même bougie)."""
    entry, stop, tp = plan["entry"], plan["stop_loss"], plan["take_profits"][0]
    sign = 1 if plan["direction"] == "ACHAT" else -1
    risk = abs(entry - stop)
    for _, h, lo, _c in future:
        hit_sl = lo <= stop if sign > 0 else h >= stop
        hit_tp = h >= tp if sign > 0 else lo <= tp
        if hit_sl:
            return -1.0, "stop"
        if hit_tp:
            return abs(tp - entry) / risk, "objectif"
    return sign * (future[-1, 3] - entry) / risk, "temps"


def first_touch(price: float, a: float, future: np.ndarray, k: float = 1.0) -> int:
    """+1 si le prix monte de k·ATR avant de baisser de k·ATR, -1 dans l'autre cas, 0 sinon."""
    for _, h, lo, _c in future:
        up, dn = h >= price + k * a, lo <= price - k * a
        if up and dn:
            return 0
        if up:
            return 1
        if dn:
            return -1
    return 0


def run_forecast(paths: list[str], window: int, step: int, horizon: int, verbose: bool = True) -> dict:
    trades, dir_hits, dir_total, briers, waits = [], 0, 0, [], 0
    by_file = {}
    for path in paths:
        data = load_ohlc(path)
        f_tr = []
        for end in range(window, len(data) - horizon, step):
            res = make_result(data[end - window : end])
            ta = analyze_technicals(res)
            if ta is None:
                continue
            fc = ta.forecast
            future = data[end : end + horizon]
            ft = first_touch(ta.last_price, ta.atr, future)
            if ft != 0:
                briers.append((fc.probability_up / 100 - (ft > 0)) ** 2)
            if fc.verdict == "ATTENDRE" or fc.plan is None:
                waits += 1
                continue
            r, _how = simulate(fc.plan.__dict__, future)
            f_tr.append(r)
            if ft != 0:
                dir_total += 1
                dir_hits += (ft > 0) == (fc.verdict == "ACHAT")
        trades += f_tr
        by_file[Path(path).name] = f_tr
    t = np.array(trades) if trades else np.zeros(1)
    out = {
        "signaux": len(trades),
        "attendre": waits,
        "taux_gain": float((t > 0).mean()) if trades else 0.0,
        "esperance_R": float(t.mean()) if trades else 0.0,
        "direction_ok": dir_hits / dir_total if dir_total else 0.0,
        "brier": float(np.mean(briers)) if briers else 0.0,
    }
    if verbose:
        for name, tr in by_file.items():
            a = np.array(tr) if tr else np.zeros(1)
            print(f"  {name:28s} signaux {len(tr):4d}  gagnants {(a > 0).mean():5.1%}  espérance {a.mean():+.3f} R")
        print(f"TOTAL : {out['signaux']} signaux, {out['attendre']} « attendre » | gagnants {out['taux_gain']:.1%} | "
              f"espérance {out['esperance_R']:+.3f} R/trade | direction juste {out['direction_ok']:.1%} | "
              f"Brier {out['brier']:.4f} (0,25 = hasard)")
    return out


# --------------------------------------------------------------------------- détection
def _degrade(img, kind: str):
    import cv2

    if kind == "net":
        return img
    if kind == "jpeg":
        _ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 60])
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if kind == "telephone":  # capture agrandie (écran haute densité) puis recompressée
        big = cv2.resize(img, None, fx=2.4, fy=2.4, interpolation=cv2.INTER_LINEAR)
        _ok, buf = cv2.imencode(".jpg", big, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if kind == "reduite":  # capture réduite (partage WhatsApp)
        small = cv2.resize(img, None, fx=0.7, fy=0.7, interpolation=cv2.INTER_AREA)
        _ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)
    raise ValueError(kind)


def run_detection(verbose: bool = True) -> dict:
    import chart_factory
    from chart_factory import draw_mt5, random_walk

    from scan_graph_trade.analyzer import analyze_image
    from scan_graph_trade.ocr import reader

    rows = []
    for scheme in ("green_on_black", "black_on_white", "colored"):
        for n in (60, 120, 200):
            for kind in ("net", "jpeg", "telephone", "reduite"):
                for seed in range(3):
                    series = random_walk(n, seed=seed + 10 * n, drift=0.05 * (seed - 1))
                    img = draw_mt5(series, width=1000, height=560, scheme=scheme)
                    labels = list(chart_factory.LAST_LABELS)
                    img = _degrade(img, kind)
                    scale = {"telephone": 2.4, "reduite": 0.7}.get(kind, 1.0)
                    words = [{k: (v * scale if k != "text" else v) for k, v in w.items()} for w in labels]
                    reader.set_word_provider(lambda _im, w=words: w)  # OCR simulé (comme ML Kit)
                    try:
                        res = analyze_image(img, technical=False)
                    finally:
                        reader.set_word_provider(None)
                    true = np.array(series)
                    got = res.candles
                    count_err = abs(len(got) - n)
                    rng = float(np.mean(true[:, 1] - true[:, 2]))
                    if len(got) == n and res.calibrated:
                        g = np.array([(c.open, c.high, c.low, c.close) for c in got])
                        ohlc_err = float(np.mean(np.abs(g - true)) / rng)
                        dir_ok = float(np.mean([(c.close >= c.open) == (t[3] >= t[0])
                                                for c, t in zip(got, true, strict=False)]))
                    else:
                        ohlc_err, dir_ok = np.nan, np.nan
                    rows.append((scheme, n, kind, count_err, ohlc_err, dir_ok, res.calibrated))
    if verbose:
        print(f"{'schéma':15s} {'n':>4s} {'image':10s} {'bougies OK':>10s} {'erreur OHLC':>12s} "
              f"{'sens OK':>8s} {'axe lu':>7s}")
        keys = sorted({(r[0], r[1], r[2]) for r in rows})
        for k in keys:
            rs = [r for r in rows if (r[0], r[1], r[2]) == k]
            ok = np.mean([r[3] == 0 for r in rs])
            err = np.nanmean([r[4] for r in rs]) if any(not np.isnan(r[4]) for r in rs) else np.nan
            d = np.nanmean([r[5] for r in rs]) if any(not np.isnan(r[5]) for r in rs) else np.nan
            cal = np.mean([r[6] for r in rs])
            print(f"{k[0]:15s} {k[1]:4d} {k[2]:10s} {ok:10.0%} {err:11.1%}  {d:7.1%} {cal:6.0%}")
    ok_all = float(np.mean([r[3] == 0 for r in rows]))
    errs = [r[4] for r in rows if not np.isnan(r[4])]
    dirs = [r[5] for r in rows if not np.isnan(r[5])]
    out = {"comptage_exact": ok_all, "erreur_ohlc": float(np.mean(errs)) if errs else float("nan"),
           "sens_ok": float(np.mean(dirs)) if dirs else float("nan"),
           "axe_lu": float(np.mean([r[6] for r in rows]))}
    if verbose:
        print(f"TOTAL : nombre de bougies exact {out['comptage_exact']:.0%} | erreur OHLC moyenne "
              f"{out['erreur_ohlc']:.1%} de la taille d'une bougie | couleur juste {out['sens_ok']:.1%} | "
              f"axe des prix lu {out['axe_lu']:.0%}")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("detection")
    f = sub.add_parser("forecast")
    f.add_argument("csv", nargs="+")
    f.add_argument("--window", type=int, default=150)
    f.add_argument("--step", type=int, default=5)
    f.add_argument("--horizon", type=int, default=48)
    a = p.parse_args()
    if a.cmd == "detection":
        run_detection()
    else:
        run_forecast(a.csv, a.window, a.step, a.horizon)


if __name__ == "__main__":
    main()
