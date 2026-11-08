"""Gestión del almacenamiento local de archivos."""

from pathlib import Path
from app.core.config import settings


def ensure_dirs() -> None:
    """Crea los directorios de almacenamiento si no existen."""
    for d in [
        settings.upload_path,
        settings.output_path,
        settings.thumbnail_path,
        settings.model_path,
        Path("logs"),
    ]:
        d.mkdir(parents=True, exist_ok=True)


def upload_file_path(project_id: str, filename: str) -> Path:
    return settings.upload_path / project_id / filename


def output_file_path(project_id: str, filename: str) -> Path:
    return settings.output_path / project_id / filename


def thumbnail_path(project_id: str, filename: str) -> Path:
    return settings.thumbnail_path / project_id / filename


def ensure_project_dirs(project_id: str) -> None:
    for base in [settings.upload_path, settings.output_path, settings.thumbnail_path]:
        (base / project_id).mkdir(parents=True, exist_ok=True)
