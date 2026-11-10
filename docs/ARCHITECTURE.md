# Architecture

```
 Capture d'écran (PNG/JPG)
          │
          ▼
 ┌─────────────────┐     ┌──────────────────────────┐
 │  OCR (Tesseract)│────▶│ Calibration axe des prix │  prix = a·y + b
 └─────────────────┘     └────────────┬─────────────┘
          │                           │
          ▼                           ▼
 ┌─────────────────────────────────────────────────┐
 │ Détection des chandeliers (OpenCV, masques HSV) │ → Candle(OHLC)
 └─────────────────────────┬───────────────────────┘
                           ▼
 ┌─────────────────────────────────────────────────┐
 │ Reconnaissance des figures (règles → IA)        │ → PatternMatch
 └─────────────────────────┬───────────────────────┘
                           ▼
                 Export CSV / JSON
```

## Modules

- **`detection/candles.py`** — masques HSV haussier/baissier, regroupement des colonnes en bougies, mèche → high/low, zone la plus large → corps.
- **`ocr/reader.py`** — lecture des graduations de la bande droite, régression linéaire pixel→prix (pente négative obligatoire).
- **`patterns/candlestick.py`** — règles classiques sur 1, 2 et 3 bougies, avec niveau de confiance.
- **`export/exporters.py`** — sérialisation CSV/JSON.
- **`analyzer.py`** — orchestre le pipeline ; `cli.py` expose la commande `sgt`.

## Limites connues (v0.1)

- Les bougies doivent être colorées (pas de thème monochrome creux/plein).
- Les indicateurs superposés de la même couleur que les bougies peuvent créer du bruit.
- La calibration OCR suppose une échelle de prix linéaire.
