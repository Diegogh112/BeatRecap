# Beat Recap — Diseño

## Principios

- Local-first, sin servicios externos. El backend hace el trabajo pesado (audio + video); el frontend orquesta la experiencia y la previsualización.
- Separación clara: análisis de audio (librosa), generación de frames (Pillow/numpy), ensamblaje de video (ffmpeg subprocess).
- Los tiempos de los beats provienen de librosa y son la fuente de verdad para la duración de cada imagen. Nunca se sintetizan con BPM × tiempo.
- Los frames se generan por tiempo absoluto `t = k/fps` y se envían a ffmpeg por stdin como `rawvideo`, garantizando que cada cambio caiga en el beat exacto y sin acumulación de desfases.

## Estructura del proyecto

```
/ (workspace root)
├── backend/
│   ├── main.py            # FastAPI app, endpoints, manejo de temporales
│   ├── audio.py           # Análisis con librosa (BPM, beats, duración)
│   ├── render.py          # Orquestación del render: frames → ffmpeg → MP4
│   ├── frames.py          # Utilidades Pillow/numpy: cover-fit, texto, transiciones
│   ├── intros/
│   │   ├── __init__.py     # Registro de estilos de intro
│   │   ├── text.py         # "Solo texto"
│   │   ├── zoom_mosaic.py  # "Zoom mosaico"
│   │   └── falling.py      # "Fotos cayendo"
│   ├── config.py           # Constantes: resoluciones, fps, fuentes, rutas
│   └── utils.py            # Limpieza de temporales, validaciones comunes
├── frontend/
│   ├── index.html
│   ├── app.js             # Lógica de UI, orquestación de pasos
│   ├── styles.css
│   └── assets/
│       └── fonts/         # Fuentes incluidas (TTF/OTF)
├── tmp/                   # Archivos temporales (audio subido, frames, salida)
├── tests/
│   ├── test_intervals.py  # Cálculo de intervalos de beats
│   └── test_image_count.py# Número de imágenes necesarias
├── requirements.txt
└── README.md
```

## Backend

### `audio.py`
Responsable del análisis de audio con librosa.

Funciones principales:
- `analyze_audio(path: str) -> AudioAnalysis`: carga el audio con `librosa.load` (mono, sr constante), valida duración ≤ 60s, ejecuta `librosa.beat.beat_track` para obtener BPM y `librosa.frames_to_time` para los tiempos de beat en segundos, y devuelve duración total.

Modelo de datos:
```
AudioAnalysis {
  bpm: float
  beats: list[float]      # tiempos en segundos
  duration: float          # segundos
}
```

Consideraciones:
- Si `librosa.beat.beat_track` no encuentra un tempo estable, devolver error legible.
- Se descarta cualquier beat posterior a la duración total.

## Ajuste de la rejilla de beats (×2 / ÷2 / offset)

Tras el análisis, el usuario puede ajustar la rejilla de beats desde el frontend:
- **×2**: duplica la densidad insertando el punto medio entre cada par de beats consecutivos (y, si procede, un beat extrapolado antes del primero). Resulta en ~2× beats.
- **÷2**: divide la densidad quedándose con un beat sí, uno no (diezmado). Resulta en ~mitad de beats.
- **Offset (ms)**: desplaza toda la rejilla sumando `offset_ms / 1000` a cada tiempo de beat; se descartan los beats que queden fuera de `[0, duration]`.

Estas transformaciones se aplican en el frontend sobre el arreglo `beats` devuelto por `POST /audio` para feedback inmediato (rejilla y conteo de imágenes se recalculan al instante). El arreglo `beats` final (ya ajustado) se envía a `POST /render`, de modo que el render usa exactamente la rejilla que vio el usuario. El backend valida que `beats` sea monótono y esté dentro de `[0, duration]`.

La semántica de referencia está en `backend/audio.py::transform_beats(beats, multiplier, offset_ms, duration)` para mantenerla documentada y poder probarla.

### `render.py`
Responsable de orquestar la generación de frames y el ensamblaje con ffmpeg.

Flujo de render:
1. Recibe el job de render (audio path, imágenes ordenadas, `beats` ajustados, drop, N, estilo de intro, título, subtítulo, color, fuente, transición, resolución).
2. Calcula la línea de tiempo:
   - Segmento intro: [0, drop). La intro termina exactamente en el drop, sin huecos.
   - Segmento carrusel: [drop, duration]. El primer intervalo empieza exactamente en el drop.
   - `beats_after_drop = [b for b in beats if drop < b <= duration]`; `B = len(beats_after_drop)`.
   - `num_images = ceil(B / N)`.
   - `img_starts = [drop] + [beats_after_drop[k*N - 1] for k in 1..num_images-1 si k*N-1 < B]`.
   - `img_ends = img_starts[1:] + [duration]` (el último intervalo se extiende hasta `duration` para mantener la última imagen hasta el final real del audio).
