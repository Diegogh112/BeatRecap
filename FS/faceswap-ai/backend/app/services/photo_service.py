"""
Validación de fotografías de reemplazo.

Estrategia correcta:
- Usar InsightFace con parámetros progresivamente más permisivos.
- Si ningún método detecta cara → rechazar (validated=False).
- NO aceptar imágenes sin cara real (quita el heurístico de retrato).
- El objetivo es asegurar que la foto tenga un rostro detectable
  para que InSwapper pueda extraer el embedding de origen.
"""

from pathlib import Path
from loguru import logger


def validate_photo_has_face(photo_path: str) -> bool:
    """
    Retorna True solo si se detecta al menos un rostro con certeza.
    Usa múltiples métodos en cascada, de más a menos estricto.
    """
    import cv2
    import numpy as np

    img = cv2.imread(photo_path)
    if img is None:
        logger.warning(f"No se pudo leer: {photo_path}")
        return False

    h, w = img.shape[:2]
    logger.info(f"Validando foto {w}×{h}: {Path(photo_path).name}")

    # ── Método 1: InsightFace 640px, threshold 0.3 ────────────────────────────
    if _try_insightface(img, det_size=640, threshold=0.3):
        logger.info("Cara detectada (InsightFace 640, thr=0.3)")
        return True

    # ── Método 2: upscale si la imagen es pequeña ─────────────────────────────
    if min(h, w) < 512:
        scale = 512 / min(h, w)
        img_up = cv2.resize(img, (int(w * scale), int(h * scale)),
                            interpolation=cv2.INTER_LINEAR)
        if _try_insightface(img_up, det_size=640, threshold=0.2):
            logger.info("Cara detectada (InsightFace 640 upscaled, thr=0.2)")
            return True

    # ── Método 3: threshold muy bajo (0.1) con imagen completa ───────────────
    if _try_insightface(img, det_size=320, threshold=0.1):
        logger.info("Cara detectada (InsightFace 320, thr=0.1)")
        return True

    # ── Método 4: Haar Cascade (OpenCV clásico) ───────────────────────────────
    if _try_haar(img):
        logger.info("Cara detectada (Haar Cascade)")
        return True

    logger.warning(f"No se detectó cara en: {Path(photo_path).name}")
    return False


# ─── Implementaciones ─────────────────────────────────────────────────────────

_face_app_cache: dict = {}


def _get_insightface_app(det_size: int):
    global _face_app_cache
    key = det_size
    if key in _face_app_cache:
        return _face_app_cache[key]
    try:
        from insightface.app import FaceAnalysis
        from app.core.config import settings
        app = FaceAnalysis(
            name=settings.insightface_model,
            providers=["CPUExecutionProvider"],  # siempre CPU para validación
        )
        app.prepare(ctx_id=-1, det_size=(det_size, det_size))
        _face_app_cache[key] = app
        return app
    except Exception as e:
        logger.error(f"InsightFace init error (det_size={det_size}): {e}")
        return None


def _try_insightface(img, det_size: int, threshold: float) -> bool:
    try:
        app = _get_insightface_app(det_size)
        if app is None:
            return False
        faces = app.get(img)
        if faces:
            best = max(faces, key=lambda f: f.det_score)
            if best.det_score >= threshold:
                return True
        return False
    except Exception as e:
        logger.debug(f"InsightFace {det_size} error: {e}")
        return False


def _try_haar(img) -> bool:
    try:
        import cv2
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        detector = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        faces = detector.detectMultiScale(
            gray, scaleFactor=1.05, minNeighbors=2, minSize=(20, 20)
        )
        return len(faces) > 0
    except Exception as e:
        logger.debug(f"Haar error: {e}")
        return False
