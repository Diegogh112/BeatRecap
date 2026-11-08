"""Servicio de procesamiento de video: metadatos, extracción de frames."""

import os
import shutil
import subprocess
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

from loguru import logger


# ─── Buscador de FFmpeg/FFprobe ──────────────────────────────────────────────
# En Windows, FFmpeg puede no estar en el PATH del proceso. Buscamos en
# ubicaciones conocidas (winget, chocolatey, instalación manual).

_CACHED_FFMPEG_DIR: Optional[str] = None


def _find_ffmpeg_dir() -> Optional[str]:
    """
    Busca el directorio que contiene ffmpeg.exe y ffprobe.exe.
    Retorna la ruta o None si no lo encuentra.
    Usa caché para no buscar en cada llamada.
    """
    global _CACHED_FFMPEG_DIR
    if _CACHED_FFMPEG_DIR is not None:
        return _CACHED_FFMPEG_DIR

    # 1. ¿Está en el PATH?
    for exe in ("ffprobe", "ffmpeg"):
        if shutil.which(exe):
            path = shutil.which(exe)
            d = str(Path(path).parent)
            _CACHED_FFMPEG_DIR = d
            logger.info(f"FFmpeg encontrado en PATH: {d}")
            return d

    # 2. Buscar en ubicaciones conocidas de Windows
    candidates = []

    # winget (Gyan.FFmpeg)
    winget_base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if winget_base.exists():
        candidates.extend(winget_base.glob("Gyan.FFmpeg*/ffmpeg*/bin"))

    # winget Links (symlinks)
    winget_links = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links"
    if winget_links.exists():
        candidates.append(winget_links)

    # Chocolatey
    candidates.append(Path("C:\\ProgramData\\chocolatey\\bin"))

    # Instalaciones comunes
    candidates.append(Path("C:\\ffmpeg\\bin"))
    candidates.append(Path("C:\\Program Files\\FFmpeg\\bin"))
    candidates.append(Path("C:\\Program Files (x86)\\FFmpeg\\bin"))

    # Conda/venv (a veces se instala via conda)
    conda = Path(os.environ.get("CONDA_PREFIX", "")) / "Library" / "bin"
    candidates.append(conda)

    for d in candidates:
        if d.exists() and (d / "ffprobe.exe").exists() and (d / "ffmpeg.exe").exists():
            _CACHED_FFMPEG_DIR = str(d)
            logger.info(f"FFmpeg encontrado en: {d}")
            return str(d)

    logger.warning("FFmpeg/FFprobe no encontrado en el sistema")
    return None


def _ffmpeg_bin(name: str) -> str:
    """
    Retorna la ruta completa al binario solicitado (ffmpeg o ffprobe).
    Si está en el PATH, usa el nombre corto. Si no, busca en ubicaciones conocidas.
    """
    ffmpeg_dir = _find_ffmpeg_dir()
    if ffmpeg_dir:
        full_path = str(Path(ffmpeg_dir) / f"{name}.exe")
        if Path(full_path).exists():
            return full_path
    # Fallback: usar el nombre corto y rezar que esté en el PATH
    return name


def extract_video_metadata(video_path: str) -> Dict[str, Any]:
    """
    Usa ffprobe para extraer metadatos del video.
    Retorna dict con: duration, width, height, fps, format.
    """
    ffprobe = _ffmpeg_bin("ffprobe")
    cmd = [
        ffprobe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        video_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe error: {result.stderr}")
        data = json.loads(result.stdout)
    except FileNotFoundError:
        raise RuntimeError(
            "ffprobe no encontrado. Instala FFmpeg en el sistema. "
            "Descárgalo desde https://ffmpeg.org/download.html o instala con: "
            "winget install Gyan.FFmpeg"
        )

    # Encontrar stream de video
    video_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
        None,
    )
    if not video_stream:
        raise RuntimeError("No se encontró un stream de video en el archivo.")

    # Calcular FPS
    fps = 25.0
    fps_str = video_stream.get("avg_frame_rate", "25/1")
    try:
        num, den = fps_str.split("/")
        if int(den) > 0:
            fps = round(int(num) / int(den), 2)
    except Exception:
        pass

    # Duración
    duration = float(data.get("format", {}).get("duration", 0))
    if duration == 0:
        duration = float(video_stream.get("duration", 0))

    return {
        "duration": duration,
        "width": int(video_stream.get("width", 0)),
        "height": int(video_stream.get("height", 0)),
        "fps": fps,
        "format": Path(video_path).suffix.lstrip(".").lower(),
        "codec": video_stream.get("codec_name", "unknown"),
        "bitrate": int(data.get("format", {}).get("bit_rate", 0)),
    }


def validate_video_file(video_path: str) -> bool:
    """Verifica que el archivo es un video válido."""
    try:
        meta = extract_video_metadata(video_path)
        return meta["width"] > 0 and meta["height"] > 0 and meta["duration"] > 0
    except Exception:
        return False


def extract_frames(
    video_path: str,
    output_dir: str,
    fps: float = 1.0,
    max_frames: int = 300,
) -> List[str]:
    """
    Extrae frames del video a la carpeta output_dir.
    fps: frames por segundo a extraer (1.0 = 1 por segundo).
    Retorna lista de rutas a los frames extraídos.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    pattern = str(output_path / "frame_%06d.jpg")

    ffmpeg = _ffmpeg_bin("ffmpeg")
    cmd = [
        ffmpeg,
        "-i", video_path,
        "-vf", f"fps={fps}",
        "-q:v", "2",
        "-frames:v", str(max_frames),
        "-y",
        pattern,
    ]
    logger.info(f"Extrayendo frames: {video_path} → {output_dir} @ {fps}fps")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        logger.error(f"ffmpeg extract_frames error: {result.stderr}")
        raise RuntimeError(f"Error al extraer frames: {result.stderr}")

    frames = sorted(output_path.glob("frame_*.jpg"))
    logger.info(f"Extraídos {len(frames)} frames")
    return [str(f) for f in frames]


def extract_all_frames(
    video_path: str,
    output_dir: str,
) -> List[str]:
    """
    Extrae TODOS los frames del video para el procesamiento completo.
    Usado durante el face swap final.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    pattern = str(output_path / "frame_%06d.png")

    ffmpeg = _ffmpeg_bin("ffmpeg")
    cmd = [
        ffmpeg,
        "-i", video_path,
        "-q:v", "1",
        "-y",
        pattern,
    ]
    logger.info(f"Extrayendo todos los frames de: {video_path}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0:
        raise RuntimeError(f"Error al extraer todos los frames: {result.stderr}")

    frames = sorted(output_path.glob("frame_*.png"))
    logger.info(f"Total frames extraídos: {len(frames)}")
    return [str(f) for f in frames]


def reconstruct_video(
    frames_dir: str,
    audio_source: str,
    output_path: str,
    fps: float = 25.0,
) -> str:
    """
    Reconstruye el video a partir de frames procesados y audio del original.
    """
    frames_pattern = str(Path(frames_dir) / "frame_%06d.png")

    ffmpeg = _ffmpeg_bin("ffmpeg")
    cmd = [
        ffmpeg,
        "-y",
        "-framerate", str(fps),
        "-i", frames_pattern,
        "-i", audio_source,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-map", "0:v:0",
        "-map", "1:a:0?",   # audio opcional (si el original tiene)
        "-shortest",
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        output_path,
    ]
    logger.info(f"Reconstruyendo video → {output_path}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0:
        raise RuntimeError(f"Error al reconstruir video: {result.stderr}")
    logger.info(f"Video reconstruido: {output_path}")
    return output_path