3. Genera los frames por tiempo absoluto (no por intervalo):
   - `total_frames = ceil(duration * fps)`.
   - Para `k` en `0..total_frames-1`: `t = k / fps`.
     - Si `t < drop`: frame de intro con `progress = t / drop`.
     - Si `t >= drop`: localizar la imagen activa en `t` (índice `i` tal que `img_starts[i] <= t < img_ends[i]`), aplicar cover-fit (cacheado por imagen) y la transición.
   - Cada frame se envía a ffmpeg por stdin como `rawvideo` RGB24; no se guardan PNG por frame.
   - El resultado de `cover_fit` se cachea por imagen (se calcula una sola vez por imagen, reutilizado en todos sus frames).
4. Ejecuta ffmpeg con subprocess leyendo frames de stdin y el audio del archivo (ver "Manejo de ffmpeg").
5. Reporta progreso: ffmpeg escribe progreso a stderr; el backend parsea `frame=` o `out_time_ms` y emite progreso al frontend vía polling.

Estrategia:
- **Decisión**: generar frames por tiempo absoluto `t = k/fps` y enviarlos a ffmpeg por stdin como `rawvideo`. Esto evita la acumulación de desfases por `round()` por intervalo y elimina la escritura de PNG por frame a disco. El cover-fit por imagen se cachea para no recalcularlo en cada frame.

### `frames.py`
Utilidades de generación de frames con Pillow/numpy.

Funciones principales:
- `cover_fit(img: Image, target_w: int, target_h: int) -> Image`: redimensiona con recorte centrado (cover) sin deformar.
- `make_text_frame(text, subtitle, color, font_path, w, h, progress) -> Image`: render de texto animado sobre negro según progreso 0..1.
- `apply_flash(frame, intensity) -> Image`: superpone un flash blanco (alpha proporcional).
- `apply_zoom(frame, factor) -> Image`: zoom breve desde el centro.

### `intros/`
Cada módulo expone `generate(config, progress) -> Image` donde `progress` es el avance dentro de la intro (0..1) y `config` contiene imágenes, título, subtítulo, color, fuente, resolución.

- `text.py`: animación de entrada del título (fade/slide), subtítulo opcional, fondo negro.
- `zoom_mosaic.py`: construye un mosaico de las imágenes subidas y aplica zoom hacia el centro a lo largo de la intro.
- `falling.py`: columnas de imágenes que descienden; al llegar al drop coinciden con el inicio del carrusel.

Registro en `intros/__init__.py`:
```
INTRO_STYLES = {
  "text": text.generate,
  "zoom_mosaic": zoom_mosaic.generate,
  "falling": falling.generate,
}
```

### `main.py`
App FastAPI con los siguientes endpoints.

## API

### `POST /audio`
Sube y analiza audio.
- Request: `multipart/form-data` con campo `file` (mp3/wav/m4a).
- Validaciones: formato permitido, tamaño/duración ≤ 60s.
- Response 200:
```json
{
  "job_id": "uuid",
  "bpm": 128.5,
  "beats": [0.464, 0.928, ...],
  "duration": 45.2
}
```
- Response 400: `{ "error": "mensaje legible" }` para audio inválido / muy largo / sin ritmo.

### `POST /render`
Inicia el renderizado.
- Request `multipart/form-data`:
  - `job_id`: referencia al audio ya analizado.
  - `images`: uno o más archivos de imagen (ordenados según el campo `order`).
  - `order`: lista de índices que define el orden final (incluye duplicados).
  - `drop`: tiempo en segundos del punto de drop.
  - `beats`: arreglo final de tiempos de beat (segundos) ya ajustado con ×2/÷2 y offset; el render lo usa tal cual (valida monótono y en `[0, duration]`).
  - `n`: 1 | 2 | 4.
  - `intro_style`: "text" | "zoom_mosaic" | "falling".
  - `title`: string (default "2025 RECAP").
  - `subtitle`: string (opcional).
  - `text_color`: hex string (ej. "#FFFFFF").
  - `font`: nombre de fuente del set incluido.
  - `transition`: "cut" | "flash" | "zoom".
  - `resolution`: "vertical" (1080x1920) | "horizontal" (1920x1080).
- Response 202:
```json
{ "render_id": "uuid", "status": "queued" }
```

### `GET /render/{render_id}`
Estado del render (para la barra de progreso).
- Response 200:
```json
{ "status": "rendering" | "completed" | "failed", "progress": 0.42, "error": null }
```

### `GET /render/{render_id}/download`
- Response 200: el MP4 (`video/mp4`) si está completado.
- Response 404/409 si no está listo.

### `POST /preview`
Genera una vista previa de baja resolución.
- Mismos campos que `/render` pero se solicita resolución reducida (ej. 270x480) y duración acortada (intro comprimida + algunos beats del carrusel).
- Response: devuelve un MP4 ligero o un set de frames representativos.

## Flujo de datos (end to end)

