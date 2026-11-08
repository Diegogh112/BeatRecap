"""
Servicio de detección y agrupación de rostros.

Pipeline:
1. Extraer frames de muestra del video.
2. Detectar todos los rostros en cada frame (InsightFace SCRFD).
3. Extraer embeddings ArcFace por cada rostro detectado.
4. Deduplicar detecciones del mismo rostro en el mismo frame (NMS).
5. Agrupar los embeddings por similitud (AgglomerativeClustering con merge de clusters cercanos).
6. Asignar identidades: persona_1, persona_2, …
7. Generar thumbnails representativos por identidad.
"""

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Callable

import cv2
import numpy as np
from loguru import logger

from app.core.config import settings
from app.services.video_service import extract_frames


@dataclass
class FaceDetection:
    """Un rostro detectado en un frame específico."""
    face_id: str
    frame_index: int
    frame_path: str
    bbox: Tuple[int, int, int, int]         # x, y, w, h
    confidence: float
    embedding: Optional[np.ndarray] = None   # ArcFace 512-d
    thumbnail_path: Optional[str] = None


@dataclass
class PersonCluster:
    """Grupo de detecciones que pertenecen a la misma identidad."""
    person_id: str
    person_index: int
    label: str
    detections: List[FaceDetection] = field(default_factory=list)
    mean_embedding: Optional[np.ndarray] = None
    thumbnail_path: Optional[str] = None
    thumbnail_url: Optional[str] = None


