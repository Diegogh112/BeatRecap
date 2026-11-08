"""
Seguimiento de identidades entre frames (face tracking).

Implementa un tracker basado en embeddings ArcFace combinado con
un tracker de bounding boxes tipo ByteTrack/IoU para mantener la
identidad correcta de cada persona a lo largo del video, incluso cuando:
  - Una persona sale y vuelve a entrar en escena.
  - Los rostros se ocluyen parcialmente.
  - Las personas se cruzan.

El tracker asigna a cada detección de un frame su person_id
(person_1, person_2, …) usando una combinación de:
  1. Similitud de embedding ArcFace (identidad).
  2. IoU de bounding boxes (continuidad espacial).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from loguru import logger


# ─── Estructuras de datos ──────────────────────────────────────────────────────

@dataclass
class TrackedFace:
    """Una pista activa de un rostro a lo largo del video."""
    track_id: int
    person_id: str                       # "person_1", "person_2", …
    bbox: Tuple[int, int, int, int]      # x1, y1, x2, y2
    embedding: np.ndarray
    confidence: float
    last_frame: int
    lost_frames: int = 0                 # frames consecutivos sin detección
    history: List[np.ndarray] = field(default_factory=list)   # últimos N embeddings


@dataclass
class FrameAssignment:
    """Resultado del tracker para un frame."""
    face_id: str              # UUID interno de la detección
    person_id: str            # identidad asignada
    bbox: Tuple[int, int, int, int]
    confidence: float


# ─── Funciones auxiliares ──────────────────────────────────────────────────────

def _iou(b1: Tuple, b2: Tuple) -> float:
    """Intersection over Union entre dos bboxes en formato (x1, y1, x2, y2)."""
    x1 = max(b1[0], b2[0])
    y1 = max(b1[1], b2[1])
    x2 = min(b1[2], b2[2])
    y2 = min(b1[3], b2[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = max(1, (b1[2] - b1[0]) * (b1[3] - b1[1]))
    area2 = max(1, (b2[2] - b2[0]) * (b2[3] - b2[1]))
    return inter / (area1 + area2 - inter)


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Similitud coseno entre dos vectores normalizados."""
    return float(np.dot(a, b))


def _mean_embedding(history: List[np.ndarray], max_history: int = 10) -> np.ndarray:
    """Embedding medio de los últimos frames de la pista."""
    recent = history[-max_history:] if len(history) > max_history else history
    mean = np.mean(recent, axis=0)
    norm = np.linalg.norm(mean)
    return mean / (norm + 1e-8)


# ─── Tracker principal ─────────────────────────────────────────────────────────

