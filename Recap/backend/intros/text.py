"""Intro 'Solo texto': título/subtítulo animado sobre fondo dinámico con partículas."""
import math
import numpy as np
from PIL import Image, ImageDraw

from .. import frames


# ---------------------------------------------------------------------------
# Fondo de partículas / destellos
# ---------------------------------------------------------------------------

# Semilla fija para partículas reproducibles entre frames
_RNG = np.random.RandomState(42)
_PARTICLES = None   # se genera la primera vez y se cachea


def _get_particles(n: int = 120):
    global _PARTICLES
    if _PARTICLES is None or len(_PARTICLES) != n:
        rng = np.random.RandomState(7)
        _PARTICLES = {
            "x":     rng.uniform(0, 1, n),          # posición X normalizada
            "y":     rng.uniform(0, 1, n),          # posición Y normalizada
            "vy":    rng.uniform(-0.25, -0.05, n),  # velocidad vertical (sube)
            "vx":    rng.uniform(-0.04,  0.04, n),  # deriva horizontal
            "size":  rng.uniform(1.5, 5.0, n),      # radio px (a 1080px)
            "phase": rng.uniform(0, 2 * math.pi, n),# fase de parpadeo
            "speed": rng.uniform(1.5, 4.0, n),      # velocidad de parpadeo
        }
    return _PARTICLES


def _draw_particles(draw: ImageDraw.ImageDraw, w: int, h: int, t: float, alpha_base: float):
    """Dibuja partículas brillantes que suben lentamente."""
    p = _get_particles(120)
    scale = w / 1080.0
    for i in range(len(p["x"])):
        # posición en tiempo t (envuelve en 0..1)
        xi = (p["x"][i] + p["vx"][i] * t) % 1.0
        yi = (p["y"][i] + p["vy"][i] * t) % 1.0
        px = int(xi * w)
        py = int(yi * h)
        # parpadeo suave
        blink = 0.5 + 0.5 * math.sin(p["phase"][i] + p["speed"][i] * t * math.pi * 2)
        a = int(alpha_base * blink * 220)
        if a < 5:
            continue
        r = max(1, int(p["size"][i] * scale))
        # color: blanco azulado o dorado según índice
        if i % 3 == 0:
            color = (255, 220, 120, a)   # dorado
        elif i % 3 == 1:
            color = (180, 200, 255, a)   # azul claro
        else:
            color = (255, 255, 255, a)   # blanco
        draw.ellipse((px - r, py - r, px + r, py + r), fill=color)


def _draw_glow_lines(draw: ImageDraw.ImageDraw, w: int, h: int, t: float, alpha_base: float):
    """Líneas horizontales sutiles que se desplazan hacia arriba."""
    n_lines = 6
    for i in range(n_lines):
        base_y = (i / n_lines + t * 0.08) % 1.0
        y      = int(base_y * h)
        a      = int(alpha_base * 18)
        draw.line([(0, y), (w, y)], fill=(100, 150, 255, a), width=max(1, int(w * 0.001)))


def _make_background(w: int, h: int, t: float, progress: float) -> Image.Image:
    """Fondo oscuro con gradiente + partículas. Opacidad crece con progress."""
    # Base: gradiente vertical oscuro (azul marino → negro)
    base = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        frac  = y / h
        blue  = int(20 + (1 - frac) * 18)
        green = int(5  + (1 - frac) * 8)
        base[y, :] = [5, green, blue]
    bg = Image.fromarray(base, "RGB").convert("RGBA")

    # Capa de partículas
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)
    alpha_fade = min(1.0, progress / 0.3)    # aparecen en el primer 30%
    _draw_particles(draw, w, h, t, alpha_fade)
    _draw_glow_lines(draw, w, h, t, alpha_fade)

    return Image.alpha_composite(bg, layer).convert("RGB")


# ---------------------------------------------------------------------------
# Genera un frame de la intro
# ---------------------------------------------------------------------------

def generate(cfg: dict, progress: float):
    """cfg: {title, subtitle, text_color, font, w, h}. progress: 0..1."""
    w, h = cfg["w"], cfg["h"]

    # Tiempo absoluto aproximado: asumimos ~30 fps, progress de 0 a 1
    # Usamos progress directamente como parámetro temporal
    t = progress * 4.0   # 4 ciclos de animación durante la intro

    bg = _make_background(w, h, t, progress)

    # Texto encima del fondo dinámico
    text_frame = frames.make_text_frame(
        cfg.get("title", ""),
        cfg.get("subtitle", ""),
        cfg.get("text_color", "#FFFFFF"),
        cfg.get("font", None),
        w, h,
        progress,
    )

    # Componer: el texto tiene su propio fondo negro, lo combino por luminancia
    # en las zonas de texto: usar text_frame; en el resto: usar bg
    bg_arr   = np.asarray(bg,         dtype=np.float32)
    txt_arr  = np.asarray(text_frame, dtype=np.float32)

    # Máscara: zonas donde text_frame > fondo negro (hay texto o glow)
    brightness = txt_arr.mean(axis=2, keepdims=True)
    mask       = np.clip(brightness / 60.0, 0, 1)

    # El fondo dinámico se ve en las zonas oscuras; el texto domina en las brillantes
    blended = bg_arr * (1 - mask) + txt_arr * mask
    return Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8), "RGB")
