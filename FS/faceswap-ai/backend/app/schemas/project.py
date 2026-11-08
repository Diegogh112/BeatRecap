"""Schemas Pydantic para proyectos, videos y detecciones.

El frontend espera los metadatos del video anidados bajo `.info`:
  { id, filename, originalName, url, uploadedAt, info: { duration, width, height, fps, size, format } }

Para lograrlo usamos `VideoInfoRead` con un campo `info` computado en `model_validator`.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, model_validator


class ProjectStatus(str, Enum):
    created = "created"
    video_uploaded = "video_uploaded"
    detecting = "detecting"
    detection_complete = "detection_complete"
    assigning = "assigning"
    queued = "queued"
    processing = "processing"
    completed = "completed"
    error = "error"


# ─── Video info sub-schema (anidado) ──────────────────────────────────────────

class VideoMetaInfo(BaseModel):
    """Metadatos del video tal como los espera el frontend."""
    duration: float
    width: int
    height: int
    fps: float
    size: int
    format: str


class VideoInfoRead(BaseModel):
    """
    Schema de video con campo `info` anidado, compatible con el frontend.
    Se construye desde el ORM model VideoInfo (atributos planos).
    """
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    filename: str
    original_name: str
    url: str
    uploaded_at: datetime

    # Campos planos del ORM (se usan para construir `info`)
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    size: int = 0
    format: str = ""

    # Campo anidado calculado — lo lee el frontend
    info: Optional[VideoMetaInfo] = None

    @model_validator(mode="after")
    def build_info(self) -> "VideoInfoRead":
        if self.info is None:
            self.info = VideoMetaInfo(
                duration=self.duration,
                width=self.width,
                height=self.height,
                fps=self.fps,
                size=self.size,
                format=self.format,
            )
        return self


# ─── Detección ────────────────────────────────────────────────────────────────

class DetectedPersonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    person_id: str
    label: str
    thumbnail_url: str
    face_count: int
    first_frame: int
    last_frame: int


class DetectionResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    total_persons: int
    total_frames_analyzed: int
    processing_time_ms: int
    persons: List[DetectedPersonRead]
    created_at: datetime


# ─── Asignaciones ─────────────────────────────────────────────────────────────

class FaceAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    person_id: str
    photo_url: Optional[str] = None
    photo_id: Optional[str] = None
    validated: bool = False


# ─── Proyecto ─────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: ProjectStatus
    error_message: Optional[str] = None
    output_video_url: Optional[str] = None
    output_video_size: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    video: Optional[VideoInfoRead] = None
    detection_result: Optional[DetectionResultRead] = None
    assignments: List[FaceAssignmentRead] = []
