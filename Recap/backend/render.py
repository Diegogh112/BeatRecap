"""Orquestación del render: línea de tiempo + frames por tiempo absoluto +
envío a ffmpeg por stdin (rawvideo) + progreso."""
import math
import re
import threading
import subprocess
from bisect import bisect_right
from pathlib import Path

from PIL import Image

from . import config, frames
from .intros import get_intro

# Estado compartido de los renders: render_id -> dict(status, progress, error, output)
RENDERS: dict = {}


# ---------------------------------------------------------------------------
# Línea de tiempo
# ---------------------------------------------------------------------------

def compute_timeline(beats, drop, n, duration):
    """Calcula los intervalos de imagen del carrusel.

    - El primer intervalo empieza exactamente en `drop`.
    - Los cambios ocurren en cada N-ésimo beat posterior al drop.
    - El último intervalo se extiende hasta `duration`.
    - num_images == ceil(beats_tras_drop / n).
    """
    beats_after_drop = [b for b in beats if drop < b <= duration]
    B = len(beats_after_drop)
    num_images = math.ceil(B / n)

    img_starts = [drop]
    for k in range(1, num_images):
        idx = k * n - 1
        if idx < B:
            img_starts.append(beats_after_drop[idx])
    img_ends = img_starts[1:] + [duration]

    if num_images == 0:
        img_starts = [drop]
        img_ends   = [duration]
        num_images = 1

    return list(zip(img_starts, img_ends)), num_images


def total_frames(duration, fps=config.FPS):
    return math.ceil(duration * fps)


def beats_after_drop_count(beats, drop, duration):
    return len([b for b in beats if drop < b <= duration])


# ---------------------------------------------------------------------------
# Slots: imagen estática o fragmento de video
# ---------------------------------------------------------------------------

VIDEO_EXTS = {"mp4", "mov", "webm", "avi", "mkv"}


def _is_video(path: str) -> bool:
    # detecta por extensión del nombre original (el archivo puede tener nombre _seek2.50.mp4)
    return Path(path).suffix.lower().lstrip(".") in VIDEO_EXTS


def _parse_seek(path: str) -> float:
    """Extrae el seek del stem del archivo si viene codificado como _seekX.XX."""
    stem = Path(path).stem
    if "_seek" in stem:
        try:
            return float(stem.split("_seek")[-1])
        except ValueError:
            pass
    return 0.0


