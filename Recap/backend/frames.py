"""Generación de frames con Pillow/numpy: cover-fit, texto, transiciones."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import config


# --- Cover fit ---------------------------------------------------------------

def cover_fit(
    img: Image.Image,
    target_w: int,
    target_h: int,
    crop_x: float = 0.5,
    crop_y: float = 0.5,
) -> Image.Image:
    """Redimensiona con recorte (cover) sin deformar.

    crop_x, crop_y ∈ [0..1]: punto de anclaje del recorte.
      0.5, 0.5 = centrado (por defecto)
      0.0, 0.0 = esquina superior-izquierda
      1.0, 1.0 = esquina inferior-derecha
    """
    img = img.convert("RGB")
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w = max(1, int(round(src_w * scale)))
    new_h = max(1, int(round(src_h * scale)))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    # margen disponible en cada eje
    max_left = new_w - target_w
    max_top  = new_h - target_h
    left = int(round(max(0, min(max_left, max_left * crop_x))))
    top  = int(round(max(0, min(max_top,  max_top  * crop_y))))
    return img.crop((left, top, left + target_w, top + target_h))


# --- Texto animado -----------------------------------------------------------

def _ease_out_cubic(p: float) -> float:
    return 1 - (1 - p) ** 3


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _load_font(font_name: str, size: int) -> ImageFont.ImageFont:
    candidates = []
    if font_name:
        # primero en la carpeta de fuentes del proyecto
        candidates.append(config.FONTS_DIR / font_name)
        # después por nombre de archivo mapeado en el sistema
        mapped = config.FONT_MAP.get(font_name)
        if mapped:
            candidates.append(config.FONTS_DIR / mapped)
            candidates.append(mapped)
        candidates.append(font_name)
    candidates += [
        config.FONTS_DIR / config.FONT_MAP[config.DEFAULT_FONT],
        config.FONT_MAP[config.DEFAULT_FONT],
        "arialbd.ttf",
        "arial.ttf",
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(str(c), size)
        except Exception:
            continue
    return ImageFont.load_default()


def make_text_frame(
    title: str,
    subtitle: str,
    color_hex: str,
    font_name: str,
    w: int,
    h: int,
    progress: float,
) -> Image.Image:
    """Frame de la intro 'Solo texto': título/subtítulo sobre fondo negro con
    animación de entrada (fade + slide) según progress (0..1)."""
    base = Image.new("RGB", (w, h), (0, 0, 0))
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    rgb = _hex_to_rgb(color_hex or "#FFFFFF")
    p = max(0.0, min(1.0, progress))

    title_size = int(w * 0.095)
    title_font = _load_font(font_name or config.DEFAULT_FONT, title_size)

    tbbox = draw.textbbox((0, 0), title, font=title_font)
    tw = tbbox[2] - tbbox[0]
    th = tbbox[3] - tbbox[1]

    # Fade-in en la primera mitad, slide (ease-out) a lo largo del 70%
    alpha = int(255 * min(1.0, p / 0.5))
    slide = int((1 - _ease_out_cubic(min(1.0, p / 0.7))) * h * 0.06)

    ty = h // 2 - th // 2 - slide - tbbox[1]
    tx = w // 2 - tw // 2 - tbbox[0]
    draw.text((tx, ty), title, font=title_font, fill=(*rgb, alpha))

    if subtitle:
        sub_size = int(w * 0.045)
        sub_font = _load_font(None, sub_size)
        sbbox = draw.textbbox((0, 0), subtitle, font=sub_font)
        sw = sbbox[2] - sbbox[0]
        sy = ty + th + tbbox[1] + int(h * 0.04)
        sx = w // 2 - sw // 2 - sbbox[0]
        sub_alpha = int(255 * min(1.0, max(0.0, (p - 0.25) / 0.5))
)  # subtítulo aparece algo después
        draw.text((sx, sy), subtitle, font=sub_font, fill=(*rgb, sub_alpha))

    return Image.alpha_composite(base.convert("RGBA"), layer).convert("RGB")


# --- Transiciones ------------------------------------------------------------

def apply_flash(img: Image.Image, intensity: float) -> Image.Image:
    """Superpone un flash blanco proporcional a intensity (0..1)."""
    intensity = max(0.0, min(1.0, intensity))
    if intensity <= 0:
        return img
    arr = np.asarray(img.convert("RGB")).astype(np.float32)
    arr = arr + (255.0 - arr) * intensity
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def apply_zoom(img: Image.Image, factor: float) -> Image.Image:
    """Zoom breve desde el centro (factor >= 1)."""
    factor = max(1.0, factor)
    if factor <= 1.0 + 1e-3:
        return img
    w, h = img.size
    new_w = max(1, int(round(w * factor)))
    new_h = max(1, int(round(h * factor)))
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    return resized.crop((left, top, left + w, top + h))


# --- Etiqueta de mes ---------------------------------------------------------

def draw_month_label(
    img: Image.Image,
    label: str,
    font_name: str = None,
    color_hex: str = "#FFFFFF",
    fade: float = 1.0,        # 0..1 para animación de entrada/salida
) -> Image.Image:
    """Superpone el nombre del mes centrado con fade sobre la imagen."""
    if not label or fade <= 0:
        return img
    img = img.copy().convert("RGBA")
    w, h = img.size

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Fondo semitransparente en la franja central
    alpha_bg = int(180 * fade)
    strip_h  = int(h * 0.22)
    cy       = h // 2
    draw.rectangle(
        [(0, cy - strip_h // 2), (w, cy + strip_h // 2)],
        fill=(0, 0, 0, alpha_bg),
    )

    # Texto grande
    font_size = int(w * 0.14)
    font = _load_font(font_name or config.DEFAULT_FONT, font_size)
    rgb  = _hex_to_rgb(color_hex or "#FFFFFF")

    bbox = draw.textbbox((0, 0), label, font=font)
    tw   = bbox[2] - bbox[0]
    th   = bbox[3] - bbox[1]
    tx   = w // 2 - tw // 2 - bbox[0]
    ty   = cy - th // 2 - bbox[1]

    alpha_text = int(255 * fade)
    draw.text((tx, ty), label, font=font, fill=(*rgb, alpha_text))

    return Image.alpha_composite(img, overlay).convert("RGB")


# --- Tilt (inclinación) ------------------------------------------------------

def apply_tilt(img: Image.Image, angle_deg: float) -> Image.Image:
    """Rota la imagen `angle_deg` grados rellenando con negro y recortando
    a las dimensiones originales (el contenido se escala levemente para evitar
    bordes negros visibles)."""
    if abs(angle_deg) < 0.5:
        return img
    w, h = img.size
    # Sobre-escalar un poco para evitar esquinas negras tras la rotación
    pad = abs(angle_deg) / 45.0 * 0.18 + 0.04   # ~4–22% extra
    sw  = int(w * (1 + pad))
    sh  = int(h * (1 + pad))
    enlarged = img.resize((sw, sh), Image.LANCZOS)
    rotated  = enlarged.rotate(angle_deg, resample=Image.BICUBIC, expand=False)
    # Recortar al centro con el tamaño original
    lx = (sw - w) // 2
    ty = (sh - h) // 2
    return rotated.crop((lx, ty, lx + w, ty + h))
