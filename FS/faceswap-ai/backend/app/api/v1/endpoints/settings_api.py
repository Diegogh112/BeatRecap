"""Endpoints para leer y actualizar la configuración de velocidad en tiempo de ejecución."""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class SpeedConfig(BaseModel):
    swap_frame_step: int       # 1=todos los frames, 10=cada 10
    apply_enhancement: bool    # True=GFPGAN activado, False=desactivado
    face_det_size: int         # 320 o 640


class SpeedConfigUpdate(BaseModel):
    swap_frame_step: Optional[int] = None
    apply_enhancement: Optional[bool] = None
    face_det_size: Optional[int] = None


@router.get("/speed", response_model=SpeedConfig)
def get_speed_config():
    """Retorna la configuración de velocidad actual."""
    from app.core.config import settings
    return SpeedConfig(
        swap_frame_step=settings.swap_frame_step,
        apply_enhancement=settings.apply_enhancement,
        face_det_size=settings.face_det_size,
    )


@router.patch("/speed", response_model=SpeedConfig)
def update_speed_config(body: SpeedConfigUpdate):
    """
    Actualiza la configuración de velocidad en memoria sin reiniciar el servidor.
    Los cambios aplican al próximo procesamiento que se inicie.
    """
    from app.core.config import settings

    if body.swap_frame_step is not None:
        if body.swap_frame_step < 1:
            body.swap_frame_step = 1
        if body.swap_frame_step > 30:
            body.swap_frame_step = 30
        object.__setattr__(settings, "swap_frame_step", body.swap_frame_step)

    if body.apply_enhancement is not None:
        object.__setattr__(settings, "apply_enhancement", body.apply_enhancement)

    if body.face_det_size is not None:
        if body.face_det_size not in (160, 320, 480, 640):
            body.face_det_size = 320
        object.__setattr__(settings, "face_det_size", body.face_det_size)

    return SpeedConfig(
        swap_frame_step=settings.swap_frame_step,
        apply_enhancement=settings.apply_enhancement,
        face_det_size=settings.face_det_size,
    )
