# Beat Recap — Tareas

## Fase 1 — Núcleo

- [ ] T1.1 Inicializar estructura del proyecto: `/backend`, `/frontend`, `/tmp`, `/tests`, `requirements.txt`, `README.md` base.
- [ ] T1.2 Definir `backend/config.py` con constantes (resoluciones, fps=30, formatos permitidos, rutas de tmp, fuentes).
- [ ] T1.3 Implementar `backend/utils.py`: validación de archivos, creación/limpieza de carpetas temporales por job.
- [ ] T1.4 Implementar `backend/audio.py`: `analyze_audio()` con librosa (carga, validación de duración ≤60s, beat_track, frames_to_time, detección de error "sin ritmo").
- [ ] T1.4b Implementar `backend/audio.py::transform_beats(beats, multiplier, offset_ms, duration)`: ×2 = inserción de puntos medios, ÷2 = diezmado (un beat sí, uno no), offset en ms; semántica de referencia para el frontend y para pruebas.
- [ ] T1.5 Implementar `backend/frames.py`: `cover_fit()` (recorte centrado sin deformar) y `make_text_frame()` (texto animado sobre negro con título/subtítulo/color/fuente y progreso).
- [ ] T1.6 Implementar `backend/intros/text.py`: animación de "Solo texto" (fade/slide del título, subtítulo opcional, fondo negro).
- [ ] T1.7 Implementar `backend/intros/__init__.py`: registro `INTRO_STYLES` con `text` (placeholder para los demás).
- [ ] T1.8 Implementar `backend/render.py`: cálculo de línea de tiempo con `num_images = ceil(B/N)`, `img_starts = [drop] + beats_after_drop[kN-1...]`, `img_ends = img_starts[1:] + [duration]` (primer intervalo empieza en el drop, último extendido a duration); bucle de frames por tiempo absoluto `t = k/fps` con `total_frames = ceil(duration*fps)` (sin `round()` por intervalo); envío de frames a ffmpeg por stdin como `rawvideo` rgb24 (sin PNG por frame); cacheo de `cover_fit` por imagen; transición "corte seco" por defecto; ensamblado H.264 + AAC + `-shortest`; parseo de progreso de stderr.
- [ ] T1.9 Implementar `backend/main.py`: endpoint `POST /audio` (subida, análisis, devolver bpm/beats/duration/job_id) con validaciones y mensajes de error claros.
- [ ] T1.10 Implementar `backend/main.py`: endpoint `POST /render` (recibe job_id, imágenes, order, beats ajustados, drop, n, intro_style, título, subtítulo, color, fuente, transición, resolución) que valida beats (monótono, en `[0,duration]`) e inicia el render en background, devolviendo render_id 202.
- [ ] T1.11 Implementar `backend/main.py`: endpoints `GET /render/{id}` (estado + progreso) y `GET /render/{id}/download` (MP4).
- [ ] T1.12 Construir `frontend/index.html` y `frontend/styles.css`: layout tipo wizard por pasos (audio → drop → imágenes → intro → preview → render) con zona de drag-and-drop y controles.
- [ ] T1.13 Implementar `frontend/app.js`: subida de audio, llamada a `POST /audio`, manejo de errores de validación (formato, >60s, sin ritmo).
- [ ] T1.14 Integrar WaveSurfer.js: mostrar forma de onda, marcar beats como regiones/marcadores verticales, clic para elegir drop, arrastrar para ajustar, botón "ajustar al beat más cercano", reproducción desde el drop.
- [ ] T1.14b Integrar controles de rejilla: botones ×2 y ÷2 sobre el BPM y campo de offset en ms; transformar el arreglo `beats` en el frontend (semántica idéntica a `transform_beats`), repintar la rejilla en WaveSurfer y recalcular el conteo de imágenes; enviar el `beats` final ajustado a `POST /render`.
- [ ] T1.15 Implementar cálculo local del número de imágenes necesarias como `ceil(beats_tras_drop / n)` y advertencias: menos de 4 beats tras el drop, menos/más imágenes que las necesarias (ofrecer bucle si faltan, avisar si sobran).
- [ ] T1.16 Implementar subida y gestión de imágenes: drag-and-drop de archivos, miniaturas numeradas, reordenar (SortableJS), eliminar, duplicar; construir `order` final.
- [ ] T1.17 Implementar panel de configuración de intro: select de estilo (solo "Solo texto" habilitado en Fase 1), título (default "2025 RECAP"), subtítulo, color (color picker), fuente (select), transición (solo "corte seco"), resolución (vertical por defecto).
- [ ] T1.18 Implementar botón de render: envío a `POST /render` con todos los campos, poll a `GET /render/{id}` para barra de progreso, descarga vía `GET /render/{id}/download`.
- [ ] T1.19 Fijar versiones en `requirements.txt` (fastapi, uvicorn, librosa, pillow, numpy, python-multipart, etc.).
- [ ] T1.20 Escribir `README.md`: requisitos (Python 3.11+, ffmpeg), instalación de ffmpeg en Windows, creación de entorno virtual, ejecución del backend y frontend.
- [ ] T1.21 Escribir `tests/test_intervals.py`: prueba del cálculo de intervalos de beats (img_starts/img_ends) a partir de beats reales.
- [ ] T1.22 Escribir `tests/test_image_count.py`: prueba del número de imágenes necesarias como `ceil(beats_tras_drop / n)`, con extensión del último intervalo a `duration`.
- [ ] T1.23 Escribir `tests/test_drop_snap.py`: prueba del ajuste del drop al beat más cercano (caso en que el drop cae entre dos beats).
- [ ] T1.24 Escribir `tests/test_total_frames.py`: prueba de que el total de frames es `ceil(duration * fps)`.

