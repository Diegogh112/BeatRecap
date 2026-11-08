"""Schemas Pydantic para trabajos de procesamiento."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProcessingJobStatus(str, Enum):
    queued = "queued"
    extracting_frames = "extracting_frames"
    detecting_faces = "detecting_faces"
    tracking_faces = "tracking_faces"
    swapping_faces = "swapping_faces"
    enhancing = "enhancing"
    reconstructing_video = "reconstructing_video"
    finalizing = "finalizing"
    completed = "completed"
    error = "error"


class ProcessingJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    status: ProcessingJobStatus
    progress: int
    current_stage: str
    estimated_seconds: Optional[int]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime


class StartProcessingRequest(BaseModel):
    assignments: dict  # {person_id: photo_id}
