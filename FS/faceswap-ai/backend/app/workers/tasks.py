"""
Tareas Celery para procesamiento asíncrono.

Cada tarea actualiza el estado en la BD en tiempo real para que el frontend
pueda hacer polling y mostrar el progreso sin bloquear la UI.
"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from celery import Task
from loguru import logger

from app.workers.celery_app import celery_app
from app.core.config import settings


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_db():
    from app.core.database import SessionLocal
    return SessionLocal()


def _update_job(db, job_id: str, commit: bool = True, **kwargs) -> None:
    from app.models.job import ProcessingJob
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if job:
        for k, v in kwargs.items():
            setattr(job, k, v)
        job.updated_at = datetime.now(timezone.utc)
        if commit:
            db.commit()


def _update_project(db, project_id: str, commit: bool = True, **kwargs) -> None:
    from app.models.project import Project
    p = db.query(Project).filter(Project.id == project_id).first()
    if p:
        for k, v in kwargs.items():
            setattr(p, k, v)
        p.updated_at = datetime.now(timezone.utc)
        if commit:
            db.commit()


def _safe_close(db) -> None:
    try:
        db.close()
    except Exception:
        pass


# ─── Tarea 1: Detección de rostros ────────────────────────────────────────────

@celery_app.task(bind=True, name="app.workers.tasks.run_face_detection",
                 max_retries=1, default_retry_delay=10)
def run_face_detection(self: Task, project_id: str) -> Dict[str, Any]:
    """
    Detecta y agrupa identidades en el video del proyecto.
    Guarda DetectionResult + DetectedPersons + FaceAssignments vacías en BD.
    """
    import time
    start_ms = int(time.time() * 1000)
    db = _get_db()

    try:
        from app.models.project import (
            Project, DetectionResult, DetectedPerson, FaceAssignment
        )
        from app.services.face_detection import run_detection_pipeline

        project = db.query(Project).filter(Project.id == project_id).first()
        if not project or not project.video:
            raise ValueError(f"Proyecto o video no encontrado: {project_id}")

        video_path = project.video.file_path
        frames_dir = str(settings.thumbnail_path / project_id / "detect_frames")

        def on_progress(pct: int, msg: str) -> None:
            logger.info(f"[Det {project_id}] {pct}% — {msg}")
            # Actualizar BD para que el frontend pueda ver progreso
            _update_job_if_exists(project_id, pct, msg)

        def _update_job_if_exists(pid: str, pct: int, msg: str) -> None:
            """Actualiza si existe un job en BD; no falla si no hay."""
            _db2 = _get_db()
            try:
                from app.models.job import ProcessingJob
                job = (
                    _db2.query(ProcessingJob)
                    .filter(ProcessingJob.project_id == pid)
                    .order_by(ProcessingJob.created_at.desc())
                    .first()
                )
                if job:
                    job.progress = pct
                    job.current_stage = msg
                    job.updated_at = datetime.now(timezone.utc)
                    _db2.commit()
            finally:
                _safe_close(_db2)

        persons = run_detection_pipeline(
            project_id=project_id,
            video_path=video_path,
            frames_dir=frames_dir,
            progress_callback=on_progress,
        )

        elapsed_ms = int(time.time() * 1000) - start_ms
        frame_count = len(list(Path(frames_dir).glob("frame_*.jpg")))

        # Limpiar resultado previo
        if project.detection_result:
            db.delete(project.detection_result)
            db.flush()

        det_result = DetectionResult(
            id=str(uuid.uuid4()),
            project_id=project_id,
            total_persons=len(persons),
            total_frames_analyzed=frame_count,
            processing_time_ms=elapsed_ms,
        )
        db.add(det_result)
        db.flush()

        for person in persons:
            emb_json = (
                json.dumps(person.mean_embedding.tolist())
                if person.mean_embedding is not None
                else None
            )
            db.add(DetectedPerson(
                id=str(uuid.uuid4()),
                detection_result_id=det_result.id,
                person_id=person.person_id,
                person_index=person.person_index,
                label=person.label,
                thumbnail_url=person.thumbnail_url or "",
                thumbnail_path=person.thumbnail_path or "",
                face_count=len(person.detections),
                first_frame=min(d.frame_index for d in person.detections) if person.detections else 0,
                last_frame=max(d.frame_index for d in person.detections) if person.detections else 0,
                embedding=emb_json,
            ))

        # Asignaciones vacías para cada persona detectada
        db.query(FaceAssignment).filter(FaceAssignment.project_id == project_id).delete()
        for person in persons:
            db.add(FaceAssignment(
                id=str(uuid.uuid4()),
                project_id=project_id,
                person_id=person.person_id,
                validated=False,
            ))

        project.status = "detection_complete"
        project.updated_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(f"[Det {project_id}] Completado: {len(persons)} personas en {elapsed_ms}ms")
        return {"project_id": project_id, "total_persons": len(persons)}

    except Exception as e:
        logger.error(f"[Det {project_id}] Error: {e}")
        _update_project(db, project_id, status="error", error_message=str(e))
        raise self.retry(exc=e, countdown=5) if self.request.retries < self.max_retries else e
    finally:
        _safe_close(db)


# ─── Tarea 2: Face Swap completo ──────────────────────────────────────────────

@celery_app.task(bind=True, name="app.workers.tasks.run_face_swap",
                 max_retries=0, soft_time_limit=7200, time_limit=7800)
def run_face_swap(
    self: Task,
    project_id: str,
    job_id: str,
    assignments: Dict[str, str],   # {person_id: photo_id}
) -> Dict[str, Any]:
    """
    Tarea principal de face swap.

    Etapas:
      1. extracting_frames   — FFmpeg extrae todos los frames del video.
      2. detecting_faces     — Construir embeddings de referencia.
      3. tracking_faces      — Inicializar tracker.
      4. swapping_faces      — Procesar frame a frame con InSwapper + Tracker.
      5. enhancing           — GFPGAN (integrado en swapping_faces).
      6. reconstructing_video— FFmpeg reensambla video + audio.
      7. finalizing          — Guardar ruta, actualizar BD.
    """
    import numpy as np
    db = _get_db()

    # ── Helper local para actualizar job ──────────────────────────────────────
    def _prog(pct: int, stage_key: str, stage_label: str, eta_secs: int = None) -> None:
        _db = _get_db()
        try:
            _update_job(_db, job_id,
                        status=stage_key,
                        progress=pct,
                        current_stage=stage_label,
                        estimated_seconds=eta_secs)
            _update_project(_db, project_id, status="processing")
        finally:
            _safe_close(_db)
        logger.info(f"[Swap {project_id}] {pct}% — {stage_label}")

    try:
        from app.models.project import Project, FaceAssignment
        from app.services.video_service import extract_all_frames, reconstruct_video
        from app.services.face_swap import process_video_frames

        # ── 1. Extraer todos los frames ───────────────────────────────────────
        _prog(3, "extracting_frames", "Extrayendo fotogramas del video")

        _db = _get_db()
        project = _db.query(Project).filter(Project.id == project_id).first()
        if not project or not project.video:
            raise ValueError(f"Proyecto no encontrado: {project_id}")
        video_path = project.video.file_path
        fps = project.video.fps
        det_result = project.detection_result
        if not det_result:
            raise ValueError("Sin resultado de detección")
        _safe_close(_db)

        project_work_dir = settings.output_path / project_id
        project_work_dir.mkdir(parents=True, exist_ok=True)
        frames_input_dir = str(project_work_dir / "frames_input")
        frames_output_dir = str(project_work_dir / "frames_output")

        frame_paths = extract_all_frames(video_path, frames_input_dir)
        total_frames = len(frame_paths)
        logger.info(f"[Swap {project_id}] {total_frames} frames extraídos")

        # ── 2. Construir embeddings de referencia ─────────────────────────────
        # ETA calculado sobre key frames reales (frame_step aplicado)
        key_frames = max(1, total_frames // settings.swap_frame_step)
        secs_per_kf = 0.8 if settings.use_gpu else 3.0
        eta = int(key_frames * secs_per_kf)
        mode_label = (
            f"step={settings.swap_frame_step} | "
            f"det={settings.face_det_size}px | "
            f"GFPGAN={'on' if settings.apply_enhancement else 'off'}"
        )
        _prog(10, "detecting_faces",
              f"Preparando embeddings ({total_frames} frames → {key_frames} a procesar | {mode_label})",
              eta)

        _db = _get_db()
        det_result_fresh = _db.query(Project).filter(Project.id == project_id).first()
        person_embeddings: Dict[str, np.ndarray] = {}
        if det_result_fresh and det_result_fresh.detection_result:
            for person in det_result_fresh.detection_result.persons:
                if person.embedding:
                    emb = np.array(json.loads(person.embedding), dtype=np.float32)
                    norm = np.linalg.norm(emb)
                    person_embeddings[person.person_id] = emb / (norm + 1e-8)
        _safe_close(_db)

        if not person_embeddings:
            raise ValueError("No se encontraron embeddings de referencia")

        # ── 3. Construir rutas de fotos de reemplazo ──────────────────────────
        _prog(12, "tracking_faces", "Cargando fotografías de reemplazo")

        _db = _get_db()
        source_face_paths: Dict[str, str] = {}
        for person_id in assignments:
            fa = (
                _db.query(FaceAssignment)
                .filter(
                    FaceAssignment.project_id == project_id,
                    FaceAssignment.person_id == person_id,
                )
                .first()
            )
            if fa and fa.photo_path and Path(fa.photo_path).exists():
                source_face_paths[person_id] = fa.photo_path
            else:
                logger.warning(f"Foto no encontrada para {person_id}")
        _safe_close(_db)

        if not source_face_paths:
            raise ValueError("No hay fotos de reemplazo válidas")

        # ── 4 + 5. Swap + Enhancement ─────────────────────────────────────────
        _prog(15, "swapping_faces",
              f"Intercambiando rostros — {key_frames} frames clave de {total_frames} totales",
              eta)

        import re
        def on_swap_progress(pct: int, msg: str) -> None:
            # pct: 0→100 desde process_video_frames
            # mapeamos a 15→82 en el total del job
            mapped = 15 + int(pct * 0.67)
            # Extraer ETA del mensaje si está presente
            eta_match = re.search(r'~(\d+)m\s*(\d+)?s?\s*restantes', msg)
            eta_val = None
            if eta_match:
                mins = int(eta_match.group(1))
                secs = int(eta_match.group(2)) if eta_match.group(2) else 0
                eta_val = mins * 60 + secs
            else:
                eta_match2 = re.search(r'~(\d+)s\s*restantes', msg)
                if eta_match2:
                    eta_val = int(eta_match2.group(1))
            _prog(mapped, "swapping_faces", msg, eta_val)

        processed_count = process_video_frames(
            frames_dir=frames_input_dir,
            output_frames_dir=frames_output_dir,
            person_embeddings=person_embeddings,
            source_face_paths=source_face_paths,
            frame_step=settings.swap_frame_step,
            apply_enhancement=settings.apply_enhancement,
            progress_callback=on_swap_progress,
        )
        logger.info(f"[Swap {project_id}] {processed_count} frames procesados")

        # ── 6. Reconstruir video ──────────────────────────────────────────────
        _prog(83, "reconstructing_video",
              "Reconstruyendo video con audio original")

        output_video_path = str(project_work_dir / f"output_{project_id[:8]}.mp4")
        reconstruct_video(
            frames_dir=frames_output_dir,
            audio_source=video_path,
            output_path=output_video_path,
            fps=fps,
        )

        output_size = Path(output_video_path).stat().st_size
        output_url = f"/api/v1/projects/{project_id}/output"

        # ── 7. Finalizar ──────────────────────────────────────────────────────
        _prog(96, "finalizing", "Finalizando")

        _db = _get_db()
        _update_job(_db, job_id,
                    status="completed",
                    progress=100,
                    current_stage="Completado",
                    estimated_seconds=None,
                    completed_at=datetime.now(timezone.utc))
        _update_project(_db, project_id,
                        status="completed",
                        output_video_url=output_url,
                        output_video_size=output_size)
        _safe_close(_db)

        # Limpiar frames temporales
        shutil.rmtree(frames_input_dir, ignore_errors=True)
        shutil.rmtree(frames_output_dir, ignore_errors=True)

        logger.info(
            f"[Swap {project_id}] ✓ Completado — "
            f"{output_size // 1024 // 1024} MB → {output_video_path}"
        )
        return {
            "project_id": project_id,
            "output_path": output_video_path,
            "output_size": output_size,
            "processed_frames": processed_count,
        }

    except Exception as e:
        logger.error(f"[Swap {project_id}] Error: {e}", exc_info=True)
        try:
            _db = _get_db()
            _update_job(_db, job_id,
                        status="error",
                        current_stage="Error",
                        error_message=str(e)[:500])
            _update_project(_db, project_id,
                            status="error",
                            error_message=str(e)[:500])
            _safe_close(_db)
        except Exception:
            pass
        raise
    finally:
        _safe_close(db)


# ─── Tarea 3: Limpieza periódica ──────────────────────────────────────────────

@celery_app.task(name="app.workers.tasks.cleanup_old_files")
def cleanup_old_files() -> Dict[str, int]:
    """
    Elimina archivos de proyectos completados con más de RETENTION_HOURS horas.
    Se ejecuta cada 6 horas mediante Celery Beat.
    """
    from datetime import timedelta
    from app.models.project import Project

    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.retention_hours)
    db = _get_db()
    deleted = 0

    try:
        old_projects = (
            db.query(Project)
            .filter(Project.updated_at < cutoff)
            .filter(Project.status.in_(["completed", "error"]))
            .all()
        )
        for project in old_projects:
            for base in [settings.upload_path, settings.output_path, settings.thumbnail_path]:
                project_dir = base / project.id
                if project_dir.exists():
                    shutil.rmtree(project_dir, ignore_errors=True)
                    deleted += 1
        logger.info(f"Limpieza: {deleted} directorios eliminados")
        return {"deleted_dirs": deleted}
    finally:
        _safe_close(db)


# ─── Beat schedule ────────────────────────────────────────────────────────────

celery_app.conf.beat_schedule = {
    "cleanup-every-6-hours": {
        "task": "app.workers.tasks.cleanup_old_files",
        "schedule": 6 * 3600,
    },
}
