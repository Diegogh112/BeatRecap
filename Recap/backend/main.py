"""Servidor FastAPI de Beat Recap."""
import json
import subprocess
import threading
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config, utils
from . import audio as audio_mod
from . import render as render_mod

app = FastAPI(title="Beat Recap")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# jobs: job_id -> {"audio_path", "bpm", "beats", "duration"}
JOBS: dict = {}

config.TMP_DIR.mkdir(parents=True, exist_ok=True)


# --- Audio ------------------------------------------------------------------

@app.post("/audio")
async def post_audio(file: UploadFile = File(...)):
    ext = utils.validate_audio_ext(file.filename or "audio.mp3")
    job_id, job_dir = utils.new_job_dir()
    audio_path = job_dir / f"audio.{ext}"
    with open(audio_path, "wb") as f:
        f.write(await file.read())

    try:
        result = audio_mod.analyze_audio(str(audio_path))
    except ValueError as e:
        utils.cleanup_dir(job_dir)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        utils.cleanup_dir(job_dir)
        raise HTTPException(status_code=400, detail=f"No se pudo analizar el audio: {e}")

    JOBS[job_id] = {
        "audio_path": str(audio_path),
        "bpm": result.bpm,
        "beats": result.beats,
        "duration": result.duration,
    }
    return {
        "job_id": job_id,
        "bpm": result.bpm,
        "beats": result.beats,
        "duration": result.duration,
    }


