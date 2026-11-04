"""Intro 'Vórtice' (Fase 3, opcional): transformación a coordenadas polares
con cv2.remap y animación de descenso. Requiere opencv-python (cv2)."""
import math
import numpy as np

try:
    import cv2
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "La intro 'vortex' requiere opencv-python. Instala con: pip install opencv-python"
    ) from exc

from .. import frames

# Cache de coordenadas polares por tamaño (w, h)
_POLAR_CACHE = {}


def _polar_maps(w, h):
    key = (w, h)
    if key not in _POLAR_CACHE:
        cx, cy = w / 2.0, h / 2.0
        xs = np.arange(w, dtype=np.float32)
        ys = np.arange(h, dtype=np.float32)
        X, Y = np.meshgrid(xs, ys)
        dx = X - cx
        dy = Y - cy
        r = np.sqrt(dx * dx + dy * dy)
        theta = np.arctan2(dy, dx)
        _POLAR_CACHE[key] = (cx, cy, r, theta)
    return _POLAR_CACHE[key]


def generate(cfg: dict, progress: float):
    from PIL import Image
    images = cfg["images"]
    w, h = cfg["w"], cfg["h"]
    if not images:
        return Image.new("RGB", (w, h), (0, 0, 0))

    src = frames.cover_fit(images[0 % len(images)], w, h)
    src_np = np.asarray(src).astype(np.float32)

    cx, cy, r, theta = _polar_maps(w, h)
    p = max(0.0, min(1.0, progress))
    max_r = math.hypot(cx, cy)

    # Remolino: el ángulo de muestreo gira más cuanto mayor es el radio y el tiempo
    swirl = p * math.pi * (r / max(max_r, 1e-6))
    src_theta = theta - swirl
    sx = cx + r * np.cos(src_theta)
    sy = cy + r * np.sin(src_theta)

    # Descenso: desplazamiento vertical que crece con el progreso
    sy = sy + p * h * 0.25

    map_x = sx.astype(np.float32)
    map_y = sy.astype(np.float32)
    out = cv2.remap(src_np, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")
