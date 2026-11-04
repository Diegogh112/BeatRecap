"""Configuración central de Beat Recap."""
import os
from pathlib import Path

# --- Video ---
RESOLUTIONS = {
    "vertical": (1080, 1920),
    "horizontal": (1920, 1080),
}
DEFAULT_RESOLUTION = "vertical"
FPS = 30

# --- Audio ---
ALLOWED_AUDIO_EXT = {"mp3", "wav", "m4a"}
MAX_AUDIO_DURATION = 60.0  # segundos

# --- Imágenes y clips de video ---
ALLOWED_IMAGE_EXT = {"jpg", "jpeg", "png", "webp"}
ALLOWED_VIDEO_EXT = {"mp4", "mov", "webm"}   # clips para el carrusel (sin audio)

# --- Transiciones ---
TRANSITIONS = ("cut", "flash", "zoom")
DEFAULT_TRANSITION = "cut"

# --- Intro ---
INTRO_STYLES = ("text", "zoom_mosaic", "falling", "vortex")
DEFAULT_INTRO_STYLE = "text"
DEFAULT_TITLE = "2025 RECAP"
DEFAULT_TEXT_COLOR = "#FFFFFF"

# Fuentes disponibles (mapeadas a archivos del sistema; también se buscan en FONTS_DIR)
FONT_MAP = {
    "Impact": "impact.ttf",
    "Arial Bold": "arialbd.ttf",
    "Arial": "arial.ttf",
    "Georgia": "georgia.ttf",
    "Courier New": "cour.ttf",
}
DEFAULT_FONT = "Impact"

# --- Rutas ---
ROOT = Path(__file__).resolve().parent.parent
TMP_DIR = ROOT / "tmp"
FRONTEND_DIR = ROOT / "frontend"
FONTS_DIR = FRONTEND_DIR / "assets" / "fonts"

# --- ffmpeg (se puede sobreescribir con la variable de entorno FFMPEG_BIN) ---
def _resolve_ffmpeg() -> str:
    # Preferimos el ffmpeg empaquetado por imageio-ffmpeg si está disponible
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return os.environ.get("FFMPEG_BIN", "ffmpeg")


FFMPEG_BIN = _resolve_ffmpeg()

# --- Preview ---
PREVIEW_SCALE = 0.5   # la vista previa usa 1/2 de resolución (suficiente para previsualizar)
