"""Interface en ligne de commande : `sgt analyze capture.png`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .analyzer import analyze_file
from .detection import PROFILE_NAMES
from .export import export_csv, export_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sgt", description="Scan Graph Trade — analyse de captures de graphiques"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="Analyser une capture d'écran")
    a.add_argument("image", type=Path)
    a.add_argument("--profile", choices=PROFILE_NAMES, default="auto",
                   help="Schéma de couleurs (défaut : détection automatique)")
    a.add_argument("--last", type=int, default=20, metavar="N",
                   help="Afficher les figures des N dernières bougies (0 = toutes, défaut : 20)")
    a.add_argument("--no-ocr", action="store_true", help="Désactiver l'OCR (Tesseract)")
    a.add_argument("--json", type=Path, help="Exporter le résultat en JSON")
    a.add_argument("--csv", type=Path, help="Exporter les bougies en CSV")

    args = parser.parse_args(argv)
    if args.command == "analyze":
        res = analyze_file(args.image, use_ocr=not args.no_ocr, profile=args.profile)
        print(f"Source       : {res.source}")
        print(f"Profil       : {res.profile}")
        print(f"Bougies      : {len(res.candles)}  (axe calibré : {'oui' if res.calibrated else 'non'})")
        print(f"Figures      : {len(res.patterns)}")
        counts: dict[str, int] = {}
        for p in res.patterns:
            counts[p.name] = counts.get(p.name, 0) + 1
        if counts:
            print("  " + ", ".join(f"{n} ×{k}" for n, k in sorted(counts.items(), key=lambda kv: -kv[1])))
        start = len(res.candles) - args.last if args.last else 0
        shown = [p for p in res.patterns if p.index >= start]
        if args.last and shown:
            print(f"Sur les {args.last} dernières bougies :")
        for p in shown:
            print(f"  - #{p.index:<4} {p.name:<22} {p.direction:<8} {p.confidence:.0%}")
        if args.json:
            print(f"JSON  → {export_json(res, args.json)}")
        if args.csv:
            print(f"CSV   → {export_csv(res, args.csv)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
