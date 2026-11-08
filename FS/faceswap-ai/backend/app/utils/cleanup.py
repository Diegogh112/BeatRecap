"""Utilidades de limpieza de archivos temporales."""

import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from loguru import logger

from app.core.config import settings


def cleanup_project_files(project_id: str) -> None:
    """Elimina todos los archivos temporales de un proyecto."""
    for base in [settings.upload_path, settings.output_path, settings.thumbnail_path]:
        project_dir = base / project_id
        if project_dir.exists():
            shutil.rmtree(project_dir, ignore_errors=True)
            logger.info(f"Directorio eliminado: {project_dir}")


def cleanup_stale_files(max_age_hours: int = None) -> int:
    """
    Elimina directorios de proyectos más antiguos que max_age_hours.
    Retorna el número de directorios eliminados.
    """
    if max_age_hours is None:
        max_age_hours = settings.retention_hours

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    deleted = 0

    for base in [settings.upload_path, settings.output_path, settings.thumbnail_path]:
        if not base.exists():
            continue
        for project_dir in base.iterdir():
            if not project_dir.is_dir():
                continue
            mtime = datetime.fromtimestamp(project_dir.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                shutil.rmtree(project_dir, ignore_errors=True)
                deleted += 1
                logger.info(f"Archivo antiguo eliminado: {project_dir}")

    return deleted
