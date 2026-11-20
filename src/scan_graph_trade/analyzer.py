"""Pipeline complet : image → OCR → bougies → figures → analyse technique → pronostic."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .detection import CandleDetector, DetectorConfig, auto_profile, get_profile
from .detection.overlays import detect_overlays
from .models import AnalysisResult
from .ocr import calibrate_price_axis, extract_text
from .ocr.reader import AxisCalibration, read_header, text_boxes
from .patterns import detect_patterns


def load_image(path: str | Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)  # gère les chemins non-ASCII (Windows)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Image illisible : {path}")
    return img


def decode_image(data: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Image illisible (formats acceptés : PNG, JPG, BMP, WEBP)")
    return img


def analyze_image(image: np.ndarray, source: str = "<memory>", use_ocr: bool = True,
                  config: DetectorConfig | None = None, profile: str = "auto",
                  axis: AxisCalibration | None = None, symbol: str | None = None,
                  timeframe: str | None = None, technical: bool = True) -> AnalysisResult:
    """Analyse une capture.

    - `profile` : "auto" (défaut) ou un nom de profil (ex. "mt5_green_on_black") ;
    - `axis` : calibration manuelle pixel → prix (prioritaire sur l'OCR) ;
    - `technical` : calcule l'analyse experte et le pronostic (``result.analysis``).
    """
    if config is None:
        config = auto_profile(image) if profile == "auto" else get_profile(profile)
    detector = CandleDetector(config)
    axis_x = CandleDetector.find_price_axis(image)

    calib = axis
    texts: list[str] = []
    boxes: list[tuple[int, int, int, int]] = []
    if use_ocr:
        boxes = text_boxes(image)
        if calib is None:
            calib = calibrate_price_axis(image, axis_x=axis_x)
        texts = extract_text(image)
        hs, ht, _ = read_header(image)
        symbol, timeframe = symbol or hs, timeframe or ht

    candles = detector.detect(image, to_price=calib, text_boxes=boxes)
    res = AnalysisResult(source=source, candles=candles, patterns=detect_patterns(candles),
                         texts=texts, calibrated=calib is not None, profile=config.name,
                         symbol=symbol, timeframe=timeframe, image_height=image.shape[0],
                         axis=(calib.slope, calib.intercept) if calib else None,
                         price_decimals=calib.decimals if calib else 0, candle_pitch=detector.pitch)
    if candles:
        res.overlays = detect_overlays(image, config, candles[0].x, candles[-1].x)
    if technical:
        from .analysis import analyze_technicals

        ta = analyze_technicals(res)
        res.analysis = ta.to_dict() if ta else None
    return res


def analyze_file(path: str | Path, **kwargs) -> AnalysisResult:
    return analyze_image(load_image(path), source=str(path), **kwargs)
