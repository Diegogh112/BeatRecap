"""Modelos SQLAlchemy para proyectos, videos y detecciones."""

import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime,
    ForeignKey, Text, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="created"
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_video_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    output_video_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    # Relaciones
    video: Mapped[Optional["VideoInfo"]] = relationship(
        "VideoInfo", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    detection_result: Mapped[Optional["DetectionResult"]] = relationship(
        "DetectionResult",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )
    assignments: Mapped[List["FaceAssignment"]] = relationship(
        "FaceAssignment", back_populates="project", cascade="all, delete-orphan"
    )
    jobs: Mapped[List["ProcessingJob"]] = relationship(
        "ProcessingJob", back_populates="project", cascade="all, delete-orphan"
    )


class VideoInfo(Base):
    __tablename__ = "video_infos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), unique=True
    )
    filename: Mapped[str] = mapped_column(String(512))
    original_name: Mapped[str] = mapped_column(String(512))
    file_path: Mapped[str] = mapped_column(String(1024))
    url: Mapped[str] = mapped_column(String(1024))
    duration: Mapped[float] = mapped_column(Float)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    fps: Mapped[float] = mapped_column(Float)
    size: Mapped[int] = mapped_column(Integer)        # bytes
    format: Mapped[str] = mapped_column(String(10))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    project: Mapped["Project"] = relationship("Project", back_populates="video")


class DetectionResult(Base):
    __tablename__ = "detection_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), unique=True
    )
    total_persons: Mapped[int] = mapped_column(Integer, default=0)
    total_frames_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    processing_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    project: Mapped["Project"] = relationship(
        "Project", back_populates="detection_result"
    )
    persons: Mapped[List["DetectedPerson"]] = relationship(
        "DetectedPerson",
        back_populates="detection_result",
        cascade="all, delete-orphan",
        order_by="DetectedPerson.person_index",
    )


class DetectedPerson(Base):
    __tablename__ = "detected_persons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    detection_result_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("detection_results.id", ondelete="CASCADE")
    )
    person_id: Mapped[str] = mapped_column(String(50))   # "person_1", "person_2"…
    person_index: Mapped[int] = mapped_column(Integer)    # 1, 2, 3…
    label: Mapped[str] = mapped_column(String(100))       # "Persona 1"
    thumbnail_url: Mapped[str] = mapped_column(String(1024))
    thumbnail_path: Mapped[str] = mapped_column(String(1024))
    face_count: Mapped[int] = mapped_column(Integer, default=1)
    first_frame: Mapped[int] = mapped_column(Integer, default=0)
    last_frame: Mapped[int] = mapped_column(Integer, default=0)
    # Embedding representativo (media de todos los embeddings del cluster)
    embedding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON

    detection_result: Mapped["DetectionResult"] = relationship(
        "DetectionResult", back_populates="persons"
    )


class FaceAssignment(Base):
    __tablename__ = "face_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE")
    )
    person_id: Mapped[str] = mapped_column(String(50))
    photo_filename: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    photo_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    photo_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    photo_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    validated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    project: Mapped["Project"] = relationship("Project", back_populates="assignments")
