"""Export des résultats d'analyse (CSV, JSON)."""
from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from ..models import AnalysisResult


def export_json(result: AnalysisResult, path: str | Path) -> Path:
    path = Path(path)
    path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def export_csv(result: AnalysisResult, path: str | Path) -> Path:
    """Une ligne par bougie, avec les figures détectées sur cette bougie."""
    path = Path(path)
    by_index: dict[int, list[str]] = {}
    for p in result.patterns:
        by_index.setdefault(p.index, []).append(p.name)
    fields = ["index", "x", "open", "high", "low", "close", "bullish", "patterns"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for c in result.candles:
            row = asdict(c)
            row["patterns"] = "|".join(by_index.get(c.index, []))
            w.writerow(row)
    return path
