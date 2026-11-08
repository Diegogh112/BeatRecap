"""Configuración central de la aplicación mediante pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    # ── Aplicación ─────────────────────────────────────────────────────────────
    app_name: str = "FaceSwap AI"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-this-in-production"

    # ── Base de datos ───────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./faceswap.db"

    # ── Redis / Celery ──────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # ── Almacenamiento ──────────────────────────────────────────────────────────
    upload_dir: str = "uploads"
    output_dir: str = "outputs"
    thumbnail_dir: str = "thumbnails"
    model_dir: str = "models"

    # ── Límites de video ────────────────────────────────────────────────────────
    max_video_duration: int = 300          # segundos
    max_video_size_mb: int = 2048          # MB
    allowed_video_formats: str = "mp4,mov,avi"

    # ── Retención ──────────────────────────────────────────────────────────────
    retention_hours: int = 24

    # ── IA / Hardware ───────────────────────────────────────────────────────────
    use_gpu: bool = False
    insightface_model: str = "buffalo_l"
    inswapper_model: str = "inswapper_128.onnx"
    gfpgan_model: str = "GFPGANv1.4.pth"
    face_detect_threshold: float = 0.5
    face_cluster_threshold: float = 0.5    # similitud mínima para agrupar

    # ── Optimizaciones de velocidad ─────────────────────────────────────────────
    # swap_frame_step: procesar 1 de cada N frames (1=todos, 2=cada 2, 10=cada 10)
    # En CPU sin GPU: step=10 → ~5 min para video de 30s
    swap_frame_step: int = 2
    # apply_enhancement: aplicar GFPGAN post-swap (True=mejor calidad, False=más rápido)
    apply_enhancement: bool = False
    # face_det_size: resolución del detector InsightFace (320=rápido, 640=preciso)
    face_det_size: int = 320

    # ── CORS ────────────────────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # ── Propiedades computadas ─────────────────────────────────────────────────

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir)

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir)

    @property
    def thumbnail_path(self) -> Path:
        return Path(self.thumbnail_dir)

    @property
    def model_path(self) -> Path:
        return Path(self.model_dir)

    @property
    def allowed_formats_list(self) -> List[str]:
        return [f.strip().lower() for f in self.allowed_video_formats.split(",")]

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def max_video_size_bytes(self) -> int:
        return self.max_video_size_mb * 1024 * 1024

    @property
    def inswapper_model_path(self) -> Path:
        return Path(self.model_dir) / self.inswapper_model

    @property
    def gfpgan_model_path(self) -> Path:
        return Path(self.model_dir) / self.gfpgan_model


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
