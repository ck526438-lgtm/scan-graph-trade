import cv2
import numpy as np
import pytest

GREEN = (80, 200, 40)   # BGR
RED = (50, 50, 230)


def draw_candle(img, x, top, body_top, body_bottom, bottom, color, w=7):
    cv2.line(img, (x, top), (x, bottom), color, 1)
    cv2.rectangle(img, (x - w // 2, body_top), (x + w // 2, body_bottom), color, -1)


@pytest.fixture
def synthetic_chart():
    """Graphique synthétique : 1 baissière puis 1 haussière englobante."""
    img = np.full((300, 200, 3), 255, np.uint8)
    draw_candle(img, 50, 100, 120, 160, 180, RED)     # baissière (open haut, close bas)
    draw_candle(img, 100, 80, 100, 170, 190, GREEN)   # haussière englobante
    return img