1. Frontend sube audio → `POST /audio` → backend guarda audio en `tmp/<job_id>/audio.<ext>`, analiza con librosa, devuelve bpm/beats/duration.
2. Frontend muestra forma de onda (WaveSurfer) con beats como regiones/marcadores; usuario elige drop y puede ajustar la rejilla (×2/÷2/offset en ms), recalculando el conteo de imágenes.
3. Frontend calcula número de imágenes necesarias localmente como `ceil(beats_tras_drop / N)` (con los beats ajustados) y muestra advertencias (menos de 4 beats tras el drop, sobran/faltan imágenes).
4. Frontend permite subir imágenes, reordenar (SortableJS), eliminar, duplicar; construye `order` final.
5. Frontend configura intro (estilo, título, subtítulo, color, fuente, transición, resolución).
6. Vista previa → `POST /preview` → MP4 ligero.
7. Render final → `POST /render` (202) → poll `GET /render/{id}` hasta `completed` → `GET .../download`.

## Cálculo de la línea de tiempo (detallado)

Dado `beats` (lista de tiempos ya ajustada con ×2/÷2 y offset), `drop`, `N`, `duration`, `fps`:

```
beats_after_drop = [b for b in beats if drop < b <= duration]
B = len(beats_after_drop)
num_images = ceil(B / N)

img_starts = [drop]
for k in range(1, num_images):
    idx = k * N - 1          # 0-indexado en beats_after_drop
    if idx < B:
        img_starts.append(beats_after_drop[idx])
img_ends = img_starts[1:] + [duration]
intervals = list(zip(img_starts, img_ends))     # len == num_images
```

Propiedades:
- El primer intervalo empieza exactamente en `drop` (la intro termina en el drop, sin huecos).
- Los cambios ocurren en cada N-ésimo beat (índices `N-1, 2N-1, 3N-1, ...` en `beats_after_drop`).
- El último intervalo se extiende hasta `duration` (la última imagen se mantiene hasta el final real del audio); los beats del último grupo parcial quedan absorbidos.
- `num_images == ceil(B / N)`.

Generación de frames (por tiempo absoluto):
```
total_frames = ceil(duration * fps)
for k in range(total_frames):
    t = k / fps
    if t < drop:
        frame = intro.generate(progress = t / drop, ...)
    else:
        i = índice tal que img_starts[i] <= t < img_ends[i]
        frame = carousel_frame(i, t, transition, ...)
    send_to_ffmpeg_stdin(frame)        # rawvideo rgb24
```
- No se usa `round()` por intervalo; el total de frames es `ceil(duration * fps)`.
- La transición se aplica al inicio de cada intervalo (en los primeros frames tras un cambio), excepto en el primero del carrusel.

## Manejo de ffmpeg

Comando base (frames por stdin, rawvideo):
```
ffmpeg -f rawvideo -pix_fmt rgb24 -s {W}x{H} -framerate {fps} -i - \
       -i tmp/<job>/audio.<ext> \
       -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest \
       tmp/<job>/output.mp4
```

- Los frames se escriben al stdin del proceso ffmpeg como bytes RGB24 en orden (`W*H*3` bytes por frame), sin archivos PNG intermedios.
- `-framerate {fps}` alineado con `t = k/fps`.
- `-shortest` asegura que el video termine con el audio.
- Progreso parseado de stderr (`frame=` o `out_time_ms=`).
- El cover-fit por imagen se cachea (una vez por imagen) para no recalcularlo en cada frame.

## Manejo de temporales y limpieza

- Cada job/render crea `tmp/<id>/`.
- Tras render exitoso, el MP4 se conserva hasta la descarga; los frames intermedios se eliminan.
- Endpoint o hook de limpieza opcional para vaciar `tmp/` antiguos.

## Frontend (detalle)

- `app.js` maneja el flujo por pasos (wizard): audio → drop → imágenes → intro → preview → render.
- WaveSurfer.js: instancia con el audio; beats pintados como regiones/marcadores verticales; clic fija el drop; botón "ajustar al beat más cercano".
- Reproducción desde el drop: `wavesurfer.play(drop)`.
- SortableJS: contenedor de miniaturas con `data-index`; al reordenar se actualiza `order`.
- Controles de intro: select de estilo, inputs de título/subtítulo, color picker, select de fuente, select de transición, toggle de resolución.
- Barra de progreso: poll a `GET /render/{id}` actualiza un `<progress>`.

## Decisiones y trade-offs

- Frames por stdin (rawvideo) por tiempo absoluto: sin PNG por frame y sin acumulación de desfases; el cover-fit se cachea por imagen. Aceptable para uso local con audios ≤ 60s.
- Polling para progreso (no SSE/WebSocket) para mantener el backend simple; suficientes para una app local.
- Intro con las mismas imágenes subidas: evita pedir assets adicionales y mantiene el flujo de un solo set de imágenes.
- Transición global (no por imagen) para simplicidad; se puede escalar a por-imagen en el futuro.
