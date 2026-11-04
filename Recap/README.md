# Beat Recap

Genera videos tipo "recap" donde las fotos cambian exactamente al ritmo de una canción. Subes un audio, la app detecta los beats con `librosa`, eliges el "punto de drop", subes y ordenas tus fotos, configuras una intro y descargas un MP4 (H.264 + AAC). Todo corre en local, sin servicios de pago.

## Características

- Detección de BPM y beats con `librosa.beat.beat_track` (tiempos reales, no `BPM × tiempo`).
- Forma de onda interactiva (WaveSurfer.js) con beats marcados y selección del drop.
- Botones **×2 / ÷2** sobre el BPM y **offset en ms** para ajustar la rejilla; el conteo de imágenes se recalcula al instante.
- Carrusel donde cada imagen dura el intervalo real entre beats; el primer intervalo empieza exactamente en el drop (la intro termina sin huecos).
- Frames por tiempo absoluto `t = k/fps` (sin `round()` por intervalo) enviados a ffmpeg por stdin (`rawvideo`); el cover-fit se cachea por imagen.
- Intros: **Solo texto**, **Zoom mosaico**, **Fotos cayendo** (y **Vórtice** opcional, Fase 3).
- Transiciones por beat: corte seco, flash blanco, zoom breve.
- Vista previa de baja resolución y render final 1080×1920 (vertical) o 1920×1080 (horizontal).
- Barra de progreso durante el render y descarga del MP4.

## Requisitos

- **Python 3.11+** (probado con Python 3.14).
- **ffmpeg**: se incluye automáticamente mediante `imageio-ffmpeg` (no necesitas instalar ffmpeg a mano). Si prefieres usar un ffmpeg del sistema, instala la variable de entorno `FFMPEG_BIN` con la ruta del ejecutable.

### (Opcional) Instalar ffmpeg del sistema en Windows

Solo si quieres usar tu propio ffmpeg en lugar del empaquetado:

```powershell
winget install --id Gyan.FFmpeg -e --source winget
```

O descarga un build desde <https://www.gyan.dev/ffmpeg/builds/>, descomprímelo y añade la carpeta `bin` al `PATH` (o define `FFMPEG_BIN`).

## Instalación

```powershell
# 1. Entorno virtual
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Dependencias
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> Si `Activate.ps1` está bloqueado por la política de ejecución, usa:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` y vuelve a intentarlo.

## Ejecución

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Abre **http://127.0.0.1:8000** en el navegador.

### Flujo de uso

1. Sube un fragmento de audio (mp3/wav/m4a, máx. 60 s).
2. Revisa BPM y beats en la forma de onda. Ajusta la rejilla con **×2/÷2** y el **offset (ms)** si hace falta.
3. Haz clic en la forma de onda para elegir el **drop**; pulsa "Beat más cercano" para ajustarlo y "▶ desde drop" para escuchar.
4. Elige "cambiar cada N beats" (1/2/4); la app muestra cuántas imágenes necesitas (`ceil(beats_tras_drop / N)`).
5. Sube tus imágenes (jpg/png/webp), reordénalas arrastrando, elimina o duplica.
6. Configura la intro (estilo, título, subtítulo, color, fuente, transición, formato).
7. Usa "Vista previa" para un borrador rápido o "Renderizar y descargar" para el MP4 final.

## Pruebas

```powershell
.\.venv\Scripts\Activate.ps1
pytest -q
```

Incluye pruebas del cálculo de intervalos de beats, del número de imágenes (`ceil(beats_tras_drop / N)`), del ajuste del drop al beat más cercano y del total de frames (`ceil(duration * fps)`).

## Estructura

```
backend/
  config.py        constantes (resoluciones, fps, fuentes, ffmpeg)
  utils.py         validaciones y carpetas temporales
  audio.py         analyze_audio() (librosa) + transform_beats() (×2/÷2/offset) + snap
  frames.py        cover_fit(), texto animado, transiciones (flash/zoom)
  render.py        línea de tiempo + frames por tiempo absoluto + pipe a ffmpeg
  main.py          FastAPI: /audio, /render, /preview, estado y descarga
  intros/          text, zoom_mosaic, falling (+ vortex opcional)
frontend/
  index.html, styles.css, app.js   (WaveSurfer.js + SortableJS por CDN)
tmp/               archivos temporales por job (se limpian al terminar)
tests/             test_intervals, test_image_count, test_drop_snap, test_total_frames
```

## API

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/audio` | Sube y analiza audio → `{job_id, bpm, beats, duration}` |
| GET  | `/audio/{job_id}` | Devuelve el audio guardado (para la forma de onda) |
| POST | `/render` | Inicia el render → `{render_id, status}` (202) |
| POST | `/preview` | Inicia una vista previa de baja resolución |
| GET  | `/render/{id}` | Estado y progreso → `{status, progress, error}` |
| GET  | `/render/{id}/download` | Descarga el MP4 cuando está listo |

## Notas

- El audio suena completo de principio a fin; la intro ocupa `[0, drop)` y el carrusel `[drop, duration]`.
- La última imagen del carrusel se mantiene hasta el final del audio.
- La intro "Vórtice" (Fase 3) requiere `opencv-python` (`pip install opencv-python`); el resto de estilos no la necesitan.
