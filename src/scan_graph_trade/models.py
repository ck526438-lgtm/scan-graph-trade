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
class Overlay:
    """Courbe tracée sur la capture (moyenne mobile, Bollinger…) : points (x, y) en pixels."""

    color: str
    points: list[tuple[int, float]] = field(default_factory=list)

    def y_at(self, x: int) -> float | None:
        if not self.points:
            return None
        xs = [p[0] for p in self.points]
        if x < xs[0] - 3 or x > xs[-1] + 3:
            return None
        best = min(self.points, key=lambda p: abs(p[0] - x))
        return best[1]


@dataclass
class AnalysisResult:
    source: str
    candles: list[Candle] = field(default_factory=list)
    patterns: list[PatternMatch] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)
    calibrated: bool = False
    profile: str = "default"
    symbol: str | None = None
    timeframe: str | None = None
    image_height: int = 0
    axis: tuple[float, float] | None = None  # (pente, ordonnée) : prix = a·y + b
    price_decimals: int = 0
    overlays: list[Overlay] = field(default_factory=list)
    analysis: dict | None = None  # rapport d'analyse technique (voir analysis.engine)

    # --- conversions pixel <-> prix -------------------------------------
    def y_to_price(self, y: float) -> float:
        if self.axis:
            return self.axis[0] * y + self.axis[1]
        return float(self.image_height - y)

    def price_to_y(self, price: float) -> float:
        if self.axis:
            return (price - self.axis[1]) / self.axis[0]
        return float(self.image_height - price)

    def fmt(self, price: float | None) -> str:
        if price is None:
            return "—"
        return f"{price:.{self.price_decimals}f}" if self.calibrated else f"{price:.0f} px"

    def to_dict(self) -> dict:
        return asdict(self)
