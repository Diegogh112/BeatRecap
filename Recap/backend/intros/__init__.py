"""Registro de estilos de intro."""
from . import text, zoom_mosaic, falling

INTRO_STYLES = {
    "text": text.generate,
    "zoom_mosaic": zoom_mosaic.generate,
    "falling": falling.generate,
}

# Vórtice (Fase 3) es opcional: requiere opencv-python.
try:  # pragma: no cover
    from . import vortex
    INTRO_STYLES["vortex"] = vortex.generate
except Exception:
    pass


def get_intro(style: str):
    return INTRO_STYLES.get(style, INTRO_STYLES["text"])
