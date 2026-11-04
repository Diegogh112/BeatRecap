"""Prueba de que el total de frames es ceil(duration * fps)."""
import math

from backend.render import total_frames
from backend import config


def test_total_frames_whole_seconds():
    fps = config.FPS
    assert total_frames(10.0) == 300
    assert total_frames(10.0) == math.ceil(10.0 * fps)


def test_total_frames_fractional():
    fps = config.FPS
    assert total_frames(10.5) == math.ceil(10.5 * fps)
    assert total_frames(10.034) == math.ceil(10.034 * fps)


def test_total_frames_no_round_per_interval():
    # 59.97s -> ceil, no truncado
    fps = config.FPS
    assert total_frames(59.97) == math.ceil(59.97 * fps)
    assert total_frames(59.97) > int(59.97 * fps)  # confirma que es techo, no suelo
