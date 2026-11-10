"""Structures de données partagées par tout le pipeline."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Candle:
    """Une bougie détectée, en coordonnées pixel (y=0 en haut de l'image).

    Les valeurs open/high/low/close sont exprimées en prix si l'axe a été
    calibré par l'OCR, sinon en « prix pixel » (hauteur inversée).
    """

    index: int
    x: int
    open: float
    high: float
    low: float
    close: float
    bullish: bool

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low


@dataclass(frozen=True)
class PatternMatch:
    name: str
    index: int  # index de la dernière bougie du motif
    direction: str  # "bullish" | "bearish" | "neutral"
    confidence: float


@dataclass
class AnalysisResult:
    source: str
    candles: list[Candle] = field(default_factory=list)
    patterns: list[PatternMatch] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)
    calibrated: bool = False

    def to_dict(self) -> dict:
        return asdict(self)
