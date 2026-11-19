# Architecture

```
 Capture d'écran (PNG/JPG)
          │
          ├──▶ OCR (Tesseract) ── en-tête : symbole, unité de temps
          │                   └─ axe des prix → calibration robuste  prix = a·y + b
          ▼
 ┌─────────────────────────────────────────────────┐
 │ Détection des chandeliers (OpenCV, masques HSV) │ → Candle(OHLC)
 │ Détection des courbes tracées (moyennes mob.)   │ → Overlay
 └─────────────────────────┬───────────────────────┘
                           ▼
 ┌─────────────────────────────────────────────────┐
 │ Figures en chandeliers (règles + contexte)      │ → PatternMatch
 └─────────────────────────┬───────────────────────┘
                           ▼
 ┌─────────────────────────────────────────────────┐
 │ Analyse experte (analysis/)                     │
 │  indicateurs · structure · niveaux · obliques   │
 │  figures chartistes · confluence → Forecast     │
 └─────────────────────────┬───────────────────────┘
                           ▼
     Rapport FR · capture annotée · JSON / CSV · API web
```

## Modules

- **`detection/candles.py`** — masques HSV, regroupement des colonnes en bougies, mèche → high/low, zone la plus large → corps.
- **`detection/overlays.py`** — courbes fines de couleur vive (moyennes mobiles) superposées aux bougies.
- **`ocr/reader.py`** — prétraitement (gris, ×3, inversion), lecture des graduations, régression robuste ; lecture tolérante de l'en-tête (`EVRUSD, NS` → `EURUSD M5`) ; calibration manuelle.
- **`patterns/candlestick.py`** — 19 figures sur 1, 2 et 3 bougies, seuils relatifs au corps moyen, contexte de tendance.
- **`analysis/indicators.py`** — EMA, SMA, RSI (Wilder), ATR, MACD, Bollinger, ADX.
- **`analysis/structure.py`** — zigzag filtré par l'ATR, étiquettes HH/HL/LH/LL, BOS/CHoCH, tendance.
- **`analysis/levels.py`** — zones de support/résistance par regroupement des pivots.
- **`analysis/chart_patterns.py`** — figures chartistes et obliques construites sur les pivots.
- **`analysis/engine.py`** — facteurs pondérés, score, verdict, plan de trade, scénarios, avertissements.
- **`report/`** — rapport texte / Markdown et annotation de l'image.
- **`web/`** — application FastAPI (`sgt serve`) et page HTML autonome.

## Limites connues

- L'échelle de prix est supposée linéaire (pas d'échelle logarithmique).
- Les indicateurs de même couleur que les bougies peuvent créer du bruit.
- Le pronostic est une lecture technique probabiliste, pas une certitude : il ne connaît ni l'actualité ni le carnet d'ordres.