class FaceTracker:
    """
    Tracker de identidades mediante embeddings + IoU.

    Parámetros:
        person_reference_embeddings: dict {person_id → embedding de referencia ArcFace}.
            Se construye a partir del resultado de la detección inicial.
        max_lost_frames: cuántos frames puede estar perdida una pista antes de cerrarla.
        emb_sim_threshold: similitud mínima para asociar un rostro a una pista.
        iou_threshold: IoU mínimo para asociar por posición.
        emb_weight: peso de la similitud de embedding en la puntuación final.
    """

    def __init__(
        self,
        person_reference_embeddings: Dict[str, np.ndarray],
        max_lost_frames: int = 30,
        emb_sim_threshold: float = 0.35,
        iou_threshold: float = 0.3,
        emb_weight: float = 0.7,
    ):
        self.reference_embeddings = person_reference_embeddings
        self.max_lost_frames = max_lost_frames
        self.emb_sim_threshold = emb_sim_threshold
        self.iou_threshold = iou_threshold
        self.emb_weight = emb_weight

        self.active_tracks: Dict[int, TrackedFace] = {}
        self._next_track_id = 1
        self._frame_count = 0

    def update(
        self,
        detections: List[Dict],   # [{"bbox": (x1,y1,x2,y2), "embedding": np.ndarray, "confidence": float, "face_id": str}]
    ) -> List[FrameAssignment]:
        """
        Actualiza el tracker con las detecciones del frame actual.
        Retorna la lista de asignaciones persona ↔ detección.
        """
        self._frame_count += 1
        assignments: List[FrameAssignment] = []

        # 1. Incrementar contador de frames perdidos para todas las pistas
        for track in self.active_tracks.values():
            track.lost_frames += 1

        # 2. Asociar cada detección con una pista activa o crear nueva
        unmatched_dets = list(range(len(detections)))
        matched_track_ids = set()

        if self.active_tracks and detections:
            # Calcular matriz de puntuación (detección × pista)
            track_list = list(self.active_tracks.values())
            score_matrix = np.zeros((len(detections), len(track_list)))

            for di, det in enumerate(detections):
                for ti, track in enumerate(track_list):
                    emb_sim = _cosine_sim(det["embedding"], _mean_embedding(track.history))
                    iou = _iou(det["bbox"], track.bbox)
                    score_matrix[di, ti] = (
                        self.emb_weight * emb_sim +
                        (1 - self.emb_weight) * iou
                    )

            # Asignación greedy (suficiente para face tracking)
            used_tracks = set()
            while True:
                if not unmatched_dets:
                    break
                # Mejor par (di, ti) que no haya sido usado
                best_score = -1
                best_di, best_ti = -1, -1
                for di in unmatched_dets:
                    for ti, track in enumerate(track_list):
                        if ti in used_tracks:
                            continue
                        if score_matrix[di, ti] > best_score:
                            best_score = score_matrix[di, ti]
                            best_di, best_ti = di, ti

                if best_score < self.emb_sim_threshold:
                    break

                track = track_list[best_ti]
                det = detections[best_di]
                track.bbox = det["bbox"]
                track.embedding = det["embedding"]
                track.history.append(det["embedding"])
                track.confidence = det["confidence"]
                track.last_frame = self._frame_count
                track.lost_frames = 0

                assignments.append(FrameAssignment(
                    face_id=det["face_id"],
                    person_id=track.person_id,
                    bbox=det["bbox"],
                    confidence=det["confidence"],
                ))
                unmatched_dets.remove(best_di)
                used_tracks.add(best_ti)
                matched_track_ids.add(track.track_id)

        # 3. Para detecciones sin pista: asignar identidad por referencia
        for di in unmatched_dets:
            det = detections[di]
            person_id = self._match_to_reference(det["embedding"])

            if person_id:
                # Reusar pista existente de esa persona si estaba perdida
                existing = self._find_lost_track(person_id)
                if existing:
                    existing.bbox = det["bbox"]
                    existing.embedding = det["embedding"]
                    existing.history.append(det["embedding"])
                    existing.confidence = det["confidence"]
                    existing.last_frame = self._frame_count
                    existing.lost_frames = 0
                    assignments.append(FrameAssignment(
                        face_id=det["face_id"],
                        person_id=person_id,
                        bbox=det["bbox"],
                        confidence=det["confidence"],
                    ))
                else:
                    # Nueva pista
                    track = TrackedFace(
                        track_id=self._next_track_id,
                        person_id=person_id,
                        bbox=det["bbox"],
                        embedding=det["embedding"],
                        confidence=det["confidence"],
                        last_frame=self._frame_count,
                        history=[det["embedding"]],
                    )
                    self._next_track_id += 1
                    self.active_tracks[track.track_id] = track
                    assignments.append(FrameAssignment(
                        face_id=det["face_id"],
                        person_id=person_id,
                        bbox=det["bbox"],
                        confidence=det["confidence"],
                    ))

        # 4. Cerrar pistas que llevan demasiados frames sin detección
        dead = [
            tid for tid, t in self.active_tracks.items()
            if t.lost_frames > self.max_lost_frames
        ]
        for tid in dead:
            del self.active_tracks[tid]

        return assignments

    def _match_to_reference(self, embedding: np.ndarray) -> Optional[str]:
        """Asigna la identidad más cercana del banco de referencias."""
        best_sim = -1.0
        best_person = None
        for person_id, ref_emb in self.reference_embeddings.items():
            sim = _cosine_sim(embedding, ref_emb)
            if sim > best_sim:
                best_sim = sim
                best_person = person_id
        if best_sim >= self.emb_sim_threshold:
            return best_person
        return None

    def _find_lost_track(self, person_id: str) -> Optional[TrackedFace]:
        """Busca una pista perdida para la persona dada."""
        for track in self.active_tracks.values():
            if track.person_id == person_id and track.lost_frames > 0:
                return track
        return None
