"""Router principal de la API v1."""

from fastapi import APIRouter

from app.api.v1.endpoints import projects, videos, detection, photos, processing, jobs
from app.api.v1.endpoints import settings_api

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(videos.router, prefix="/projects", tags=["videos"])
api_router.include_router(detection.router, prefix="/projects", tags=["detection"])
api_router.include_router(photos.router, prefix="/projects", tags=["photos"])
api_router.include_router(processing.router, prefix="/projects", tags=["processing"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(settings_api.router, prefix="/settings", tags=["settings"])
