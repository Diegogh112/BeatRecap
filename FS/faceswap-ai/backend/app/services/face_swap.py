"""
Motor de Face Swap con tracking y optimizaciones de velocidad.

Optimizaciones activas (configurables en .env):
  SWAP_FRAME_STEP   — procesar 1 de cada N frames, copiar el resto (3=velocidad x3)
  APPLY_ENHANCEMENT — activar/desactivar GFPGAN post-swap
  FACE_DET_SIZE     — resolución del detector InsightFace (320=rápido, 640=preciso)
"""

from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path
from typing import Callable, Dict, List, Optional

import cv2
import numpy as np
from loguru import logger

from app.core.config import settings
from app.services.face_tracker import FaceTracker


# ─── Motor principal ──────────────────────────────────────────────────────────

class FaceSwapEngine:
    """
    Carga modelos una sola vez y los reutiliza durante todo el procesamiento.
    det_size se puede ajustar en tiempo de inicialización.
    """

    def __init__(self, det_size: int = None):
        self._det_size = det_size or settings.face_det_size
        self._face_analyzer = None
        self._swapper = None
        self._enhancer = None
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        self._load_face_analyzer()
        self._load_swapper()
        self._load_enhancer()
        self._initialized = True
        logger.info(
            f"FaceSwapEngine listo — det_size={self._det_size}, "
            f"GPU={settings.use_gpu}, GFPGAN={self._enhancer is not None}"
        )

    def _get_providers(self) -> list:
        """Retorna los providers en orden de preferencia."""
        if settings.use_gpu:
            return ["DmlExecutionProvider", "CPUExecutionProvider"]
        return ["CPUExecutionProvider"]

    def _load_face_analyzer(self) -> None:
        from insightface.app import FaceAnalysis
        providers = self._get_providers()
        # ctx_id=0 para DirectML/GPU, -1 para CPU
        ctx_id = 0 if settings.use_gpu else -1
        self._face_analyzer = FaceAnalysis(
            name=settings.insightface_model,
            providers=providers,
        )
        self._face_analyzer.prepare(
            ctx_id=ctx_id,
            det_size=(self._det_size, self._det_size),
        )
        logger.info(f"FaceAnalyzer listo (providers={providers}, det_size={self._det_size}×{self._det_size})")

    def _load_swapper(self) -> None:
        model_path = settings.inswapper_model_path
        if not model_path.exists():
            raise FileNotFoundError(
                f"Modelo InSwapper no encontrado: {model_path}\n"
                "Descarga 'inswapper_128.onnx' y colócalo en backend/models/"
            )
        from insightface.model_zoo import get_model
        providers = self._get_providers()
        self._swapper = get_model(str(model_path), providers=providers)
        logger.info(f"InSwapper cargado con providers={providers}: {model_path.name}")

    def _load_enhancer(self) -> None:
        """Carga GFPGAN solo si apply_enhancement está activo en config."""
        if not settings.apply_enhancement:
            logger.info("GFPGAN desactivado (APPLY_ENHANCEMENT=false) — modo rápido")
            self._enhancer = None
            return

        model_path = settings.gfpgan_model_path
        if not model_path.exists():
            logger.warning(f"Modelo GFPGAN no encontrado ({model_path.name}) — sin mejora de calidad")
            self._enhancer = None
            return
        try:
            from gfpgan import GFPGANer
            self._enhancer = GFPGANer(
                model_path=str(model_path),
                upscale=1,
                arch="clean",
                channel_multiplier=2,
                bg_upsampler=None,
            )
            logger.info(f"GFPGAN listo: {model_path.name}")
        except ImportError:
            logger.warning("GFPGAN no instalado — sin mejora de calidad")
            self._enhancer = None

    # ─── API pública ──────────────────────────────────────────────────────────

    def get_faces(self, img: np.ndarray) -> list:
        try:
            return self._face_analyzer.get(img)
        except Exception as e:
            logger.warning(f"Error detectando rostros: {e}")
            return []

    def swap_face(
        self,
        target_frame: np.ndarray,
        target_face,
        source_img: np.ndarray,
        source_face,
    ) -> np.ndarray:
        try:
            return self._swapper.get(target_frame, target_face, source_face, paste_back=True)
        except Exception as e:
            logger.warning(f"Error en InSwapper: {e}")
            return target_frame

    def enhance(self, frame: np.ndarray) -> np.ndarray:
        if self._enhancer is None:
            return frame
        try:
            _, _, enhanced = self._enhancer.enhance(
                frame,
                has_aligned=False,
                only_center_face=False,
                paste_back=True,
            )
            return enhanced if enhanced is not None else frame
        except Exception as e:
            logger.warning(f"Error en GFPGAN: {e}")
            return frame

    @property
    def enhancement_active(self) -> bool:
        return self._enhancer is not None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _load_source_faces(
    engine: FaceSwapEngine,
    source_face_paths: Dict[str, str],
) -> Dict[str, tuple]:
    """
    Pre-carga fotos de reemplazo y extrae el Face object de cada una.
    Intenta múltiples estrategias si la detección estándar falla.
    """
    source_faces: Dict[str, tuple] = {}

    for person_id, photo_path in source_face_paths.items():
        img = cv2.imread(photo_path)
        if img is None:
            logger.warning(f"No se pudo leer foto: {photo_path}")
            continue

        face = _detect_face_robust(engine, img, photo_path)
        if face is not None:
            source_faces[person_id] = (img, face)
            logger.info(f"Foto cargada para {person_id}: {Path(photo_path).name}")
        else:
            logger.error(f"No se detectó rostro en foto de {person_id} tras todos los intentos: {photo_path}")

    return source_faces


