"""Utilidades: validación de archivos y manejo de carpetas temporales por job."""
import uuid
import shutil
from pathlib import Path
from fastapi import HTTPException

from . import config


def new_job_dir() -> tuple:
    """Crea una carpeta temporal única para un job/render y devuelve (id, path)."""
    job_id = uuid.uuid4().hex
    d = config.TMP_DIR / job_id
    d.mkdir(parents=True, exist_ok=True)
    return job_id, d


def validate_audio_ext(filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in config.ALLOWED_AUDIO_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Formato de audio no permitido: .{ext}. Usa mp3, wav o m4a.",
        )
    return ext


def validate_image_ext(filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext == "jpeg":
        ext = "jpg"
    allowed = config.ALLOWED_IMAGE_EXT | {v for v in config.ALLOWED_VIDEO_EXT}
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no permitido: .{ext}. Usa jpg/png/webp o mp4/mov.",
        )
    return ext


def is_video_ext(ext: str) -> bool:
    return ext.lower().lstrip(".") in config.ALLOWED_VIDEO_EXT


def cleanup_dir(d: Path) -> None:
    """Elimina una carpeta temporal si existe."""
    if d and d.exists():
        shutil.rmtree(d, ignore_errors=True)
