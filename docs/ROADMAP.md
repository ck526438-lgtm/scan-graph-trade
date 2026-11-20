# Feuille de route

## v0.1 — Fondations ✅
- [x] Détection des chandeliers par couleur
- [x] OCR + calibration de l'axe des prix
- [x] Figures en chandeliers de base
- [x] Export CSV / JSON + CLI `sgt`

## v0.2 — Robustesse ✅
- [x] Profils de couleurs MetaTrader 5 + détection automatique
- [x] Détection des thèmes clair/sombre (MT5)
- [x] Première capture réelle annotée dans `assets/samples/`

## v0.3 — Analyse experte & pronostic ✅
- [x] Indicateurs recalculés : EMA, RSI, MACD, ATR, ADX, Bollinger
- [x] Courbes (moyennes mobiles) lues directement sur la capture
- [x] Structure de marché : pivots, HH/HL/LH/LL, BOS, CHoCH, tendance
- [x] Supports / résistances, obliques de tendance
- [x] Double sommet/creux, tête-épaules, triangles, biseaux, canaux, rectangle
- [x] 19 figures en chandeliers avec contexte (pendu vs marteau, etc.)
- [x] Pronostic par confluence : verdict, confiance, plan de trade, scénarios
- [x] OCR de l'en-tête (symbole, unité de temps) et de l'axe (robuste)
- [x] Capture annotée, rapport Markdown
- [x] Interface web glisser-déposer + API REST (FastAPI)

## v0.4 — Applications ✅
- [x] Application Windows `.exe` autonome (fenêtre native, Tesseract embarqué)
- [x] Application Android `.apk` (Python embarqué, OCR ML Kit hors ligne, partage d'images)
- [x] Construction et publication automatiques (GitHub Actions → Releases)

## v0.5 — Plateformes
- [ ] Profils TradingView, MT4, cTrader, applis mobiles de broker
- [ ] Recadrage automatique de la zone graphique
- [ ] Jeu de captures réelles annotées (vérité terrain) pour mesurer la précision

## v1.0 — Produit
- [ ] Modèle IA de classification des figures (entraîné sur les captures annotées)
- [ ] Backtest du pronostic sur historique MT5 (taux de réussite par configuration)
- [ ] Notifications (Telegram / e-mail)
