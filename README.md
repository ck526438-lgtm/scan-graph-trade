<p align="center">
  <img src="assets/logo/scan-graph-trade-logo.png" alt="Scan Graph Trade" width="520">
</p>

<h1 align="center">Scan Graph Trade</h1>

<p align="center">
  <b>Logiciel de trading intelligent qui scanne et analyse les captures d'écran de graphiques boursiers.</b><br>
  Chandeliers japonais · Structure de marché · Supports/résistances · Figures chartistes · Pronostic argumenté
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="OpenCV" src="https://img.shields.io/badge/OpenCV-4.x-orange">
  <img alt="Licence" src="https://img.shields.io/badge/licence-MIT-green">
  <img alt="Version" src="https://img.shields.io/badge/version-0.4.0-blue">
  <img alt="Windows" src="https://img.shields.io/badge/Windows-.exe-0078D6">
  <img alt="Android" src="https://img.shields.io/badge/Android-.apk-3DDC84">
</p>

---

## 📌 Présentation

**Scan Graph Trade** transforme une simple capture d'écran (TradingView, MetaTrader 4/5, cTrader, application mobile de broker…) en **données exploitables** :

1. il **détecte chaque chandelier** (ouverture, plus haut, plus bas, clôture) par vision par ordinateur ;
2. il **lit le texte** de l'image par OCR (symbole, unité de temps, graduations de l'axe des prix) pour convertir les pixels en **prix réels** ;
3. il **analyse le graphique comme un trader** : tendance, structure (HH/HL/LH/LL, BOS, CHoCH), supports et résistances, obliques, figures chartistes et en chandeliers, indicateurs recalculés (EMA, RSI, MACD, ATR, ADX, Bollinger) ;
4. il **donne un pronostic argumenté** : ACHAT / VENTE / ATTENDRE, score de confluence, confiance, probabilité de hausse, plan de trade (entrée, stop, objectifs, R:R), scénario principal et alternatif ;
5. il **annote la capture** et **exporte** le tout (rapport Markdown, JSON, CSV) — en ligne de commande ou via une **interface web** en glisser-déposer.

<p align="center">
  <img src="assets/samples/mt5_eurusd_m5_annotated.png" alt="Capture MT5 annotée par Scan Graph Trade" width="900">
</p>

> ⚠️ Scan Graph Trade est un **outil d'aide à l'analyse**. Il ne constitue pas un conseil en investissement. Le trading comporte un risque élevé de perte en capital.

## 📥 Télécharger les applications

