"""Endpoints para consultar el estado de los jobs."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.job import ProcessingJob
from app.schemas.job import ProcessingJobRead

router = APIRouter()


@router.get("/{job_id}", response_model=ProcessingJobRead)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Obtiene el estado actual de un job de procesamiento."""
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    return job