class VideoSlot:
    """Decodifica con ffmpeg los frames de un fragmento de video y los almacena en RAM.

    Los frames se extraen al fps del proyecto, desde seek_sec durante interval_sec.
    Ya llevan el cover-fit aplicado (escala + crop) con el offset cx/cy elegido.
    """

    def __init__(
        self,
        path: str,
        seek_sec: float,
        interval_sec: float,
        w: int,
        h: int,
        fps: int,
        cx: float = 0.5,
        cy: float = 0.5,
    ):
        n_frames    = max(1, math.ceil(interval_sec * fps))
        self._w     = w
        self._h     = h
        self._frames: list = []

        # Usamos un filtro de escala + crop que respeta el aspect-ratio (cover)
        # y luego aplicamos el offset de encuadre.
        # La fórmula del offset: el "extra" que hay tras escalar al mínimo que cubre w×h.
        # Lo implementamos escalando a mayor tamaño y usando el filtro crop con offsets.
        vf = (
            f"scale='if(gt(a,{w}/{h}),{-2}*{h//2*2},{w})':'if(gt(a,{w}/{h}),{h},{-2}*{w//2*2})',"
            f"crop={w}:{h}:'(iw-{w})*{cx}':'(ih-{h})*{cy}'"
        )

        cmd = [
            config.FFMPEG_BIN,
            "-ss", str(max(0.0, seek_sec)),
            "-i", str(path),
            "-t", str(interval_sec + 2.0 / fps),   # margen de 2 frames
            "-vf", vf,
            "-r", str(fps),
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-an",
            "-",
        ]
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            raw  = proc.stdout.read()
            proc.wait()
        except Exception:
            raw = b""

        frame_bytes = w * h * 3
        for i in range(min(n_frames, max(1, len(raw) // frame_bytes))):
            chunk = raw[i * frame_bytes : (i + 1) * frame_bytes]
            if len(chunk) == frame_bytes:
                self._frames.append(Image.frombytes("RGB", (w, h), chunk))

        if not self._frames:
            # fallback: frame negro
            self._frames.append(Image.new("RGB", (w, h), (0, 0, 0)))

    def get_frame(self, local_t: float, fps: int) -> Image.Image:
        idx = min(int(local_t * fps), len(self._frames) - 1)
        return self._frames[max(0, idx)]


def _load_slot(path, seek_sec, interval_sec, w, h, fps, cx, cy):
    """Carga un slot: VideoSlot para videos, Image con cover-fit para imágenes."""
    if _is_video(path):
        return VideoSlot(path, seek_sec, interval_sec, w, h, fps, cx, cy)
    img = Image.open(path).convert("RGB")
    return frames.cover_fit(img, w, h, cx, cy)


# ---------------------------------------------------------------------------
# Helpers de render
# ---------------------------------------------------------------------------

def _interval_index(intervals, t):
    """Índice i tal que intervals[i][0] <= t < intervals[i][1] (o el último)."""
    starts = [iv[0] for iv in intervals]
    i = bisect_right(starts, t) - 1
    if i < 0:
        i = 0
    if i >= len(intervals):
        i = len(intervals) - 1
    return i


def _carousel_frame(base, intervals, i, t, transition):
    """Aplica la transición elegida al inicio del intervalo (excepto el primero)."""
    if transition == "cut" or i == 0:
        return base
    start, _ = intervals[i]
    local_t   = t - start
    if transition == "flash":
        flash_dur = 0.08
        if local_t < flash_dur:
            return frames.apply_flash(base, 1.0 - local_t / flash_dur)
    elif transition == "zoom":
        zoom_dur = 0.12
        if local_t < zoom_dur:
            factor = 1.0 + (1.0 - local_t / zoom_dur) * 0.10
            return frames.apply_zoom(base, factor)
    return base


# ---------------------------------------------------------------------------
# run_render
# ---------------------------------------------------------------------------

def run_render(
    render_id: str,
    audio_path: str,
    image_paths: list,
    order: list,
    beats: list,
    duration: float,
    drop: float,
    n: int,
    intro_style: str,
    title: str,
    subtitle: str,
    text_color: str,
    font: str,
    transition: str,
    resolution: str,
    preview: bool = False,
    crop_offsets: dict = None,    # {str(carousel_index): [cx, cy]}
    month_labels: dict = None,    # {str(carousel_index): "Enero"}
    tilt_angle: float = 0.0,      # grados de inclinación alternada por imagen
):
    """Ejecuta el render en un hilo. Actualiza RENDERS[render_id]."""
    try:
        RENDERS[render_id] = {"status": "rendering", "progress": 0.0, "error": None, "output": None}

        base_w, base_h = config.RESOLUTIONS[resolution or config.DEFAULT_RESOLUTION]
        if preview:
            base_w = max(2, int(round(base_w * config.PREVIEW_SCALE)))
            base_h = max(2, int(round(base_h * config.PREVIEW_SCALE)))
        w, h   = base_w, base_h
        fps    = config.FPS
        max_duration = duration

        beats = sorted(float(b) for b in beats)
        beats = [b for b in beats if -1e-6 <= b <= duration + 1e-6]

        intervals, num_images = compute_timeline(beats, drop, n, max_duration)

        if not image_paths or not order:
            raise ValueError("No hay imágenes para renderizar.")

        ordered_files = [image_paths[idx] for idx in order]
        _offsets      = crop_offsets  or {}
        _labels       = month_labels  or {}
        _tilt         = float(tilt_angle) if tilt_angle else 0.0

        # Intervalo promedio (para saber cuántos frames cargar en VideoSlot cuando
        # el slot se reutiliza más allá de len(intervals))
        avg_interval = (sum(e - s for s, e in intervals) / len(intervals)) if intervals else 1.0

        # Cargar slots
        slots = []
        for ci, path in enumerate(ordered_files):
            cx, cy    = _offsets.get(str(ci), [0.5, 0.5])
            iv_sec    = (intervals[ci][1] - intervals[ci][0]) if ci < len(intervals) else avg_interval
            seek      = _parse_seek(path)
            slots.append(_load_slot(path, seek, iv_sec, w, h, fps, cx, cy))

        # Pre-calcular etiquetas por tiempo (12 segmentos de [drop, duration])
        # _labels viene del frontend como {str(img_index): "Mes"} pero
        # lo convertimos a {segmento_0_11: "Mes"} por tiempo.
        # Si hay etiquetas por imagen, las re-mapeamos a segmentos temporales.
        _carousel_dur = max_duration - drop
        _seg_dur      = _carousel_dur / 12.0 if _carousel_dur > 0 else 1.0
        # Construir mapa seg→label: el mes del primer imagen que cae en ese segmento
        _seg_labels = {}
        if _labels:
            for ci, label in _labels.items():
                if not label:
                    continue
                ci_int = int(ci)
                if ci_int < len(intervals):
                    img_t    = intervals[ci_int][0]     # tiempo de inicio de esa imagen
                    seg_idx  = min(11, int((img_t - drop) / _seg_dur)) if _seg_dur > 0 else 0
                    if seg_idx not in _seg_labels:      # primer imagen de cada segmento
                        _seg_labels[seg_idx] = label

        _last_shown_seg: list = [-1]   # mutable para closure

        # Estado para el efecto de pila (imagen anterior cuando hay tilt)
        _prev_frame: list = [None]   # mutable para captura en closure

        def get_slot_frame(carousel_i: int, local_t: float) -> Image.Image:
            slot = slots[carousel_i % len(slots)]
            if isinstance(slot, VideoSlot):
                base = slot.get_frame(local_t, fps)
            else:
                base = slot

            # ── Tilt aleatorio por imagen ──────────────────────────────────
            if abs(_tilt) > 0.1:
                import math as _m
                rnd   = _m.sin(carousel_i * 2.399963) * _m.cos(carousel_i * 1.618034)
                angle = rnd * _tilt
                base  = frames.apply_tilt(base, angle)

                # Efecto pila: superponer la imagen anterior semitransparente
                # solo en el inicio del intervalo (primeros 0.15s)
                prev = _prev_frame[0]
                if prev is not None and local_t < 0.15:
                    # La imagen anterior aparece detrás, ligeramente más pequeña
                    fade_out = 1.0 - local_t / 0.15        # 1→0
                    # Escalar levemente la imagen anterior (parece más atrás)
                    small_w = max(1, int(w * 0.92))
                    small_h = max(1, int(h * 0.92))
                    prev_small = prev.resize((small_w, small_h), Image.LANCZOS)
                    # Centrar sobre canvas negro
                    bg = Image.new("RGB", (w, h), (0, 0, 0))
                    lx = (w - small_w) // 2
                    ly = (h - small_h) // 2
                    bg.paste(prev_small, (lx, ly))
                    # Componer: bg (anterior) + base (actual) con fade
                    alpha_prev = int(220 * fade_out)
                    mask  = Image.new("L", (w, h), alpha_prev)
                    base  = Image.composite(bg, base, mask)

            # Etiqueta de mes por tiempo
            label = _labels.get(str(carousel_i), "")
            if label:
                iv_dur    = intervals[carousel_i][1] - intervals[carousel_i][0] if carousel_i < len(intervals) else 1.0
                label_dur = min(0.4, iv_dur * 0.6)
                if local_t < label_dur:
                    fade_in  = min(1.0, local_t / 0.08)
                    fade_out = min(1.0, (label_dur - local_t) / 0.08) if local_t > label_dur - 0.1 else 1.0
                    base = frames.draw_month_label(
                        base, label, font_name=font,
                        color_hex=text_color, fade=fade_in * fade_out,
                    )

            # Actualizar frame previo solo al inicio del intervalo
            if local_t < 1.0 / fps:
                _prev_frame[0] = base

            return base

        # Intro: primer frame de cada slot
        intro_images = []
        for slot in slots:
            if isinstance(slot, VideoSlot):
                intro_images.append(slot.get_frame(0.0, fps))
            else:
                intro_images.append(slot)

        intro_gen = get_intro(intro_style)
        intro_cfg = {
            "images":     intro_images,
            "title":      title,
            "subtitle":   subtitle,
            "text_color": text_color,
            "font":       font,
            "w": w, "h": h,
        }

        out_dir  = Path(audio_path).parent
        out_path = out_dir / ("preview.mp4" if preview else "output.mp4")

        cmd = [
            config.FFMPEG_BIN, "-y",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
            "-framerate", str(fps), "-i", "-",
            "-i", str(audio_path),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", "-movflags", "+faststart",
            str(out_path),
        ]

        total = total_frames(max_duration, fps)
        proc  = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        stop = threading.Event()

        def reader():
            for raw_line in proc.stderr:
                if stop.is_set():
                    break
                line = raw_line.decode(errors="ignore")
                m = re.search(r"frame=\s*(\d+)", line)
                if m:
                    RENDERS[render_id]["progress"] = min(0.99, int(m.group(1)) / total) if total else 0.0

        rthread = threading.Thread(target=reader, daemon=True)
        rthread.start()

        for k in range(total):
            t = k / fps
            if t < drop and drop > 0:
                frame = intro_gen(intro_cfg, t / drop)
            else:
                i       = _interval_index(intervals, t)
                local_t = max(0.0, t - intervals[i][0])
                base    = get_slot_frame(i, local_t)
                frame   = _carousel_frame(base, intervals, i, t, transition)

                # Etiqueta de mes por segmento de tiempo
                if _seg_labels and _carousel_dur > 0:
                    seg_idx = min(11, int((t - drop) / _seg_dur))
                    label   = _seg_labels.get(seg_idx, "")
                    # Mostrar el label durante los primeros 0.5s del segmento
                    seg_local = (t - drop) - seg_idx * _seg_dur
                    label_dur = min(0.5, _seg_dur * 0.4)
                    if label and seg_local < label_dur:
                        fade_in  = min(1.0, seg_local / 0.08)
                        fade_out = min(1.0, (label_dur - seg_local) / 0.1) if seg_local > label_dur - 0.12 else 1.0
                        frame = frames.draw_month_label(
                            frame, label, font_name=font,
                            color_hex=text_color, fade=fade_in * fade_out,
                        )

            proc.stdin.write(frame.tobytes())
            if k % 15 == 0:
                RENDERS[render_id]["progress"] = min(0.99, k / total) if total else 0.0

        proc.stdin.close()
        proc.wait()
        stop.set()
        rthread.join(timeout=2)

        if proc.returncode != 0:
            err = proc.stderr.read().decode(errors="ignore")[-800:]
            raise RuntimeError(f"ffmpeg falló al renderizar. {err}")

        RENDERS[render_id]["progress"] = 1.0
        RENDERS[render_id]["status"]   = "completed"
        RENDERS[render_id]["output"]   = str(out_path)

    except Exception as e:
        RENDERS[render_id] = {"status": "failed", "progress": 0.0, "error": str(e), "output": None}