Rendez-vous dans **[Releases](https://github.com/ck526438-lgtm/scan-graph-trade/releases/latest)** :

| Plateforme | Fichier | Installation |
|---|---|---|
| 🪟 **Windows 10 / 11** | `ScanGraphTrade.exe` | Double-cliquez, rien à installer (OCR Tesseract inclus). Si SmartScreen s'affiche : « Informations complémentaires » → « Exécuter quand même ». |
| 🤖 **Android 7+** | `ScanGraphTrade.apk` | Ouvrez le fichier sur le téléphone et autorisez l'installation depuis cette source. |

Les deux applications analysent **sur l'appareil, hors ligne** : aucune capture n'est envoyée sur Internet. Sur Android, l'OCR utilise Google ML Kit (modèle intégré) et vous pouvez **partager** une capture depuis MetaTrader 5 ou la galerie directement vers Scan Graph Trade.

## ✨ Fonctionnalités

| Module | Description | Statut |
|---|---|---|
| 🕯️ **Détection des chandeliers** | Segmentation HSV (OpenCV), bougies pleines ou creuses, extraction OHLC | ✅ |
| 🟢 **MetaTrader 5** | Profils Green On Black / Black On White / couleurs perso, détection automatique | ✅ |
| 🔤 **OCR** | Axe des prix (prix réels), en-tête (symbole + unité de temps), tolérant aux erreurs de lecture | ✅ |
| 📐 **Figures en chandeliers** | 19 figures **selon le contexte** : marteau / pendu, étoile filante / marteau inversé, avalements, harami, ligne pénétrante, nuage noir, pinces, étoiles du matin / du soir, 3 soldats / 3 corbeaux, marubozu, doji | ✅ |
| 🧭 **Structure de marché** | Pivots zigzag filtrés par l'ATR, HH/HL/LH/LL, BOS et CHoCH, tendance + force (ADX) | ✅ |
| 🧱 **Supports / résistances** | Zones par regroupement des pivots, nombre de contacts, force, obliques de tendance | ✅ |
| 📊 **Figures chartistes** | Double sommet/creux, tête-épaules (et inversée), triangles, biseaux, canaux, rectangle — avec ligne de cou et objectif | ✅ |
| 📈 **Indicateurs** | EMA 20/50/200, RSI, MACD, ATR, ADX, Bollinger recalculés + moyennes mobiles **lues sur la capture** | ✅ |
| 🎯 **Pronostic** | Confluence pondérée → ACHAT / VENTE / ATTENDRE, confiance, plan de trade, scénarios, avertissements | ✅ |
| 🖼️ **Annotation** | Zones, obliques, pivots, figures, entrée / SL / TP dessinés sur la capture | ✅ |
| 🖥️ **Interface web** | Glisser-déposer ou Ctrl+V d'une capture, rapport complet, exports | ✅ |
| 🪟 **Application Windows** | `ScanGraphTrade.exe` autonome, fenêtre native, Tesseract embarqué | ✅ |
| 🤖 **Application Android** | `ScanGraphTrade.apk` (Python embarqué via Chaquopy, OCR ML Kit, partage d'images) | ✅ |
| 💾 **Export** | Rapport Markdown, JSON complet, CSV des bougies | ✅ |
| 🧠 **Modèle IA** | Classification des figures par apprentissage automatique | 🔜 |
| 🔔 **Alertes** | Notifications Telegram / e-mail | 🔜 |

## 🗂️ Structure du projet

```
scan-graph-trade/
├── src/scan_graph_trade/
│   ├── analyzer.py          # Pipeline complet image → résultat
│   ├── cli.py               # Commande `sgt`
│   ├── models.py            # Candle, PatternMatch, AnalysisResult
│   ├── detection/           # Détection des chandeliers (OpenCV)
│   ├── ocr/                 # OCR + calibration de l'axe des prix
│   ├── patterns/            # Figures en chandeliers (avec contexte)
│   ├── analysis/            # Indicateurs, structure, niveaux, figures chartistes, pronostic
│   ├── report/              # Rapport texte/Markdown + annotation de la capture
│   ├── web/                 # Interface web (FastAPI ou serveur local sans dépendance)
│   ├── desktop.py           # Application de bureau (fenêtre native)
│   └── export/              # Export CSV / JSON
├── android/                 # Application Android (Kotlin + Chaquopy + ML Kit)
├── packaging/windows/       # Construction de l'exe (PyInstaller)
├── tests/                   # Tests unitaires (pytest, graphiques synthétiques)
├── docs/                    # Architecture, roadmap
├── assets/
│   ├── logo/                # Logo et icône
│   └── samples/             # Captures d'exemple
├── pyproject.toml
├── requirements.txt
└── requirements-dev.txt
```

## 🚀 Installation

### Prérequis

- **Python 3.10+**
- **Tesseract OCR** (facultatif mais recommandé, pour convertir les pixels en prix) :

| Système | Commande |
|---|---|
| Windows | Installer depuis [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) puis ajouter au `PATH` |
| Ubuntu / Debian / Kali | `sudo apt install tesseract-ocr` |
| macOS | `brew install tesseract` |
| Termux (Android) | `pkg install tesseract` |

### Installation du projet

```bash
git clone https://github.com/ck526438-lgtm/scan-graph-trade.git
cd scan-graph-trade

python -m venv .venv
# Windows : .venv\Scripts\activate
source .venv/bin/activate

pip install -e ".[web]"      # avec l'interface web
# ou : pip install -e ".[dev]" pour développer (tests, lint)
```

Ou, sans installation en mode paquet : `pip install -r requirements.txt`.

## 🧪 Utilisation

### En ligne de commande

```bash
sgt analyze capture.png                                   # rapport complet + pronostic
sgt analyze capture.png --annotate capture_annotee.png    # + capture annotée
sgt analyze capture.png --report analyse.md --json analyse.json --csv bougies.csv
sgt analyze capture.png --quiet                           # verdict seul (scripts, robots)
```

Exemple (capture `assets/samples/mt5_eurusd_m5.png`) :

```
SCAN GRAPH TRADE — EURUSD M5

=== PRONOSTIC ===
  • Verdict : VENTE  (biais baissier, score -51/100, confiance 76 %)
  • Probabilité estimée d'un prochain mouvement haussier : 21 %
  • Arguments : Tendance baissière (structure LL-LH-LL-LH, ADX 31); Cassure de structure (BOS)
    baissière; Prix en dessous de l'EMA 20, EMA 20 < EMA 50. À surveiller : Étoile du matin.
  • Scénario principal : poursuite de la baisse vers TP1 puis TP2, tant que le prix reste sous le stop.

=== PLAN DE TRADE ===
  • Entrée : dernière clôture · Stop : au-dessus du dernier sommet · Objectifs : R:R 1.5 et 2.5
...
```

Options utiles :

| Option | Rôle |
|---|---|
| `--profile` | Forcer un schéma de couleurs (sinon détection automatique) |
| `--axis "16=1.16540,684=1.15210"` | Calibration manuelle pixel → prix si l'axe n'est pas lisible |
| `--symbol XAUUSD --timeframe M5` | Forcer le symbole / l'unité de temps |
| `--no-ocr` | Désactiver Tesseract (niveaux exprimés en pixels) |

### Interface web

```bash
sgt serve            # puis ouvrir http://127.0.0.1:8000
```

Glissez une capture (ou collez-la avec **Ctrl+V**) : verdict, score, probabilité, plan de trade, scénarios, détail des facteurs, niveaux clés, figures et capture annotée, avec export Markdown / JSON / PNG.

<p align="center"><img src="docs/img/interface-web.png" alt="Interface web" width="820"></p>

## 🎯 Comment le pronostic est construit

Comme un analyste, le moteur ne se fie jamais à un seul signal. Chaque facteur vote entre −1 et +1, avec un poids :

| Facteur | Poids | Lecture |
|---|---|---|
| Tendance (structure + pente + EMA, modérée si ADX faible) | 2,0 | sens et force du marché |
| Figure chartiste confirmée / en formation | 2,0 / 1,0 | double sommet, tête-épaules, triangle… |
| Cassure de structure récente (BOS / CHoCH) | 1,5 | continuation ou retournement |
| Figures en chandeliers des 3 dernières bougies | 1,5 | renforcées ×1,5 si elles sont **sur une zone** |
| Moyennes mobiles (EMA 20/50) | 1,2 | position du prix, croisement |
| Emplacement (support / résistance à moins d'1 ATR) | 1,2 | acheter les supports, vendre les résistances |
| RSI, MACD | 1,0 | momentum, surachat / survente |
| Courbe tracée sur la capture, obliques, Bollinger | 0,6 – 0,8 | confirmation |

Le score (−100 à +100) donne **ACHAT** au-delà de +25, **VENTE** en dessous de −25, **ATTENDRE** sinon (seuil relevé à 35 en range). Le **stop** est placé derrière le dernier pivot ou la zone (entre 0,8 et 3 ATR), les **objectifs** sur la prochaine zone puis à 1,5 R et 2,5 R. Des **avertissements** signalent les situations à risque : peu de bougies, ADX faible, RSI extrême, R:R insuffisant, axe non calibré.

> Pour avoir de **vrais prix** (et non des pixels), laissez l'échelle des prix visible à droite de la capture : l'OCR la lit automatiquement.

### En Python

```python
from scan_graph_trade.analyzer import analyze_file
from scan_graph_trade.export import export_csv

from scan_graph_trade.report import render_report

result = analyze_file("capture.png")
fc = result.analysis["forecast"]
print(fc["verdict"], fc["score"], fc["confidence"], fc["plan"])
print(render_report(result))          # rapport complet en français

export_csv(result, "bougies.csv")
```

### 🟢 MetaTrader 5

Scan Graph Trade est optimisé pour les captures **MT5** (Fichier > Enregistrer sous image, ou capture d'écran classique). Le schéma de couleurs est **détecté automatiquement** :

| Schéma MT5 (clic droit > Propriétés > Couleurs) | Profil | Comment les bougies sont reconnues |
|---|---|---|
| **Green On Black** (défaut) | `mt5_green_on_black` | Contour vert ; haussière **creuse**, baissière **pleine blanche** |
| **Black On White** | `mt5_black_on_white` | Contour noir ; haussière **blanche**, baissière **noire** |
| Couleurs perso vert / rouge | `mt5_colored` | Couleur du corps |

```bash
sgt analyze capture_mt5.png                        # détection automatique
sgt analyze capture_mt5.png --profile mt5_green_on_black
```

Le logiciel ignore automatiquement l'en-tête (symbole, unité de temps), l'axe des prix, l'axe du temps, la grille et la ligne Bid. Il résiste aux captures compressées en JPEG (WhatsApp, Telegram).

**Conseils pour de meilleurs résultats :**
- capturez en **PNG** si possible et zoomez pour que les bougies fassent au moins 5 px de large ;
- masquez les indicateurs de même couleur que les bougies (ou analysez une capture sans indicateurs) ;
- gardez l'axe des prix visible : l'OCR s'en sert pour convertir les pixels en prix réels.

### Adapter les couleurs à votre plateforme

```python
from scan_graph_trade.detection import DetectorConfig
from scan_graph_trade.analyzer import analyze_file

config = DetectorConfig(
    bull_ranges=[((35, 60, 60), (100, 255, 255))],                          # vert
    bear_ranges=[((0, 80, 80), (25, 255, 255)), ((165, 80, 80), (179, 255, 255))],  # rouge
)
result = analyze_file("capture.png", config=config)
```

## 📏 Précision mesurée

La précision est mesurée par un banc d'essai reproductible, `tools/benchmark.py` :

```bash
python tools/benchmark.py detection            # lecture de la capture (image → bougies)
python tools/benchmark.py forecast data/*.csv  # pronostic rejoué sur de vraies données
```

**Lecture de la capture** (graphiques MT5 dont on connaît les vraies bougies, 3 thèmes, 60 à 200 bougies) :

| Capture | Nombre de bougies exact — avant | après |
|---|---|---|
| Nette (PNG) | 67 % | **100 %** |
| Compressée (JPEG) | 33 % | **96 %** |
| Capture de téléphone (haute densité + JPEG) | 11 % | **78 %** (±2 bougies : 100 %) |
| Réduite (partage WhatsApp) | 0 % | **33 %** |

Ce qui a changé : le pas entre les bougies est mesuré (MT5 les dessine à intervalle constant) et
sert à redécouper les bougies soudées par le flou ; le texte lu par l'OCR (en-tête, heures,
étiquettes) est effacé avant la détection ; la couleur haussière/baissière des bougies creuses
est lue à la luminosité du corps, insensible à la teinte ajoutée par la compression.

**Pronostic** : rejoué sur 15 394 bougies réelles (EURUSD M5/H1, XAUUSD M5/M15, une action en D1),
1 655 signaux : objectif 1 atteint avant le stop dans 44 % des cas, sens juste dans 51 %,
espérance ≈ 0 R. Un modèle ré-entraîné sur ces facteurs ne fait pas mieux hors échantillon.
L'application affiche donc des chiffres **calibrés** — la « réussite historique » est le taux
réellement observé, la probabilité de hausse reste proche de 50 % — plutôt qu'une confiance
artificielle. Le pronostic est une lecture technique structurée, pas une prédiction fiable.

## 🏗️ Construire les applications

Les deux applications sont construites automatiquement par GitHub Actions (`.github/workflows/apps.yml`) à chaque tag `v*` et publiées dans une Release :

```bash
git tag v0.4.0 && git push origin v0.4.0
```

En local :

```bash
# Windows (.exe) — sous Windows, avec Tesseract installé
pip install . pywebview pyinstaller
set TESSERACT_DIR=C:\Program Files\Tesseract-OCR
pyinstaller packaging/windows/ScanGraphTrade.spec --noconfirm      # → dist/ScanGraphTrade.exe

# Android (.apk) — JDK 17, SDK Android, Python 3.10 ; ou ouvrez le dossier android/ dans Android Studio
cd android && gradle assembleRelease                                 # → app/build/outputs/apk/release/
```

Signature Android stable (facultatif) : ajoutez les secrets `SGT_KEYSTORE_BASE64`, `SGT_KEYSTORE_PASSWORD`, `SGT_KEY_ALIAS`, `SGT_KEY_PASSWORD` au dépôt. Sans eux, l'APK est signé avec une clé de debug (installable, mais une mise à jour peut demander de désinstaller l'ancienne version).

Sans compiler : `pip install ".[desktop]"` puis `sgt-app` ouvre la même application de bureau.

## ✅ Tests

```bash
pytest            # tests unitaires
pytest --cov      # avec couverture
ruff check src    # qualité du code
```

## 🛣️ Feuille de route

Voir [`docs/ROADMAP.md`](docs/ROADMAP.md) et [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## 🤝 Contribuer

1. Forkez le dépôt
2. Créez une branche : `git checkout -b feature/ma-fonctionnalite`
3. Commitez : `git commit -m "feat: ajoute ..."`
4. Poussez et ouvrez une Pull Request

## 📄 Licence

Distribué sous licence **MIT** — voir [`LICENSE`](LICENSE).

---

<p align="center">Développé par <b>Christ</b> · <a href="https://github.com/ck526438-lgtm">@ck526438-lgtm</a></p>