@app.get("/audio/{job_id}")
@app.head("/audio/{job_id}")
async def get_audio(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado.")
    return FileResponse(job["audio_path"], media_type="audio/mpeg")


# --- Extraer frame de un clip de video ------------------------------------

@app.post("/extract-frame")
async def extract_frame(
    file: UploadFile = File(...),
    seek: float = Form(0.0),
):
    """Recibe un clip de video y devuelve el frame en seek=X segundos como JPEG."""
    ext = Path(file.filename or "clip.mp4").suffix.lower().lstrip(".")
    if ext not in config.ALLOWED_VIDEO_EXT:
        raise HTTPException(status_code=400, detail=f"Formato de video no permitido: .{ext}")

    _, job_dir = utils.new_job_dir()
    video_path = job_dir / f"clip.{ext}"
    frame_path = job_dir / "frame.jpg"

    with open(video_path, "wb") as f:
        f.write(await file.read())

    cmd = [
        config.FFMPEG_BIN, "-y",
        "-ss", str(max(0.0, seek)),
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(frame_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0 or not frame_path.exists():
            err = result.stderr.decode(errors="ignore")[-400:]
            raise HTTPException(status_code=400, detail=f"No se pudo extraer el frame: {err}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=400, detail="Tiempo de espera agotado extrayendo el frame.")

    return FileResponse(str(frame_path), media_type="image/jpeg")


# --- Render -----------------------------------------------------------------

def _start_render(
    job_id: str,
    image_files: list,
    order: list,
    beats: list,
    drop: float,
    n: int,
    intro_style: str,
    title: str,
    subtitle: str,
    text_color: str,
    font: str,
    transition: str,
    resolution: str,
    preview: bool,
    crop_offsets: dict = None,
    month_labels: dict = None,
    tilt_angle: float = 0.0,
):
    """image_files: lista de (filename, bytes). Inicia el render en un hilo."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado.")

    duration = job["duration"]
    drop = max(0.0, min(float(drop), duration))
    n = int(n) if n in (1, 2, 4) else 1
    if resolution not in config.RESOLUTIONS:
        resolution = config.DEFAULT_RESOLUTION
    if transition not in config.TRANSITIONS:
        transition = config.DEFAULT_TRANSITION

    # Guardar imágenes en la carpeta del job
    job_dir = Path(job["audio_path"]).parent
    img_dir = job_dir / ("preview_imgs" if preview else "imgs")
    img_dir.mkdir(exist_ok=True)
    image_paths = []
    for idx, (filename, data) in enumerate(image_files):
        ext = utils.validate_image_ext(filename or f"img_{idx}.jpg")
        # Preservar el nombre original para que _seekX.XX y la extensión lleguen intactos
        # a render.py (que detecta videos por extensión y extrae el seek del stem).
        # Solo sanitizamos caracteres problemáticos en paths de Windows.
        safe_name = (filename or f"img_{idx:03d}.{ext}").replace(" ", "_")
        # prefijo numérico para mantener orden y evitar colisiones
        p = img_dir / f"{idx:03d}_{safe_name}"
        with open(p, "wb") as f:
            f.write(data)
        image_paths.append(str(p))

    # order: lista de índices (con duplicados) que define el orden final
    order = [int(i) for i in order]
    if not order:
        order = list(range(len(image_paths)))
    order = [i for i in order if 0 <= i < len(image_paths)]
    if not order:
        raise HTTPException(status_code=400, detail="El orden de imágenes está vacío.")

    render_id, _ = utils.new_job_dir()
    thread = threading.Thread(
        target=render_mod.run_render,
        args=(render_id, job["audio_path"], image_paths, order, beats,
              duration, drop, n, intro_style, title, subtitle, text_color, font,
              transition, resolution),
        kwargs={
            "preview":      preview,
            "crop_offsets": crop_offsets  or {},
            "month_labels": month_labels  or {},
            "tilt_angle":   tilt_angle    or 0.0,
        },
        daemon=True,
    )
    thread.start()
    return {"render_id": render_id, "status": "queued"}


async def _read_images(images: list) -> list:
    return [(img.filename or f"img_{i}.jpg", await img.read()) for i, img in enumerate(images)]


async def _common_render_params(
    job_id, images, order, beats, drop, n, intro_style, title,
    subtitle, text_color, font, transition, resolution, preview,
    crop_offsets="{}",
    month_labels="{}",
    tilt_angle=0.0,
):
    try:
        order_list        = json.loads(order)         if order         else []
        beats_list        = json.loads(beats)         if beats         else []
        crop_offsets_dict = json.loads(crop_offsets)  if crop_offsets  else {}
        month_labels_dict = json.loads(month_labels)  if month_labels  else {}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"JSON inválido: {e}")

    if not beats_list:
        beats_list = JOBS.get(job_id, {}).get("beats", [])

    image_files = await _read_images(images)
    return _start_render(
        job_id, image_files, order_list, beats_list, drop, n, intro_style,
        title, subtitle, text_color, font, transition, resolution, preview,
        crop_offsets=crop_offsets_dict,
        month_labels=month_labels_dict,
        tilt_angle=float(tilt_angle),
    )


@app.post("/render")
async def post_render(
    job_id: str = Form(...),
    images: list[UploadFile] = File(...),
    order: str = Form("[]"),
    beats: str = Form("[]"),
    drop: float = Form(0.0),
    n: int = Form(1),
    intro_style: str = Form(config.DEFAULT_INTRO_STYLE),
    title: str = Form(config.DEFAULT_TITLE),
    subtitle: str = Form(""),
    text_color: str = Form(config.DEFAULT_TEXT_COLOR),
    font: str = Form(config.DEFAULT_FONT),
    transition: str = Form(config.DEFAULT_TRANSITION),
    resolution: str = Form(config.DEFAULT_RESOLUTION),
    crop_offsets: str = Form("{}"),
    month_labels: str = Form("{}"),
    tilt_angle: float = Form(0.0),
):
    return await _common_render_params(
        job_id, images, order, beats, drop, n, intro_style, title,
        subtitle, text_color, font, transition, resolution, preview=False,
        crop_offsets=crop_offsets, month_labels=month_labels, tilt_angle=tilt_angle,
    )


@app.post("/preview")
async def post_preview(
    job_id: str = Form(...),
    images: list[UploadFile] = File(...),
    order: str = Form("[]"),
    beats: str = Form("[]"),
    drop: float = Form(0.0),
    n: int = Form(1),
    intro_style: str = Form(config.DEFAULT_INTRO_STYLE),
    title: str = Form(config.DEFAULT_TITLE),
    subtitle: str = Form(""),
    text_color: str = Form(config.DEFAULT_TEXT_COLOR),
    font: str = Form(config.DEFAULT_FONT),
    transition: str = Form(config.DEFAULT_TRANSITION),
    resolution: str = Form(config.DEFAULT_RESOLUTION),
    crop_offsets: str = Form("{}"),
    month_labels: str = Form("{}"),
    tilt_angle: float = Form(0.0),
):
    return await _common_render_params(
        job_id, images, order, beats, drop, n, intro_style, title,
        subtitle, text_color, font, transition, resolution, preview=True,
        crop_offsets=crop_offsets, month_labels=month_labels, tilt_angle=tilt_angle,
    )


@app.get("/render/{render_id}")
async def get_render(render_id: str):
    state = render_mod.RENDERS.get(render_id)
    if not state:
        raise HTTPException(status_code=404, detail="Render no encontrado.")
    return {
        "status": state["status"],
        "progress": state["progress"],
        "error": state["error"],
    }


@app.get("/render/{render_id}/download")
async def download_render(render_id: str):
    state = render_mod.RENDERS.get(render_id)
    if not state:
        raise HTTPException(status_code=404, detail="Render no encontrado.")
    if state["status"] != "completed" or not state["output"]:
        raise HTTPException(status_code=409, detail="El render aún no está listo.")
    name = "preview.mp4" if "preview" in str(state["output"]) else "beat_recap.mp4"
    return FileResponse(
        state["output"],
        media_type="video/mp4",
        filename=name,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@app.get("/render/{render_id}/stream")
async def stream_render(render_id: str, request: Request):
    """Sirve el MP4 como inline con soporte de Range para que el <video> pueda
    hacer seek y reproducir sin descargar el archivo completo."""
    from fastapi.responses import StreamingResponse
    state = render_mod.RENDERS.get(render_id)
    if not state:
        raise HTTPException(status_code=404, detail="Render no encontrado.")
    if state["status"] != "completed" or not state["output"]:
        raise HTTPException(status_code=409, detail="El render aún no está listo.")

    path       = Path(state["output"])
    total_size = path.stat().st_size
    range_hdr  = request.headers.get("range")

    if range_hdr:
        # Parsear "bytes=start-end"
        byte_range = range_hdr.replace("bytes=", "").split("-")
        start = int(byte_range[0])
        end   = int(byte_range[1]) if byte_range[1] else total_size - 1
        end   = min(end, total_size - 1)
        chunk = end - start + 1

        def iter_file():
            with open(path, "rb") as f:
                f.seek(start)
                remaining = chunk
                while remaining > 0:
                    data = f.read(min(65536, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            iter_file(),
            status_code=206,
            media_type="video/mp4",
            headers={
                "Content-Range":       f"bytes {start}-{end}/{total_size}",
                "Accept-Ranges":       "bytes",
                "Content-Length":      str(chunk),
                "Content-Disposition": "inline",
            },
        )
    else:
        def iter_full():
            with open(path, "rb") as f:
                while True:
                    data = f.read(65536)
                    if not data:
                        break
                    yield data

        return StreamingResponse(
            iter_full(),
            status_code=200,
            media_type="video/mp4",
            headers={
                "Accept-Ranges":       "bytes",
                "Content-Length":      str(total_size),
                "Content-Disposition": "inline",
            },
        )


# --- Frontend estático ------------------------------------------------------

if config.FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIR), html=True), name="frontend")
