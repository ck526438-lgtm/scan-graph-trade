"""Interface en ligne de commande : `sgt analyze capture.png`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .analyzer import analyze_file
from .export import export_csv, export_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sgt", description="Scan Graph Trade — analyse de captures de graphiques"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="Analyser une capture d'écran")
    a.add_argument("image", type=Path)
    a.add_argument("--no-ocr", action="store_true", help="Désactiver l'OCR (Tesseract)")
    a.add_argument("--json", type=Path, help="Exporter le résultat en JSON")
    a.add_argument("--csv", type=Path, help="Exporter les bougies en CSV")

    args = parser.parse_args(argv)
    if args.command == "analyze":
        res = analyze_file(args.image, use_ocr=not args.no_ocr)
        print(f"Source       : {res.source}")
        print(f"Bougies      : {len(res.candles)}  (axe calibré : {'oui' if res.calibrated else 'non'})")
        print(f"Figures      : {len(res.patterns)}")
        for p in res.patterns:
            print(f"  - #{p.index:<4} {p.name:<22} {p.direction:<8} {p.confidence:.0%}")
        if args.json:
            print(f"JSON  → {export_json(res, args.json)}")
        if args.csv:
            print(f"CSV   → {export_csv(res, args.csv)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
