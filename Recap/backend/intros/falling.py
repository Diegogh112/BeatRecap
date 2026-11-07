"""Intro 'Túnel de fotos' — estilo CapCut.

Para cada celda (anillo × sector):
  - Calculamos el bounding box cartesiano de la cuña.
  - Renderizamos la foto con cover_fit al tamaño de ese bounding box.
  - Para cada pixel de la cuña, calculamos su posición RELATIVA dentro
    del bounding box (0..1) y muestreamos la foto en esa posición.

Esto garantiza que cada cuña muestre la foto completa sin deformación.
Los anillos cubren todo el canvas (R normalizado por la diagonal).
"""
import math
import numpy as np
from PIL import Image, ImageDraw

from .. import frames

_MAP_CACHE: dict  = {}
_PHOTO_CACHE: dict = {}


def _cover_np(img: Image.Image, w: int, h: int) -> np.ndarray:
    key = (id(img), w, h)
    if key not in _PHOTO_CACHE:
        _PHOTO_CACHE[key] = np.asarray(frames.cover_fit(img, w, h), dtype=np.uint8)
    return _PHOTO_CACHE[key]


def _build_polar_maps(w: int, h: int):
    key = (w, h)
    if key in _MAP_CACHE:
        return _MAP_CACHE[key]
    cx, cy = w / 2.0, h / 2.0
    mr     = math.hypot(cx, cy)   # diagonal/2 — las esquinas quedan en r≈1
    xs     = (np.arange(w, dtype=np.float32) - cx) / mr
    ys     = (np.arange(h, dtype=np.float32) - cy) / mr
    X, Y   = np.meshgrid(xs, ys)
    R      = np.sqrt(X*X + Y*Y)   # 0..≈1 (esquinas ~1)
    THETA  = np.arctan2(Y, X)     # -π..π
    _MAP_CACHE[key] = (R, THETA)
    return R, THETA


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

    N_SECTORS = 14
    N_RINGS   = 4

    n_cells = N_SECTORS * N_RINGS
    pool    = (images * max(1, math.ceil(n_cells / len(images))))[:n_cells]

    R_INNER = 0.06
    R_OUTER = 1.01   # cubre las esquinas
    r_breaks = np.exp(np.linspace(math.log(R_INNER), math.log(R_OUTER), N_RINGS + 1))

    ring_shift = (p * N_RINGS) % N_RINGS

    R, THETA   = _build_polar_maps(w, h)
    THETA_norm = ((THETA + math.pi) / (2 * math.pi))

    out = np.zeros((h, w, 3), dtype=np.uint8)

    for ring_idx in range(N_RINGS):
        # La animación desplaza los ÍNDICES de foto, no los radios.
        # Los radios permanecen fijos — sin encoger → sin bordes negros.
        r_lo = r_breaks[ring_idx]
        r_hi = r_breaks[ring_idx + 1]
        ring_mask = (R >= r_lo) & (R < r_hi)
        if not np.any(ring_mask):
            continue

        for sec_idx in range(N_SECTORS):
            theta_lo = sec_idx       / N_SECTORS
            theta_hi = (sec_idx + 1) / N_SECTORS
            cell = ring_mask & (THETA_norm >= theta_lo) & (THETA_norm < theta_hi)
            if not np.any(cell):
                continue

            # La animación rota las fotos: avanzar ring_shift posiciones
            photo_idx = (ring_idx * N_SECTORS + sec_idx + int(ring_shift * N_SECTORS)) % len(pool)
            img_src   = pool[photo_idx]

            rows_c, cols_c = np.where(cell)

            # Bounding box de la cuña
            x0 = int(cols_c.min()); x1 = int(cols_c.max()) + 1
            y0 = int(rows_c.min()); y1 = int(rows_c.max()) + 1
            bw = max(2, x1 - x0)
            bh = max(2, y1 - y0)

            # Foto renderizada al tamaño del bounding box
            tile = _cover_np(img_src, bw, bh)

            # Coordenadas locales: posición relativa dentro del bbox (0..bw-1, 0..bh-1)
            lc = (cols_c - x0).clip(0, bw - 1)
            lr = (rows_c - y0).clip(0, bh - 1)

            out[rows_c, cols_c] = tile[lr, lc]

    # ── Oscurecimiento radial (perspectiva de profundidad) ────────────────
    dark = np.clip(R * 1.1, 0.08, 1.0)[:, :, np.newaxis]
    out  = (out.astype(np.float32) * dark).clip(0, 255).astype(np.uint8)

    # ── Líneas separadoras finas entre celdas ─────────────────────────────
    sec_edge  = np.abs(np.mod(THETA_norm * N_SECTORS, 1.0)) < 0.025
    ring_edge = np.zeros((h, w), dtype=bool)
    for rb in r_breaks[1:-1]:
        ring_edge |= (np.abs(R - rb) < 0.012)
    border = (sec_edge | ring_edge) & (R > R_INNER)
    out[border] = (out[border].astype(np.float32) * 0.3).astype(np.uint8)

    canvas = Image.fromarray(out, "RGB")

    if title:
        canvas = _overlay_text(canvas, w, h, title, subtitle, text_color, font)
    return canvas


def _overlay_text(canvas, w, h, title, subtitle, text_color, font):
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)
    cx, cy = w // 2, h // 2
    cr     = int(min(w, h) * 0.22)

    for extra in range(int(min(w, h) * 0.07), 0, -3):
        a = int(75 * (1 - extra / (min(w, h) * 0.07 + 1)))
        draw.ellipse([(cx-cr-extra, cy-cr-extra),(cx+cr+extra, cy+cr+extra)],
                     fill=(0, 0, 0, max(0, a)))
    draw.ellipse([(cx-cr, cy-cr),(cx+cr, cy+cr)], fill=(0, 0, 0, 255))

    def hex_rgb(hx):
        hx = hx.lstrip("#")
        if len(hx) == 3: hx = "".join(c*2 for c in hx)
        return int(hx[0:2],16), int(hx[2:4],16), int(hx[4:6],16)

    rgb   = hex_rgb(text_color or "#FFFFFF")
    tfont = frames._load_font(font, int(w * 0.12))
    bbox  = draw.textbbox((0, 0), title, font=tfont)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    draw.text((cx - tw//2 - bbox[0], cy - th//2 - bbox[1]),
              title, font=tfont, fill=(*rgb, 255))
    if subtitle:
        sfont = frames._load_font(None, int(w * 0.045))
        sbbox = draw.textbbox((0, 0), subtitle, font=sfont)
        draw.text((cx - (sbbox[2]-sbbox[0])//2 - sbbox[0],
                   cy + th//2 + int(h * 0.025)),
                  subtitle, font=sfont, fill=(*rgb, 220))
    return Image.alpha_composite(canvas.convert("RGBA"), layer).convert("RGB")
