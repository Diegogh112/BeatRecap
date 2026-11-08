"""Endpoints para iniciar el procesamiento de face swap."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.project import Project
from app.models.job import ProcessingJob
from app.schemas.job import StartProcessingRequest, ProcessingJobRead
from app.workers.tasks import run_face_swap

router = APIRouter()


@router.post("/{project_id}/process")
def start_processing(
    project_id: str,
    body: StartProcessingRequest,
    db: Session = Depends(get_db),
):
    """Inicia el procesamiento de face swap en el video del proyecto."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not project.video:
        raise HTTPException(status_code=400, detail="Sin video cargado")
    if not project.detection_result:
        raise HTTPException(status_code=400, detail="Sin detección completada")
    if not body.assignments:
        raise HTTPException(status_code=400, detail="Sin asignaciones de reemplazo")

    # Validar que las asignaciones son válidas
    valid_person_ids = {p.person_id for p in project.detection_result.persons}
    for person_id in body.assignments:
        if person_id not in valid_person_ids:
            raise HTTPException(
                status_code=400,
                detail=f"person_id desconocido: {person_id}",
            )

    # Crear job de procesamiento
    job = ProcessingJob(
        id=str(uuid.uuid4()),
        project_id=project_id,
        status="queued",
        progress=0,
        current_stage="En cola",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(job)
    project.status = "queued"
    db.commit()
    db.refresh(job)

    # Enviar a Celery
    task = run_face_swap.delay(project_id, job.id, body.assignments)
    job.celery_task_id = task.id
    db.commit()

    return {"jobId": job.id, "projectId": project_id}


@router.get("/{project_id}/job", response_model=ProcessingJobRead)
def get_project_job(project_id: str, db: Session = Depends(get_db)):
    """Obtiene el job de procesamiento más reciente del proyecto."""
    job = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.project_id == project_id)
        .order_by(ProcessingJob.created_at.desc())
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="No hay job para este proyecto")
    return job


@router.get("/{project_id}/output")
def get_output_video(
    project_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Sirve el video final con soporte de Range Requests.
    Necesario para que el reproductor del navegador pueda hacer seek y streaming.
    """
    from pathlib import Path
    from fastapi.responses import StreamingResponse, Response
    from app.core.config import settings

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project or project.status != "completed":
        raise HTTPException(status_code=404, detail="Video de salida no disponible")

    output_dir = settings.output_path / project_id
    mp4_files = list(output_dir.glob("output_*.mp4"))
    if not mp4_files:
        raise HTTPException(status_code=404, detail="Archivo de salida no encontrado")

    video_path = mp4_files[0]
    file_size = video_path.stat().st_size

    range_header = request.headers.get("range")

    if range_header:
        # Parsear Range: bytes=start-end
        try:
            range_val = range_header.replace("bytes=", "")
            parts = range_val.split("-")
            start = int(parts[0])
            end = int(parts[1]) if parts[1] else file_size - 1
        except Exception:
            start = 0
            end = file_size - 1

        end = min(end, file_size - 1)
        chunk_size = end - start + 1

        def iter_file(path: Path, s: int, e: int):
            with path.open("rb") as f:
                f.seek(s)
                remaining = e - s + 1
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
            "Content-Disposition": f'inline; filename="faceswap_{project_id}.mp4"',
        }
        return StreamingResponse(
            iter_file(video_path, start, end),
            status_code=206,
            media_type="video/mp4",
            headers=headers,
        )

    # Sin Range header — devolver el archivo completo
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
        "Content-Disposition": f'inline; filename="faceswap_{project_id}.mp4"',
    }

    def iter_full(path: Path):
        with path.open("rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        iter_full(video_path),
        status_code=200,
        media_type="video/mp4",
        headers=headers,
    )
