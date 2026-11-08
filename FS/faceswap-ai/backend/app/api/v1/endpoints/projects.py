"""Endpoints CRUD de proyectos."""

import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.storage import ensure_project_dirs
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectRead

router = APIRouter()


def _get_project_or_404(project_id: str, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return project


@router.get("", response_model=List[ProjectRead])
def list_projects(db: Session = Depends(get_db)):
    """Lista todos los proyectos ordenados por fecha de creación."""
    return (
        db.query(Project)
        .order_by(Project.created_at.desc())
        .all()
    )


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    """Crea un nuevo proyecto vacío."""
    project = Project(
        id=str(uuid.uuid4()),
        name=body.name.strip() or "Sin nombre",
        status="created",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    ensure_project_dirs(project.id)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, db: Session = Depends(get_db)):
    return _get_project_or_404(project_id, db)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    """Elimina un proyecto y todos sus archivos asociados."""
    import shutil
    from app.core.config import settings

    project = _get_project_or_404(project_id, db)
    db.delete(project)
    db.commit()

    # Limpiar archivos del proyecto
    for base in [settings.upload_path, settings.output_path, settings.thumbnail_path]:
        project_dir = base / project_id
        if project_dir.exists():
            shutil.rmtree(project_dir, ignore_errors=True)
