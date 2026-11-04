"""Intro 'Túnel de fotos': efecto tipo CapCut.

Proyección cilíndrica correcta:
  - Se construye una tira larga con todas las fotos pegadas.
  - Para cada pixel del canvas, se calcula su ángulo (theta) y su radio (r).
  - theta → posición horizontal en la tira (qué foto y qué columna).
  - r     → posición vertical en la tira (qué fila de la foto).
  - El radio se mapea logarítmicamente para dar perspectiva de profundidad.
  - La animación avanza desplazando el radio logarítmico, haciendo que las
    franjas se "acerquen" al centro como en un túnel.
"""
import math
import numpy as np
from PIL import Image, ImageDraw

from .. import frames


# ---------------------------------------------------------------------------
# Cache de mapas polares
# ---------------------------------------------------------------------------
_MAP_CACHE: dict = {}


def _build_polar_maps(w: int, h: int):
    key = (w, h)
    if key in _MAP_CACHE:
        return _MAP_CACHE[key]
    cx, cy  = w / 2.0, h / 2.0
    max_r   = math.hypot(cx, cy)
    xs      = (np.arange(w, dtype=np.float32) - cx)
    ys      = (np.arange(h, dtype=np.float32) - cy)
    X, Y    = np.meshgrid(xs, ys)
    R_px    = np.sqrt(X * X + Y * Y)                    # radio en píxeles
    R_norm  = (R_px / max_r).clip(0, 1)                 # normalizado 0..1
    THETA   = np.arctan2(Y, X)                          # -π..π
    _MAP_CACHE[key] = (R_norm, THETA, max_r)
    return _MAP_CACHE[key]


def _build_strip(images: list, strip_w: int, strip_h: int) -> np.ndarray:
    """Tira horizontal con todas las fotos. Se repite si hay pocas."""
    MIN = 6
    pool   = images * max(1, math.ceil(MIN / max(1, len(images))))
    pool   = pool[:MIN]
    n      = len(pool)
    tile_w = max(1, strip_w // n)
    strip  = Image.new("RGB", (strip_w, strip_h), (0, 0, 0))
    for i, img in enumerate(pool):
        strip.paste(frames.cover_fit(img, tile_w, strip_h), (i * tile_w, 0))
    # Rellenar el último pixel si hay hueco
    return np.asarray(strip, dtype=np.uint8)


def generate(cfg: dict, progress: float) -> Image.Image:
    images     = cfg["images"]
    w, h       = cfg["w"], cfg["h"]
    title      = cfg.get("title", "")
    subtitle   = cfg.get("subtitle", "")
    text_color = cfg.get("text_color", "#FFFFFF")
    font       = cfg.get("font", None)
    p          = max(0.0, min(1.0, progress))

    if not images:
        return Image.new("RGB", (w, h), (0, 0, 0))

    # ── Tira de fotos ─────────────────────────────────────────────────────
    # strip_h = h de la tira (se muestrea verticalmente por el radio)
    # strip_w = ancho total de la tira (se muestrea horizontalmente por theta)
    strip_h = h
    strip_w = max(w * 4, w * len(images))   # ancho generoso para no pixelar
    strip   = _build_strip(images, strip_w, strip_h)    # (strip_h, strip_w, 3)

    # ── Mapas polares ─────────────────────────────────────────────────────
    R_norm, THETA, max_r = _build_polar_maps(w, h)

    # u: eje angular → columna de la tira (0..1, circular)
    u = ((THETA + math.pi) / (2 * math.pi))            # 0..1

    # v: eje radial → fila de la tira (profundidad)
    # Transformación log para perspectiva: r pequeño = lejos = abajo de la tira
    # r grande = cerca = arriba de la tira
    # Con la animación, el scroll avanza hacia arriba (hacia el borde)
    SCROLL_CYCLES = 1.2   # cuántas veces recorre la tira durante la intro
    r_log = np.log1p(R_norm * 6.0) / math.log(7.0)    # 0..1 log

    # Scroll: p avanza → las texturas se desplazan hacia el centro (v baja)
    scroll_offset = p * SCROLL_CYCLES
    v = (r_log + scroll_offset) % 1.0

    # ── Muestrear la tira ─────────────────────────────────────────────────
    src_x = (u * (strip_w - 1)).astype(np.int32).clip(0, strip_w - 1)
    src_y = (v * (strip_h - 1)).astype(np.int32).clip(0, strip_h - 1)
    out   = strip[src_y, src_x]                         # (h, w, 3)

    # ── Oscurecimiento hacia el centro (agujero negro) ────────────────────
    # Cuanto menor el radio, más oscuro (efecto de profundidad)
    dark_f = np.clip(R_norm * 1.3, 0.0, 1.0)[:, :, np.newaxis]
    out    = (out.astype(np.float32) * dark_f).clip(0, 255).astype(np.uint8)

    # ── Vignette en el borde exterior ────────────────────────────────────
    vig = np.clip((R_norm - 0.82) / 0.18, 0, 1)[:, :, np.newaxis]
    out = (out.astype(np.float32) * (1 - vig * 0.55)).clip(0, 255).astype(np.uint8)

    canvas = Image.fromarray(out, "RGB")

    # ── Texto sobre círculo negro central ─────────────────────────────────
    text_fade = min(1.0, p / 0.3)
    if title:
        canvas = _overlay_text(canvas, w, h, title, subtitle,
                               text_color, font, text_fade)
    return canvas


def _overlay_text(canvas, w, h, title, subtitle, text_color, font, fade):
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)

    cx, cy = w // 2, h // 2
    cr     = int(min(w, h) * 0.22)

    # Halo difuso alrededor del círculo
    for extra in range(int(min(w, h) * 0.08), 0, -3):
        a = int(100 * fade * (1 - extra / (min(w, h) * 0.08 + 1)))
        draw.ellipse([(cx - cr - extra, cy - cr - extra),
                      (cx + cr + extra, cy + cr + extra)],
                     fill=(0, 0, 0, max(0, a)))

    # Círculo negro sólido
    draw.ellipse([(cx - cr, cy - cr), (cx + cr, cy + cr)],
                 fill=(0, 0, 0, int(248 * fade)))

    def hex_rgb(hx):
        hx = hx.lstrip("#")
        if len(hx) == 3: hx = "".join(c*2 for c in hx)
        return int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)

    rgb   = hex_rgb(text_color or "#FFFFFF")
    alpha = int(255 * fade)

    title_size = int(w * 0.12)
    tfont = frames._load_font(font, title_size)
    bbox  = draw.textbbox((0, 0), title, font=tfont)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = cx - tw // 2 - bbox[0]
    ty = cy - th // 2 - bbox[1]
    draw.text((tx, ty), title, font=tfont, fill=(*rgb, alpha))

    if subtitle:
        sfont = frames._load_font(None, int(w * 0.045))
        sbbox = draw.textbbox((0, 0), subtitle, font=sfont)
        sx = cx - (sbbox[2] - sbbox[0]) // 2 - sbbox[0]
        sy = ty + th + int(h * 0.025)
        draw.text((sx, sy), subtitle, font=sfont,
                  fill=(*rgb, int(alpha * 0.85)))

    return Image.alpha_composite(canvas.convert("RGBA"), layer).convert("RGB")
