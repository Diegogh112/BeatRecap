# Beat Recap — Requisitos

## Visión

Aplicación web local que genera videos tipo "recap" verticales donde las fotos cambian exactamente al ritmo de una canción. El usuario sube un audio, la app detecta los beats con librosa, elige un "punto de drop" donde arranca el carrusel, sube y ordena imágenes, configura una intro, y descarga un MP4 renderizado con ffmpeg. Todo corre en local, sin servicios de pago.

## Requisitos funcionales

### FR-1: Subida y análisis de audio
- FR-1.1: El usuario debe poder subir un archivo de audio en formatos mp3, wav o m4a.
- FR-1.2: La duración máxima del fragmento es de 60 segundos.
- FR-1.3: El backend debe detectar el BPM y los tiempos exactos de cada beat usando `librosa.beat.beat_track`.
- FR-1.4: El frontend debe mostrar la forma de onda del audio (WaveSurfer.js) con los beats marcados visualmente.
- FR-1.5: La respuesta del análisis debe incluir: BPM, arreglo de tiempos de beats (en segundos), duración total del audio.
- FR-1.6: El frontend debe ofrecer botones ×2 y ÷2 sobre el BPM que duplican o dividen la rejilla de beats (inserción de puntos medios para ×2, diezmado un-beat-sí-un-beat-no para ÷2), y un offset manual en ms que desplaza toda la rejilla. Al cambiarlos se recalcula el conteo de imágenes necesarias.

### FR-2: Selección del punto de drop
- FR-2.1: El usuario debe poder hacer clic en la forma de onda para elegir el "punto de drop" (momento donde empieza el carrusel).
- FR-2.2: El usuario debe poder ajustar el punto de drop arrastrándolo.
- FR-2.3: El usuario debe poder escuchar el audio desde el punto de drop.
- FR-2.4: Debe existir una opción "ajustar al beat más cercano" que mueve el drop al beat más cercano al punto clicado.
- FR-2.5: Si el punto de drop deja menos de 4 beats entre el drop y el final del audio, se debe mostrar una advertencia (no bloquear).

### FR-3: Cálculo de imágenes necesarias
- FR-3.1: La app debe calcular cuántas imágenes se necesitan como `ceil(beats_tras_drop / N)`, donde `beats_tras_drop` es el número de beats estrictamente posteriores al drop y `N` es "cambiar cada N beats".
- FR-3.2: El usuario puede elegir N entre las opciones 1, 2 o 4 (por defecto 1).
- FR-3.3: El número de imágenes requeridas debe mostrarse claramente.
- FR-3.4: Si el usuario sube menos imágenes de las necesarias, ofrecer repetirlas en bucle.
- FR-3.5: Si el usuario sube más imágenes de las necesarias, avisar que sobran (no descartarlas automáticamente, pero el render usa solo las necesarias salvo repetición en bucle).

### FR-4: Gestión de imágenes
- FR-4.1: El usuario debe poder subir imágenes en formatos jpg, png o webp.
- FR-4.2: Debe existir una pantalla para reordenar las imágenes con drag and drop (SortableJS).
- FR-4.3: Debe poder eliminar una imagen individual.
- FR-4.4: Debe poder duplicar una imagen.
- FR-4.5: Las miniaturas deben estar numeradas en el orden de reproducción.

### FR-5: Configuración de la intro
- FR-5.1: La intro corresponde a todo el segmento anterior al drop.
- FR-5.2: Estilos disponibles:
  - (a) "Zoom mosaico": collage de fotos con zoom hacia el centro.
  - (b) "Fotos cayendo": columnas de fotos que bajan.
  - (c) "Solo texto": texto animado sobre fondo negro.
- FR-5.3: El título debe ser editable (por defecto "2025 RECAP").
- FR-5.4: Subtítulo opcional.
- FR-5.5: Color del texto seleccionable.
- FR-5.6: Fuente seleccionable (de un conjunto de fuentes incluidas).
- FR-5.7: Las fotos usadas en la intro se toman de las mismas imágenes subidas.

### FR-6: Vista previa
- FR-6.1: Debe existir una vista previa de baja resolución antes de renderizar el video final.
- FR-6.2: La vista previa debe representar el comportamiento de intro + carrusel.

### FR-7: Renderizado y descarga
- FR-7.1: El usuario debe poder iniciar el renderizado del video final.
- FR-7.2: El video final debe ser MP4 con códec de video H.264 y audio AAC.
- FR-7.3: El audio original debe sonar completo de principio a fin.
- FR-7.4: Antes del drop se muestra la intro con el estilo elegido; la intro termina exactamente en el drop, sin huecos.
- FR-7.5: El primer intervalo del carrusel empieza exactamente en el drop.
- FR-7.6: Desde el drop, cada imagen dura el intervalo hasta el siguiente cambio (cada N beats), usando los tiempos reales de los beats (no BPM × tiempo).
- FR-7.7: El cambio de imagen debe caer exacto en el beat.
- FR-7.8: Los frames se generan por tiempo absoluto `t = k/fps` (no con `round()` por intervalo), para evitar acumulación de desfases. El total de frames es `ceil(duration * fps)`.
- FR-7.9: Los frames se envían a ffmpeg por stdin como `rawvideo` (sin guardar PNG por frame); el recorte cover de cada imagen se cachea una sola vez por imagen.
- FR-7.10: Las imágenes se ajustan al lienzo con recorte centrado (cover), sin deformarse.
- FR-7.11: Transición opcional en cada beat: corte seco (por defecto), flash blanco corto o zoom breve.
- FR-7.12: La última imagen se mantiene hasta que termine el audio.
- FR-7.13: Debe mostrarse una barra de progreso durante el renderizado.
- FR-7.14: El usuario debe poder descargar el MP4 resultante.

