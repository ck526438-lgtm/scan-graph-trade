"""Interface en ligne de commande : `sgt analyze capture.png`, `sgt serve`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .analyzer import analyze_file, load_image
from .detection import PROFILE_NAMES
from .export import export_csv, export_json
from .ocr.reader import manual_axis
from .report import annotate, render_report


def _write_image(path: Path, img) -> Path:
    import cv2

    ok, buf = cv2.imencode(path.suffix or ".png", img)
    if not ok:
        raise ValueError(f"Format d'image non pris en charge : {path.suffix}")
    buf.tofile(str(path))  # gère les chemins non-ASCII (Windows)
    return path


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # accents dans la console Windows
        except (ValueError, OSError):
            pass
    parser = argparse.ArgumentParser(
        prog="sgt", description="Scan Graph Trade — analyse experte de captures de graphiques"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="Analyser une capture d'écran et donner un pronostic")
    a.add_argument("image", type=Path)
    a.add_argument("--profile", choices=PROFILE_NAMES, default="auto",
                   help="Schéma de couleurs (défaut : détection automatique)")
    a.add_argument("--no-ocr", action="store_true", help="Désactiver l'OCR (Tesseract)")
    a.add_argument("--axis", metavar="Y1=PRIX1,Y2=PRIX2",
                   help="Calibration manuelle de l'axe des prix (ex. \"16=1.16540,684=1.15210\")")
    a.add_argument("--symbol", help="Forcer le symbole (ex. XAUUSD)")
    a.add_argument("--timeframe", help="Forcer l'unité de temps (ex. M5)")
    a.add_argument("--annotate", type=Path, metavar="IMAGE",
                   help="Enregistrer la capture annotée (zones, figures, plan de trade)")
    a.add_argument("--report", type=Path, metavar="FICHIER.md", help="Enregistrer le rapport en Markdown")
    a.add_argument("--json", type=Path, help="Exporter le résultat complet en JSON")
    a.add_argument("--csv", type=Path, help="Exporter les bougies en CSV")
    a.add_argument("--quiet", action="store_true", help="N'afficher que le verdict")

    s = sub.add_parser("serve", help="Lancer l'interface web (glisser-déposer des captures)")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)
    if args.command == "serve":
        from .web import run

        run(args.host, args.port)
        return 0

    if args.command == "analyze":
        axis = manual_axis(args.axis) if args.axis else None
        res = analyze_file(args.image, use_ocr=not args.no_ocr, profile=args.profile, axis=axis,
                           symbol=args.symbol, timeframe=args.timeframe)
        if args.quiet and res.analysis:
            fc = res.analysis["forecast"]
            print(f"{fc['verdict']} score={fc['score']:+.0f} confiance={fc['confidence']:.0f}%")
        else:
            print(render_report(res))
        if args.annotate:
            print(f"Image annotée → {_write_image(args.annotate, annotate(load_image(args.image), res))}")
        if args.report:
            args.report.write_text(render_report(res, markdown=True), encoding="utf-8")
            print(f"Rapport      → {args.report}")
        if args.json:
            print(f"JSON         → {export_json(res, args.json)}")
        if args.csv:
            print(f"CSV          → {export_csv(res, args.csv)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
