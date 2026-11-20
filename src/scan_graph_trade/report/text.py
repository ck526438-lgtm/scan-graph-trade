"""Rapport d'analyse lisible (terminal / Markdown), en français."""
from __future__ import annotations

from ..models import AnalysisResult
from ..patterns.candlestick import LABELS_FR

DISCLAIMER = ("⚠️ Analyse automatique à but informatif, pas un conseil en investissement. "
              "Le trading comporte un risque élevé de perte en capital : utilisez toujours un stop.")


def render_report(res: AnalysisResult, markdown: bool = False) -> str:
    ta = res.analysis
    H = (lambda t: f"\n## {t}\n") if markdown else (lambda t: f"\n=== {t} ===")
    B = "- " if markdown else "  • "
    lines: list[str] = []
    title = " ".join(x for x in (res.symbol, res.timeframe) if x) or res.source
    lines.append(f"# Scan Graph Trade — {title}" if markdown else f"SCAN GRAPH TRADE — {title}")
    lines.append(f"{B}Capture : {res.source}")
    lines.append(f"{B}Profil : {res.profile} · {len(res.candles)} bougies · "
                 f"axe des prix {'calibré' if res.calibrated else 'non calibré (pixels)'}")
    if not ta:
        lines.append(f"{B}Pas assez de bougies détectées pour une analyse technique.")
        return "\n".join(lines)

    fc = ta["forecast"]
    lines.append(H("PRONOSTIC"))
    lines.append(f"{B}Verdict : {fc['verdict']}  (biais {fc['bias']}, score {fc['score']:+.0f}/100, "
                 f"réussite historique {fc['confidence']:.0f} %)")
    lines.append(f"{B}Probabilité estimée d'un prochain mouvement haussier : {fc['probability_up']:.0f} %")
    if fc.get("reliability", {}).get("note"):
        lines.append(f"{B}Fiabilité mesurée : {fc['reliability']['note']}")
    lines.append(f"{B}{fc['summary']}")
    lines.append(f"{B}{fc['main_scenario']}")
    lines.append(f"{B}{fc['alt_scenario']}")
    if fc["plan"]:
        p = fc["plan"]
        lines.append(H("PLAN DE TRADE"))
        lines.append(f"{B}Sens : {p['direction']}")
        lines.append(f"{B}Entrée : {res.fmt(p['entry'])} (dernière clôture)")
        lines.append(f"{B}Stop loss : {res.fmt(p['stop_loss'])}")
        for k, (tp, rr) in enumerate(zip(p["take_profits"], p["risk_reward"], strict=False), 1):
            lines.append(f"{B}Objectif {k} : {res.fmt(tp)}  (R:R {rr:.1f})")

    t = ta["trend"]
    lines.append(H("TENDANCE & STRUCTURE"))
    lines.append(f"{B}Tendance {t['direction']} — force {t['strength']:.0%}, structure {t['structure']}"
                 + (f", ADX {t['adx']:.0f}" if t["adx"] is not None else ""))
    for b in ta["breaks"][-3:]:
        kind = "CHoCH" if b["kind"] == "CHoCH" else "BOS"
        sens = "haussier" if b["direction"] == "bullish" else "baissier"
        lines.append(f"{B}{kind} {sens} à la bougie #{b['index']} (niveau {res.fmt(b['level'])})")

    lines.append(H("NIVEAUX CLÉS"))
    price = ta["last_price"]
    for lv in sorted(ta["levels"], key=lambda lv: -lv["price"]):
        mark = "◀ prix" if lv["low"] <= price <= lv["high"] else ""
        lines.append(f"{B}{lv['kind'].capitalize():<11} {res.fmt(lv['price']):>12}  "
                     f"{lv['touches']} contact(s), force {lv['strength']:.0%} {mark}")
    lines.append(f"{B}Prix actuel : {res.fmt(price)} · ATR(14) : {res.fmt(ta['atr'])}")
    for tl in ta["trendlines"]:
        lines.append(f"{B}Oblique de {tl['kind']} ({tl['touches']} contacts)")

    if ta["chart_patterns"]:
        lines.append(H("FIGURES CHARTISTES"))
        for cp in ta["chart_patterns"]:
            state = "cassure confirmée" if cp["confirmed"] else "en formation"
            tgt = f", objectif {res.fmt(cp['target'])}" if cp["target"] is not None else ""
            lines.append(f"{B}{cp['label']} — {state}, confiance {cp['confidence']:.0%}{tgt}")

    recent = [p for p in res.patterns if p.index >= len(res.candles) - 10]
    if recent:
        lines.append(H("CHANDELIERS (10 dernières bougies)"))
        for p in recent:
            lines.append(f"{B}#{p.index} {LABELS_FR.get(p.name, p.name)} ({p.direction}, {p.confidence:.0%})")

    ind = ta["indicators"]
    lines.append(H("INDICATEURS (recalculés)"))
    parts = []
    if ind["rsi14"] is not None:
        parts.append(f"RSI14 {ind['rsi14']:.0f}")
    for k, lbl in (("ema20", "EMA20"), ("ema50", "EMA50"), ("ema200", "EMA200")):
        if ind[k] is not None:
            parts.append(f"{lbl} {res.fmt(ind[k])}")
    if ind["macd_hist"] is not None:
        parts.append(f"MACD hist {'+' if ind['macd_hist'] > 0 else '-'}")
    lines.append(B + " · ".join(parts))
    for ov in res.overlays:
        lines.append(f"{B}Courbe {ov.color} détectée sur la capture (moyenne mobile probable)")

    lines.append(H("DÉTAIL DES FACTEURS"))
    for f in sorted(ta["factors"], key=lambda f: -abs(f["contribution"])):
        sign = "▲" if f["vote"] > 0.05 else "▼" if f["vote"] < -0.05 else "•"
        lines.append(f"{B}{sign} {f['contribution']:+.2f}  {f['detail']}")

    if fc["warnings"]:
        lines.append(H("AVERTISSEMENTS"))
        for wmsg in fc["warnings"]:
            lines.append(f"{B}{wmsg}")
    lines.append("")
    lines.append(DISCLAIMER)
    return "\n".join(lines)
