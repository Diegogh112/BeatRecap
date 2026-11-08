"""Endpoints para carga y gestión de videos."""

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.storage import ensure_project_dirs
from app.models.project import Project, VideoInfo
from app.schemas.project import VideoInfoRead
from app.services.video_service import extract_video_metadata, validate_video_file

router = APIRouter()


@router.post("/{project_id}/video", response_model=VideoInfoRead)
async def upload_video(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Carga un video al proyecto. Valida formato, duración y tamaño."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    # Validar formato por extensión y MIME
    filename = file.filename or ""
    ext = Path(filename).suffix.lstrip(".").lower()
    if ext not in settings.allowed_formats_list:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no admitido: {ext}. Use: {', '.join(settings.allowed_formats_list)}",
        )

    ensure_project_dirs(project_id)
    safe_name = f"{uuid.uuid4()}.{ext}"
    dest_path = settings.upload_path / project_id / safe_name

    # Guardar en disco
    with dest_path.open("wb") as f:
        chunk_size = 1024 * 1024  # 1 MB
        total_bytes = 0
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > settings.max_video_size_bytes:
                dest_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"El archivo supera el tamaño máximo ({settings.max_video_size_mb} MB)",
                )
            f.write(chunk)

    # Extraer metadatos con FFprobe
    try:
        meta = extract_video_metadata(str(dest_path))
    except Exception as e:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Error al leer el video: {e}")

    # Validar duración
    if meta["duration"] > settings.max_video_duration:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=(
                f"La duración del video ({meta['duration']:.0f}s) supera el máximo "
                f"de {settings.max_video_duration} segundos."
            ),
        )

    # Eliminar video anterior si existe
    if project.video:
        old_path = Path(project.video.file_path)
        if old_path.exists():
            old_path.unlink(missing_ok=True)
        db.delete(project.video)

    # Construir URL pública
    video_url = f"/api/v1/projects/{project_id}/video/stream"

    video = VideoInfo(
        id=str(uuid.uuid4()),
        project_id=project_id,
        filename=safe_name,
        original_name=filename,
        file_path=str(dest_path),
        url=video_url,
        duration=meta["duration"],
        width=meta["width"],
        height=meta["height"],
        fps=meta["fps"],
        size=dest_path.stat().st_size,
        format=ext,
    )
    db.add(video)
    project.status = "video_uploaded"
    db.commit()
    db.refresh(video)
    return video


@router.get("/{project_id}/video/stream")
def stream_video(project_id: str, request: Request, db: Session = Depends(get_db)):
    """Sirve el video original con soporte de Range Requests para seek en el reproductor."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project or not project.video:
        raise HTTPException(status_code=404, detail="Video no encontrado")
    path = Path(project.video.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado en disco")

    file_size = path.stat().st_size
    range_header = request.headers.get("range")

    def iter_file(p: Path, start: int, end: int):
        with p.open("rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    if range_header:
        try:
            range_val = range_header.replace("bytes=", "")
            parts = range_val.split("-")
            start = int(parts[0])
            end = int(parts[1]) if parts[1] else file_size - 1
        except Exception:
            start = 0
            end = file_size - 1

        end = min(end, file_size - 1)
        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(end - start + 1),
        }
        return StreamingResponse(
            iter_file(path, start, end),
            status_code=206,
            media_type="video/mp4",
            headers=headers,
        )

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
    }
    return StreamingResponse(
        iter_file(path, 0, file_size - 1),
        status_code=200,
        media_type="video/mp4",
        headers=headers,
    )


@router.delete("/{project_id}/video", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(project_id: str, db: Session = Depends(get_db)):
    """Elimina el video de un proyecto y lo resetea a 'created'."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if project.video:
        path = Path(project.video.file_path)
        path.unlink(missing_ok=True)
        db.delete(project.video)
    project.status = "created"
    db.commit()