### FR-8: Formato del video
- FR-8.1: Formato vertical 1080x1920 a 30 fps por defecto.
- FR-8.2: Opción de formato horizontal 1920x1080 a 30 fps.

## Reglas del video (consolidadas)

- Resolución: 1080x1920 (vertical, por defecto) o 1920x1080 (horizontal, opcional). FPS: 30.
- El audio suena completo de principio a fin.
- Segmento intro: desde t=0 hasta el drop (termina exactamente en el drop, sin huecos). Segmento carrusel: desde el drop hasta el final del audio (el primer intervalo empieza en el drop).
- En el carrusel, el tiempo de cada imagen se deriva de los tiempos reales de los beats (cada N beats), no de BPM × duración. Número de imágenes = `ceil(beats_tras_drop / N)`.
- El último beat puede no coincidir con el final del audio; la última imagen se mantiene hasta el final real.
- Los frames se generan por tiempo absoluto `t = k/fps`; el total es `ceil(duration * fps)` (sin `round()` por intervalo).
- Los frames se envían a ffmpeg por stdin como `rawvideo`; el cover-fit de cada imagen se cachea una sola vez.
- Cover fit: recorte centrado, sin deformación.
- Transiciones por beat (configurable globalmente): corte seco, flash blanco, zoom breve.

## Requisitos no funcionales

### NFR-1: Entorno y dependencias
- NFR-1.1: Python 3.11+.
- NFR-1.2: Backend en FastAPI.
- NFR-1.3: Procesamiento de audio con librosa.
- NFR-1.4: Generación de video con ffmpeg vía subprocess.
- NFR-1.5: Frames generados con Pillow y numpy.
- NFR-1.6: Frontend en HTML + JavaScript (o React con Vite). WaveSurfer.js para forma de onda, SortableJS para drag and drop.
- NFR-1.7: Todo gratuito y local, sin servicios de pago ni llamadas externas.

### NFR-2: Rendimiento
- NFR-2.1: El análisis de audio de un fragmento de hasta 60s debe completarse en menos de 10 segundos en una máquina estándar.
- NFR-2.2: El renderizado debe mostrar progreso incremental al frontend.

### NFR-3: Manejo de archivos temporales
- NFR-3.1: Los archivos temporales se guardan en una carpeta /tmp (o equivalente del SO) dentro del proyecto.
- NFR-3.2: Los temporales se limpian al terminar el renderizado (y en cierre de sesión si es viable).

### NFR-4: Errores y validaciones
- NFR-4.1: Mensajes claros si el audio es inválido, muy largo (>60s) o no se detecta ritmo.
- NFR-4.2: Si el punto de drop deja menos de 4 beats, advertir (no bloquear).
- NFR-4.3: Errores de ffmpeg deben devolverse como mensajes legibles al usuario.

### NFR-5: Entregables
- NFR-5.1: Código completo.
- NFR-5.2: requirements.txt con versiones fijadas.
- NFR-5.3: README con instrucciones para instalar ffmpeg y ejecutar la app.

## Criterios de aceptación (por fase)

### Fase 1 — Núcleo (obligatorio)
- AC-1.1: Se puede subir audio mp3/wav/m4a de hasta 60s y se devuelve BPM, beats y duración.
- AC-1.2: La forma de onda se muestra con beats marcados y se puede elegir/ajustar el drop, escuchar desde ahí y ajustar al beat más cercano.
- AC-1.3: Se calcula y muestra el número de imágenes necesarias según N (1/2/4).
- AC-1.4: Se pueden subir, reordenar (drag and drop), eliminar y duplicar imágenes.
- AC-1.5: Se puede configurar intro "Solo texto" (título, subtítulo, color, fuente).
- AC-1.6: Se renderiza y descarga un MP4 1080x1920 @30fps con intro de texto + carrusel al beat, audio completo, cover fit, última imagen mantenida.
- AC-1.7: Advertencia si quedan menos de 4 beats tras el drop.

### Fase 2 — Intros avanzadas, transiciones, preview
- AC-2.1: Intro "Zoom mosaico" funcionando (collage con zoom al centro).
- AC-2.2: Intro "Fotos cayendo" funcionando (columnas que bajan).
- AC-2.3: Transiciones por beat: corte seco, flash blanco y zoom breve.
- AC-2.4: Vista previa de baja resolución operativa.
- AC-2.5: Opción de formato horizontal 1920x1080.

### Fase 3 — Opcional
- AC-3.1: Intro tipo túnel/vórtice usando cv2.remap a coordenadas polares con animación de descenso.

## Pruebas requeridas

- PR-1: Prueba del cálculo de beats por intervalo (los intervalos derivados de los tiempos reales de librosa).
- PR-2: Prueba del número de imágenes necesarias como `ceil(beats_tras_drop / N)`, con extensión del último intervalo a `duration`.
- PR-3: Prueba del ajuste del drop al beat más cercano (caso en que el drop cae entre dos beats).
- PR-4: Prueba de que el total de frames es `ceil(duration * fps)`.
