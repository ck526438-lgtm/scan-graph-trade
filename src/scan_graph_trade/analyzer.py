"""Pipeline complet : image → OCR → bougies → figures."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .detection import CandleDetector, DetectorConfig
from .models import AnalysisResult
from .ocr import calibrate_price_axis, extract_text
from .patterns import detect_patterns


def load_image(path: str | Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)  # gère les chemins non-ASCII (Windows)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Image illisible : {path}")
    return img


def analyze_image(image: np.ndarray, source: str = "<memory>", use_ocr: bool = True,
                  config: DetectorConfig | None = None) -> AnalysisResult:
    calib = calibrate_price_axis(image) if use_ocr else None
    texts = extract_text(image) if use_ocr else []
    candles = CandleDetector(config).detect(image, to_price=calib)
    return AnalysisResult(source=source, candles=candles, patterns=detect_patterns(candles),
                          texts=texts, calibrated=calib is not None)


def analyze_file(path: str | Path, **kwargs) -> AnalysisResult:
    return analyze_image(load_image(path), source=str(path), **kwargs)
