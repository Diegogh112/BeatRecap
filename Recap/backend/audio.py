"""Análisis de audio con librosa y ajuste de la rejilla de beats."""
import math
from dataclasses import dataclass
from typing import List

from . import config


@dataclass
class AudioAnalysis:
    bpm: float
    beats: List[float]
    duration: float


def analyze_audio(path: str) -> AudioAnalysis:
    """Carga el audio, valida duración y detecta BPM y beats con librosa."""
    import librosa  # import diferido: librosa no es necesario para importar este módulo

    y, sr = librosa.load(path, sr=22050, mono=True)
    duration = float(librosa.get_duration(y=y, sr=sr))

    if duration > config.MAX_AUDIO_DURATION + 0.5:
        raise ValueError(
            f"El audio dura {duration:.1f}s; el máximo es "
            f"{int(config.MAX_AUDIO_DURATION)}s."
        )

    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    if beat_frames is None or len(beat_frames) == 0:
        raise ValueError("No se detectó ritmo en el audio. Prueba con otro fragmento.")

    beats = librosa.frames_to_time(beat_frames, sr=sr)
    beats = [float(b) for b in beats if b <= duration + 1e-6]
    if not beats:
        raise ValueError("No se detectó ritmo en el audio. Prueba con otro fragmento.")

    import numpy as np
    bpm = float(np.ravel(tempo)[0])
    return AudioAnalysis(bpm=bpm, beats=beats, duration=duration)


# --- Ajuste de la rejilla de beats (×2 / ÷2 / offset) ----------------------

def transform_beats(
    beats: List[float],
    multiplier: float = 1.0,
    offset_ms: float = 0.0,
    duration: float = None,
) -> List[float]:
    """Aplica offset (ms) y multiplicador de densidad (×2/÷2) a la rejilla de beats.

    - multiplier == 2  -> inserta el punto medio entre cada par de beats (~2×).
    - multiplier == 0.5 -> queda con un beat sí, uno no (diezmado).
    - Otros valores se interpretan como potencias de 2 (4, 0.25, ...).
    El offset desplaza toda la rejilla; los beats fuera de [0, duration] se descartan.
    """
    off = offset_ms / 1000.0
    bs = [b + off for b in beats]

    if multiplier == 2:
        bs = _double_beats(bs)
    elif multiplier == 0.5:
        bs = _halve_beats(bs)
    elif multiplier != 1:
        # Soporte genérico por potencias de 2
        if multiplier > 1:
            for _ in range(int(round(math.log2(multiplier)))):
                bs = _double_beats(bs)
        else:
            for _ in range(int(round(math.log2(1 / multiplier)))):
                bs = _halve_beats(bs)

    bs = sorted(bs)
    if duration is not None:
        bs = [b for b in bs if -1e-6 < b <= duration + 1e-6]
    return bs


def _double_beats(beats: List[float]) -> List[float]:
    if not beats:
        return beats
    out: List[float] = []
    for i in range(len(beats)):
        out.append(beats[i])
        if i + 1 < len(beats):
            out.append((beats[i] + beats[i + 1]) / 2.0)
    return out


def _halve_beats(beats: List[float]) -> List[float]:
    return beats[::2]


def snap_to_nearest_beat(drop: float, beats: List[float]) -> float:
    """Devuelve el beat más cercano al punto de drop dado."""
    if not beats:
        return drop
    return min(beats, key=lambda b: abs(b - drop))
