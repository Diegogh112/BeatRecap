"""Endpoints para detección de rostros."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.project import Project, DetectionResult
from app.schemas.project import DetectionResultRead
from app.workers.tasks import run_face_detection

router = APIRouter()


@router.post("/{project_id}/detect")
def start_detection(project_id: str, db: Session = Depends(get_db)):
    """Inicia la detección de rostros en el video del proyecto."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not project.video:
        raise HTTPException(status_code=400, detail="El proyecto no tiene video cargado")
    if project.status not in ("video_uploaded", "detection_complete", "error"):
        raise HTTPException(
            status_code=400,
            detail=f"No se puede detectar en estado '{project.status}'",
        )

    project.status = "detecting"
    db.commit()

    # Enviar a la cola de Celery
    task = run_face_detection.delay(project_id)
    return {"jobId": task.id, "projectId": project_id, "status": "detecting"}


@router.get("/{project_id}/detection", response_model=DetectionResultRead)
def get_detection_result(project_id: str, db: Session = Depends(get_db)):
    """Obtiene el resultado de la detección de rostros."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if not project.detection_result:
        raise HTTPException(
            status_code=404,
            detail="Detección no completada aún",
        )
    return project.detection_result