class FaceDetectionService:
    """
    Servicio principal de detección facial.
    Inicializa InsightFace una sola vez y reutiliza la instancia.
    """

    def __init__(self):
        self._app = None
        self._initialized = False

    def _initialize(self):
        if self._initialized:
            return
        try:
            from insightface.app import FaceAnalysis
            ctx_id = 0 if settings.use_gpu else -1
            providers = (
                ["DmlExecutionProvider", "CPUExecutionProvider"]
                if settings.use_gpu
                else ["CPUExecutionProvider"]
            )
            self._app = FaceAnalysis(
                name=settings.insightface_model,
                providers=providers,
            )
            self._app.prepare(ctx_id=ctx_id, det_size=(640, 640))
            self._initialized = True
            logger.info(f"InsightFace inicializado: modelo={settings.insightface_model}, providers={providers}")
        except ImportError:
            logger.error("InsightFace no instalado. Instala con: pip install insightface")
            raise
        except Exception as e:
            logger.error(f"Error inicializando InsightFace: {e}")
            raise

    def detect_in_frame(self, frame_path: str, frame_index: int) -> List[FaceDetection]:
        """Detecta todos los rostros en un frame y extrae sus embeddings."""
        self._initialize()
        img = cv2.imread(frame_path)
        if img is None:
            logger.warning(f"No se pudo leer frame: {frame_path}")
            return []

        try:
            faces = self._app.get(img)
        except Exception as e:
            logger.warning(f"Error detectando rostros en frame {frame_index}: {e}")
            return []

        detections = []
        for face in faces:
            if face.det_score < settings.face_detect_threshold:
                continue

            bbox = face.bbox.astype(int)
            x1, y1, x2, y2 = bbox
            w, h = x2 - x1, y2 - y1

            # Descartar detecciones demasiado pequeñas (ruido)
            if w < 30 or h < 30:
                continue

            detections.append(FaceDetection(
                face_id=str(uuid.uuid4()),
                frame_index=frame_index,
                frame_path=frame_path,
                bbox=(max(0, x1), max(0, y1), max(0, w), max(0, h)),
                confidence=float(face.det_score),
                embedding=face.normed_embedding if hasattr(face, "normed_embedding") else None,
            ))

        return detections

    @staticmethod
    def _iou(d1: FaceDetection, d2: FaceDetection) -> float:
        """IoU entre dos detecciones (mismo frame)."""
        x1 = max(d1.bbox[0], d2.bbox[0])
        y1 = max(d1.bbox[1], d2.bbox[1])
        x2 = min(d1.bbox[0] + d1.bbox[2], d2.bbox[0] + d2.bbox[2])
        y2 = min(d1.bbox[1] + d1.bbox[3], d2.bbox[1] + d2.bbox[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = d1.bbox[2] * d1.bbox[3]
        area2 = d2.bbox[2] * d2.bbox[3]
        return inter / (area1 + area2 - inter + 1e-8)

    def _deduplicate_frame(
        self, detections: List[FaceDetection], iou_threshold: float = 0.5
    ) -> List[FaceDetection]:
        """
        NMS dentro del mismo frame: si dos detecciones tienen IoU > threshold,
        conservar la de mayor confianza (evita duplicados del mismo rostro).
        """
        if len(detections) <= 1:
            return detections

        # Ordenar por confianza descendente
        sorted_dets = sorted(detections, key=lambda d: d.confidence, reverse=True)
        keep = []
        for det in sorted_dets:
            is_dup = False
            for kept in keep:
                if self._iou(det, kept) > iou_threshold:
                    is_dup = True
                    break
            if not is_dup:
                keep.append(det)
        return keep

    def cluster_by_identity(
        self,
        detections: List[FaceDetection],
        threshold: float = None,
    ) -> List[PersonCluster]:
        """
        Agrupa las detecciones por identidad usando embeddings ArcFace.

        Estrategia de dos pasos:
        1. AgglomerativeClustering con distancia coseno.
        2. Merge de clusters cuyos centroides tienen similitud > merge_threshold
           (consolida la misma persona que se dividió por variaciones de ángulo/luz).
        """
        if threshold is None:
            threshold = settings.face_cluster_threshold

        # Filtrar detecciones sin embedding
        with_embedding = [d for d in detections if d.embedding is not None]
        if not with_embedding:
            logger.warning("Sin embeddings — no se puede agrupar identidades")
            return []

        embeddings = np.array([d.embedding for d in with_embedding])

        if len(with_embedding) == 1:
            cluster = PersonCluster(
                person_id="person_1",
                person_index=1,
                label="Persona 1",
                detections=with_embedding,
                mean_embedding=embeddings[0],
            )
            return [cluster]

        # ── Paso 1: AgglomerativeClustering ────────────────────────────────
        try:
            from sklearn.cluster import AgglomerativeClustering
            # distance_threshold en espacio coseno normalizado
            # cos_dist = 1 - cos_similarity
            # threshold=0.6 → distance_threshold=0.4 (similitud > 0.6 para agrupar)
            # Usamos un threshold MÁS permisivo para evitar dividir la misma persona
            dist_threshold = 1.0 - threshold  # default: 1 - 0.6 = 0.4

            clustering = AgglomerativeClustering(
                n_clusters=None,
                distance_threshold=dist_threshold,
                metric="cosine",
                linkage="average",
            )
            labels = clustering.fit_predict(embeddings)
        except Exception as e:
            logger.error(f"Error en clustering inicial: {e}")
            labels = list(range(len(with_embedding)))

        # Construir clusters del paso 1
        cluster_map: Dict[int, List[FaceDetection]] = {}
        for det, label in zip(with_embedding, labels):
            cluster_map.setdefault(int(label), []).append(det)

        # Calcular centroides
        centroids: Dict[int, np.ndarray] = {}
        for label, dets in cluster_map.items():
            mean_emb = np.mean([d.embedding for d in dets], axis=0)
            mean_emb /= np.linalg.norm(mean_emb) + 1e-8
            centroids[label] = mean_emb

        # ── Paso 2: Merge de clusters cercanos ─────────────────────────────
        # Si dos clusters tienen centroides con similitud coseno > merge_threshold,
        # los fusionamos. Esto corrige el caso donde la misma persona se dividió
        # en clusters separados por variaciones de ángulo o iluminación.
        merge_threshold = 0.45  # similitud coseno mínima para fusionar
        labels_list = list(cluster_map.keys())
        parent = {l: l for l in labels_list}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for i in range(len(labels_list)):
            for j in range(i + 1, len(labels_list)):
                li, lj = labels_list[i], labels_list[j]
                sim = float(np.dot(centroids[li], centroids[lj]))
                if sim > merge_threshold:
                    union(li, lj)

        # Reagrupar con union-find
        merged_map: Dict[int, List[FaceDetection]] = {}
        for label in labels_list:
            root = find(label)
            merged_map.setdefault(root, []).extend(cluster_map[label])

        # Ordenar por primera aparición
        sorted_clusters = sorted(
            merged_map.items(),
            key=lambda item: min(d.frame_index for d in item[1]),
        )

        persons = []
        for idx, (_, cluster_dets) in enumerate(sorted_clusters, start=1):
            mean_emb = np.mean([d.embedding for d in cluster_dets], axis=0)
            mean_emb /= np.linalg.norm(mean_emb) + 1e-8
            persons.append(PersonCluster(
                person_id=f"person_{idx}",
                person_index=idx,
                label=f"Persona {idx}",
                detections=cluster_dets,
                mean_embedding=mean_emb,
            ))

        logger.info(f"Identidades detectadas: {len(persons)} (de {len(with_embedding)} detecciones)")
        return persons

    def generate_thumbnails(
        self,
        persons: List[PersonCluster],
        project_id: str,
        thumb_size: int = 256,
    ) -> None:
        """Genera una miniatura representativa por cada persona detectada."""
        thumb_dir = settings.thumbnail_path / project_id
        thumb_dir.mkdir(parents=True, exist_ok=True)

        for person in persons:
            # Elegir la detección con mayor confianza
            best = max(person.detections, key=lambda d: d.confidence)
            img = cv2.imread(best.frame_path)
            if img is None:
                continue

            x, y, w, h = best.bbox
            # Añadir margen del 20%
            margin = int(max(w, h) * 0.2)
            x1 = max(0, x - margin)
            y1 = max(0, y - margin)
            x2 = min(img.shape[1], x + w + margin)
            y2 = min(img.shape[0], y + h + margin)

            crop = img[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            thumb = cv2.resize(crop, (thumb_size, thumb_size))
            thumb_name = f"{person.person_id}_thumb.jpg"
            thumb_path = thumb_dir / thumb_name
            cv2.imwrite(str(thumb_path), thumb, [cv2.IMWRITE_JPEG_QUALITY, 90])

            person.thumbnail_path = str(thumb_path)
            person.thumbnail_url = f"/api/v1/thumbnails/{project_id}/{thumb_name}"

        logger.info(f"Thumbnails generados para {len(persons)} personas")


def run_detection_pipeline(
    project_id: str,
    video_path: str,
    frames_dir: str,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> List[PersonCluster]:
    """
    Pipeline completo de detección:
    1. Extrae frames de muestra.
    2. Detecta rostros en cada frame.
    3. Deduplica detecciones del mismo frame (NMS).
    4. Agrupa por identidad con merge de clusters.
    5. Genera thumbnails.
    """

    def _progress(pct: int, msg: str):
        if progress_callback:
            progress_callback(pct, msg)
        logger.info(f"[{pct}%] {msg}")

    _progress(5, "Extrayendo frames de muestra...")

    # 1 frame por segundo para el análisis inicial
    try:
        frame_paths = extract_frames(
            video_path=video_path,
            output_dir=frames_dir,
            fps=1.0,
            max_frames=300,
        )
    except Exception as e:
        logger.error(f"Error extrayendo frames: {e}")
        raise

    if not frame_paths:
        raise RuntimeError("No se pudieron extraer frames del video")

    _progress(20, f"Detectando rostros en {len(frame_paths)} frames...")

    service = FaceDetectionService()
    all_detections: List[FaceDetection] = []

    for i, frame_path in enumerate(frame_paths):
        dets = service.detect_in_frame(frame_path, i)
        # NMS dentro del frame: eliminar duplicados del mismo rostro
        dets = service._deduplicate_frame(dets, iou_threshold=0.5)
        all_detections.extend(dets)

        pct = 20 + int((i + 1) / len(frame_paths) * 40)
        if i % 10 == 0:
            _progress(pct, f"Analizando frame {i + 1}/{len(frame_paths)}")

    total_faces = len(all_detections)
    _progress(60, f"Agrupando {total_faces} detecciones por identidad...")

    if total_faces == 0:
        logger.warning("No se detectaron rostros en el video")
        return []

    # 3. Agrupar por identidad (con merge de clusters cercanos)
    persons = service.cluster_by_identity(all_detections)
    _progress(80, f"Generando miniaturas para {len(persons)} personas...")

    # 4. Generar thumbnails
    service.generate_thumbnails(persons, project_id)
    _progress(95, "Detección completada")

    return persons
