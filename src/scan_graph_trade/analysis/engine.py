"""Moteur d'analyse « expert » : confluence de tous les signaux → pronostic.

Chaque facteur (tendance, structure, moyennes mobiles, momentum, figures,
emplacement sur un support/une résistance…) donne un vote entre -1 et +1,
pondéré selon son importance. La somme donne un score de -100 à +100 :

- score ≥ +25 : biais **ACHAT**   · score ≤ -25 : biais **VENTE**
- entre les deux : **ATTENDRE** (pas d'avantage statistique clair)

Le plan de trade (entrée, stop, objectifs) s'appuie sur la structure :
stop derrière le dernier pivot / la zone, objectifs sur les prochaines zones
ou à défaut en multiples du risque (R).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from ..models import AnalysisResult, PatternMatch
from ..patterns.candlestick import LABELS_FR
from .chart_patterns import ChartPattern, TrendLine, detect_chart_patterns, trend_lines
from .indicators import atr, bollinger, ema, last, macd, ohlc, rsi
from .levels import Level, find_levels, nearest
from .structure import StructureBreak, Swing, TrendInfo, structure_breaks, trend_info, zigzag

BUY_THRESHOLD = 25
MIN_CANDLES = 30


@dataclass
class Factor:
    name: str
    vote: float  # -1 … +1
    weight: float
    detail: str

    @property
    def contribution(self) -> float:
        return self.vote * self.weight


@dataclass
class TradePlan:
    direction: str  # "ACHAT" | "VENTE"
    entry: float
    stop_loss: float
    take_profits: list[float]
    risk_reward: list[float]
    invalidation: str  # "au-dessus" / "en dessous" (du stop)


@dataclass
class Forecast:
    verdict: str  # "ACHAT" | "VENTE" | "ATTENDRE"
    bias: str  # "haussier" | "baissier" | "neutre"
    score: float  # -100 … +100
    confidence: float  # 0-100 %
    probability_up: float  # estimation 0-100 % que le prochain mouvement significatif soit haussier
    summary: str
    main_scenario: str
    alt_scenario: str
    plan: TradePlan | None
    warnings: list[str] = field(default_factory=list)


@dataclass
class TechnicalAnalysis:
    last_price: float
    atr: float
    trend: TrendInfo
    swings: list[Swing]
    breaks: list[StructureBreak]
    levels: list[Level]
    trendlines: list[TrendLine]
    chart_patterns: list[ChartPattern]
    indicators: dict
    factors: list[Factor]
    forecast: Forecast

    def to_dict(self) -> dict:
        d = asdict(self)
        d["factors"] = [{**asdict(f), "contribution": round(f.contribution, 3)} for f in self.factors]
        return d


def _clip(x: float) -> float:
    return float(np.clip(x, -1, 1))


def _dir_vote(direction: str) -> int:
    return 1 if direction == "bullish" else -1 if direction == "bearish" else 0


def analyze_technicals(res: AnalysisResult) -> TechnicalAnalysis | None:
    """Analyse complète d'un résultat de détection. None si trop peu de bougies."""
    candles = res.candles
    if len(candles) < 5:
        return None
    _, h, lo, c = ohlc(candles)
    n = len(c)
    atr_series = atr(h, lo, c, 14)
    a = last(atr_series) or float(np.mean(h - lo)) or 1.0
    price = float(c[-1])
    fmt = res.fmt

    swings = zigzag(h, lo, threshold=max(1.5 * a, 1e-9))
    breaks = structure_breaks(swings, c)
    trend = trend_info(h, lo, c, swings, a)
    levels = find_levels(swings, price, a, n)
    lines = trend_lines(swings, c, a)
    charts = detect_chart_patterns(swings, c, a)

    r = last(rsi(c, 14))
    m_line, m_sig, m_hist = macd(c)
    hist_now, hist_prev = last(m_hist), (float(m_hist[-2]) if n > 2 and not np.isnan(m_hist[-2]) else None)
    bb_lo, bb_mid, bb_up = bollinger(c, 20)
    e20, e50, e200 = last(ema(c, 20)), last(ema(c, 50)), last(ema(c, 200))
    indicators = {
        "rsi14": None if r is None else round(r, 1),
        "macd": None if last(m_line) is None else last(m_line),
        "macd_signal": last(m_sig),
        "macd_hist": hist_now,
        "ema20": e20, "ema50": e50, "ema200": e200,
        "bollinger_low": last(bb_lo), "bollinger_mid": last(bb_mid), "bollinger_up": last(bb_up),
        "atr14": a, "adx14": trend.adx,
    }

    factors: list[Factor] = []
    add = factors.append

    # 1. Tendance globale (structure + pente + EMA)
    tv = 1 if trend.direction == "haussière" else -1 if trend.direction == "baissière" else 0
    add(Factor("Tendance", tv * max(0.3, trend.strength), 2.0,
               f"Tendance {trend.direction} (force {trend.strength:.0%}, structure {trend.structure}"
               + (f", ADX {trend.adx:.0f}" if trend.adx is not None else "") + ")"))

    # 2. Dernière cassure de structure
    recent_breaks = [b for b in breaks if b.index >= n - max(10, n // 6)]
    if recent_breaks:
        b = recent_breaks[-1]
        v = _dir_vote(b.direction) * (1.0 if b.kind == "CHoCH" else 0.8)
        kind = "Changement de caractère (CHoCH)" if b.kind == "CHoCH" else "Cassure de structure (BOS)"
        add(Factor("Structure", v, 1.5,
                   f"{kind} {'haussier' if v > 0 else 'baissier'} au-delà de {fmt(b.level)}"))

    # 3. Moyennes mobiles
    if e20 is not None:
        v = 0.5 if price > e20 else -0.5
        detail = f"Prix {'au-dessus' if v > 0 else 'en dessous'} de l'EMA 20 ({fmt(e20)})"
        if e50 is not None:
            v += 0.5 if e20 > e50 else -0.5
            detail += f", EMA 20 {'>' if e20 > e50 else '<'} EMA 50"
        add(Factor("Moyennes mobiles", v, 1.2, detail))

    # 3 bis. Moyennes mobiles affichées sur la capture
    last_c = candles[-1]
    for ov in res.overlays:
        y = ov.y_at(last_c.x)
        if y is None:
            continue
        ov_price = res.y_to_price(y)
        v = 0.6 if price > ov_price else -0.6
        add(Factor(f"Courbe {ov.color} de la capture", v, 0.8,
                   f"Prix {'au-dessus' if v > 0 else 'en dessous'} de la courbe {ov.color} "
                   f"affichée ({fmt(ov_price)})"))

    # 4. Momentum RSI
    if r is not None:
        if r >= 75:
            v, d = -0.6, f"RSI {r:.0f} : surachat, risque de correction"
        elif r <= 25:
            v, d = 0.6, f"RSI {r:.0f} : survente, rebond possible"
        elif r >= 55:
            v, d = 0.5, f"RSI {r:.0f} : momentum acheteur"
        elif r <= 45:
            v, d = -0.5, f"RSI {r:.0f} : momentum vendeur"
        else:
            v, d = 0.0, f"RSI {r:.0f} : neutre"
        add(Factor("RSI", v, 1.0, d))

    # 5. MACD
    if hist_now is not None:
        v = 0.6 if hist_now > 0 else -0.6
        if hist_prev is not None:
            accel = hist_now - hist_prev
            v += 0.4 if accel > 0 else -0.4
            d = f"Histogramme MACD {'positif' if hist_now > 0 else 'négatif'} et " \
                f"{'en hausse' if accel > 0 else 'en baisse'}"
        else:
            d = f"Histogramme MACD {'positif' if hist_now > 0 else 'négatif'}"
        add(Factor("MACD", _clip(v), 1.0, d))

    # 6. Emplacement : proximité d'un support / d'une résistance
    sup, resi = nearest(levels, price, "support"), nearest(levels, price, "résistance")
    d_sup = (price - sup.price) / a if sup else None
    d_res = (resi.price - price) / a if resi else None
    if d_sup is not None and d_sup <= 1.0:
        add(Factor("Emplacement", 0.7 * (0.5 + sup.strength / 2), 1.2,
                   f"Prix sur un support ({fmt(sup.price)}, {sup.touches} contact(s))"))
    elif d_res is not None and d_res <= 1.0:
        add(Factor("Emplacement", -0.7 * (0.5 + resi.strength / 2), 1.2,
                   f"Prix sous une résistance ({fmt(resi.price)}, {resi.touches} contact(s))"))

    # 7. Bollinger : excès
    if last(bb_up) is not None:
        if price > last(bb_up):
            add(Factor("Bollinger", -0.4, 0.6, "Clôture au-dessus de la bande de Bollinger haute (excès)"))
        elif price < last(bb_lo):
            add(Factor("Bollinger", 0.4, 0.6, "Clôture sous la bande de Bollinger basse (excès)"))

    # 8. Figures en chandeliers récentes (3 dernières bougies), renforcées si sur une zone
    recent: list[PatternMatch] = [p for p in res.patterns if p.index >= n - 3 and p.direction != "neutral"]
    if recent:
        vote = 0.0
        names = []
        for p in recent:
            boost = 1.0
            if p.direction == "bullish" and d_sup is not None and d_sup <= 1.5:
                boost = 1.5
            if p.direction == "bearish" and d_res is not None and d_res <= 1.5:
                boost = 1.5
            vote += _dir_vote(p.direction) * p.confidence * boost * (1 - 0.2 * (n - 1 - p.index))
            names.append(LABELS_FR.get(p.name, p.name) + (" sur zone" if boost > 1 else ""))
        add(Factor("Chandeliers", _clip(vote), 1.5, "Figure(s) récente(s) : " + ", ".join(names)))

    # 9. Figures chartistes
    for cp in charts:
        if cp.direction == "neutral":
            continue
        w = 2.0 if cp.confirmed else 1.0
        state = "(cassure confirmée)" if cp.confirmed else "(en formation)"
        tgt = f", objectif {fmt(cp.target)}" if cp.target is not None else ""
        add(Factor(cp.label, _dir_vote(cp.direction) * cp.confidence, w, f"{cp.label} {state}{tgt}"))

    # 10. Lignes de tendance
    for tl in lines:
        val = tl.at(n - 1)
        if tl.kind == "support" and 0 <= (price - val) / a <= 1.0:
            add(Factor("Ligne de tendance", 0.5, 0.8, f"Prix sur l'oblique de support ({tl.touches} contacts)"))
        if tl.kind == "résistance" and 0 <= (val - price) / a <= 1.0:
            add(Factor("Ligne de tendance", -0.5, 0.8,
                       f"Prix sous l'oblique de résistance ({tl.touches} contacts)"))

    forecast = _forecast(res, factors, trend, price, a, swings, sup, resi, n, r)
    return TechnicalAnalysis(price, a, trend, swings, breaks, levels, lines, charts, indicators,
                             factors, forecast)


def _forecast(res, factors, trend, price, a, swings, sup, resi, n, r) -> Forecast:
    fmt = res.fmt
    total_w = sum(f.weight for f in factors) or 1.0
    raw = sum(f.contribution for f in factors) / total_w  # -1 … +1
    score = round(100 * raw, 1)
    pos = sum(f.weight for f in factors if f.vote > 0.1)
    neg = sum(f.weight for f in factors if f.vote < -0.1)
    agreement = max(pos, neg) / (pos + neg) if pos + neg else 0.0

    warnings: list[str] = []
    quality = 1.0
    if n < MIN_CANDLES:
        quality *= 0.6
        warnings.append(f"Peu de bougies visibles ({n}) : dézoomez pour une analyse plus fiable.")
    if not res.calibrated:
        warnings.append("Axe des prix non lu : les niveaux sont en pixels. Laissez l'échelle des prix "
                        "visible (ou utilisez la calibration manuelle) pour obtenir de vrais prix.")
    if trend.adx is not None and trend.adx < 18:
        warnings.append(f"ADX faible ({trend.adx:.0f}) : marché sans direction, signaux moins fiables.")
    if r is not None and (r > 75 or r < 25):
        warnings.append("RSI extrême : éviter d'entrer en retard dans le sens du mouvement.")

    confidence = round(min(95.0, abs(score) * 1.4 * (0.5 + agreement / 2) * quality + 10), 1)
    prob_up = round(float(50 + 40 * np.tanh(raw * 1.8)), 1)

    # en range sans figure confirmée, on exige davantage de confluence
    confirmed = any(f.weight >= 2.0 and f.name not in ("Tendance",) for f in factors)
    threshold = BUY_THRESHOLD if trend.direction != "range" or confirmed else BUY_THRESHOLD + 10
    if trend.direction == "range" and not confirmed:
        warnings.append("Pas de tendance claire : seuil de décision relevé, privilégier les cassures.")
    if score >= threshold:
        verdict, bias = "ACHAT", "haussier"
    elif score <= -threshold:
        verdict, bias = "VENTE", "baissier"
    else:
        verdict, bias = "ATTENDRE", "haussier" if score > 8 else "baissier" if score < -8 else "neutre"

    plan = None
    lows = [s for s in swings if s.kind == "low"]
    highs = [s for s in swings if s.kind == "high"]
    if verdict == "ACHAT":
        anchor = min([x for x in [sup.low if sup and price - sup.price < 3 * a else None,
                                  lows[-1].price if lows and lows[-1].price < price else None] if x is not None],
                     default=price - 1.5 * a)
        stop = float(np.clip(anchor - 0.2 * a, price - 3 * a, price - 0.8 * a))
        plan = _plan("ACHAT", price, stop, resi, a)
    elif verdict == "VENTE":
        anchor = max([x for x in [resi.high if resi and resi.price - price < 3 * a else None,
                                  highs[-1].price if highs and highs[-1].price > price else None]
                      if x is not None], default=price + 1.5 * a)
        stop = float(np.clip(anchor + 0.2 * a, price + 0.8 * a, price + 3 * a))
        plan = _plan("VENTE", price, stop, sup, a)

    if plan and plan.risk_reward and plan.risk_reward[0] < 1.0:
        warnings.append(f"Premier objectif proche (R:R {plan.risk_reward[0]:.1f}) : attendre un meilleur "
                        f"prix d'entrée ou viser l'objectif 2.")

    sign = 1 if score >= 0 else -1
    pro = sorted([f for f in factors if f.vote * sign > 0.05], key=lambda f: -abs(f.contribution))[:3]
    con = sorted([f for f in factors if f.vote * sign < -0.05], key=lambda f: -abs(f.contribution))[:2]
    reasons = "Arguments : " + "; ".join(f.detail for f in pro) if pro else "Aucun argument dominant"
    if con:
        reasons += ". À surveiller : " + "; ".join(f.detail for f in con)
    sym = " ".join(x for x in (res.symbol, res.timeframe) if x) or "Le marché"
    if verdict == "ATTENDRE":
        summary = f"{sym} : pas de signal net (score {score:+.0f}/100), biais {bias}. {reasons}."
        up = fmt(resi.price) if resi else fmt(price + a)
        dn = fmt(sup.price) if sup else fmt(price - a)
        main = (f"Range probable entre {dn} et {up}. Achat seulement sur cassure et clôture au-dessus de {up}, "
                f"vente sur cassure sous {dn}.")
        alt = "Si la volatilité se contracte encore, se préparer à une cassure franche (souvent dans le sens " \
              f"de la tendance de fond : {trend.direction})."
    else:
        summary = f"{sym} : biais {bias} — {verdict} (score {score:+.0f}/100, confiance {confidence:.0f} %). " \
                  f"{reasons}."
        tps = " puis ".join(fmt(t) for t in plan.take_profits)
        move = "de la hausse" if bias == "haussier" else "de la baisse"
        main = (f"Scénario principal : poursuite {move} vers {tps}, "
                f"tant que le prix reste {plan.invalidation} de {fmt(plan.stop_loss)}.")
        other = "baissier" if bias == "haussier" else "haussier"
        alt = f"Scénario alternatif : si {fmt(plan.stop_loss)} est franchi, le scénario est invalidé et un " \
              f"mouvement {other} devient probable."
    return Forecast(verdict, bias, score, confidence, prob_up, summary, main, alt, plan, warnings)


def _plan(direction: str, entry: float, stop: float, level: Level | None, a: float) -> TradePlan:
    risk = abs(entry - stop)
    sign = 1 if direction == "ACHAT" else -1
    tps: list[float] = []
    if level is not None:
        edge = level.low if sign > 0 else level.high  # on sort juste avant la zone
        if sign * (edge - entry) > 0.5 * risk:
            tps.append(edge)
    for mult in (1.5, 2.5):
        t = entry + sign * mult * risk
        if not tps or sign * (t - tps[-1]) > 0.5 * risk:
            tps.append(t)
        if len(tps) == 2:
            break
    rr = [round(abs(t - entry) / risk, 2) for t in tps] if risk else []
    inval = "au-dessus" if sign > 0 else "en dessous"
    return TradePlan(direction, entry, stop, tps, rr, inval)
