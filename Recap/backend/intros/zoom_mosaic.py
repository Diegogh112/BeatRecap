"""Intro 'Zoom mosaico': collage de fotos con zoom hacia el centro."""
import math
from PIL import Image

from .. import frames


def _ease_in_out(p: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * p)


def _build_mosaic(images, w, h):
    n = max(1, len(images))
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    cell_w = max(1, w // cols)
    cell_h = max(1, h // rows)
    canvas = Image.new("RGB", (cols * cell_w, rows * cell_h), (0, 0, 0))
    for i, img in enumerate(images):
        r = i // cols
        c = i % cols
        canvas.paste(frames.cover_fit(img, cell_w, cell_h), (c * cell_w, r * cell_h))
    return frames.cover_fit(canvas, w, h)


def generate(cfg: dict, progress: float):
    images = cfg["images"]
    w, h = cfg["w"], cfg["h"]
    if not images:
        return Image.new("RGB", (w, h), (0, 0, 0))
    mosaic = _build_mosaic(images, w, h)
    p = max(0.0, min(1.0, progress))
    factor = 1.0 + 0.6 * _ease_in_out(p)  # zoom 1.0 -> 1.6
    return frames.apply_zoom(mosaic, factor)
