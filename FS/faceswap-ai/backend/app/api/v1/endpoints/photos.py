"""Endpoints para carga de fotografías de reemplazo."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.storage import ensure_project_dirs
from app.models.project import Project, FaceAssignment
from app.services.photo_service import validate_photo_has_face

router = APIRouter()

ACCEPTED_PHOTO_MIMES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/{project_id}/photos")
async def upload_replacement_photo(
    project_id: str,
    file: UploadFile = File(...),
    person_id: str = Form(...),
    db: Session = Depends(get_db),
):
    """Sube una fotografía de reemplazo y la valida (debe contener un rostro)."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    if file.content_type not in ACCEPTED_PHOTO_MIMES:
        raise HTTPException(
            status_code=400,
            detail=f"Formato de imagen no admitido: {file.content_type}",
        )

    ensure_project_dirs(project_id)
    ext = Path(file.filename or "photo.jpg").suffix.lstrip(".").lower() or "jpg"
    safe_name = f"{person_id}_{uuid.uuid4()}.{ext}"
    dest_path = settings.thumbnail_path / project_id / safe_name
    # Siempre guardar ruta absoluta para que el worker la encuentre
    dest_path_abs = dest_path.resolve()

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:   # 10 MB máx para fotos
        raise HTTPException(status_code=413, detail="La imagen supera 10 MB")

    with dest_path_abs.open("wb") as f:
        f.write(content)

    # Validar que la imagen contiene un rostro real
    validated = False
    try:
        validated = validate_photo_has_face(str(dest_path_abs))
    except Exception as e:
        logger.warning(f"Error en validación: {e}")
        validated = False

    # NO forzar validated=True — si no hay cara, el usuario debe subir otra foto

    photo_url = f"/api/v1/projects/{project_id}/photos/{person_id}/image"
    photo_id = str(uuid.uuid4())

    # Actualizar o crear la asignación
    assignment = (
        db.query(FaceAssignment)
        .filter(
            FaceAssignment.project_id == project_id,
            FaceAssignment.person_id == person_id,
        )
        .first()
    )

    if assignment:
        if assignment.photo_path:
            Path(assignment.photo_path).unlink(missing_ok=True)
        assignment.photo_filename = safe_name
        assignment.photo_path = str(dest_path_abs)
        assignment.photo_url = photo_url
        assignment.photo_id = photo_id
        assignment.validated = validated
    else:
        assignment = FaceAssignment(
            id=str(uuid.uuid4()),
            project_id=project_id,
            person_id=person_id,
            photo_filename=safe_name,
            photo_path=str(dest_path_abs),
            photo_url=photo_url,
            photo_id=photo_id,
            validated=validated,
        )
        db.add(assignment)

    if project.status == "detection_complete":
        project.status = "assigning"

    db.commit()

    return {
        "photoId": photo_id,
        "url": photo_url,
        "validated": validated,
    }


@router.get("/{project_id}/photos/{person_id}/image")
def get_replacement_photo(
    project_id: str, person_id: str, db: Session = Depends(get_db)
):
    """Sirve la imagen de reemplazo."""
    from fastapi.responses import FileResponse

    assignment = (
        db.query(FaceAssignment)
        .filter(
            FaceAssignment.project_id == project_id,
            FaceAssignment.person_id == person_id,
        )
        .first()
    )
    if not assignment or not assignment.photo_path:
        raise HTTPException(status_code=404, detail="Foto no encontrada")
    path = Path(assignment.photo_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado en disco")
    return FileResponse(str(path))


@router.delete("/{project_id}/photos/{person_id}")
def delete_replacement_photo(
    project_id: str, person_id: str, db: Session = Depends(get_db)
):
    """Elimina la fotografía de reemplazo de una persona."""
    assignment = (
        db.query(FaceAssignment)
        .filter(
            FaceAssignment.project_id == project_id,
            FaceAssignment.person_id == person_id,
        )
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")
    if assignment.photo_path:
        Path(assignment.photo_path).unlink(missing_ok=True)
    assignment.photo_filename = None
    assignment.photo_path = None
    assignment.photo_url = None
    assignment.photo_id = None
    assignment.validated = False
    db.commit()
    return {"ok": True}