def _detect_face_robust(engine: FaceSwapEngine, img, photo_path: str):
    """
    Detecta un rostro en la foto de reemplazo para extraer el objeto Face.
    Usa múltiples estrategias, siempre con CPU (más estable para fotos).
    Retorna el objeto Face de InsightFace o None si falla todo.
    """
    import cv2

    # Siempre usar CPU para detección en fotos de origen (más estable que DML)
    try:
        from insightface.app import FaceAnalysis
        from app.core.config import settings as cfg

        def _run_detection(test_img, det_size: int, threshold: float):
            app = FaceAnalysis(
                name=cfg.insightface_model,
                providers=["CPUExecutionProvider"],
            )
            app.prepare(ctx_id=-1, det_size=(det_size, det_size))
            faces = app.get(test_img)
            if faces:
                valid = [f for f in faces if f.det_score >= threshold]
                if valid:
                    return max(valid, key=lambda f: (f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]))
            return None

        h, w = img.shape[:2]

        # Intento 1: 640px, threshold 0.3
        face = _run_detection(img, 640, 0.3)
        if face:
            logger.info(f"Cara de origen detectada (640, score={face.det_score:.2f})")
            return face

        # Intento 2: upscale si la imagen es pequeña
        if min(h, w) < 512:
            scale = 512 / min(h, w)
            img_up = cv2.resize(img, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_LINEAR)
            face = _run_detection(img_up, 640, 0.2)
            if face:
                logger.info(f"Cara de origen detectada (640 upscaled, score={face.det_score:.2f})")
                return face

        # Intento 3: threshold muy bajo 0.1
        face = _run_detection(img, 320, 0.1)
        if face:
            logger.info(f"Cara de origen detectada (320, thr=0.1, score={face.det_score:.2f})")
            return face

        # Intento 4: Haar crop → InsightFace
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray_eq = cv2.equalizeHist(gray)
        detector = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        bboxes = detector.detectMultiScale(gray_eq, scaleFactor=1.05, minNeighbors=2, minSize=(20, 20))
        if len(bboxes) > 0:
            x, y, wb, hb = bboxes[0]
            margin = int(max(wb, hb) * 0.4)
            x1, y1 = max(0, x-margin), max(0, y-margin)
            x2, y2 = min(img.shape[1], x+wb+margin), min(img.shape[0], y+hb+margin)
            crop = img[y1:y2, x1:x2]
            crop_r = cv2.resize(crop, (320, 320), interpolation=cv2.INTER_LINEAR)
            face = _run_detection(crop_r, 320, 0.05)
            if face:
                # Retornar la detección sobre la imagen completa en vez del crop
                face_full = _run_detection(img, 640, 0.05)
                result = face_full if face_full else face
                logger.info(f"Cara de origen detectada (Haar+crop, score={result.det_score:.2f})")
                return result

    except Exception as e:
        logger.error(f"Error en _detect_face_robust: {e}")

    logger.warning(f"No se pudo detectar cara de origen en: {photo_path}")
    return None