## Fase 2 — Intros avanzadas, transiciones, preview

- [ ] T2.1 Implementar `backend/intros/zoom_mosaic.py`: collage de fotos con zoom hacia el centro a lo largo de la intro.
- [ ] T2.2 Implementar `backend/intros/falling.py`: columnas de fotos que descienden, coincidiendo con el inicio del carrusel en el drop.
- [ ] T2.3 Habilitar "Zoom mosaico" y "Fotos cayendo" en el select de estilo del frontend.
- [ ] T2.4 Implementar transición "flash blanco corto" en `frames.py`/`render.py` (superposición de flash al inicio de cada intervalo del carrusel).
- [ ] T2.5 Implementar transición "zoom breve" en `frames.py`/`render.py` (zoom desde el centro durante los primeros frames del intervalo).
- [ ] T2.6 Habilitar selección de transición (corte seco / flash / zoom) en el frontend.
- [ ] T2.7 Implementar endpoint `POST /preview` en `main.py`: render de baja resolución (resolución reducida + duración acortada) que devuelve un MP4 ligero o frames representativos.
- [ ] T2.8 Implementar vista previa en el frontend: botón "Vista previa", llamada a `POST /preview`, reproducción del resultado ligero.
- [ ] T2.9 Habilitar opción de resolución horizontal 1920x1080 (backend + frontend).
- [ ] T2.10 Pruebas de regresión de las nuevas intros y transiciones (verificar conteo de frames y duraciones).

## Fase 3 — Opcional (vórtice)

- [ ] T3.1 Implementar `backend/intros/vortex.py`: transformación a coordenadas polares con `cv2.remap` y animación de descenso.
- [ ] T3.2 Registrar el estilo "vortex" en `INTRO_STYLES` y habilitarlo en el frontend.
- [ ] T3.3 Prueba básica de la intro vórtice (generación de frames sin error).

## Entregables finales

- [ ] T4.1 Revisar `requirements.txt` con versiones fijadas y coherentes.
- [ ] T4.2 Revisar `README.md` con instrucciones completas (instalación de ffmpeg en Windows, entorno virtual, ejecución).
- [ ] T4.3 Ejecutar el plan de pruebas y verificar que pasa (intervalos, número de imágenes, snap del drop, total de frames).
- [ ] T4.4 Verificación end-to-end manual documentada en el README (flujo completo audio → render → descarga).