# ─── Pipeline principal ───────────────────────────────────────────────────────

def process_video_frames(
    frames_dir: str,
    output_frames_dir: str,
    person_embeddings: Dict[str, np.ndarray],
    source_face_paths: Dict[str, str],
    frame_step: int = None,
    apply_enhancement: bool = None,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> int:
    """
    Procesa frames con face swap aplicando las tres optimizaciones:

    1. FRAME STEP (skip + copy-forward):
       Solo se procesa 1 de cada `frame_step` frames con el motor de IA.
       Los frames intermedios copian el resultado del frame procesado anterior.
       Esto es transparente porque entre frames consecutivos la cara
       prácticamente no cambia de posición.

    2. SIN GFPGAN:
       Si apply_enhancement=False, se salta el paso de mejora de calidad,
       que consume ~30% del tiempo total por frame.

    3. DET_SIZE 320:
       El detector InsightFace se inicializa con 320×320 en vez de 640×640,
       lo que reduce el tiempo de detección ~2x con mínima pérdida de precisión.

    Retorna el número de frames de salida escritos.
    """
    # Usar valores de config si no se pasan explícitamente
    if frame_step is None:
        frame_step = settings.swap_frame_step
    if apply_enhancement is None:
        apply_enhancement = settings.apply_enhancement

    frames_path = Path(frames_dir)
    output_path = Path(output_frames_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    frame_files = sorted(frames_path.glob("frame_*.png"))
    total = len(frame_files)
    if total == 0:
        raise RuntimeError(f"No hay frames en: {frames_dir}")

    # Frames que se van a procesar con IA vs. los que se copian
    key_frame_indices = set(range(0, total, frame_step))
    frames_to_process = len(key_frame_indices)
    frames_to_copy = total - frames_to_process

    def _cb(pct: int, msg: str) -> None:
        if progress_callback:
            progress_callback(pct, msg)
        logger.info(f"[swap {pct}%] {msg}")

    logger.info(
        f"Frame step={frame_step} | "
        f"Procesando {frames_to_process}/{total} frames "
        f"({frames_to_copy} copiados) | "
        f"Enhancement={'on' if apply_enhancement else 'off'} | "
        f"det_size={settings.face_det_size}"
    )

    # ── Inicializar motor ─────────────────────────────────────────────────────
    _cb(0, "Inicializando motor de IA...")
    engine = FaceSwapEngine(det_size=settings.face_det_size)
    engine.initialize()

    _cb(2, "Cargando fotografías de reemplazo...")
    source_faces = _load_source_faces(engine, source_face_paths)
    if not source_faces:
        # Último recurso: intentar con CPU provider aunque el motor use DML
        logger.warning("DML no detectó rostros en las fotos — reintentando con CPU provider")
        engine_cpu = FaceSwapEngine(det_size=640)
        # Forzar CPU para la carga de fotos de origen
        engine_cpu._face_analyzer = engine._face_analyzer  # reusar si ya está cargado
        source_faces = _load_source_faces(engine_cpu, source_face_paths)

    if not source_faces:
        raise RuntimeError(
            "No se pudo detectar ningún rostro en las fotografías de reemplazo. "
            "Asegúrate de que la foto muestre claramente el rostro de frente, "
            "con buena iluminación y sin obstrucciones."
        )

    _cb(3, "Inicializando tracker de identidades...")
    tracker = FaceTracker(
        person_reference_embeddings=person_embeddings,
        max_lost_frames=max(30, frame_step * 3),   # escalar con el step
        emb_sim_threshold=0.35,
    )

    # ── Bucle principal ───────────────────────────────────────────────────────
    _cb(5, f"Procesando {frames_to_process} frames clave de {total} totales...")

    processed = 0
    swap_count = 0
    t_start = time.time()
    last_swapped: Optional[np.ndarray] = None   # último frame con swap aplicado
    key_frames_done = 0                           # contador de frames procesados con IA

    for i, frame_file in enumerate(frame_files):
        out_file = output_path / frame_file.name
        is_key_frame = (i in key_frame_indices)

        if not is_key_frame:
            # ── Frame de relleno: copiar el resultado anterior ────────────────
            if last_swapped is not None:
                cv2.imwrite(str(out_file), last_swapped, [cv2.IMWRITE_PNG_COMPRESSION, 1])
            else:
                # Todavía no hay ningún frame procesado — copiar el original
                shutil.copy(str(frame_file), str(out_file))
            processed += 1
            continue

        # ── Key frame: procesar con IA ────────────────────────────────────────
        frame = cv2.imread(str(frame_file))
        if frame is None:
            shutil.copy(str(frame_file), str(out_file))
            processed += 1
            continue

        result = frame.copy()
        has_swap = False

        detected_faces = engine.get_faces(frame)

        if detected_faces:
            det_list = []
            for face in detected_faces:
                if face.det_score < settings.face_detect_threshold:
                    continue
                if face.normed_embedding is None:
                    continue
                x1, y1, x2, y2 = face.bbox.astype(int)
                det_list.append({
                    "face_id": str(uuid.uuid4()),
                    "bbox": (x1, y1, x2, y2),
                    "embedding": face.normed_embedding,
                    "confidence": float(face.det_score),
                    "_face_obj": face,
                })

            assignments = tracker.update(det_list)
            assignment_map = {a.face_id: a.person_id for a in assignments}

            for det in det_list:
                person_id = assignment_map.get(det["face_id"])
                if person_id is None or person_id not in source_faces:
                    continue
                source_img, source_face_obj = source_faces[person_id]
                result = engine.swap_face(result, det["_face_obj"], source_img, source_face_obj)
                has_swap = True

        if has_swap:
            if apply_enhancement and engine.enhancement_active:
                result = engine.enhance(result)
            swap_count += 1

        cv2.imwrite(str(out_file), result, [cv2.IMWRITE_PNG_COMPRESSION, 1])
        last_swapped = result    # guardar para los frames de relleno siguientes
        processed += 1
        key_frames_done += 1

        # Progreso cada 3 key frames — basado en los key frames restantes
        if key_frames_done % 3 == 0 or key_frames_done == frames_to_process:
            pct = 5 + int(key_frames_done / frames_to_process * 90)
            elapsed = time.time() - t_start
            if elapsed > 0 and key_frames_done > 1:
                kf_per_sec = key_frames_done / elapsed
                kf_remaining = frames_to_process - key_frames_done
                eta_secs = int(kf_remaining / kf_per_sec)
                if eta_secs < 60:
                    eta_str = f"~{eta_secs}s restantes"
                else:
                    eta_str = f"~{eta_secs // 60}m {eta_secs % 60}s restantes"
            else:
                eta_str = ""
            _cb(
                pct,
                f"Frame clave {key_frames_done}/{frames_to_process} "
                f"({i + 1}/{total} total) — {swap_count} swaps — {eta_str}".strip(" —"),
            )

    _cb(95, f"Completado: {processed}/{total} frames escritos, {swap_count} swaps aplicados")
    return processed
